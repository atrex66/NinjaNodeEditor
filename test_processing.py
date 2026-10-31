"""Behavior, compiled C parity and synchronous feedback tests."""
import ctypes,random,re,subprocess,tempfile,unittest
from pathlib import Path
import processing
from model import Graph

class Compiled:
 def __init__(self,g,folder,debug=False):
  path=Path(folder)/'proc_check.comp';g.export(path,debug=debug)
  header,body=path.read_text().split(';;\n',1)
  pins=re.findall(r'^pin (in|out) (bit|s32|u32|float) ([\w-]+)',header,re.M)
  self.inputs=[(n,t) for direction,t,n in pins if direction=='in'];self.outputs=[(n,t) for direction,t,n in pins if direction=='out']
  source='#include <stdint.h>\nlong period;\nlong long rtapi_get_time(void){return 0;}\n'
  for direction,t,name in pins:
   n=name.replace('-','_');typ={'float':'double','bit':'int','s32':'int32_t','u32':'uint32_t'}[t]
   source+=f'{typ} storage_{n};\n#define {n} (0+storage_{n})\n'
   if direction=='out':source+=f'#define {n}_set(x) (storage_{n}=(x))\n'
  source+=body.replace('FUNCTION(update)','void update(void)')
  source+='\nvoid nne_test_tick(double *in,double *out,long ns){period=ns;\n'
  for j,(name,_) in enumerate(self.inputs):source+=f'storage_{name.replace("-","_")}=in[{j}];\n'
  source+='update();\n'
  for j,(name,_) in enumerate(self.outputs):source+=f'out[{j}]=storage_{name.replace("-","_")};\n'
  source+='}\n';path.with_suffix('.c').write_text(source)
  subprocess.run(['cc','-shared','-fPIC','-O2','-std=c11','-Werror=implicit-function-declaration',str(path.with_suffix('.c')),'-lm','-o',str(path.with_suffix('.so'))],check=True,capture_output=True)
  self.lib=ctypes.CDLL(str(path.with_suffix('.so')));self.lib.nne_test_tick.argtypes=[ctypes.POINTER(ctypes.c_double),ctypes.POINTER(ctypes.c_double),ctypes.c_long]
 def sample(self,inputs,dt):
  a=(ctypes.c_double*len(self.inputs))(*(inputs[n] for n,t in self.inputs));b=(ctypes.c_double*len(self.outputs))()
  self.lib.nne_test_tick(a,b,round(dt*1e9));return dict(zip((n for n,t in self.outputs),b))

def graph_for(kind,**params):
 g=Graph();node=g.add(kind);g.nodes[node]['p'].update(params);sources={};targets={}
 for j,port in enumerate(g.inputs(node)):
  a=g.add('input');g.nodes[a]['p'].update(name='source-'+str(j),dtype=g.input_type(node,port));g.connect(a,node,port);sources[port]=a
 for j,port in enumerate(g.outputs(node)):
  a=g.add('output');g.nodes[a]['p'].update(name='result-'+str(j),dtype=g.dtype(node,port));g.connect(node,a,'in',port);targets[port]=a
 return g,node,sources,targets

class ProcessingTests(unittest.TestCase):
 def test_latch_and_hysteresis(self):
  for priority,result in [('set',1),('reset',0)]:
   p=processing.defaults('latch');p['priority']=priority;s={}
   self.assertEqual(processing.step('latch',p,s,{'set':1,'reset':1},.001),result)
   self.assertEqual(processing.step('latch',p,s,{},.001),result)
  p=processing.defaults('hysteresis');s={}
  for x,out in [(0,0),(1,1),(.5,1),(0,0),(.5,0)]:self.assertEqual(processing.step('hysteresis',p,s,{'in':x},.001),out)
 def test_watchdog_timeout_and_recovery(self):
  p=processing.defaults('watchdog');p['timeout_ms']=3;s={}
  processing.step('watchdog',p,s,{'trigger':1},.001)
  for _ in range(3):processing.step('watchdog',p,s,{'trigger':1},.001)
  self.assertEqual(s['ports']['fault'],1)
  processing.step('watchdog',p,s,{'trigger':0},.001);self.assertEqual(s['ports']['fault'],1)
  processing.step('watchdog',p,s,{'reset':1},.001);self.assertEqual(s['ports']['healthy'],0);self.assertEqual(s['ports']['fault'],0)
  processing.step('watchdog',p,s,{'enable':0},.1);self.assertEqual(s['ports']['elapsed-ms'],0)
  p['latched']=False;processing.step('watchdog',p,s,{},.1);self.assertEqual(s['ports']['fault'],1)
  processing.step('watchdog',p,s,{'trigger':1},.001);self.assertEqual(s['ports']['healthy'],1)
 def test_ramp_asymmetric_reset_hold(self):
  p=processing.defaults('ramp');p.update(rise_rate=2,fall_rate=1);s={}
  self.assertAlmostEqual(processing.step('ramp',p,s,{'in':10},.1),.2)
  self.assertAlmostEqual(processing.step('ramp',p,s,{'in':-10},.1),.1)
  self.assertAlmostEqual(processing.step('ramp',p,s,{'in':10,'enable':0},1),.1)
  self.assertEqual(processing.step('ramp',p,s,{'reset':1},.1),0)
  p['rise_rate']=0;self.assertEqual(processing.step('ramp',p,s,{'in':10},1),0)
 def test_filter_startup_reset_and_outliers(self):
  p=processing.defaults('filter');p.update(filter_mode='average',window=3);s={}
  self.assertEqual([processing.step('filter',p,s,{'in':x},.001) for x in (3,6,9,12)],[3,4.5,6,9])
  p['filter_mode']='median';s={}
  self.assertEqual([processing.step('filter',p,s,{'in':x},.001) for x in (1,100,2)],[1,50.5,2])
  self.assertEqual(processing.step('filter',p,s,{'reset':1},.001),0)
  self.assertEqual(processing.step('filter',p,s,{'in':7},.001),7)
  p.update(filter_mode='lowpass',tau_ms=100);s={};self.assertAlmostEqual(processing.step('filter',p,s,{'in':10},.1),5)
 def test_sequencer_inactive_edges_timeout_and_reset(self):
  p=processing.defaults('sequencer');p['states'][1]['timeout_ms']=2;s={}
  self.assertEqual(processing.step('sequencer',p,s,{'advance0':1,'advance1':1},.001),1)
  processing.step('sequencer',p,s,{'advance1':1},.001);self.assertEqual(s['q'],1)
  processing.step('sequencer',p,s,{'advance1':0},.001);self.assertTrue(s['fault'])
  processing.step('sequencer',p,s,{'advance1':1},.001);self.assertEqual(s['q'],1)
  processing.step('sequencer',p,s,{'reset':1},.001);self.assertEqual(s['q'],0);self.assertFalse(s['fault'])
 def test_validation(self):
  for kind,key,val in [('filter','window',0),('filter','window',64),('ramp','rise_rate',-1),('watchdog','timeout_ms',0),('hysteresis','high',-1),('sequencer','states',[]),('latch','priority','none')]:
   g=Graph();i=g.add(kind);g.nodes[i]['p'][key]=val
   with self.subTest(kind=kind,key=key),self.assertRaises(ValueError):g.validate()
 def test_generated_c_matches_simulation_all_ports(self):
  variants=[('latch',{'priority':v}) for v in ('set','reset')]+[('hysteresis',{}),('ramp',{'rise_rate':32,'fall_rate':13})]+[('filter',{'filter_mode':v,'window':7}) for v in ('lowpass','average','median')]+[('watchdog',{'watch_mode':v,'latched':l,'timeout_ms':4}) for v in ('rising','both') for l in (False,True)]+[('sequencer',{})]
  for debug in (False,True):
   for kind,params in variants:
    with self.subTest(kind=kind,params=params,debug=debug),tempfile.TemporaryDirectory() as folder:
     g,node,sources,targets=graph_for(kind,**params);c=Compiled(g,folder,debug);rng=random.Random(733)
     for tick in range(180):
      dt=rng.choice([.001,.002,.0005,0]);values={}
      for port,i in sources.items():
       x=rng.uniform(-10,10) if g.dtype(i)=='float' else int(rng.random() < (.04 if port=='reset' else .8 if port=='enable' else .2))
       g.nodes[i]['p']['value']=x;values[g.nodes[i]['p']['name']]=x
      g.step(dt);result=c.sample(values,dt)
      for port,i in targets.items():self.assertAlmostEqual(g.values[i],result[g.nodes[i]['p']['name']],places=9,msg=f'{kind} {port} tick{tick}')
      if debug:
       for port in g.outputs(node):self.assertAlmostEqual(g.value(node,port),result[f'debug-n{node}-{port}'],places=9)
 def test_memory_previous_cycle_shared_across_modules_and_save(self):
  g=Graph();writer,reader=g.add_memory_pair();m=g.add('math');g.set_expression(m,'x + 1');g.connect(reader,m,'x');g.connect(m,writer,'in')
  other=g.add_module('Other');reader2=g.add('memory_read',module=other)
  target=g.add('output');g.nodes[target]['p'].update(name='value',dtype='float');g.connect(reader2,target,'in')
  with tempfile.TemporaryDirectory() as folder:
   c=Compiled(g,folder,True)
   for tick in range(20):
    g.step(.001);self.assertEqual(g.value(reader),tick);self.assertEqual(g.value(reader2),tick);self.assertEqual(c.sample({},.001)['value'],tick)
   path=Path(folder)/'project.json';g.save(path);loaded=Graph.load(path);loaded.step(.001);self.assertEqual(loaded.value(reader),0)
  duplicate=g.add('memory_write')
  with self.assertRaisesRegex(ValueError,'multiple writers'):g.validate()
  del g.nodes[duplicate];g.nodes[reader2]['p']['dtype']='bit'
  with self.assertRaisesRegex(ValueError,'types differ'):g.validate()
 def test_ordinary_cycles_rejected(self):
  g=Graph();a=g.add('invert');b=g.add('invert');g.connect(a,b,'in')
  with self.assertRaises(ValueError):g.connect(b,a,'in')

class ProcessingUITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import os,sys
  os.environ['QT_QPA_PLATFORM']='offscreen';sys.argv=[sys.argv[0],'--windowed','--no-restore']
  from PySide6.QtWidgets import QApplication
  cls.app=QApplication.instance() or QApplication([])
 def test_every_node_property_panel_and_memory_action(self):
  import os
  from unittest.mock import patch
  from app import Editor
  from PySide6.QtWidgets import QPushButton
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,PLC_STATE_DIR=folder):
   w=Editor();w.graph=Graph();w.rebuild();w.resize(800,600);w.show()
   try:
    for kind in processing.KINDS:
     if kind.startswith('memory_'):continue
     w.add(kind);self.app.processEvents();i=max(w.graph.nodes)
     self.assertEqual(w.graph.nodes[i]['kind'],kind)
     self.assertIsNotNone(w.scroll.widget())
    w.add_memory_pair();self.app.processEvents()
    self.assertEqual(len(w.graph.memory_pairs()),1)
    self.assertIsNotNone(w.scroll.widget().findChild(QPushButton,'edit-memory'))
    w.graph.validate();w.grab()
   finally:w.shutdown();w.close()

class ProcessingBoundaryTests(unittest.TestCase):
 def test_memory_commit_after_early_writer_and_integer_conversion(self):
  g=Graph();source=g.add('input');g.nodes[source]['p'].update(name='sample',dtype='float')
  writer,reader=g.add_memory_pair()
  for i in (writer,reader):g.nodes[i]['p']['dtype']='s32'
  g.nodes[reader]['p']['initial']=7
  g.connect(source,writer,'in');out=g.add('output');g.nodes[out]['p'].update(name='stored',dtype='s32');g.connect(reader,out,'in')
  with tempfile.TemporaryDirectory() as folder:
   c=Compiled(g,folder)
   for x,expected in [(4.9,7),(-2.8,4),(1e12,-2),(0,2147483647)]:
    g.nodes[source]['p']['value']=x;g.step(.001)
    self.assertEqual(g.value(reader),expected);self.assertEqual(c.sample({'sample':x},.001)['stored'],expected)
 def test_filter_maximum_window_and_parameter_reference(self):
  for mode in ('median','average','lowpass'):
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
    g,node,sources,targets=graph_for('filter',filter_mode=mode,window=63)
    const=g.add('constant');g.nodes[const]['p'].update(name='filter_tau',value=25);g.nodes[node]['p']['tau_ms']='@filter_tau'
    c=Compiled(g,folder)
    for tick in range(130):
     values={'filter-tau':25.0}
     for port,i in sources.items():
      x=(130-tick if tick%9 else 1000) if port=='in' else int(port=='enable')
      g.nodes[i]['p']['value']=x;values[g.nodes[i]['p']['name']]=x
     g.step(.001);result=c.sample(values,.001)
     self.assertAlmostEqual(g.value(node),result['result-0'],places=8)
 def test_sequencer_branch_timeout_tie_and_disabled_edge_consumption(self):
  p=processing.defaults('sequencer');p['states'][0].update(next=2,timeout_ms=2);s={}
  processing.step('sequencer',p,s,{'advance0':1,'enable':0},.1)
  processing.step('sequencer',p,s,{'advance0':1},.001);self.assertEqual(s['q'],0)
  processing.step('sequencer',p,s,{'advance0':0},.001);self.assertTrue(s['fault'])
  processing.step('sequencer',p,s,{'reset':1},.001)
  processing.step('sequencer',p,s,{'advance0':1},.001);self.assertEqual(s['q'],2);self.assertEqual(s['ports']['done'],1)
  s={};processing.step('sequencer',p,s,{},.001)
  processing.step('sequencer',p,s,{'advance0':1},.001);self.assertEqual(s['q'],0);self.assertTrue(s['fault'])
