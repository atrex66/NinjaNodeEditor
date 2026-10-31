import ast
import json
import ctypes
import math
from copy import deepcopy
from pathlib import Path
import subprocess
import tempfile
import unittest
from model import Graph,calc,expression,demo,detected_variables,circular_demo,modulo,convert

class Tests(unittest.TestCase):
    def test_timer_modes_reset_edges_and_zero_duration(self):
        from model import timer_step
        for mode in ('level','pulse'):
            p=dict(duration_ms=3,timer_mode=mode);state={}
            values=[timer_step(p,state,dict(trigger=1),.001) for _ in range(5)]
            self.assertEqual(values,[False,False,False,True,mode=='level'])
            self.assertFalse(timer_step(p,state,dict(trigger=1,reset=1),.001))
            self.assertFalse(timer_step(p,state,dict(trigger=1),.1)) # Held trigger cannot restart.
            timer_step(p,state,dict(trigger=0),.001)
            self.assertFalse(timer_step(p,state,dict(trigger=1),.001))
            timer_step(p,state,dict(trigger=0),.001)
            self.assertFalse(timer_step(p,state,dict(trigger=1),.001)) # Busy edge ignored.
            self.assertTrue(timer_step(p,state,dict(trigger=0),.001))
            p['duration_ms']=0;state={}
            self.assertTrue(timer_step(p,state,dict(trigger=1),.001))
            self.assertEqual(timer_step(p,state,dict(trigger=1),.001),mode=='level')
            self.assertFalse(timer_step(p,state,dict(trigger=1,reset=1),.001))
            for dt in (0,-1,float('inf'),float('nan')):
                self.assertFalse(timer_step(p,{},dict(trigger=1),dt))
        # Falling trigger does not cancel; duration is latched at its starting edge.
        p=dict(duration_ms=3,timer_mode='level');state={}
        timer_step(p,state,dict(trigger=1),.001);p['duration_ms']=1000
        self.assertTrue(timer_step(p,state,dict(trigger=0),.003))

    def test_timer_graph_roundtrip_validation_and_compiled_parity(self):
        g=Graph();start=g.add('input');clear=g.add('input');duration=g.add('constant')
        g.nodes[start]['p']['name']='start';g.nodes[clear]['p']['name']='clear'
        g.nodes[duration]['p'].update(name='wait_ms',dtype='u32',value=3)
        timers=[];outputs=[]
        for mode in ('level','pulse'):
            timer=g.add('timer');g.nodes[timer]['p'].update(duration_ms='@wait_ms',timer_mode=mode)
            self.assertEqual(g.inputs(timer),('trigger','reset'));self.assertEqual(g.outputs(timer),('out',))
            self.assertEqual(g.dtype(timer),'bit');self.assertEqual(g.input_type(timer,'trigger'),'bit')
            g.connect(start,timer,'trigger');g.connect(clear,timer,'reset');timers.append(timer)
            output=g.add('output');g.nodes[output]['p']['name']=mode+'-out';g.connect(timer,output,'in');outputs.append(output)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g.save(root/'timer.json');loaded=Graph.load(root/'timer.json')
            self.assertEqual(loaded.nodes,g.nodes);self.assertEqual(loaded.links,g.links)
            g.export(root/'timer.comp')
            text=(root/'timer.comp').read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            harness='int start_storage,clear_storage,level_out,pulse_out;double wait_ms;long period;\n'
            harness+='#define start (0+start_storage)\n#define clear (0+clear_storage)\n'+text
            harness+='\nvoid sample(int trigger,int reset,double duration,long ns,int *out){start_storage=trigger;clear_storage=reset;wait_ms=duration;period=ns;update();out[0]=level_out;out[1]=pulse_out;}\n'
            (root/'timer.c').write_text(harness)
            subprocess.run(['cc','-shared','-fPIC',str(root/'timer.c'),'-lm','-o',str(root/'timer.so')],check=True)
            lib=ctypes.CDLL(str(root/'timer.so'));lib.sample.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_double,ctypes.c_long,ctypes.POINTER(ctypes.c_int)]
            samples=[(1,0,3,1000000),(0,0,100,1000000),(1,0,100,1000000),(0,0,100,1000000)]+[(1,0,3,1000000)]*5
            samples += [(1,1,3,1000000),(1,0,3,10000000),(0,0,3,1000000),(1,0,3,1000000),(0,1,3,10000000)]
            samples += [(0,0,0,1000000),(1,0,0,1000000),(1,0,0,1000000),(0,0,0,1000000),(1,0,0,1000000)]
            for trigger,reset,ms,ns in samples:
                g.nodes[start]['p']['value']=trigger;g.nodes[clear]['p']['value']=reset;g.nodes[duration]['p']['value']=ms
                expected=g.step(ns*1e-9);actual=(ctypes.c_int*2)();lib.sample(trigger,reset,ms,ns,actual)
                self.assertEqual(list(actual),[expected[i] for i in outputs])
        timer=timers[0];g.nodes[timer]['p']['duration_ms']=-1
        with self.assertRaisesRegex(ValueError,'Timer duration'):g.validate()
        g.nodes[timer]['p']['duration_ms']=1.5
        with self.assertRaisesRegex(ValueError,'Timer duration'):g.validate()
        g.nodes[timer]['p']['duration_ms']=1;g.nodes[timer]['p']['timer_mode']='invalid'
        with self.assertRaisesRegex(ValueError,'Timer output'):g.validate()

    def test_output_setters_with_legacy_and_accessor_hal_macros(self):
        # 2.10 pin getters are expressions, not writable C lvalues.
        g=Graph();outputs=[]
        for dtype in ('bit','float','s32','u32'):
            source=g.add('input');g.nodes[source]['p'].update(name='input-'+dtype,dtype=dtype)
            output=g.add('output');g.nodes[output]['p'].update(name='output-'+dtype,dtype=dtype)
            g.connect(source,output,'in');outputs.append(output)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g.export(root/'setters.comp')
            text=(root/'setters.comp').read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            for accessors in (False,True):
                with self.subTest(accessors=accessors):
                    harness='long period=1000000;\n'
                    for dtype in ('bit','float','s32','u32'):
                        harness+=f'double input_{dtype}=0,storage_{dtype}=0;\n'
                        if accessors:
                            harness+=f'#define output_{dtype} (0.0+storage_{dtype})\n'
                            harness+=f'#define output_{dtype}_set(v) (storage_{dtype}=(v))\n'
                        else:
                            harness+=f'#define output_{dtype} storage_{dtype}\n'
                    harness+=text+'\nvoid sample(double value,double *out){\n'
                    harness+=''.join(f'input_{dtype}=value;' for dtype in ('bit','float','s32','u32'))
                    harness+='update();'+''.join(f'out[{j}]=storage_{g.nodes[i]["p"]["dtype"]};' for j,i in enumerate(outputs))+'}\n'
                    path=root/f'setters_{int(accessors)}';path.with_suffix('.c').write_text(harness)
                    subprocess.run(['cc','-shared','-fPIC',str(path.with_suffix('.c')),'-lm','-o',str(path.with_suffix('.so'))],check=True)
                    lib=ctypes.CDLL(str(path.with_suffix('.so')))
                    lib.sample.argtypes=[ctypes.c_double,ctypes.POINTER(ctypes.c_double)]
                    for value in (-3.9,0,3.9,4294967295,1e20):
                        for node in g.nodes.values():
                            if node['kind']=='input':node['p']['value']=value
                        expected=g.step(.001);actual=(ctypes.c_double*4)();lib.sample(value,actual)
                        for i,result in zip(outputs,actual):self.assertEqual(expected[i],result)

    def test_modules_are_persistent_editor_metadata_only(self):
        g=Graph();source=g.add('input');g.nodes[source]['p'].update(dtype='float',value=4)
        fifo=g.add('fifo');g.connect(source,fifo,'in')
        output=g.add('output');g.nodes[output]['p']['dtype']='float';g.connect(fifo,output,'in','last')
        g.step(.02);state=deepcopy(g.state);values=dict(g.values);links=deepcopy(g.links)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);export=root/'modules.comp';g.export(export);original=export.read_text()
            module=g.add_module('Lubrication');g.move_nodes([fifo,output],module);g.rename_module(module,'Lubrication guard')
            self.assertEqual(g.state,state);self.assertEqual(g.values,values);self.assertEqual(g.links,links)
            g.view_module=module;path=root/'modules.json';g.save(path);loaded=Graph.load(path)
            self.assertEqual(loaded.modules,g.modules);self.assertEqual(loaded.nodes,g.nodes);self.assertEqual(loaded.view_module,module)
            loaded.export(export);self.assertEqual(export.read_text(),original)
            target=g.delete_module(module);self.assertEqual(target,0);self.assertEqual(g.nodes[fifo]['module'],0)
            self.assertEqual(g.state,state);self.assertEqual(g.links,links)
            g.export(export);self.assertEqual(export.read_text(),original)
            with self.assertRaisesRegex(ValueError,'at least one'):g.delete_module(0)
            g.view_module=None;g.save(path);self.assertIsNone(Graph.load(path).view_module)
            data=json.loads(path.read_text());data['version']=3;data.pop('modules');data.pop('view_module')
            for n in data['nodes'].values():n.pop('module')
            path.write_text(json.dumps(data));legacy=Graph.load(path)
            self.assertEqual(legacy.modules,{0:'Main'});self.assertTrue(all(n['module']==0 for n in legacy.nodes.values()))
        with self.assertRaisesRegex(ValueError,'Duplicate'):g.add_module('main')
        g.nodes[source]['module']=999
        with self.assertRaisesRegex(ValueError,'unknown module'):g.validate()
    def test_named_constants_references_validation_and_roundtrip(self):
        g=Graph();gain=g.add('constant');g.nodes[gain]['p'].update(name='gain',value=3,dtype='u32')
        math=g.add('math');g.set_expression(math,'x * @gain + @gain')
        self.assertEqual(g.inputs(gain),());self.assertEqual(g.outputs(gain),())
        self.assertEqual(g.inputs(math),('x',))
        g.set_variable(math,'x','mode','constant');g.set_variable(math,'x','value','@gain')
        self.assertEqual(g.step(.001)[math],12)
        g.nodes[gain]['p']['value']=4;self.assertEqual(g.step(.001)[math],20)
        with self.assertRaisesRegex(ValueError,'Unknown constant'):g.set_expression(math,'@missing')
        self.assertEqual(g.nodes[math]['p']['expression'],'x * @gain + @gain')
        other=g.add('constant');g.nodes[other]['p']['name']='gain'
        with self.assertRaisesRegex(ValueError,'Duplicate constant'):g.validate()
        del g.nodes[other]
        g.nodes[gain]['p']['value']='@gain'
        with self.assertRaisesRegex(ValueError,'finite number'):g.validate()
        g.nodes[gain]['p']['value']=4
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'constants.json';g.save(path);loaded=Graph.load(path)
            self.assertEqual(loaded.nodes,g.nodes);self.assertEqual(loaded.step(.001)[math],20)

    def test_named_constant_pins_dynamic_generated_c_matches_simulation(self):
        g=Graph();ids={}
        for name,dtype,value in [('gain','float',2),('wait','u32',2),('initial','s32',7),('flag','bit',True)]:
            i=g.add('constant');g.nodes[i]['p'].update(name=name,dtype=dtype,value=value);ids[name]=i
        x=g.add('input');g.nodes[x]['p'].update(name='reading',dtype='float')
        gate=g.add('input');g.nodes[gate]['p']['name']='gate'
        math=g.add('math');g.set_expression(math,'x * @gain + @initial + offset')
        g.set_variable(math,'offset','mode','constant');g.set_variable(math,'offset','value','@initial');g.connect(x,math,'x')
        result=g.add('output');g.nodes[result]['p'].update(name='result',dtype='float');g.connect(math,result,'in')
        fifo=g.add('fifo');g.nodes[fifo]['p']['initial']='@initial';g.connect(x,fifo,'in')
        previous=g.add('output');g.nodes[previous]['p'].update(name='previous',dtype='float');g.connect(fifo,previous,'in','last')
        pid=g.add('pid');g.nodes[pid]['p'].update(kp='@gain',setpoint='@initial',filter_ms='@wait',enabled='@flag')
        pid_out=g.add('output');g.nodes[pid_out]['p'].update(name='pid-value',dtype='float');g.connect(pid,pid_out,'in')
        delayed=g.add('output');g.nodes[delayed]['p'].update(name='delayed',initial='@flag',on_delay='@wait',off_delay='@wait');g.connect(gate,delayed,'in')
        display=g.add('display');g.nodes[display]['p']['cooldown_ms']='@wait';g.connect(gate,display,'trigger')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'named_constants.comp';g.export(path)
            text=path.read_text();self.assertIn('pin in u32 wait = 2;',text);self.assertIn('pin in bit flag = 1;',text)
            body=text.split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            harness='#define RTAPI_MSG_ERR 1\nint rtapi_print_msg(int level,const char *format,...){return 0;}\n'
            harness+='static double gain,reading,result,previous,pid_value;static unsigned wait;static int initial,flag,gate,delayed;static long period;\n'+body
            harness+='\ndouble sample(double a,double b,int c,unsigned d,int on,int output){gain=a;reading=b;initial=c;wait=d;flag=1;gate=on;period=1000000;update();return output==0?result:output==1?previous:output==2?pid_value:delayed;}\n'
            (root/'runtime.c').write_text(harness);subprocess.run(['cc','-shared','-fPIC',str(root/'runtime.c'),'-lm','-o',str(root/'runtime.so')],check=True)
            lib=ctypes.CDLL(str(root/'runtime.so'));lib.sample.argtypes=[ctypes.c_double,ctypes.c_double,ctypes.c_int,ctypes.c_uint,ctypes.c_int,ctypes.c_int];lib.sample.restype=ctypes.c_double
            # Separate copies give every output the same sequence and initial history.
            for selected,node in enumerate((result,previous,pid_out,delayed)):
                copy=root/f'runtime{selected}.so';copy.write_bytes((root/'runtime.so').read_bytes());runtime=ctypes.CDLL(str(copy))
                runtime.sample.argtypes=lib.sample.argtypes;runtime.sample.restype=ctypes.c_double;g.reset()
                for a,b,c,d,on in ((2,4,7,2,0),(3,5,9,3,1),(4,6,10,3,1),(4,8,10,3,1),(1,9,5,1,0)):
                    for name,value in [('gain',a),('initial',c),('wait',d)]:g.nodes[ids[name]]['p']['value']=value
                    g.nodes[x]['p']['value']=b;g.nodes[gate]['p']['value']=on;g.step(.001)
                    self.assertAlmostEqual(runtime.sample(a,b,c,d,on,selected),g.values[node])
    def test_display_levels_cooldown_and_reset(self):
        g=Graph();gate=g.add('input');display=g.add('display');g.connect(gate,display,'trigger')
        p=g.nodes[display]['p'];p.update(message='Ready',cooldown_ms=1000)
        self.assertEqual(g.step(.125)[display],0);self.assertEqual(g.messages,[])
        g.nodes[gate]['p']['value']=1;g.step(.125);self.assertEqual(g.messages,['Ready'])
        for _ in range(20):g.step(.125);self.assertEqual(g.messages,[])
        g.nodes[gate]['p']['value']=0;g.step(.125)
        g.nodes[gate]['p']['value']=1;g.step(.125);self.assertEqual(g.messages,['Ready'])
        g.nodes[gate]['p']['value']=0;g.step(.125)
        g.nodes[gate]['p']['value']=1;g.step(.125);self.assertEqual(g.messages,[])
        # Suppressed edges are not queued and a held input never repeats.
        for _ in range(10):g.step(.125);self.assertEqual(g.messages,[])
        g.nodes[gate]['p']['value']=0;g.step(.125)
        g.nodes[gate]['p']['value']=1;g.step(.125);self.assertEqual(g.messages,['Ready'])
        p.update(trigger_high=False,cooldown_ms=0);g.reset();g.step(.125);self.assertEqual(g.messages,[])
        g.nodes[gate]['p']['value']=0;g.step(.125);self.assertEqual(g.messages,['Ready'])
        g.step(.125);self.assertEqual(g.messages,[])
        g.reset();g.step(.125);self.assertEqual(g.messages,['Ready'])
        g.disconnect_node(display);g.step(.125);self.assertEqual(g.messages,[])

    def test_display_values_validation_roundtrip_and_compiled_messages(self):
        g=Graph();gate=g.add('input');reading=g.add('input');reset=g.add('input');g.nodes[gate]['p']['name']='gate';g.nodes[reading]['p'].update(name='reading',dtype='float');g.nodes[reset]['p']['name']='clear-message'
        for high in (True,False):
            d=g.add('display');g.nodes[d]['p'].update(message='Hiba "nyomás" 50% \\ próba 😀',show_value=high,trigger_high=high,cooldown_ms=1000 if high else 250)
            g.connect(gate,d,'trigger');g.connect(reading,d,'value')
            g.connect(reset,d,'reset')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g.save(root/'display.json');copy=Graph.load(root/'display.json');self.assertEqual(copy.nodes,g.nodes);self.assertEqual(copy.links,g.links)
            g.export(root/'display_runtime.comp')
            text=(root/'display_runtime.comp').read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            harness='#include <stdarg.h>\n#include <stdio.h>\n#define RTAPI_MSG_ERR 1\nint gate,count,clear_message;double reading;long period;char messages[4][512];\n'
            harness+='int rtapi_print_msg(int level,const char *format,...){va_list args;va_start(args,format);vsnprintf(messages[count++],512,format,args);va_end(args);return 0;}\n'+text
            harness+='\nint sample(int on,double value,int reset,long ns){gate=on;reading=value;clear_message=reset;period=ns;count=0;update();return count;}\nconst char *get_message(int index){return messages[index];}\n'
            (root/'display_runtime.c').write_text(harness)
            subprocess.run(['cc','-shared','-fPIC',str(root/'display_runtime.c'),'-lm','-o',str(root/'display_runtime.so')],check=True)
            lib=ctypes.CDLL(str(root/'display_runtime.so'));lib.sample.argtypes=[ctypes.c_int,ctypes.c_double,ctypes.c_int,ctypes.c_long];lib.sample.restype=ctypes.c_int
            lib.get_message.argtypes=[ctypes.c_int];lib.get_message.restype=ctypes.c_char_p
            samples=[(on,value,0) for on,value in [(0,0),(1,3.5),(1,4),(0,-2),(1,8),(0,4),(1,1),(0,9),(1,5)]+[(1,0)]*10+[(0,2),(1,7)]]
            samples += [(1,9,1),(1,10,1),(1,11,0),(1,12,1),(0,4,1),(0,5,0),(0,6,1)]
            for on,value,clear in samples:
                g.nodes[gate]['p']['value']=on;g.nodes[reading]['p']['value']=value;g.nodes[reset]['p']['value']=clear;g.step(.125)
                count=lib.sample(on,value,clear,125000000)
                actual=[lib.get_message(i).decode().rstrip('\n') for i in range(count)]
                self.assertEqual(actual,g.messages)
        p=g.nodes[d]['p']
        for key,value in (('message',''),('message','bad\nline'),('message','é'*101),('show_value',1),('trigger_high',1),('cooldown_ms',-1),('cooldown_ms',float('inf'))):
            old=p[key];p[key]=value
            with self.assertRaises(ValueError):g.validate()
            p[key]=old

    def test_display_reset_overrides_cooldown_without_held_reset_flood(self):
        g=Graph();gate=g.add('input');reset=g.add('input');d=g.add('display')
        g.connect(gate,d,'trigger');g.connect(reset,d,'reset');g.nodes[gate]['p']['value']=1
        g.step(.02);self.assertEqual(g.messages,['PLC message'])
        g.nodes[reset]['p']['value']=1;g.step(.02);self.assertEqual(g.messages,['PLC message'])
        for _ in range(60):g.step(.02);self.assertEqual(g.messages,[])
        g.nodes[reset]['p']['value']=0;g.step(.02);self.assertEqual(g.messages,[])
        g.nodes[reset]['p']['value']=1;g.step(.02);self.assertEqual(g.messages,['PLC message'])
        g.nodes[gate]['p']['value']=0;g.nodes[reset]['p']['value']=0;g.step(.02)
        g.nodes[reset]['p']['value']=1;g.step(.02);self.assertEqual(g.messages,[])
        g.nodes[gate]['p']['value']=1;g.step(.02);self.assertEqual(g.messages,['PLC message'])

    def test_legacy_display_severity_migrates_to_self_contained_export(self):
        g=Graph();gate=g.add('input');d=g.add('display');g.connect(gate,d,'trigger')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);project=root/'project.json';g.save(project)
            for severity in ('Info','Error'):
                data=json.loads(project.read_text());data['nodes'][str(d)]['p']['severity']=severity
                project.write_text(json.dumps(data));loaded=Graph.load(project)
                self.assertNotIn('severity',loaded.nodes[d]['p'])
                self.assertEqual(loaded.links,g.links)
                loaded.nodes[gate]['p']['value']=1;loaded.step(.02)
                self.assertEqual(loaded.messages,['PLC message'])
                export=root/'messages.comp';loaded.export(export);text=export.read_text()
                self.assertIn('rtapi_print_msg(RTAPI_MSG_ERR',text)
                self.assertNotIn('lpn-display-',text)
                self.assertEqual(sorted(p.name for p in root.iterdir()),['messages.comp','messages.hal','messages.hal.json','messages.test.hal','messages.test.unload.hal','messages.unload.hal','project.json'])
            # Re-export removes only recognized helper metadata and its generated companions.
            (root/'messages.display.json').write_text(json.dumps(dict(component='messages-display',messages=[])))
            for suffix in ('.display.hal','.display.py'):export.with_suffix(suffix).write_text('obsolete helper')
            loaded.export(export)
            self.assertEqual(sorted(p.name for p in root.iterdir()),['messages.comp','messages.hal','messages.hal.json','messages.test.hal','messages.test.unload.hal','messages.unload.hal','project.json'])
            export.with_suffix('.display.json').write_text('{"unrelated":true}')
            loaded.export(export);self.assertTrue(export.with_suffix('.display.json').exists())

    def test_pid_feedforward_switch_limits_integrator_and_migration(self):
        g=Graph();i=g.add('pid');p=g.nodes[i]['p']
        p.update(kp=0,ki=0,kd=0,setpoint=4,feedback=4,ff_gain=2)
        self.assertEqual(g.step(.1)[i],0)
        p['ff_enabled']=True;self.assertEqual(g.step(.1)[i],8)
        self.assertEqual(g.value(i,'error'),0)
        p.update(setpoint=-4,feedback=-4);self.assertEqual(g.step(.1)[i],-8)
        p.update(kp=2,setpoint=4,feedback=3);self.assertEqual(g.step(.1)[i],10)
        p.update(kp=0,ki=1,output_max=9);g.reset()
        self.assertEqual(g.step(2)[i],9);self.assertEqual(g.state[i]['integral'],1)
        self.assertEqual(g.step(2)[i],9);self.assertEqual(g.state[i]['integral'],1)
        p.update(feedback=5);self.assertEqual(g.step(1)[i],8)
        p['enabled']=False;self.assertEqual(g.step(.1)[i],0)
        p['enabled']=True;reset=g.add('input');g.nodes[reset]['p']['value']=1;g.connect(reset,i,'reset')
        self.assertEqual(g.step(.1)[i],0)
        for key,value in (('ff_gain',float('inf')),('ff_enabled',1)):
            old=p[key];p[key]=value
            with self.assertRaises(ValueError):g.validate()
            p[key]=old
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ff.json';g.save(path);copy=Graph.load(path)
            self.assertEqual(copy.nodes,g.nodes)
            data=json.loads(path.read_text());oldp=data['nodes'][str(i)]['p']
            del oldp['ff_enabled'];del oldp['ff_gain'];path.write_text(json.dumps(data))
            legacy=Graph.load(path)
            self.assertFalse(legacy.nodes[i]['p']['ff_enabled']);self.assertEqual(legacy.nodes[i]['p']['ff_gain'],1)

    def test_pid_terms_time_and_derivative_on_measurement(self):
        g=Graph();i=g.add('pid');p=g.nodes[i]['p']
        p.update(kp=2.0,ki=3.0,kd=4.0,setpoint=5.0,feedback=2.0)
        self.assertAlmostEqual(g.step(.1)[i],6.9)
        self.assertEqual(g.value(i,'error'),3)
        self.assertAlmostEqual(g.step(.2)[i],8.7)
        p['feedback']=3
        self.assertAlmostEqual(g.step(.5)[i],4+5.7-8)
        # Setpoint changes produce no derivative kick.
        p['setpoint']=6
        self.assertAlmostEqual(g.step(.1)[i],6+6.6)
        g.reset();p.update(kp=0,ki=0,kd=1,feedback=0,filter_ms=100)
        self.assertEqual(g.step(.1)[i],0)
        p['feedback']=1;self.assertAlmostEqual(g.step(.1)[i],-5)
        self.assertAlmostEqual(g.step(.1)[i],-2.5)

    def test_pid_limits_antiwindup_reset_enable_and_invalid_time(self):
        g=Graph();i=g.add('pid');p=g.nodes[i]['p']
        reset=g.add('input');enable=g.add('input');g.nodes[enable]['p']['value']=1
        g.connect(reset,i,'reset');g.connect(enable,i,'enable')
        p.update(kp=0,ki=1,kd=0,setpoint=1,output_min=-2,output_max=2)
        self.assertEqual([g.step(1)[i] for _ in range(10)],[1]+[2]*9)
        self.assertEqual(g.state[i]['integral'],2)
        p['setpoint']=-1;self.assertEqual(g.step(1)[i],1)
        self.assertEqual([g.step(1)[i] for _ in range(6)],[0,-1,-2,-2,-2,-2])
        g.nodes[reset]['p']['value']=1;self.assertEqual(g.step(1)[i],0)
        self.assertEqual(g.state[i]['integral'],0)
        g.nodes[reset]['p']['value']=0;self.assertEqual(g.step(1)[i],-1)
        g.nodes[enable]['p']['value']=0;self.assertEqual(g.step(1)[i],0)
        g.nodes[enable]['p']['value']=1;self.assertEqual(g.step(1)[i],-1)
        for dt in (0,-1,float('nan'),float('inf')):
            self.assertEqual(g.step(dt)[i],0);self.assertFalse(g.state[i]['ready'])
        # Limits apply to P too; no hidden integral grows behind a saturated P term.
        p.update(kp=10,ki=1,setpoint=1);self.assertEqual(g.step(.1)[i],2)
        self.assertEqual(g.state[i]['integral'],0)
        p.update(setpoint=-1);self.assertEqual(g.step(.1)[i],-2)
        self.assertEqual(g.state[i]['integral'],0)
        # A pure integrator with a large increment reaches the limit rather than stalling at zero.
        g.reset();p.update(kp=0,ki=10,setpoint=1)
        self.assertEqual(g.step(1)[i],2);self.assertEqual(g.state[i]['integral'],2)
        p['setpoint']=-1;self.assertEqual(g.step(1)[i],-2)

    def test_pid_defaults_validation_types_and_roundtrip(self):
        g=Graph();i=g.add('pid');p=g.nodes[i]['p']
        self.assertEqual(g.inputs(i),('setpoint','feedback','enable','reset'))
        self.assertEqual(g.outputs(i),('out','error'))
        self.assertEqual([g.input_type(i,k) for k in g.inputs(i)],['float','float','bit','bit'])
        self.assertEqual(g.dtype(i,'out'),'float');self.assertEqual(g.dtype(i,'error'),'float')
        p.update(setpoint=12,feedback=3);self.assertEqual(g.step(.02)[i],9)
        p['enabled']=False;self.assertEqual(g.step(.02)[i],0)
        for key,value in (('filter_ms',-1),('output_min',101),('kp',float('nan')),('enabled',1)):
            previous=p[key];p[key]=value
            with self.assertRaises(ValueError):g.validate()
            p[key]=previous
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'pid.json';g.save(path);copy=Graph.load(path)
            self.assertEqual(copy.nodes,g.nodes);self.assertEqual(copy.step(.02)[i],0)

    def test_pid_closed_loop_first_order_plant(self):
        g=Graph();i=g.add('pid');p=g.nodes[i]['p']
        p.update(kp=2,ki=1,setpoint=1,output_min=-3,output_max=3)
        measured=0
        for _ in range(2000):
            p['feedback']=measured;out=g.step(.01)[i]
            self.assertLessEqual(abs(out),3)
            measured+=.01*(out-measured)
        self.assertAlmostEqual(measured,1,delta=.001)

    def test_pid_compiled_runtime_parity_and_independent_state(self):
        g=Graph();sources=[]
        for name,dtype in (('target','float'),('measured','float'),('enabled','bit'),('clear','bit')):
            i=g.add('input');g.nodes[i]['p'].update(name=name,dtype=dtype);sources.append(i)
        controllers=[];outputs=[]
        for index in range(2):
            pid=g.add('pid');controllers.append(pid)
            g.nodes[pid]['p'].update(kp=1.5+index,ki=.8,kd=.2,filter_ms=30,output_min=-4,output_max=6)
            g.nodes[pid]['p'].update(ff_enabled=bool(index),ff_gain=.7 if index else 100)
            for source,port in zip(sources,g.inputs(pid)):g.connect(source,pid,port)
            for port in ('out','error'):
                out=g.add('output');g.nodes[out]['p'].update(name=f'{port}-{index}',dtype='float');g.connect(pid,out,'in',port);outputs.append(out)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g.export(root/'pid_runtime.comp')
            text=(root/'pid_runtime.comp').read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            # halcompile exposes input pins as macros, which must not collide with helper arguments.
            harness='double target_storage,measured_storage,out_0,error_0,out_1,error_1;int enabled_storage,clear_storage;long period;\n'
            harness+='#define target (0+target_storage)\n#define measured (0+measured_storage)\n#define enabled (0+enabled_storage)\n#define clear (0+clear_storage)\n'+text
            harness+='\nvoid sample(double t,double m,int e,int r,long ns,double *out){target_storage=t;measured_storage=m;enabled_storage=e;clear_storage=r;period=ns;update();out[0]=out_0;out[1]=error_0;out[2]=out_1;out[3]=error_1;}\n'
            (root/'pid_runtime.c').write_text(harness)
            subprocess.run(['cc','-shared','-fPIC',str(root/'pid_runtime.c'),'-lm','-o',str(root/'pid_runtime.so')],check=True)
            lib=ctypes.CDLL(str(root/'pid_runtime.so'));lib.sample.argtypes=[ctypes.c_double,ctypes.c_double,ctypes.c_int,ctypes.c_int,ctypes.c_long,ctypes.POINTER(ctypes.c_double)]
            samples=[(1,0,1,0,20000000)]*10+[(10,2,1,0,10000000)]*20
            samples += [(0,3,1,0,40000000),(-10,2,1,0,20000000)]*10
            samples += [(1,0,1,1,20000000),(1,0,1,0,20000000),(1,0,0,0,20000000),(1,0,1,0,20000000),(1,0,1,0,0),(1,0,1,0,-1)]
            samples += [(1e308,-1e308,1,0,20000000),(1e308,0,1,0,20000000),(1,0,1,0,20000000)]
            for target,measured,enabled,clear,ns in samples:
                for source,value in zip(sources,(target,measured,enabled,clear)):g.nodes[source]['p']['value']=value
                g.step(ns*1e-9);actual=(ctypes.c_double*4)();lib.sample(target,measured,enabled,clear,ns,actual)
                for out,value in zip(outputs,actual):self.assertAlmostEqual(g.values[out],value,delta=1e-10)

    def test_expression_language(self):
        env=dict(x=4,y=2,gain=3,offset=1)
        self.assertEqual(calc(expression('clamp(x * gain + offset, 0, 10)'),env),10)
        self.assertTrue(calc(expression('0 < x < 5 and y != 0'),env))
        self.assertEqual(calc(expression('x / 0'),env),0)
        for source in ('x.__class__','__import__("os")','x[0]','abs','min(x)','float(x)','pi(x)'):
            with self.assertRaises(ValueError):expression(source)

    def test_bitshift_expressions_and_compiled_runtime(self):
        self.assertEqual(detected_variables('(x << count) + @offset'),('x','count'))
        for source,expected in [('1 << 2 + 1',8),('16 >> 1 >> 1',4),
                                ('1 << 2 == 4',True),('2^3 << 1',16),
                                ('(1 << 3) + (1 << 1)',10)]:
            self.assertEqual(calc(expression(source),{}),expected)
        cases=[(1,0,1,1),(1,3,8,0),(128,3,1024,16),
               (1,31,2147483648,0),(4294967295,1,4294967294,2147483647),
               (2147483648,1,0,1073741824),(-1,1,4294967294,2147483647),
               (-8,1,4294967280,2147483644),(3.9,1,6,1),
               (4294967297,0,1,1),(1,-1,0,0),(1,32,0,0),
               (1,1.5,0,0),(1,1e20,0,0),(1,float('inf'),0,0),
               (float('nan'),1,0,0),(float('inf'),1,0,0)]
        g=Graph();x=g.add('input');count=g.add('input')
        g.nodes[x]['p'].update(name='source',dtype='float')
        g.nodes[count]['p'].update(name='shift-count',dtype='float')
        outputs=[]
        for formula in ('x << count','x >> count'):
            m=g.add('math');g.set_expression(m,formula)
            g.connect(x,m,'x');g.connect(count,m,'count')
            output=g.add('output');g.nodes[output]['p'].update(name='left-result' if not outputs else 'right-result',dtype='float')
            g.connect(m,output,'in');outputs.append(output)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g.save(root/'shift.json');g=Graph.load(root/'shift.json')
            g.export(root/'shift.comp')
            text=(root/'shift.comp').read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            harness='double source_storage,shift_count_storage,left_result,right_result;long period=1000000;\n'
            harness+='#define source (0.0+source_storage)\n#define shift_count (0.0+shift_count_storage)\n'+text
            harness+='\nvoid sample(double value,double shift,double *out){source_storage=value;shift_count_storage=shift;update();out[0]=left_result;out[1]=right_result;}\n'
            (root/'shift.c').write_text(harness)
            subprocess.run(['cc','-shared','-fPIC','-fsanitize=undefined','-fno-sanitize-recover=all',str(root/'shift.c'),'-lm','-o',str(root/'shift.so')],check=True)
            lib=ctypes.CDLL(str(root/'shift.so'))
            lib.sample.argtypes=[ctypes.c_double,ctypes.c_double,ctypes.POINTER(ctypes.c_double)]
            for value,shift,left,right in cases:
                with self.subTest(value=value,shift=shift):
                    self.assertEqual([calc(expression(formula),dict(x=value,count=shift)) for formula in ('x << count','x >> count')],[left,right])
                    if math.isfinite(value) and math.isfinite(shift):
                        g.nodes[x]['p']['value']=value;g.nodes[count]['p']['value']=shift
                        simulated=g.step(.001)
                        self.assertEqual([simulated[i] for i in outputs],[left,right])
                    actual=(ctypes.c_double*2)();lib.sample(value,shift,actual)
                    self.assertEqual(list(actual),[left,right])
    def test_connections_and_feedback(self):
        g=demo();old=list(g.links)
        with self.assertRaises(ValueError):g.connect(3,2,'pressure')
        self.assertEqual(g.links,old)
        g.connect(1,4,'in');self.assertEqual(g.conversion(4,'in'),('float','bit'))
        g.connect(1,3,'pressure');self.assertEqual(len(g.links),3)
    def test_edge_and_debounce(self):
        g=Graph();i=g.add('input');p=g.nodes[i]['p'];p.update(edge='rising',debounce=30)
        self.assertEqual(g.step(.01)[i],0)
        p['value']=1
        self.assertEqual(g.step(.01)[i],0)
        self.assertEqual(g.step(.01)[i],0)
        self.assertEqual(g.step(.01)[i],1)
        self.assertEqual(g.step(.01)[i],0)
        p['value']=0;g.step(.03)
        p['value']=1;self.assertEqual(g.step(.03)[i],1)
    def test_cancelled_delays_and_inversion(self):
        g=Graph();i=g.add('input');o=g.add('output');g.connect(i,o,'in');p=g.nodes[o]['p'];p.update(on_delay=50,off_delay=100)
        g.nodes[i]['p']['value']=1;self.assertEqual(g.step(.02)[o],0)
        g.nodes[i]['p']['value']=0;self.assertEqual(g.step(.02)[o],0)
        g.nodes[i]['p']['value']=1;g.step(.02);g.step(.02);self.assertEqual(g.step(.02)[o],1)
        g.nodes[i]['p']['value']=0;self.assertEqual(g.step(.04)[o],1)
        g.nodes[i]['p']['value']=1;g.step(.02)
        g.nodes[i]['p']['value']=0;self.assertEqual(g.step(.06)[o],1);self.assertEqual(g.step(.04)[o],0)
        p['invert']=True;self.assertEqual(g.step(.01)[o],1)
    def test_dynamic_variables_and_constant_ports(self):
        g=Graph();m=g.add('math')
        g.set_expression(m,'abs(speed) * multiplier + speed')
        self.assertEqual(detected_variables(g.nodes[m]['p']['expression']),('speed','multiplier'))
        self.assertEqual(g.inputs(m),('speed','multiplier'))
        g.set_variable(m,'multiplier','mode','constant');g.set_variable(m,'multiplier','value',2)
        self.assertEqual(g.inputs(m),('speed',))
        g.set_expression(m,'speed * multiplier + trim')
        self.assertEqual(g.nodes[m]['p']['variables']['multiplier']['value'],2)
        self.assertEqual(g.inputs(m),('speed','trim'))
        g.set_variable(m,'trim','dtype','bit');g.set_variable(m,'trim','value',10)
        self.assertEqual(g.step(.01)[m],1)
        g.set_expression(m,'42');self.assertEqual(g.inputs(m),());self.assertEqual(g.step(.01)[m],42)

    def test_condition_outputs_and_variable_types(self):
        g=Graph();i=g.add('input');g.nodes[i]['p']['dtype']='float'
        c=g.add('condition');g.set_expression(c,'pressure > minimum and door_closed')
        self.assertEqual(g.nodes[c]['p']['variables']['door_closed']['dtype'],'bit')
        g.connect(i,c,'pressure')
        g.connect(i,c,'door_closed');self.assertEqual(g.conversion(c,'door_closed'),('float','bit'))
        g.set_variable(c,'pressure','dtype','bit')
        self.assertEqual(g.input_type(c,'pressure'),'bit')
        g.set_variable(c,'pressure','dtype','float')
        g.links=[l for l in g.links if l[2:]!=[c,'door_closed']]
        self.assertEqual(g.input_type(c,'pressure'),'float')
        a=g.add('output');b=g.add('output');g.connect(c,a,'in','true');g.connect(c,b,'in','false')
        g.set_variable(c,'minimum','value',3);g.set_variable(c,'door_closed','value',1)
        g.nodes[i]['p']['value']=5
        self.assertEqual((g.step(.01)[a],g.values[b]),(1,0))
        g.set_variable(c,'door_closed','value',0)
        self.assertEqual((g.step(.01)[a],g.values[b]),(0,1))
        g.set_variable(c,'door_closed','dtype','float');g.connect(i,c,'door_closed')
        self.assertEqual((g.step(.01)[a],g.values[b]),(1,0))

    def test_edit_preserves_valid_connections_and_rejects_invalid_expression(self):
        g=demo();links=list(g.links)
        with self.assertRaises((SyntaxError,ValueError)):g.set_expression(2,'pressure +')
        self.assertEqual(g.links,links)
        g.set_expression(2,'pressure * scale + trim');self.assertEqual(g.links,links)
        self.assertEqual(g.set_expression(2,'trim + scale'),1)
        self.assertTrue(all(l[2]!=2 for l in g.links))
        g.set_expression(3,'pressure > minimum')
        self.assertEqual(g.set_variable(3,'pressure','mode','constant'),1)
        self.assertTrue(all(l[2]!=3 for l in g.links))

    def test_legacy_project_load(self):
        fixture=Path(__file__).parent/'examples/legacy-v1.json'
        g=Graph.load(fixture)
        self.assertEqual(g.inputs(2),('x','gain','offset'))
        self.assertEqual(g.outputs(3),('true','false'))
        self.assertEqual(g.links[-1],[3,'true',4,'in'])
        self.assertEqual(g.step(.02)[2],8)

    def test_roundtrip_and_codegen_matches_simulator(self):
        g=demo()
        g.set_expression(2,'clamp(pressure * scale + trim, 0, 20) / 2')
        g.set_variable(2,'scale','value',10)
        g.set_variable(2,'trim','mode','constant');g.set_variable(2,'trim','value',2)
        g.set_expression(3,'scaled >= minimum and door_closed')
        g.connect(2,3,'scaled')
        g.set_variable(3,'minimum','value',3)
        door=g.add('input');g.nodes[door]['p']['name']='door'
        fault=g.add('output');g.nodes[fault]['p']['name']='fault'
        g.connect(door,3,'door_closed');g.connect(3,fault,'in','false')
        g.nodes[4]['p'].update(on_delay=0,off_delay=40,invert=True)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g.save(root/'project.json');copy=Graph.load(root/'project.json');self.assertEqual(g.nodes,copy.nodes);self.assertEqual(g.links,copy.links)
            g.export(root/'generated.comp')
            text=(root/'generated.comp').read_text().split(';;\n',1)[1]
            text=text.replace('FUNCTION(update)', 'void update(void)')
            harness='double pressure; int door,pump,fault; long period;\n'+text+'\nint sample(double p,int d,long ns){pressure=p;door=d;period=ns;update();return 2*pump+fault;}\n'
            (root/'generated.c').write_text(harness)
            subprocess.run(['cc','-shared','-fPIC',str(root/'generated.c'),'-lm','-o',str(root/'generated.so')],check=True)
            lib=ctypes.CDLL(str(root/'generated.so'));lib.sample.argtypes=[ctypes.c_double,ctypes.c_int,ctypes.c_long];lib.sample.restype=ctypes.c_int
            for value,d in [(0,1),(4,0),(4,1),(4,1),(1,0),(0,0),(0,1),(5,1)]:
                g.nodes[1]['p']['value']=value;g.nodes[door]['p']['value']=d
                values=g.step(.02)
                self.assertEqual(2*values[4]+values[fault],lib.sample(value,d,20000000))

    def test_modulo_signs_and_zero(self):
        for a in (-14.,-12.,-11.,-1.,0.,1.,11.,12.,14.):
            for b in (-12.,-5.,5.,12.):
                self.assertEqual(calc(expression('a % b'),dict(a=a,b=b)),a % b)
        self.assertEqual(modulo(4,0),0)
        self.assertEqual(modulo(float('inf'),12),0)

    def test_generated_modulo_matches_simulator(self):
        g=Graph();a=g.add('input');g.nodes[a]['p'].update(name='operand-a',dtype='float')
        b=g.add('input');g.nodes[b]['p'].update(name='operand-b',dtype='float')
        m=g.add('math');g.set_expression(m,'a % b');g.connect(a,m,'a');g.connect(b,m,'b')
        out=g.add('output');g.nodes[out]['p'].update(name='result',dtype='float');g.connect(m,out,'in')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g.export(root/'modulo.comp')
            text=(root/'modulo.comp').read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            harness='double operand_a,operand_b,result;long period=1000000;\n'+text+'\ndouble sample(double a,double b){operand_a=a;operand_b=b;update();return result;}\n'
            (root/'modulo.c').write_text(harness)
            subprocess.run(['cc','-shared','-fPIC',str(root/'modulo.c'),'-lm','-o',str(root/'modulo.so')],check=True)
            lib=ctypes.CDLL(str(root/'modulo.so'));lib.sample.argtypes=[ctypes.c_double,ctypes.c_double];lib.sample.restype=ctypes.c_double
            for av in (-4294967295.,-14.5,-12.,-1.,0.,1.,12.,14.5,4294967295.):
                for bv in (-12.,-5.,0.,1e-13,5.,12.):
                    g.nodes[a]['p']['value']=av;g.nodes[b]['p']['value']=bv
                    self.assertEqual(g.step(.001)[out],lib.sample(av,bv))

    def test_integer_conversion_limits(self):
        for value,kind,result in [(-1,'u32',0),(4294967296,'u32',4294967295),
                                  (3.9,'u32',3),(-3.9,'s32',-3),
                                  (-2147483649,'s32',-2147483648),(2147483648,'s32',2147483647)]:
            self.assertEqual(convert(value,kind),result)
        g=Graph();i=g.add('input');g.nodes[i]['p'].update(dtype='u32',value=4294967295)
        m=g.add('math');g.set_expression(m,'position - 4294967294');g.set_variable(m,'position','dtype','u32');g.connect(i,m,'position')
        self.assertEqual(g.step(.01)[m],1)
        self.assertEqual(convert(float('nan'),'s32'),0)

    def test_invert_node(self):
        g=Graph();i=g.add('input');inv=g.add('invert');o=g.add('output');g.connect(i,inv,'in');g.connect(inv,o,'in')
        self.assertEqual(g.outputs(inv),('out',));self.assertEqual(g.inputs(inv),('in',))
        self.assertEqual(g.step(.01)[o],1)
        g.nodes[i]['p']['value']=1;self.assertEqual(g.step(.01)[o],0)
        g.nodes[i]['p']['dtype']='float'
        g.validate();self.assertEqual(g.conversion(inv,'in'),('float','bit'))
        self.assertEqual(g.step(.01)[o],0)

    def test_extended_math_and_precedence(self):
        for source,wanted in [('2 ^ 3 + 1',9),('2 ** 3 ** 2',512),
                              ('-2 ^ 2',-4),('(-2)^2',4),('2^-2',.25),
                              ('sqrt(9)',3),('pow(2,3)',8),('sin(pi/2)',1),
                              ('cos(0)',1),('tan(0)',0),('asin(1)',__import__('math').pi/2),
                              ('acos(1)',0),('atan(0)',0),('atan2(1,0)',__import__('math').pi/2),
                              ('log(e)',1),('log10(100)',2),('exp(0)',1),
                              ('floor(-2.1)',-3),('ceil(-2.1)',-2),
                              ('sqrt(-1)',0),('log(0)',0),('asin(2)',0),
                              ('exp(10000)',0),('(-1)^0.5',0),('0^-1',0)]:
            with self.subTest(source=source):self.assertAlmostEqual(calc(expression(source),{}),wanted)
        self.assertEqual(detected_variables('sin(angle) + pi * r^2 + e'),('angle','r'))

    def test_math_template_roundtrip_and_transactional_load(self):
        from copy import deepcopy
        g=Graph();source=g.add('input');m=g.add('math',(123,45));out=g.add('output')
        g.set_expression(m,'n0 + spare');g.connect(source,m,'n0');g.connect(source,m,'spare');g.connect(m,out,'in')
        root=Path(__file__).parent/'templates'
        original=deepcopy(g.nodes);links=deepcopy(g.links)
        with self.assertRaises(ValueError):g.load_math_template(m,root/'4-bit-to-u32.json')
        self.assertEqual(g.nodes,original);self.assertEqual(g.links,links)
        g.disconnect_node(m)
        removed=g.load_math_template(m,root/'4-bit-to-u32.json')
        self.assertEqual(removed,0);self.assertEqual(g.dtype(m),'u32')
        self.assertEqual(g.input_type(m,'n0'),'bit');self.assertEqual(g.nodes[m]['pos'],[123,45])
        self.assertFalse(g.has_connections(m))
        g.set_variable(m,'n1','mode','constant');g.set_variable(m,'n1','value',1)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'template.json';g.save_math_template(m,path)
            copy=Graph();other=copy.add('math');copy.load_math_template(other,path)
            self.assertEqual(g.math_template(m),copy.math_template(other))
            copy.set_variable(other,'n1','value',0)
            self.assertEqual(g.nodes[m]['p']['variables']['n1']['value'],1)
        nodes=deepcopy(g.nodes);links=deepcopy(g.links)
        for data in [dict(format='wrong',version=1),
                     dict(g.math_template(m),expression='n0 +'),
                     dict(g.math_template(m),expression='unknown'),
                     dict(g.math_template(m),variables={'n0':{'dtype':'bit'}}),
                     dict(g.math_template(m),dtype='bad')]:
            with self.assertRaises((ValueError,SyntaxError)):g.apply_math_template(m,data)
            self.assertEqual(g.nodes,nodes);self.assertEqual(g.links,links)

    def test_bit_packing_templates_all_values(self):
        for count in (4,8):
            g=Graph();m=g.add('math')
            g.load_math_template(m,Path(__file__).parent/'templates'/f'{count}-bit-to-u32.json')
            sources=[]
            for j in range(count):
                source=g.add('input');sources.append(source);g.connect(source,m,f'n{j}')
            for number in range(1<<count):
                for j,source in enumerate(sources):g.nodes[source]['p']['value']=(number>>j)&1
                self.assertEqual(g.step(.02)[m],number)

    def test_template_lock_incoming_and_outgoing_connections(self):
        from copy import deepcopy
        path=Path(__file__).parent/'templates/4-bit-to-u32.json'
        g=circular_demo();original=deepcopy(g.nodes);links=deepcopy(g.links)
        for subset in [links,[l for l in links if l[0]==3],[l for l in links if l[2]==3]]:
            g.links=deepcopy(subset);self.assertTrue(g.has_connections(3))
            with self.assertRaises(ValueError):g.load_math_template(3,path)
            self.assertEqual(g.nodes,original);self.assertEqual(g.links,subset)
        g.links=links;g.disconnect_node(3);self.assertFalse(g.has_connections(3))
        g.load_math_template(3,path)
        self.assertEqual(g.inputs(3),('n0','n1','n2','n3'));self.assertEqual(g.dtype(3),'u32')

    def test_fifo_sampling_reset_and_unconnected_initial_value(self):
        g=Graph();source=g.add('input');g.nodes[source]['p']['dtype']='float'
        fifo=g.add('fifo');g.nodes[fifo]['p']['initial']=5
        delta=g.add('math');g.set_expression(delta,'now - last')
        g.connect(source,fifo,'in');g.connect(fifo,delta,'last','last');g.connect(fifo,delta,'now','now')
        self.assertEqual(g.outputs(fifo),('last','now'));self.assertEqual(g.inputs(fifo),('in',))
        for current,last,difference in [(10,5,5),(12,10,2),(12,12,0),(7,12,-5)]:
            g.nodes[source]['p']['value']=current;g.step(.02)
            self.assertEqual(g.value(fifo,'last'),last);self.assertEqual(g.value(fifo,'now'),current)
            self.assertEqual(g.values[delta],difference)
        g.reset();g.step(.02);self.assertEqual(g.value(fifo,'last'),5)
        g.disconnect_node(fifo)
        for _ in range(3):
            g.step(.02);self.assertEqual((g.value(fifo,'last'),g.value(fifo,'now')),(5,5))

    def test_fifo_inherits_input_type_and_chain_roundtrip(self):
        g=Graph();source=g.add('input');first=g.add('fifo');second=g.add('fifo')
        g.connect(source,first,'in');g.connect(first,second,'in','now')
        for dtype in ('bit','float','s32','u32'):
            g.nodes[source]['p']['dtype']=dtype;g.reset()
            for fifo in (first,second):
                self.assertEqual(g.input_type(fifo,'in'),dtype)
                self.assertEqual(g.dtype(fifo,'last'),dtype);self.assertEqual(g.dtype(fifo,'now'),dtype)
                self.assertIsNone(g.conversion(fifo,'in'))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fifo.json';g.save(path);copy=Graph.load(path)
            self.assertEqual(copy.dtype(second),'u32');self.assertEqual(copy.links,g.links)
            g.nodes[source]['p']['value']=4294967295;copy.nodes[source]['p']['value']=4294967295
            self.assertEqual(g.step(.02),copy.step(.02))
        links=list(g.links)
        with self.assertRaises(ValueError):g.connect(second,first,'in','last')
        self.assertEqual(g.links,links)

    def test_fifo_compiled_runtime_matches_all_types(self):
        c_types={'bit':'int','float':'double','s32':'int32_t','u32':'uint32_t'}
        for dtype in c_types:
            g=Graph();source=g.add('input');g.nodes[source]['p'].update(name='sample-value',dtype=dtype)
            fifo=g.add('fifo');g.nodes[fifo]['p']['initial']=-2.9;g.connect(source,fifo,'in')
            last=g.add('output');g.nodes[last]['p'].update(name='last-value',dtype=dtype);g.connect(fifo,last,'in','last')
            now=g.add('output');g.nodes[now]['p'].update(name='now-value',dtype=dtype);g.connect(fifo,now,'in','now')
            delta=g.add('math');g.set_expression(delta,'now - last');g.connect(fifo,delta,'now','now');g.connect(fifo,delta,'last','last')
            out=g.add('output');g.nodes[out]['p'].update(name='difference',dtype='float');g.connect(delta,out,'in')
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);g.export(root/'fifo_runtime.comp')
                text=(root/'fifo_runtime.comp').read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
                harness='#include <stdint.h>\n'+c_types[dtype]+' sample_value,last_value,now_value;double difference;long period=20000000;\n'+text
                harness+='\nvoid sample(double value,double *out){sample_value=value;update();out[0]=last_value;out[1]=now_value;out[2]=difference;}\n'
                (root/'fifo_runtime.c').write_text(harness)
                subprocess.run(['cc','-shared','-fPIC',str(root/'fifo_runtime.c'),'-lm','-o',str(root/'fifo_runtime.so')],check=True)
                lib=ctypes.CDLL(str(root/'fifo_runtime.so'));lib.sample.argtypes=[ctypes.c_double,ctypes.POINTER(ctypes.c_double)];lib.sample.restype=None
                previous=convert(-2.9,dtype)
                for value in [0,3.9,3.9,-7.2,4294967295,0,2147483647,-2147483648]:
                    g.nodes[source]['p']['value']=value;g.step(.02)
                    current=convert(value,dtype);actual=(ctypes.c_double*3)();lib.sample(current,actual)
                    expected=(previous,current,current-previous)
                    self.assertEqual((g.values[last],g.values[now],g.values[out]),expected)
                    self.assertEqual(tuple(actual),expected);previous=current

    def test_math_result_types_and_legacy_migration(self):
        g=Graph();m=g.add('math');g.set_expression(m,'-3.9')
        self.assertEqual(g.dtype(m),'float')
        g.nodes[m]['p']['dtype']='s32';self.assertEqual(g.step(.01)[m],-3)
        g.nodes[m]['p']['dtype']='u32';self.assertEqual(g.step(.01)[m],0)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'project.json';g.save(path)
            self.assertEqual(Graph.load(path).dtype(m),'u32')
            legacy=json.loads(path.read_text());legacy['version']=2
            legacy['nodes'][str(m)]['p']['dtype']='bit';path.write_text(json.dumps(legacy))
            loaded=Graph.load(path);self.assertEqual(loaded.dtype(m),'float')
            self.assertEqual(loaded.step(.01)[m],-3.9)

    def test_extended_math_compiled_runtime(self):
        formulas=['x^y','x**y','pow(x,y)','sqrt(x)','sin(x)','cos(x)','tan(x)',
                  'asin(x)','acos(x)','atan(x)','atan2(x,y)','log(x)','log10(x)',
                  'exp(x)','floor(x)','ceil(x)','abs(x)','min(x,y)','max(x,y)',
                  'clamp(x,-2,2)','sin(pi/2)+log(e)','x^2 + y^2']
        g=Graph();x=g.add('input');y=g.add('input')
        g.nodes[x]['p'].update(name='input-x',dtype='float')
        g.nodes[y]['p'].update(name='input-y',dtype='float')
        outputs=[]
        for index,formula in enumerate(formulas):
            m=g.add('math');g.set_expression(m,formula)
            for variable in g.inputs(m):g.connect(x if variable=='x' else y,m,variable)
            o=g.add('output');g.nodes[o]['p'].update(name=f'result-{index}',dtype='float')
            g.connect(m,o,'in');outputs.append(o)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g.export(root/'extended.comp')
            text=(root/'extended.comp').read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            results=','.join(f'result_{i}' for i in range(len(formulas)))
            harness='double input_x,input_y,'+results+';long period=1000000;\n'+text
            harness+='\nvoid sample(double x,double y,double *out){input_x=x;input_y=y;update();'
            harness+=''.join(f'out[{i}]=result_{i};' for i in range(len(formulas)))+'}\n'
            (root/'extended.c').write_text(harness)
            subprocess.run(['cc','-shared','-fPIC',str(root/'extended.c'),'-lm','-o',str(root/'extended.so')],check=True)
            lib=ctypes.CDLL(str(root/'extended.so'));lib.sample.argtypes=[ctypes.c_double,ctypes.c_double,ctypes.POINTER(ctypes.c_double)]
            for xv,yv in [(-3.9,2),(-1,.5),(0,-1),(0,0),(.5,3),(1,2),(3.9,2),(10000,10000)]:
                g.nodes[x]['p']['value']=xv;g.nodes[y]['p']['value']=yv
                values=g.step(.01);actual=(ctypes.c_double*len(formulas))();lib.sample(xv,yv,actual)
                for index,o in enumerate(outputs):
                    with self.subTest(formula=formulas[index],x=xv,y=yv):
                        self.assertAlmostEqual(values[o],actual[index],delta=max(1e-12,abs(values[o])*1e-12))

    def test_all_automatic_conversions_and_compiled_result_types(self):
        from model import TYPES
        g=Graph();sources=[];outputs=[];maths=[]
        for dtype in TYPES:
            i=g.add('input');g.nodes[i]['p'].update(name='source-'+dtype,dtype=dtype);sources.append(i)
            for target in TYPES:
                m=g.add('math');g.nodes[m]['p']['dtype']=target
                g.set_variable(m,'x','dtype',target);g.connect(i,m,'x');maths.append(m)
                self.assertEqual(g.conversion(m,'x'),(dtype,target) if dtype!=target else None)
                o=g.add('output');g.nodes[o]['p'].update(name=f'result-{dtype}-{target}',dtype=target)
                g.connect(m,o,'in');outputs.append(o)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g.export(root/'conversions.comp')
            text=(root/'conversions.comp').read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            ctypes_c={'bit':'int','float':'double','s32':'int32_t','u32':'uint32_t'}
            harness='#include <stdint.h>\nlong period=1000000;\n'
            for i in sources+outputs:
                p=g.nodes[i]['p'];harness+=ctypes_c[p['dtype']]+' '+p['name'].replace('-','_')+';\n'
            harness+=text+'\nvoid sample(double *in,double *out){'
            harness+=''.join(g.nodes[i]['p']['name'].replace('-','_')+f'=in[{j}];' for j,i in enumerate(sources))
            harness+='update();'+''.join(f'out[{j}]='+g.nodes[i]['p']['name'].replace('-','_')+';' for j,i in enumerate(outputs))+'}\n'
            (root/'conversions.c').write_text(harness)
            subprocess.run(['cc','-shared','-fPIC',str(root/'conversions.c'),'-lm','-o',str(root/'conversions.so')],check=True)
            lib=ctypes.CDLL(str(root/'conversions.so'));lib.sample.argtypes=[ctypes.POINTER(ctypes.c_double)]*2
            for value in (-1e20,-2147483649,-3.9,0,3.9,2147483648,4294967295,1e20):
                for i in sources:g.nodes[i]['p']['value']=value
                values=g.step(.01);inputs=(ctypes.c_double*4)(*(values[i] for i in sources))
                actual=(ctypes.c_double*16)();lib.sample(inputs,actual)
                for j,o in enumerate(outputs):self.assertEqual(values[o],actual[j])

    def test_circular_all_positions_and_compiled_runtime(self):
        g=circular_demo()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g.save(root/'circle.json');self.assertEqual(Graph.load(root/'circle.json').nodes,g.nodes)
            g.export(root/'circle.comp')
            text=(root/'circle.comp').read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            harness='#include <stdint.h>\nuint32_t actual_position,target_position; int at_position,motor_cw,motor_ccw; long period;\n'+text+'\nint sample(uint32_t a,uint32_t t){actual_position=a;target_position=t;period=1000000;update();return at_position+2*motor_cw+4*motor_ccw;}\n'
            (root/'circle.c').write_text(harness)
            subprocess.run(['cc','-shared','-fPIC',str(root/'circle.c'),'-lm','-o',str(root/'circle.so')],check=True)
            lib=ctypes.CDLL(str(root/'circle.so'));lib.sample.argtypes=[ctypes.c_uint32,ctypes.c_uint32];lib.sample.restype=ctypes.c_int
            named={n['p']['name']:i for i,n in g.nodes.items() if n['kind']=='output'}
            for actual in range(12):
                for target in range(12):
                    g.nodes[1]['p']['value']=actual;g.nodes[2]['p']['value']=target
                    values=g.step(.001)
                    cw,ccw=values[named['motor-cw']],values[named['motor-ccw']]
                    self.assertFalse(cw and ccw)
                    distance=(target-actual+6)%12-6
                    self.assertEqual(cw,distance>0);self.assertEqual(ccw,distance<0)
                    code=values[named['at-position']]+2*cw+4*ccw
                    self.assertEqual(code,lib.sample(actual,target))
            for stations in (5,7):
                g.set_variable(3,'stations','value',stations)
                for actual in range(stations):
                    for target in range(stations):
                        g.nodes[1]['p']['value']=actual;g.nodes[2]['p']['value']=target
                        self.assertEqual(g.step(.001)[3],(target-actual+stations/2)%stations-stations/2)

    def test_generated_integer_output_and_constants(self):
        g=Graph();source=g.add('input');g.nodes[source]['p'].update(name='source',dtype='float')
        mathnode=g.add('math');g.set_expression(mathnode,'value + unsigned_const + signed_const')
        for name,kind,value in [('unsigned_const','u32',4294967295),('signed_const','s32',-2147483648)]:
            g.set_variable(mathnode,name,'dtype',kind);g.set_variable(mathnode,name,'mode','constant');g.set_variable(mathnode,name,'value',value)
        g.connect(source,mathnode,'value')
        signed=g.add('output');g.nodes[signed]['p'].update(name='signed-result',dtype='s32')
        unsigned=g.add('output');g.nodes[unsigned]['p'].update(name='unsigned-result',dtype='u32')
        g.connect(mathnode,signed,'in');g.connect(mathnode,unsigned,'in')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g.export(root/'integers.comp')
            text=(root/'integers.comp').read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            harness='#include <stdint.h>\ndouble source; int32_t signed_result; uint32_t unsigned_result; long period=1000000;\n'+text+'\nint32_t get_signed(double v){source=v;update();return signed_result;}\nuint32_t get_unsigned(double v){source=v;update();return unsigned_result;}\n'
            (root/'integers.c').write_text(harness)
            subprocess.run(['cc','-shared','-fPIC',str(root/'integers.c'),'-lm','-o',str(root/'integers.so')],check=True)
            lib=ctypes.CDLL(str(root/'integers.so'))
            lib.get_signed.argtypes=[ctypes.c_double];lib.get_signed.restype=ctypes.c_int32
            lib.get_unsigned.argtypes=[ctypes.c_double];lib.get_unsigned.restype=ctypes.c_uint32
            for value in (-1e20,-2147483649,-3.9,0,1.9,2147483648,1e20):
                g.nodes[source]['p']['value']=value;values=g.step(.001)
                self.assertEqual(values[signed],lib.get_signed(value));self.assertEqual(values[unsigned],lib.get_unsigned(value))

if __name__=='__main__':unittest.main()
