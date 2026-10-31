"""Counter behavior, exported C parity, typed monitors and editor integration."""
import ctypes
from copy import deepcopy
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from model import Graph, counter_step
from hal_bindings import monitor_map


def counter_graph():
    g=Graph();inputs=[]
    for j,name in enumerate(('pulse-up','pulse-down','run-enable','clear-count')):
        i=g.add('input',(0,j*150));g.nodes[i]['p']['name']=name;inputs.append(i)
    initial=g.add('constant',(0,640));g.nodes[initial]['p'].update(name='start_value',dtype='s32',value=0)
    threshold=g.add('constant',(280,640));g.nodes[threshold]['p'].update(name='target_value',dtype='s32',value=3)
    counter=g.add('counter',(330,120));g.nodes[counter]['p'].update(initial='@start_value',threshold='@target_value')
    for source,port in zip(inputs,('up','down','enable','reset')):g.connect(source,counter,port)
    outputs=[]
    for j,(port,dtype,name) in enumerate((('count','s32','count-value'),('reached','bit','threshold-reached'))):
        i=g.add('output',(720,120+j*190));g.nodes[i]['p'].update(name=name,dtype=dtype)
        g.connect(counter,i,'in',port);outputs.append(i)
    return g,inputs,initial,threshold,counter,outputs


class CounterTests(unittest.TestCase):
    def test_edges_reset_enable_simultaneous_and_threshold(self):
        p=dict(initial=0,threshold=2,enabled=True);s={}
        samples=[(1,0,1,0,1),(1,0,1,0,1),(0,0,1,0,1),(1,0,1,0,2),
                 (0,1,1,0,1),(1,0,0,0,1),(1,0,1,0,1),(0,0,1,0,1),
                 (1,1,1,0,1),(0,0,1,0,1),(1,1,0,1,0),(1,1,1,0,0),
                 (0,0,1,0,0),(0,1,1,0,-1),(1,1,1,0,0)]
        for up,down,enable,reset,expected in samples:
            self.assertEqual(counter_step(p,s,dict(up=up,down=down,enable=enable,reset=reset)),expected)
            self.assertEqual(s['reached'],expected>=2)
        p['initial']=8
        self.assertEqual(counter_step(p,s,dict(reset=1,enable=0)),8)
        p['threshold']=9
        self.assertEqual(counter_step(p,s,dict(enable=0)),8);self.assertFalse(s['reached'])
        p['threshold']=8;counter_step(p,s,dict(enable=0));self.assertTrue(s['reached'])

    def test_saturation_and_return_from_limits(self):
        for initial,direction,opposite,expected in ((2147483647,'up','down',2147483646),(-2147483648,'down','up',-2147483647)):
            p=dict(initial=initial,threshold=0,enabled=True);s={}
            self.assertEqual(counter_step(p,s,{direction:1}),initial)
            counter_step(p,s,{})
            self.assertEqual(counter_step(p,s,{direction:1}),initial)
            self.assertEqual(counter_step(p,s,{opposite:1}),expected)

    def test_defaults_types_validation_references_and_save(self):
        g=Graph();i=g.add('counter');j=g.add('counter')
        self.assertEqual(g.inputs(i),('up','down','enable','reset'))
        self.assertEqual(g.outputs(i),('count','reached'))
        self.assertEqual(g.dtype(i),'s32');self.assertEqual(g.dtype(i,'reached'),'bit')
        self.assertTrue(all(g.input_type(i,p)=='bit' for p in g.inputs(i)))
        self.assertEqual(g.step(.001)[i],0)
        g.nodes[j]['p'].update(initial=20,enabled=False);g.reset();g.step(.001)
        self.assertEqual(g.value(i,'reached'),0);self.assertEqual(g.value(j,'reached'),1)
        g.state[i]['count']=99;g.step(.001);self.assertEqual(g.value(j),20)
        g.reset();self.assertEqual(g.step(.001)[i],0)
        original=deepcopy(g.nodes[i]['p'])
        for key,value in [('initial',.5),('initial',-2147483649),('threshold',2147483648),('threshold',float('nan')),('threshold',True),('threshold',None),('enabled',1),('dtype','float')]:
            with self.subTest(key=key,value=value):
                g.nodes[i]['p'][key]=value
                with self.assertRaises(ValueError):g.validate()
                g.nodes[i]['p']=deepcopy(original)
        g,inputs,initial,threshold,i,outputs=counter_graph()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'counter.json';g.save(path);loaded=Graph.load(path)
            self.assertEqual(loaded.nodes,g.nodes);self.assertEqual(loaded.links,g.links)
        g.nodes[inputs[2]]['p']['value']=1;g.nodes[inputs[0]]['p']['value']=1
        g.step(.001);self.assertEqual(g.value(i),1)
        g.nodes[initial]['p']['value']=6;g.step(.001);self.assertEqual(g.value(i),1)
        g.nodes[inputs[3]]['p']['value']=1;g.step(.001);self.assertEqual(g.value(i),6)
        g.nodes[i]['p']['threshold']='@missing'
        with self.assertRaisesRegex(ValueError,'Unknown constant'):g.validate()

    def test_exported_c_matches_python_and_debug_pins(self):
        for debug in (False,True):
            g,inputs,initial,threshold,counter,outputs=counter_graph()
            with self.subTest(debug=debug),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);path=root/'counter_check.comp';g.export(path,debug=debug)
                header,body=path.read_text().split(';;\n',1);body=body.replace('FUNCTION(update)','void update(void)')
                harness='#include <stdint.h>\nlong period=1000000;\nlong long rtapi_get_time(void){return 0;}\n'
                for direction,dtype,name in re.findall(r'^pin (in|out) (bit|s32|u32|float) ([\w-]+)',header,re.M):
                    name=name.replace('-','_');ctype={'bit':'int','s32':'int32_t','u32':'uint32_t','float':'double'}[dtype]
                    harness+=f'{ctype} storage_{name};\n#define {name} (0+storage_{name})\n'
                    if direction=='out':harness+=f'#define {name}_set(v) (storage_{name}=(v))\n'
                harness+=body+'\nvoid sample(int up,int down,int enable,int reset,int32_t start,int32_t target,double *result){\n'
                harness+='storage_pulse_up=up;storage_pulse_down=down;storage_run_enable=enable;storage_clear_count=reset;storage_start_value=start;storage_target_value=target;update();\nresult[0]=storage_count_value;result[1]=storage_threshold_reached;\n'
                if debug:
                    harness+=f'result[2]=storage_debug_n{counter}_count;result[3]=storage_debug_n{counter}_reached;\n'
                    self.assertEqual({m['port']:m['dtype'] for m in monitor_map(g,'counter_check') if m['node']==counter},dict(count='s32',reached='bit'))
                (root/'check.c').write_text(harness+'}\n')
                subprocess.run(['cc','-shared','-fPIC','-fsanitize=undefined','-fno-sanitize-recover=all',str(root/'check.c'),'-lm','-o',str(root/'check.so')],check=True,capture_output=True)
                lib=ctypes.CDLL(str(root/'check.so'));lib.sample.argtypes=[ctypes.c_int]*4+[ctypes.c_int32]*2+[ctypes.POINTER(ctypes.c_double)]
                samples=[(1,0,1,0,0,2),(1,0,1,0,0,2),(0,0,1,0,0,2),(1,0,1,0,0,2)]
                for bound in (2147483647,-2147483648):
                    samples.extend([(0,0,0,1,bound,bound),(1,1,1,0,bound,bound),(0,0,1,0,bound,0),(1,0,1,0,bound,0),(0,0,1,0,bound,0),(0,1,1,0,bound,0)])
                rng=random.Random(42)
                samples += [tuple(rng.randrange(2) for _ in range(4))+(rng.choice((0,5,-4,2147483647,-2147483648)),rng.choice((0,3,-3,2147483647,-2147483648))) for _ in range(250)]
                for sample in samples:
                    for node,value in zip(inputs,sample):g.nodes[node]['p']['value']=value
                    g.nodes[initial]['p']['value']=sample[4];g.nodes[threshold]['p']['value']=sample[5]
                    values=g.step(.001);expected=[values[i] for i in outputs]
                    if debug:expected += [g.value(counter,'count'),g.value(counter,'reached')]
                    actual=(ctypes.c_double*4)();lib.sample(*sample,actual)
                    self.assertEqual(list(actual)[:len(expected)],expected,sample)


class CounterUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['QT_QPA_PLATFORM']='offscreen';sys.argv=[sys.argv[0],'--windowed']
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_toolbar_properties_simulation_live_monitor_and_languages(self):
        from PySide6.QtWidgets import QPushButton,QDoubleSpinBox
        from app import Editor
        import i18n
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'PLC_STATE_DIR':tmp}):
            w=Editor();self.addCleanup(w.close);self.addCleanup(w.shutdown);self.addCleanup(lambda:i18n.set_language('en'))
            w.graph=Graph();w.rebuild();w.show();self.app.processEvents()
            button=next(b for b in w.toolbars['Nodes'].findChildren(QPushButton) if b.property('translation_text')=='+ Counter')
            button.click();self.app.processEvents();i=w.selected;self.assertEqual(w.graph.nodes[i]['kind'],'counter')
            for key,value in (('initial',-3),('threshold',7)):
                control=w.scroll.widget().findChild(QDoubleSpinBox,'counter:'+key)
                self.assertEqual(control.decimals(),0);self.assertEqual(control.minimum(),-2147483648);self.assertEqual(control.maximum(),2147483647)
                control.setValue(value);self.app.processEvents();self.assertEqual(w.graph.nodes[i]['p'][key],value)
            for code in i18n.LANGUAGES:
                w.language_picker.setCurrentIndex(w.language_picker.findData(code));self.app.processEvents()
                self.assertEqual(w.items[i].title_text.text(),i18n.tr('COUNTER'))
                self.assertEqual(w.items[i].output_labels['reached'].text(),'reached : bit')
                self.assertLess(w.items[i].input_labels['down'][0].sceneBoundingRect().right(),w.items[i].output_labels['reached'].sceneBoundingRect().left())
            w.run(True);w.timer.stop();w.tick()
            self.assertEqual(w.graph.value(i),-3);self.assertEqual(w.simulation_values[i,'count'].text(),'-3')
            self.assertEqual(w.simulation_values[i,'reached'].text(),i18n.tr('OFF (0)'))
            w.apply_live_event(dict(event='values',values=[dict(node=i,port='count',value=12),dict(node=i,port='reached',value=1)],inputs={},time_ns=100,tmax_ns=100,hal_time=1))
            self.assertEqual(w.graph.values[i],12);self.assertEqual(w.graph.value(i,'reached'),1)
            self.assertIn('count=12',w.items[i].value_text.text());w.run(False)


if __name__=='__main__':unittest.main()
