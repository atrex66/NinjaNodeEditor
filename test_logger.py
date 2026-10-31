import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from model import Graph
from logger_runtime import SimulationLogger,write_snapshot,validate_config,SnapshotWriter

class LoggerTests(unittest.TestCase):
    def graph(self):
        g=Graph();a=g.add('input');g.nodes[a]['p'].update(name='position',dtype='u32',value=4294967295)
        trigger=g.add('input');g.nodes[trigger]['p'].update(name='save-log',value=0)
        l=g.add('logger');g.nodes[l]['p'].update(buffer_length=2,sample_ms=2)
        g.connect(a,l,'in1');g.connect(trigger,l,'trigger');return g,a,trigger,l
    def test_ring_sampling_trigger_types_and_roundtrip(self):
        g,a,t,l=self.graph();self.assertEqual(g.input_type(l,'in1'),'u32');self.assertIsNone(g.conversion(l,'in1'))
        g.step(.001);self.assertEqual(g.values[l],0);g.step(.001)
        for v in (4294967295,23,24):
            g.nodes[a]['p']['value']=v;g.step(.002)
        g.nodes[t]['p']['value']=1;g.step(.001)
        snap=g.logger_requests[0];self.assertEqual([row[1][0] for row in snap['rows']],[23,24])
        self.assertEqual(snap['config']['channels'][0]['name'],'Main / position.out')
        g.step(.001);self.assertEqual(g.logger_requests,[])
        g.nodes[t]['p']['value']=0;g.step(.001);g.nodes[t]['p']['value']=1;g.step(.001)
        self.assertEqual(g.logger_requests[0]['sequence'],2)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'graph.json';g.save(path);h=Graph.load(path);self.assertEqual(h.inputs(l),('in1','in2','trigger'));self.assertEqual(h.input_type(l,'in1'),'u32')
    def test_between_samples_and_empty_save(self):
        g,a,t,l=self.graph();g.nodes[l]['p']['sample_ms']=10;g.nodes[t]['p']['value']=1
        g.step(.001);self.assertEqual(g.logger_requests[0]['rows'],())
        g.nodes[t]['p']['value']=0;g.step(.009)
        g.nodes[a]['p']['value']=20;g.nodes[t]['p']['value']=1;g.step(.001)
        self.assertEqual(g.logger_requests[0]['rows'][0][1][0],4294967295)
    def test_validation_and_formats(self):
        g,a,t,l=self.graph();p=g.nodes[l]['p']
        for key,value in [('input_count',19),('buffer_length',0),('sample_ms',0),('number_format','%f'),('filename','{node.__class__}'),('file_format','raw')]:
            old=p[key];p[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):g.validate()
            p[key]=old
        with tempfile.TemporaryDirectory() as tmp:
            for fmt in ('csv','tsv','jsonl'):
                p.update(file_format=fmt,filename='history-{sequence}.'+fmt)
                config=g.logger_config(l,tmp);logger=SimulationLogger(config)
                snap=logger.step(.002,2,True,[4294967295,1.23456789]);path=write_snapshot(snap)
                self.assertTrue(path.exists())
                if fmt=='jsonl':
                    row=json.loads(path.read_text());self.assertEqual(row['signals'][0]['value'],4294967295);self.assertEqual(row['signals'][0]['type'],'u32')
                else:
                    with path.open() as f:rows=list(csv.reader(f,delimiter='\t' if fmt=='tsv' else ','))
                    self.assertIn('position.out [u32]',rows[0][1]);self.assertEqual(rows[1][1],'4294967295')
                self.assertFalse(list(Path(tmp).glob('.*')))
    def test_export_bundle_and_retirement(self):
        g,a,t,l=self.graph()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'logger_test.comp';g.export(path)
            source=path.read_text();self.assertIn('hal_stream_write',source);self.assertIn('EXTRA_SETUP()',source);self.assertNotIn('fopen',source)
            config=json.loads(path.with_suffix('.logger.json').read_text())['loggers'][0]
            self.assertEqual(config['stream_format'],'fbbff');self.assertEqual(config['channels'][0]['dtype'],'u32')
            setup=path.with_suffix('.logger.hal').read_text();self.assertIn('loadusr -Wn logger_test-logger',setup);self.assertIn('logger-test.update servo-thread',setup)
            self.assertIn('def write_snapshot',path.with_suffix('.logger.py').read_text())
            del g.nodes[l];g.links=[];g.export(path);self.assertFalse(path.with_suffix('.logger.py').exists())
    def test_generated_realtime_stream_matches_simulation(self):
        import ctypes
        import subprocess
        from logger_runtime import Collector
        g,a,t,l=self.graph()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'stream_parity.comp';g.export(path)
            source=path.read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            harness='\n'.join([
                '#include <stdint.h>',
                'union hal_stream_data {double f;int b;}; typedef int hal_stream_t;',
                'static int comp_id=1,save_log,seen;static double position;static long period;',
                'static union hal_stream_data captured[5];',
                'int hal_stream_create(hal_stream_t *s,int c,int k,int d,const char *f){return 0;}',
                'void hal_stream_destroy(hal_stream_t *s){}',
                'int hal_stream_write(hal_stream_t *s,union hal_stream_data *d){for(int j=0;j<5;j++)captured[j]=d[j];seen=1;return 0;}',
                '#define EXTRA_SETUP() int extra_setup(void)',
                '#define EXTRA_CLEANUP() void extra_cleanup(void)',source,
                'int sample(double value,int trigger,long ns,double *result){position=value;save_log=trigger;period=ns;seen=0;update();if(seen){result[0]=captured[0].f;result[1]=captured[1].b;result[2]=captured[2].b;result[3]=captured[3].f;result[4]=captured[4].f;}return seen;}'
            ])
            (root/'parity.c').write_text(harness)
            subprocess.run(['cc','-shared','-fPIC',str(root/'parity.c'),'-lm','-o',str(root/'parity.so')],check=True)
            lib=ctypes.CDLL(str(root/'parity.so'));lib.sample.argtypes=[ctypes.c_double,ctypes.c_int,ctypes.c_long,ctypes.POINTER(ctypes.c_double)]
            collector=Collector(g.logger_config(l))
            for value,trigger,ns in [(4294967295,0,1000000),(12,0,1000000),(23,1,1000000),(24,1,1000000),(25,0,2000000),(26,1,1000000),(27,1,3000000),(28,0,1000000),(29,1,1000000)]:
                g.nodes[a]['p']['value']=value;g.nodes[t]['p']['value']=trigger;g.step(ns*1e-9)
                actual=(ctypes.c_double*5)();snapshot=None
                if lib.sample(value,trigger,ns,actual):snapshot=collector.accept(tuple(actual))
                self.assertEqual(list(collector.rows),list(g.state[l]['logger'].collector.rows))
                self.assertEqual(bool(snapshot),bool(g.logger_requests))
                if snapshot:self.assertEqual(snapshot['rows'],g.logger_requests[0]['rows'])
    def test_userspace_helper_attaches_drains_and_shuts_down(self):
        import signal
        import types
        import logger_runtime
        g,a,t,l=self.graph();snapshots=[];calls=[];handlers={}
        class Component:
            def ready(self):calls.append('ready')
            def exit(self):calls.append('exit')
        class Stream:
            num_overruns=1
            def __init__(self):self.records=iter([(2,True,False,4294967295,0),(3,False,True,23,0)])
            def read(self):return next(self.records,None)
        class Writer:
            def poll(self):return []
            def submit(self,snapshot):snapshots.append(snapshot);return True
            def close(self):calls.append('closed')
        component=Component()
        def attach(c,key,fmt):
            self.assertIs(c,component);self.assertEqual(fmt,'fbbff');calls.append('attached');return Stream()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'helper_test.comp';g.export(path)
            hal=types.SimpleNamespace(component=lambda name:(calls.append(name) or component),stream=attach)
            with patch.dict('sys.modules',{'hal':hal}),patch('sys.argv',['logger.py',str(path.with_suffix('.logger.json'))]),patch('signal.signal',side_effect=lambda sig,fn:handlers.update({sig:fn})),patch('time.sleep',side_effect=lambda seconds:handlers[signal.SIGTERM]()),patch.object(logger_runtime,'SnapshotWriter',Writer),patch('sys.stderr'):
                logger_runtime.main()
        self.assertEqual(calls,['helper_test-logger','attached','ready','closed','exit'])
        self.assertEqual(snapshots[0]['rows'],((2.0,(4294967295,0)),))
    def test_failed_write_keeps_previous_file_and_removes_temporary(self):
        g,a,t,l=self.graph()
        with tempfile.TemporaryDirectory() as tmp:
            g.nodes[l]['p']['filename']='history.csv';config=g.logger_config(l,tmp);logger=SimulationLogger(config)
            snap=logger.step(.002,2,True,[23,1]);path=Path(tmp)/'history.csv';path.write_text('old data')
            with patch('logger_runtime.os.replace',side_effect=OSError('permission denied')),self.assertRaises(OSError):write_snapshot(snap)
            self.assertEqual(path.read_text(),'old data');self.assertEqual(list(Path(tmp).iterdir()),[path])
    def test_async_snapshot_bounded_and_disk_error_reported(self):
        from concurrent.futures import Future
        g,a,t,l=self.graph();logger=SimulationLogger(g.logger_config(l));snap=logger.step(.002,2,True,[1,2])
        writer=SnapshotWriter();self.addCleanup(writer.close);future=Future()
        with patch.object(writer.executor,'submit',return_value=future):
            self.assertTrue(writer.submit(snap));self.assertFalse(writer.submit(snap));self.assertEqual(writer.poll(),[])
        future.set_exception(OSError('disk full'));self.assertEqual(writer.poll(),[(l,None,'disk full')])
