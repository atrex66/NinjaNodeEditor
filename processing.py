"""Bounded, stateful processing blocks. No Qt or HAL dependency."""
import math
import re
from copy import deepcopy

DEFAULTS={
 'latch':dict(dtype='bit',initial=False,priority='reset'),
 'hysteresis':dict(dtype='bit',initial=False,low=0.0,high=1.0),
 'watchdog':dict(dtype='bit',timeout_ms=1000.0,watch_mode='both',latched=True,enabled=True),
 'ramp':dict(dtype='float',initial=0.0,rise_rate=10.0,fall_rate=10.0,enabled=True),
 'filter':dict(dtype='float',initial=0.0,filter_mode='lowpass',tau_ms=100.0,window=5,enabled=True),
 'sequencer':dict(dtype='u32',states=[dict(name='Wait',next=1,timeout_ms=0.0),dict(name='Work',next=2,timeout_ms=5000.0),dict(name='Done',next=2,timeout_ms=0.0)],enabled=True),
 'memory_read':dict(dtype='float',initial=0.0,memory='memory1'),
 'memory_write':dict(dtype='float',memory='memory1'),
}
# These keys may reference named constants. Buffer sizes and state tables are structural.
NUMERIC=('low','high','timeout_ms','rise_rate','fall_rate','tau_ms')
KINDS=tuple(DEFAULTS)

def defaults(kind):return deepcopy(DEFAULTS[kind])
def inputs(kind,p):
 if kind=='sequencer':return tuple('advance'+str(i) for i in range(len(p['states'])))+('enable','reset')
 return {'latch':('set','reset'),'hysteresis':('in','reset'),'watchdog':('trigger','enable','reset'),'ramp':('in','enable','reset'),'filter':('in','enable','reset'),'memory_read':(),'memory_write':('in',)}[kind]
def outputs(kind,p):
 if kind=='sequencer':return ('state','done','fault')+tuple('active'+str(i) for i in range(len(p['states'])))
 return {'latch':('out','not'),'hysteresis':('out',),'watchdog':('healthy','fault','elapsed-ms'),'ramp':('out','reached'),'filter':('out',),'memory_read':('out',),'memory_write':()}[kind]
def dtype(kind,p,port=None):
 if kind=='watchdog':return 'float' if port=='elapsed-ms' else 'bit'
 if kind=='sequencer':return 'u32' if port in (None,'state') else 'bit'
 if kind=='ramp':return 'bit' if port=='reached' else 'float'
 return p['dtype']
def input_type(kind,p,port):
 if kind=='memory_write':return p['dtype']
 return 'float' if port=='in' else 'bit'

def validate(kind,p):
 def number(key,lo=-1e300,hi=1e300):
  v=p.get(key)
  if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Invalid processing parameter: '+key)
 for key in ('enabled','latched'):
  if key in p and type(p[key]) is not bool:raise ValueError('Invalid switch: '+key)
 if kind not in ('memory_read','memory_write') and p['dtype']!=DEFAULTS[kind]['dtype']:raise ValueError('Invalid processing node type')
 if kind=='latch' and p.get('priority') not in ('set','reset'):raise ValueError('Invalid latch priority')
 if kind in ('latch','hysteresis') and p.get('initial') not in (False,True,0,1):raise ValueError('Initial state must be 0 or 1')
 if kind=='hysteresis':
  number('low');number('high')
  if p['low']>=p['high']:raise ValueError('Hysteresis low must be below high')
 if kind=='watchdog':
  number('timeout_ms',0.001)
  if p.get('watch_mode') not in ('rising','both'):raise ValueError('Invalid watchdog mode')
 if kind=='ramp':number('rise_rate',0);number('fall_rate',0);number('initial')
 if kind=='filter':
  number('tau_ms',0);number('initial')
  if p.get('filter_mode') not in ('lowpass','average','median'):raise ValueError('Invalid filter mode')
  if type(p.get('window')) is not int or not 1<=p['window']<=63:raise ValueError('Filter window must be 1..63')
 if kind=='sequencer':
  states=p.get('states')
  if not isinstance(states,list) or not 2<=len(states)<=16:raise ValueError('State count must be 2..16')
  for s in states:
   if not isinstance(s,dict) or not isinstance(s.get('name'),str) or not 1<=len(s['name'])<=40:raise ValueError('Invalid state name')
   if type(s.get('next')) is not int or not 0<=s['next']<len(states):raise ValueError('Invalid next state')
   t=s.get('timeout_ms')
   if type(t) not in (int,float) or not math.isfinite(t) or not 0<=t<=1e12:raise ValueError('Invalid state timeout')
 if kind in ('memory_read','memory_write'):
  if not isinstance(p.get('memory'),str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}',p['memory']):raise ValueError('Invalid memory name')


def step(kind,p,s,e,dt):
 dt=dt if math.isfinite(dt) and dt>0 else 0.0
 reset=bool(e.get('reset',0));enabled=bool(e.get('enable',p.get('enabled',True)))
 x=float(e.get('in',0));x=x if math.isfinite(x) else p.get('initial',0.0)
 if kind=='latch':
  q=s.get('q',bool(p['initial']));set_=bool(e.get('set',0))
  q=(set_ or (q and not reset)) if p['priority']=='set' else (not reset and (set_ or q))
  out=dict(out=float(q),**{'not':float(not q)})
 elif kind=='hysteresis':
  q=s.get('q',bool(p['initial']))
  if reset:q=bool(p['initial'])
  elif x>=p['high']:q=True
  elif x<=p['low']:q=False
  out=dict(out=float(q))
 elif kind=='watchdog':
  trigger=bool(e.get('trigger',0));prev=s.get('prev',False)
  pulse=trigger!=prev if p['watch_mode']=='both' else trigger and not prev
  s['prev']=trigger;age=s.get('age',0.0);fault=s.get('fault',False)
  if reset or not enabled:age=0.;fault=False
  elif pulse:
   age=0.
   if not p['latched']:fault=False
  else:age=min(p['timeout_ms'],age+dt*1000)
  if enabled and not reset and age+1e-9>=p['timeout_ms']:fault=True
  s.update(age=age,fault=fault)
  out={'healthy':float(enabled and not reset and not fault),'fault':float(fault),'elapsed-ms':age}
 elif kind=='ramp':
  q=s.get('q',float(p['initial']))
  if reset:q=float(p['initial'])
  elif enabled:q=min(x,q+p['rise_rate']*dt) if x>=q else max(x,q-p['fall_rate']*dt)
  if not math.isfinite(q):q=float(p['initial'])
  out=dict(out=q,reached=float(q==x))
 elif kind=='filter':
  q=s.get('q',float(p['initial']))
  if reset:s['samples']=[];q=float(p['initial'])
  elif enabled:
   if p['filter_mode']=='lowpass':
    alpha=dt/(p['tau_ms']*.001+dt) if dt else 0.
    q=(1-alpha)*q+alpha*x
   else:
    samples=(s.get('samples',[])+[x])[-p['window']:];s['samples']=samples
    if p['filter_mode']=='average':q=sum(v/len(samples) for v in samples)
    else:
     ordered=sorted(samples);n=len(ordered);q=ordered[n//2] if n%2 else ordered[n//2-1]*.5+ordered[n//2]*.5
   if not math.isfinite(q):q=float(p['initial'])
  out=dict(out=q)
 elif kind=='sequencer':
  states=p['states'];q=s.get('q',0);age=s.get('age',0.);fault=s.get('fault',False)
  levels=[bool(e.get('advance'+str(i),0)) for i in range(len(states))]
  edges=[v and not old for v,old in zip(levels,s.get('levels',[False]*len(states)))];s['levels']=levels
  if reset:q=0;age=0.;fault=False
  elif enabled and not fault and q!=len(states)-1:
   age+=dt*1000;t=states[q]['timeout_ms']
   if t>0 and age+1e-9>=t:fault=True
   elif edges[q]:q=states[q]['next'];age=0.
  s.update(age=age,fault=fault)
  out=dict(state=float(q),done=float(q==len(states)-1 and not fault),fault=float(fault))
  out.update({'active'+str(i):float(q==i and not fault) for i in range(len(states))})
 else:raise ValueError(kind)
 if kind in ('latch','hysteresis','ramp','filter','sequencer'):s['q']=q
 s['ports']=out
 return next(iter(out.values()))


def c_port(i,port):return 'lpn_proc_'+str(i)+'_'+port.replace('-','_')

def c_body(i,kind,p,env,cv):
 """Generate bounded C with persistent per-node storage and no RT allocation."""
 prefix=f'lpn_p{i}_';lines=[]
 def emit(code):lines.append('  '+code.replace('$',prefix))
 def inp(name,default='0'):return env.get(name,default)
 enable=inp('enable',cv(p.get('enabled',True)));reset=inp('reset')
 emit(f'int $reset=!!({reset}),$enable=!!({enable});')
 if kind in ('latch','hysteresis','ramp','filter','sequencer'):
  initial='0' if kind=='sequencer' else cv(p['initial'])
  emit(f'static int $initialized=0; static double $q=0; if(!$initialized) {{$q={initial};$initialized=1;}}')
 if kind in ('hysteresis','ramp','filter'):
  emit(f'double $x={inp("in")}; if(!isfinite($x)) $x={cv(p["initial"])};')
 emit('double $dt=isfinite(dt) && dt>0?dt:0;')
 values={}
 if kind=='latch':
  emit(f'int $set=!!({inp("set")});')
  emit('$q=$set || ($q && !$reset);' if p['priority']=='set' else '$q=!$reset && ($set || $q);')
  values={'out':'$q','not':'!$q'}
 elif kind=='hysteresis':
  emit(f'if($reset)$q=!!({cv(p["initial"])}); else if($x>={cv(p["high"])})$q=1; else if($x<={cv(p["low"])})$q=0;')
  values={'out':'$q'}
 elif kind=='watchdog':
  emit(f'static int $prev=0,$fault=0; static double $age=0; int $trigger=!!({inp("trigger")});')
  emit('int $pulse=$trigger!=$prev;' if p['watch_mode']=='both' else 'int $pulse=$trigger && !$prev;')
  emit(f'$prev=$trigger; double $limit=fmax(0.001,{cv(p["timeout_ms"])});')
  emit('if($reset || !$enable){$age=0;$fault=0;} else if($pulse){$age=0;'+('' if p['latched'] else '$fault=0;')+'}else $age=fmin($limit,$age+$dt*1000);')
  emit('if($enable && !$reset && $age+1e-9>=$limit)$fault=1;')
  values={'healthy':'$enable && !$reset && !$fault','fault':'$fault','elapsed-ms':'$age'}
 elif kind=='ramp':
  emit(f'if($reset)$q={cv(p["initial"])};else if($enable)$q=$x>=$q?fmin($x,$q+fmax(0,{cv(p["rise_rate"])})*$dt):fmax($x,$q-fmax(0,{cv(p["fall_rate"])})*$dt);')
  emit(f'if(!isfinite($q))$q={cv(p["initial"])};')
  values={'out':'$q','reached':'$q==$x'}
 elif kind=='filter':
  n=p['window']
  emit(f'static double $samples[{n}]={{0}};static int $count=0,$index=0;')
  emit(f'if($reset){{$q={cv(p["initial"])};$count=0;$index=0;}}else if($enable){{')
  if p['filter_mode']=='lowpass':
   emit(f'double $alpha=$dt?$dt/(fmax(0,{cv(p["tau_ms"])})*.001+$dt):0;$q=(1-$alpha)*$q+$alpha*$x;')
  else:
   emit(f'$samples[$index]=$x;$index=($index+1)%{n};if($count<{n})$count++;')
   if p['filter_mode']=='average':emit('$q=0;for(int $j=0;$j<$count;$j++)$q+=$samples[$j]/$count;')
   else:
    emit(f'double $sorted[{n}];for(int $j=0;$j<$count;$j++){{$sorted[$j]=$samples[$j];for(int $k=$j;$k>0 && $sorted[$k]<$sorted[$k-1];$k--){{double $t=$sorted[$k];$sorted[$k]=$sorted[$k-1];$sorted[$k-1]=$t;}}}}')
    emit('$q=$count%2?$sorted[$count/2]:.5*$sorted[$count/2-1]+.5*$sorted[$count/2];')
  emit(f'if(!isfinite($q))$q={cv(p["initial"])};}}')
  values={'out':'$q'}
 elif kind=='sequencer':
  n=len(p['states']);limits=','.join(repr(float(s['timeout_ms'])) for s in p['states']);targets=','.join(str(s['next']) for s in p['states'])
  emit(f'static int $previous[{n}]={{0}},$fault=0;static double $age=0;const double $limits[{n}]={{{limits}}};const int $targets[{n}]={{{targets}}};int $edges[{n}];')
  for j in range(n):emit(f'int $level{j}=!!({inp("advance"+str(j))});$edges[{j}]=$level{j} && !$previous[{j}];$previous[{j}]=$level{j};')
  emit(f'if($reset){{$q=0;$age=0;$fault=0;}}else if($enable && !$fault && (int)$q!={n-1}){{$age+=$dt*1000;int $state=(int)$q;double $limit=$limits[$state];if($limit>0 && $age+1e-9>=$limit)$fault=1;else if($edges[$state]){{$q=$targets[$state];$age=0;}}}}')
  values={'state':'$q','done':f'(int)$q=={n-1} && !$fault','fault':'$fault'}
  values.update({'active'+str(j):f'(int)$q=={j} && !$fault' for j in range(n)})
 for port,source in values.items():emit(f'double {c_port(i,port)}=({source});')
 emit(f'n{i}={c_port(i,next(iter(values)))};')
 return lines
