import ctypes
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from hal_bindings import Catalogue,wiring_plan,monitor_map,fingerprint
from live_hal import LiveSession
from model import Graph

PINS='''motion bit OUT TRUE motion.enabled ==> machine-on
ui bit IN TRUE ui.ready <== machine-on
io float OUT 1.25 io.position
io bit IN FALSE io.command
'''
SIGS='bit TRUE machine-on <== motion.enabled ==> ui.ready\nfloat 0 free-position\n'

class HALTests(unittest.TestCase):
    def test_install_uses_prompted_sudo_password_only_on_standard_input(self):
        from live_hal import install_component
        calls=[];events=[]
        def install(argv,**kwargs):
            calls.append((argv,kwargs));error='Permission denied' if len(calls)==1 else 'sudo: a password is required' if len(calls)==2 else ''
            return subprocess.CompletedProcess(argv,int(bool(error)),stdout='',stderr=error)
        install_component(Path('/tmp/test.comp'),install,lambda *args,**fields:events.append(fields),which=lambda name:'/usr/bin/'+name,request_password=lambda:'test-only-secret')
        self.assertEqual(calls[-1],(['/usr/bin/sudo','-S','-p','','/usr/bin/halcompile','--install','/tmp/test.comp'],{'password':'test-only-secret'}))
        self.assertFalse(events)
        self.assertNotIn('test-only-secret',str([argv for argv,_ in calls]))
    def test_install_password_prompt_cancellation_stops_before_install(self):
        from live_hal import install_component
        calls=[]
        def install(argv):
            calls.append(argv);return subprocess.CompletedProcess(argv,1,stdout='',stderr='Permission denied')
        with self.assertRaisesRegex(RuntimeError,'cancelled'):
            install_component(Path('/tmp/test.comp'),install,lambda *args,**fields:None,which=lambda name:'/usr/bin/'+name,request_password=lambda:None)
        self.assertEqual(len(calls),2)
    def test_compile_failure_after_sudo_is_not_reported_as_bad_password(self):
        from live_hal import install_component
        calls=[]
        def install(argv,**kwargs):
            calls.append(argv)
            error='Permission denied' if len(calls)==1 else 'sudo: a password is required' if len(calls)==2 else 'cc1: error: /sshfs/project: Permission denied'
            return subprocess.CompletedProcess(argv,1,stdout='',stderr=error)
        with self.assertRaisesRegex(RuntimeError,'build/install failed after sudo authorization') as failure:
            install_component(Path('/tmp/test.comp'),install,lambda *args,**fields:None,which=lambda name:'/usr/bin/'+name,request_password=lambda:'test-only-secret')
        self.assertNotIn('Check the sudo password',str(failure.exception))
    def test_install_permission_failure_requests_system_authentication(self):
        from live_hal import install_component
        calls=[];events=[]
        def install(argv):
            calls.append(argv)
            error='Permission denied' if len(calls)==1 else 'sudo: a password is required' if len(calls)==2 else ''
            return subprocess.CompletedProcess(argv,int(bool(error)),stdout='',stderr=error)
        install_component(Path('/tmp/test.comp'),install,lambda *args,**fields:events.append(fields),which=lambda name:'/usr/bin/'+name)
        self.assertEqual(calls[-1],['/usr/bin/pkexec','--disable-internal-agent','/usr/bin/halcompile','--install','/tmp/test.comp'])
        self.assertEqual(len(events),1)
    def test_install_compile_error_does_not_request_privileges(self):
        from live_hal import install_component
        calls=[]
        def install(argv):
            calls.append(argv);return subprocess.CompletedProcess(argv,1,stdout='',stderr='syntax error in component')
        with self.assertRaisesRegex(RuntimeError,'syntax error'):
            install_component(Path('/tmp/test.comp'),install,lambda *args,**fields:None,which=lambda name:'/usr/bin/'+name)
        self.assertEqual(len(calls),1)
    def test_install_authentication_unavailable_or_cancelled(self):
        from live_hal import install_component
        for available in (False,True):
            with self.subTest(pkexec=available):
                def install(argv):return subprocess.CompletedProcess(argv,1,stdout='',stderr='Permission denied')
                def which(name):return '/usr/bin/'+name if name!='pkexec' or available else None
                with self.assertRaisesRegex(RuntimeError,'authentication tool' if not available else 'authorization failed'):
                    install_component(Path('/tmp/test.comp'),install,lambda *args,**fields:None,which=which)
    def test_halcmd_bidirectional_pin_does_not_abort_discovery(self):
        pins=PINS+'motion bit I/O FALSE spindle.0.index-enable <=> spindle-index\nmotion u32 OUT 0x0000000F motion.count\nalias old-name\n'
        signals=SIGS+'bit FALSE spindle-index <=> spindle.0.index-enable\n'
        def run(*args):
            self.assertIn(args,[('-s','show','pin'),('-s','show','sig')])
            return pins if args[-1]=='pin' else signals
        c=Catalogue.discover(run)
        self.assertEqual(len(c.pins),6)
        self.assertEqual(c.pins['spindle.0.index-enable']['direction'],'IO')
        self.assertEqual(c.pins['spindle.0.index-enable']['signal'],'spindle-index')
        self.assertEqual(c.signals['spindle-index']['pins'],[dict(name='spindle.0.index-enable',direction='IO')])
        self.assertEqual(c.binding('pin','spindle.0.index-enable','input')['writers'],['spindle.0.index-enable'])
        with self.assertRaises(ValueError):c.binding('signal','spindle-index','output')
        self.assertEqual(c.pins['motion.count']['value'],15)
        self.assertIn('motion.enabled',c.pins)
        with self.assertRaisesRegex(ValueError,'SIDEWAYS.*bad.pin'):
            Catalogue.parse('motion bit SIDEWAYS FALSE bad.pin\n','')
    def graph(self):
        g=Graph();a=g.add('input',global_io=True);g.nodes[a]['p'].update(name='enabled',hal_binding=Catalogue.parse(PINS,SIGS).binding('pin','motion.enabled','input'))
        out=g.add('output',global_io=True);g.nodes[out]['p'].update(name='command',hal_binding=Catalogue.parse(PINS,SIGS).binding('pin','io.command','output'));g.connect(a,out,'in');return g,a,out
    def test_catalogue_parsing_aliases_binding_and_roundtrip(self):
        c=Catalogue.parse(PINS+'alias old-name\n',SIGS)
        self.assertEqual(c.pins['motion.enabled']['value'],1);self.assertEqual(c.signals['machine-on']['pins'][0]['direction'],'OUT')
        self.assertEqual(c.binding('pin','ui.ready','input')['signal'],'machine-on')
        for kind,name,role in [('signal','machine-on','output'),('pin','motion.enabled','output'),('pin','io.command','input')]:
            with self.assertRaises(ValueError):c.binding(kind,name,role)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'catalogue.json';c.save(p);self.assertEqual(Catalogue.load(p).data(),c.data())
    def test_global_output_single_driver_modules_and_load(self):
        g,a,out=self.graph();m=g.add_module('Tools');b=g.add('input',module=m)
        with self.assertRaisesRegex(ValueError,'already driven'):g.connect(b,out,'in')
        g.disconnect_node(out);g.connect(b,out,'in');self.assertEqual(g.driver(out),(b,'out'))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'global.json';g.save(p);loaded=Graph.load(p);self.assertTrue(loaded.nodes[out]['p']['global_io']);self.assertEqual(loaded.links,g.links)
    def test_global_to_global_driver_remembers_connection_module(self):
        g=Graph();a=g.add('input',global_io=True);out=g.add('output',global_io=True);m=g.add_module('Tools');g.view_module=m;g.connect(a,out,'in')
        self.assertEqual(g.driver_module(out),m)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'context.json';g.save(path);loaded=Graph.load(path);self.assertEqual(loaded.driver_module(out),m)
        g.delete_module(m);self.assertEqual(g.driver_module(out),0)
        g.disconnect_node(out);g.view_module=None;g.connect(a,out,'in');self.assertIsNone(g.driver_module(out))
    def test_export_normal_input_only_and_debug_map(self):
        g,a,out=self.graph()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'wiring.comp';g.export(path,debug=True)
            normal=path.with_suffix('.hal').read_text();test=path.with_suffix('.test.hal').read_text();source=path.read_text()
            self.assertIn('net machine-on wiring.enabled',normal);self.assertNotIn('newsig machine-on',normal)
            self.assertIn('io.command',normal);self.assertNotIn('io.command',test);self.assertIn('addf wiring.update servo-thread',test)
            self.assertIn('pin out bit debug-n1-out;',source);self.assertNotIn('debug-lpn_n1',source)
            manifest=json.loads(path.with_suffix('.hal.json').read_text());self.assertTrue(manifest['debug']);self.assertEqual(manifest['time_pin'],'wiring.update.time')
            self.assertEqual(manifest['monitors'][0]['pin'],'wiring.debug-n1-out')
            g.export(path);self.assertNotIn('debug-n',path.read_text())
    def test_direct_hal_wires_omit_unused_component_pins(self):
        g,a,out=self.graph()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'direct.comp';g.export(path)
            source=path.read_text();normal=path.with_suffix('.hal').read_text();test=path.with_suffix('.test.hal').read_text()
            self.assertIn('net machine-on io.command',normal)
            self.assertNotIn('loadrt',normal);self.assertNotIn('addf',normal)
            self.assertNotIn('pin in bit enabled;',source);self.assertNotIn('pin out bit command;',source)
            self.assertNotIn('direct.enabled',normal);self.assertNotIn('direct.command',normal)
            self.assertNotIn('io.command',test);self.assertNotIn('direct.enabled',test)
            math=g.add('math');g.set_expression(math,'x');g.connect(a,math,'x');g.export(path)
            self.assertIn('pin in bit enabled;',path.read_text());self.assertIn('net machine-on direct.enabled',path.with_suffix('.hal').read_text())
            self.assertNotIn('pin out bit command;',path.read_text())
            self.assertIn('loadrt direct',path.with_suffix('.hal').read_text())
    def test_direct_hal_requires_external_unprocessed_same_type_endpoints(self):
        from hal_bindings import direct_connections
        g,a,out=self.graph();self.assertEqual(direct_connections(g),{out:a})
        for node,key,value in ((a,'invert',True),(a,'edge','rising'),(a,'debounce',1),(out,'invert',True),(out,'on_delay',1),(out,'off_delay',1),(out,'dtype','s32'),(out,'hal_binding',None),(a,'hal_binding',None)):
            old=g.nodes[node]['p'][key];g.nodes[node]['p'][key]=value
            self.assertEqual(direct_connections(g),{},(node,key));g.nodes[node]['p'][key]=old
        g.nodes[out]['p']['hal_binding']=dict(kind='signal',name='other-net',dtype='bit',writers=[])
        self.assertEqual(direct_connections(g),{})
    def test_direct_hal_free_source_uses_existing_destination_signal_and_fanout(self):
        g=Graph();catalogue=Catalogue.parse(PINS,SIGS+'float 0 position-net\n')
        a=g.add('input');g.nodes[a]['p'].update(dtype='float',hal_binding=catalogue.binding('pin','io.position','input'))
        b=g.add('output');g.nodes[b]['p'].update(dtype='float',hal_binding=dict(kind='pin',name='ui.position',dtype='float',direction='IN',signal='',writers=[]));g.connect(a,b,'in')
        c=g.add('output');g.nodes[c]['p'].update(dtype='float',hal_binding=catalogue.binding('signal','position-net','output'));g.connect(a,c,'in')
        plan=wiring_plan(g,'direct');commands=[s['command'] for s in plan]
        self.assertIn(['net','position-net','io.position'],commands);self.assertIn(['net','position-net','ui.position'],commands)
        self.assertFalse(any(command[0]=='newsig' for command in commands))
        self.assertIn(['unlinkp','ui.position'],[undo for step in plan for undo in step['undo']])
        self.assertFalse(any(undo[0]=='delsig' for step in plan for undo in step['undo']))
    def test_processed_hal_endpoints_export_through_component(self):
        for endpoint,key,value in (('input','edge','rising'),('input','edge','falling'),('input','edge','both'),('input','invert',True),('input','debounce',1),('output','invert',True),('output','on_delay',1),('output','off_delay',1)):
            with self.subTest(endpoint=endpoint,key=key,value=value),tempfile.TemporaryDirectory() as tmp:
                g,a,out=self.graph();g.nodes[a if endpoint=='input' else out]['p'][key]=value
                path=Path(tmp)/'processed.comp';g.export(path)
                source=path.read_text();hal=path.with_suffix('.hal').read_text()
                self.assertIn('pin in bit enabled;',source);self.assertIn('pin out bit command;',source)
                self.assertIn('loadrt processed',hal);self.assertIn('addf processed.update servo-thread',hal)
                self.assertIn('net machine-on processed.enabled',hal)
                self.assertIn('processed.command',hal);self.assertNotIn('net machine-on io.command',hal)
    def test_runtime_plan_rechecks_machine_and_rolls_back_on_failure(self):
        g,a,out=self.graph();path=Path('/tmp/live_test.comp');manifest=dict(source=str(path))
        calls=[]
        def run(*args):
            calls.append(args)
            if args[0]=='addf':raise RuntimeError('missing thread')
        session=LiveSession(g,'live_test',manifest,Catalogue.parse(PINS,SIGS),run)
        with self.assertRaises(RuntimeError):session.start()
        self.assertEqual(calls[-2:], [('unlinkp','live-test.enabled'),('unloadrt','live_test')])
        self.assertFalse(any('io.command' in args for args in calls));self.assertFalse(any(args[0]=='delsig' for args in calls))
        with self.assertRaisesRegex(ValueError,'not found'):LiveSession(g,'live_test',manifest,Catalogue(),run)
    def test_input_only_samples_include_hal_time_and_block_bound_input_write(self):
        g,a,out=self.graph();unbound=g.add('input');g.nodes[unbound]['p'].update(name='manual',dtype='s32')
        manifest=dict(source='/tmp/live.comp',monitors=monitor_map(g,'live'),time_pin='live.update.time',tmax_param='live.update.tmax',runtime_pin='live.lpn-debug-runtime-ns',max_runtime_pin='live.lpn-debug-max-runtime-ns')
        calls=[];session=LiveSession(g,'live',manifest,Catalogue.parse(PINS,SIGS),lambda *args:calls.append(args))
        values=session.sample(lambda pin:2000)
        self.assertEqual(values['time_ns'],2000);self.assertEqual(values['hal_time'],2000)
        with self.assertRaises(ValueError):session.set_input(a,1)
        with self.assertRaises(ValueError):session.set_input(out,1)
        session.set_input(unbound,-12.9);self.assertEqual(calls,[('setp','live.manual','-12')])
        constant=g.add('constant');g.nodes[constant]['p'].update(name='gain_limit',dtype='s32',value=12.9)
        session.set_input(constant,-7.9);self.assertEqual(calls[-1],('setp','live.gain-limit','-7'))
        plan=wiring_plan(g,'live',inputs_only=True);self.assertIn(['setp','live.gain-limit','12'],[step['command'] for step in plan])
    def test_generated_debug_pins_and_measured_runtime_match_simulation(self):
        g=Graph();a=g.add('input');g.nodes[a]['p'].update(name='source',dtype='s32',value=-12)
        fifo=g.add('fifo');g.connect(a,fifo,'in');math=g.add('math');g.set_expression(math,'x * 2');g.connect(fifo,math,'x','last')
        condition=g.add('condition');g.set_expression(condition,'x > 0');g.connect(math,condition,'x')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'debug.comp';g.export(path,debug=True)
            monitors=monitor_map(g,'debug');declarations=['#include <stdint.h>','static long period=1000000;static int source;','static long long rtapi_get_time(void){static long long time=0;time+=2500;return time;}']
            for monitor in monitors:declarations.append('static double '+monitor['suffix'].replace('-','_')+';')
            declarations += ['static unsigned lpn_debug_id0,lpn_debug_id1,lpn_debug_id2,lpn_debug_id3;','static double lpn_debug_runtime_ns,lpn_debug_max_runtime_ns;']
            body=path.read_text().split(';;\n',1)[1].replace('FUNCTION(update)','void update(void)')
            wrapper='void sample(int value,double *result){source=value;update();'+''.join(f'result[{j}]={m["suffix"].replace("-","_")};' for j,m in enumerate(monitors))+f'result[{len(monitors)}]=lpn_debug_runtime_ns;'+'}'
            (root/'debug.c').write_text('\n'.join(declarations)+'\n'+body+wrapper)
            subprocess.run(['cc','-shared','-fPIC',str(root/'debug.c'),'-lm','-o',str(root/'debug.so')],check=True)
            lib=ctypes.CDLL(str(root/'debug.so'));lib.sample.argtypes=[ctypes.c_int,ctypes.POINTER(ctypes.c_double)]
            for value in (-12,4,8):
                g.nodes[a]['p']['value']=value;g.step(.001);actual=(ctypes.c_double*(len(monitors)+1))();lib.sample(value,actual)
                self.assertEqual(list(actual)[:-1],[g.value(m['node'],m['port']) for m in monitors]);self.assertEqual(actual[len(monitors)],2500)
    def test_live_worker_initializes_hal_before_lookup_and_unloads_own_session(self):
        import io,types
        from unittest.mock import patch
        import live_hal
        g,a,out=self.graph();calls=[];attached=[False]
        class Observer:
            def ready(self):attached[0]=True;calls.append(('observer-ready',))
            def exit(self):calls.append(('observer-exit',))
        def exists(name):
            if not attached[0]:raise RuntimeError('Cannot call before creating component')
            return False
        class Child:
            def __init__(self,attempt):self.attempt=attempt;self.returncode=0 if attempt==3 else 1
            def communicate(self,timeout,input=None):
                if self.attempt==1:return ('','Permission denied')
                if self.attempt==2:return ('','sudo: a password is required')
                self_test.assertEqual(input,'test-only-secret\n')
                return ('compiled test-only-secret','')
        self_test=self;attempts=[]
        def popen(argv,**kwargs):
            self.assertEqual(kwargs['cwd'],str(root))
            self.assertEqual(kwargs['env']['LC_ALL'],'C')
            attempts.append(argv);return Child(len(attempts))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);project=root/'project.json';component=root/'nne_live_1000.comp';g.save(project)
            def read(pin):
                manifest=json.loads(component.with_suffix('.hal.json').read_text());index=int(pin[-1]);return int(manifest['fingerprint'][index*8:index*8+8],16)
            hal=types.SimpleNamespace(component=lambda name:Observer(),component_exists=exists,get_value=read)
            output=io.StringIO()
            def command(*args):calls.append(args);return ''
            with patch.dict('os.environ',{'PLC_STATE_DIR':str(root)}),patch.dict('sys.modules',{'hal':hal}),patch('sys.argv',['live_hal.py',str(project),str(component)]),patch('signal.signal'),patch.object(live_hal.Catalogue,'discover',return_value=Catalogue.parse(PINS,SIGS)),patch.object(live_hal,'command',side_effect=command),patch('subprocess.Popen',side_effect=popen),patch('select.select',return_value=([0],[],[])),patch('os.read',side_effect=[b'{"cmd":"authorize","password":"test-only-secret"}\n',b'{"cmd":"stop"}\n']),patch('sys.stdout',output):
                live_hal.main()
            events=[json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual([e['event'] for e in events],['log','authorization','ready','stopped'])
            log=(root/'logs'/'live-hal.log').read_text()
            self.assertIn('Build/install exit=0',log);self.assertIn('HAL command:',log)
            self.assertIn('[redacted]',log);self.assertNotIn('test-only-secret',log)
            self.assertNotIn('test-only-secret',output.getvalue())
        self.assertFalse(any('io.command' in call for call in calls));self.assertIn(('addf','nne-live-1000.update','servo-thread'),calls)
        self.assertEqual(calls[-3:],[('unlinkp','nne-live-1000.enabled'),('unloadrt','nne_live_1000'),('observer-exit',)])
    def test_conflicting_project_output_bindings_rejected(self):
        g,a,out=self.graph();second=g.add('output');g.nodes[second]['p']['hal_binding']=dict(g.nodes[out]['p']['hal_binding'])
        with self.assertRaisesRegex(ValueError,'Multiple project outputs'):g.validate()
    def test_fingerprint_ignores_layout_and_input_test_value(self):
        g,a,out=self.graph();before=fingerprint(g);g.nodes[a]['p']['value']=1;g.nodes[a]['pos']=[200,300];g.rename_module(0,'Changed')
        self.assertEqual(fingerprint(g),before);g.nodes[out]['p']['on_delay']=20;self.assertNotEqual(fingerprint(g),before)
