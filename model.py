"""Finite dataflow model shared by the simulator and LinuxCNC .comp exporter."""
import processing
import ast
from copy import deepcopy
from pathlib import Path
import json
import math
import re
from logger_runtime import validate_config, SimulationLogger

TYPES = ('bit', 'float', 's32', 'u32')
DEFAULTS = dict(name='', dtype='bit', invert=False, edge='level', debounce=0.0,
                on_delay=0.0, off_delay=0.0, initial=False, value=0.0,
                expression='x',global_io=False,hal_binding=None)

# name: (argument count, Python implementation, C implementation)
FUNCTIONS = {
    'abs': (1, abs, 'fabs'), 'min': (2, min, 'fmin'), 'max': (2, max, 'fmax'),
    'clamp': (3, lambda x,l,h:min(max(x,l),h), 'lpn_clamp'),
    'pow': (2, math.pow, 'pow'), 'sqrt': (1, math.sqrt, 'sqrt'),
    'sin': (1, math.sin, 'sin'), 'cos': (1, math.cos, 'cos'),
    'tan': (1, math.tan, 'tan'), 'asin': (1, math.asin, 'asin'),
    'acos': (1, math.acos, 'acos'), 'atan': (1, math.atan, 'atan'),
    'atan2': (2, math.atan2, 'atan2'), 'log': (1, math.log, 'log'),
    'log10': (1, math.log10, 'log10'), 'exp': (1, math.exp, 'exp'),
    'floor': (1, math.floor, 'floor'), 'ceil': (1, math.ceil, 'ceil'),
}
CONSTANTS = {'pi': math.pi, 'e': math.e}
REFERENCE = re.compile(r'@([a-z][a-z0-9_]*)')
NUMERIC_PARAMETERS = ('value','initial','debounce','on_delay','off_delay','cooldown_ms',
                      'kp','ki','kd','output_min','output_max','filter_ms','setpoint','feedback','ff_gain','enabled','duration_ms','sample_ms','threshold') + processing.NUMERIC
TIME_PARAMETERS = ('debounce','on_delay','off_delay','cooldown_ms','filter_ms','duration_ms','sample_ms')

def reference(value):
    match=REFERENCE.fullmatch(value) if isinstance(value,str) else None
    return match.group(1) if match else None


def math_function(name,*args):
    if not all(math.isfinite(a) for a in args):return 0.0
    try:result=float(FUNCTIONS[name][1](*args))
    except (ValueError,OverflowError):return 0.0
    return result if math.isfinite(result) else 0.0


def expression(source):
    # In this formula language ^ is exponentiation, with the same precedence as **.
    if 'lpn_ref_' in source:raise ValueError('Reserved expression name: lpn_ref_')
    tree = ast.parse(REFERENCE.sub(lambda m:'lpn_ref_'+m.group(1),source).replace('^','**'), mode='eval')
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
               ast.Call, ast.Name, ast.Load, ast.Constant, ast.Add, ast.Sub,
               ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.LShift, ast.RShift,
               ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
               ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
    for n in ast.walk(tree):
        if not isinstance(n, allowed):
            raise ValueError('Unsupported expression operation')
        if isinstance(n, ast.Name) and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',n.id):
            raise ValueError('Variable names must use ASCII letters, digits and underscores')
        if isinstance(n, ast.Constant) and (type(n.value) not in (int, float, bool) or not math.isfinite(n.value)):
            raise ValueError('Only finite numeric constants are supported')
        if isinstance(n, ast.Call) and (not isinstance(n.func, ast.Name) or
                n.func.id not in FUNCTIONS or n.keywords or len(n.args) != FUNCTIONS[n.func.id][0]):
            raise ValueError('Unsupported function or argument count: '+', '.join(FUNCTIONS))
        if isinstance(n, ast.Name) and n.id in FUNCTIONS:
            if not any(isinstance(p, ast.Call) and p.func is n for p in ast.walk(tree)):
                raise ValueError('Function names must be called')
    return tree


def detected_variables(source):
    tree=expression(source)
    calls={id(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)}
    names=sorted((n for n in ast.walk(tree) if isinstance(n,ast.Name) and id(n) not in calls and n.id not in CONSTANTS and not n.id.startswith('lpn_ref_')),
                 key=lambda n:(n.lineno,n.col_offset))
    return tuple(dict.fromkeys(n.id for n in names))


def new_variables(source,old=None):
    tree=expression(source);bits=set()
    for n in ast.walk(tree):
        if isinstance(n,ast.BoolOp):
            bits.update(v.id for v in n.values if isinstance(v,ast.Name))
        elif isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.Not) and isinstance(n.operand,ast.Name):
            bits.add(n.operand.id)
    return {name:dict((old or {}).get(name,dict(dtype='bit' if name in bits else 'float',
                    mode='port',value=1.0 if name=='gain' else 0.0)))
            for name in detected_variables(source)}


def modulo(a,b):
    # Python-style modulo: the nonzero remainder has the divisor's sign.
    if abs(b)<=1e-12 or not math.isfinite(a) or not math.isfinite(b):return 0.0
    r=math.fmod(a,b)
    return r+b if r!=0 and (r<0)!=(b<0) else r


def bitshift(value,count,left):
    # Logical 32-bit shifts; normalize the operand to its low 32 bits.
    if not math.isfinite(value) or not math.isfinite(count) or not 0<=count<=31 or count!=math.trunc(count):
        return 0.0
    bits=math.trunc(value)&0xffffffff
    return float(((bits<<int(count))&0xffffffff) if left else bits>>int(count))


def convert(value,dtype):
    value=float(value)
    if dtype=='bit':return float(bool(value))
    if dtype=='float':return value
    if not math.isfinite(value):return 0.0
    low,high=(-2147483648,2147483647) if dtype=='s32' else (0,4294967295)
    return float(math.trunc(min(max(value,low),high)))


def cconvert(source,dtype):
    return {'bit':f'!!({source})','float':f'({source})',
            's32':f'lpn_s32({source})','u32':f'lpn_u32({source})'}[dtype]


def counter_step(p,state,env):
    up=bool(env.get('up',0));down=bool(env.get('down',0))
    delta=int(up and not state.get('counter_up',False))-int(down and not state.get('counter_down',False))
    # Consume edges even during reset/disable: releasing either must not replay them.
    state['counter_up']=up;state['counter_down']=down
    count=state.get('count',int(p['initial']))
    if env.get('reset',0):count=int(p['initial'])
    elif env.get('enable',p['enabled']):count=max(-2147483648,min(2147483647,count+delta))
    state['count']=count;state['reached']=count>=p['threshold']
    return count


def pid_step(p,state,env,dt):
    target=env.get('setpoint',p['setpoint']);feedback=env.get('feedback',p['feedback'])
    error=target-feedback
    if (not env.get('enable',p['enabled']) or env.get('reset',0)
            or not all(math.isfinite(v) for v in (target,feedback,error,dt)) or dt<=0):
        state.update(integral=0.0,derivative=0.0,ready=False,error=0.0)
        return 0.0
    raw=-(feedback-state.get('feedback',feedback))/dt if state.get('ready',False) else 0.0
    tau=p['filter_ms']/1000
    derivative=state.get('derivative',0.0)+dt/(tau+dt)*(raw-state.get('derivative',0.0))
    integral=state.get('integral',0.0)
    increment=p['ki']*error*dt
    feedforward=p['ff_gain']*target if p['ff_enabled'] else 0.0
    pd=p['kp']*error+p['kd']*derivative+feedforward
    candidate=pd+integral+increment
    if not all(math.isfinite(v) for v in (raw,derivative,increment,pd,candidate)):
        state.update(integral=0.0,derivative=0.0,ready=False,error=0.0)
        return 0.0
    # Clip the outward increment at the limit; a large first increment still reaches it.
    if candidate>p['output_max'] and increment>0:
        increment=max(0.0,p['output_max']-(pd+integral))
    elif candidate<p['output_min'] and increment<0:
        increment=min(0.0,p['output_min']-(pd+integral))
    integral+=increment
    state.update(integral=integral,derivative=derivative,feedback=feedback,ready=True,error=error)
    return min(max(pd+integral,p['output_min']),p['output_max'])


def timer_step(p,state,env,dt):
    trigger=bool(env.get('trigger',0));rising=trigger and not state.get('timer_prev',False)
    state['timer_prev']=trigger
    if bool(env.get('reset',0)) or not math.isfinite(dt) or dt<=0:
        state.update(timer_running=False,timer_done=False,timer_elapsed=0.0,timer_limit=0.0)
        return False
    expired=False
    if rising and not state.get('timer_running',False) and (p['timer_mode']=='pulse' or not state.get('timer_done',False)):
        state.update(timer_running=True,timer_done=False,timer_elapsed=0.0,timer_limit=p['duration_ms']/1000)
    elif state.get('timer_running',False):
        state['timer_elapsed']=min(state['timer_limit'],state['timer_elapsed']+dt)
    if state.get('timer_running',False) and state['timer_elapsed']+1e-12>=state['timer_limit']:
        state.update(timer_running=False,timer_done=True);expired=True
    return expired if p['timer_mode']=='pulse' else state.get('timer_done',False)


def calc(n, env):
    if isinstance(n, ast.Expression): return calc(n.body, env)
    if isinstance(n, ast.Constant): return float(n.value)
    if isinstance(n, ast.Name): return CONSTANTS[n.id] if n.id in CONSTANTS else env[n.id]
    if isinstance(n, ast.BinOp):
        a,b=calc(n.left,env),calc(n.right,env)
        if isinstance(n.op,ast.Add): return a+b
        if isinstance(n.op,ast.Sub): return a-b
        if isinstance(n.op,ast.Mult): return a*b
        if isinstance(n.op,ast.Mod):return modulo(a,b)
        if isinstance(n.op,ast.Pow):return math_function('pow',a,b)
        if isinstance(n.op,(ast.LShift,ast.RShift)):return bitshift(a,b,isinstance(n.op,ast.LShift))
        return a/b if abs(b)>1e-12 else 0.0
    if isinstance(n, ast.UnaryOp):
        a=calc(n.operand,env)
        return -a if isinstance(n.op,ast.USub) else (not a if isinstance(n.op,ast.Not) else a)
    if isinstance(n, ast.BoolOp):
        values=[bool(calc(v,env)) for v in n.values]
        return all(values) if isinstance(n.op,ast.And) else any(values)
    if isinstance(n, ast.Compare):
        values=[calc(n.left,env)]+[calc(v,env) for v in n.comparators]
        return all(compare(op,a,b) for op,a,b in zip(n.ops,values,values[1:]))
    args=[calc(v,env) for v in n.args]
    return math_function(n.func.id,*args)


def compare(op,a,b):
    return {ast.Eq:lambda:a==b,ast.NotEq:lambda:a!=b,ast.Lt:lambda:a<b,
            ast.LtE:lambda:a<=b,ast.Gt:lambda:a>b,ast.GtE:lambda:a>=b}[type(op)]()


def cexpr(n,env):
    if isinstance(n,ast.Expression):return cexpr(n.body,env)
    if isinstance(n,ast.Constant):return repr(float(n.value))
    if isinstance(n,ast.Name):return repr(CONSTANTS[n.id]) if n.id in CONSTANTS else env[n.id]
    if isinstance(n,ast.BinOp):
        a,b=cexpr(n.left,env),cexpr(n.right,env)
        if isinstance(n.op,ast.Div):return f'lpn_div({a},{b})'
        if isinstance(n.op,ast.Mod):return f'lpn_mod({a},{b})'
        if isinstance(n.op,ast.Pow):return f'lpn_math_pow({a},{b})'
        if isinstance(n.op,(ast.LShift,ast.RShift)):
            return f'lpn_shift({a},{b},{int(isinstance(n.op,ast.LShift))})'
        return f'({a} { {ast.Add:"+",ast.Sub:"-",ast.Mult:"*"}[type(n.op)]} {b})'
    if isinstance(n,ast.UnaryOp):return f'({ {ast.USub:"-",ast.UAdd:"+",ast.Not:"!"}[type(n.op)]}{cexpr(n.operand,env)})'
    if isinstance(n,ast.BoolOp):return '('+(' && ' if isinstance(n.op,ast.And) else ' || ').join(cexpr(v,env) for v in n.values)+')'
    if isinstance(n,ast.Compare):
        values=[n.left]+n.comparators
        ops={ast.Eq:'==',ast.NotEq:'!=',ast.Lt:'<',ast.LtE:'<=',ast.Gt:'>',ast.GtE:'>='}
        return '('+' && '.join(f'({cexpr(a,env)} {ops[type(op)]} {cexpr(b,env)})' for op,a,b in zip(n.ops,values,values[1:]))+')'
    fn='lpn_math_'+n.func.id
    return fn+'('+','.join(cexpr(v,env) for v in n.args)+')'


class Graph:
    def __init__(self):
        self.nodes={};self.links=[];self.state={};self.values={};self.messages=[];self.monitor_values={}
        self.modules={0:'Main'};self.view_module=0;self.global_positions={};self.hal_thread='servo-thread'
    def module_name(self,name,exclude=None):
        if not isinstance(name,str) or not name.strip() or len(name.strip())>64 or any(ord(c)<32 for c in name):raise ValueError('Module name must be 1–64 printable characters')
        name=name.strip()
        if any(title.casefold()==name.casefold() for i,title in self.modules.items() if i!=exclude):raise ValueError('Duplicate module name')
        return name
    def add_module(self,name):
        name=self.module_name(name);i=max(self.modules,default=-1)+1;self.modules[i]=name;return i
    def rename_module(self,i,name):
        if i not in self.modules:raise ValueError('Unknown module')
        self.modules[i]=self.module_name(name,i)
    def delete_module(self,i):
        if i not in self.modules:raise ValueError('Unknown module')
        if len(self.modules)==1:raise ValueError('Keep at least one module')
        target=min(j for j in self.modules if j!=i)
        for n in self.nodes.values():
            if n.get('module',0)==i:n['module']=target
            if n.get('driver_module')==i:n['driver_module']=target
        del self.modules[i]
        if self.view_module==i:self.view_module=target
        return target
    def move_nodes(self,ids,module):
        if module not in self.modules or any(i not in self.nodes for i in ids):raise ValueError('Unknown node or module')
        if any(self.nodes[i]['p'].get('global_io') for i in ids):raise ValueError('Global I/O is shared by all modules')
        for i in ids:self.nodes[i]['module']=module
    def add(self,kind,pos=(0,0),module=None,global_io=False):
        module=min(self.modules) if module is None else module
        if module not in self.modules:raise ValueError('Unknown module')
        i=max(self.nodes,default=0)+1
        p=dict(DEFAULTS);p['name']=f'{kind}-{i}';p['global_io']=bool(global_io)
        if kind=='constant':p.update(name=f'constant{i}',dtype='float')
        if kind=='math':p['dtype']='float';p['template_name']=''
        if kind=='fifo':p['dtype']='float';p['initial']=0.0
        if kind=='display':p.update(message='PLC message',show_value=False,trigger_high=True,cooldown_ms=1000.0)
        if kind=='logger':p.update(input_count=2,buffer_length=1000,sample_ms=1.0,filename='logger-{node}-{timestamp}.csv',file_format='csv',number_format='.10g')
        if kind=='timer':p.update(duration_ms=1000.0,timer_mode='level')
        if kind=='counter':p.update(dtype='s32',initial=0,threshold=10,enabled=True)
        if kind=='pid':p.update(dtype='float',kp=1.0,ki=0.0,kd=0.0,output_min=-100.0,
                               output_max=100.0,filter_ms=0.0,setpoint=0.0,feedback=0.0,enabled=True,
                               ff_enabled=False,ff_gain=1.0)
        if kind=='condition':p['expression']='x > limit'
        if kind in ('math','condition'):p['variables']=new_variables(p['expression'])
        if kind in processing.KINDS:p.update(processing.defaults(kind))
        self.nodes[i]={'kind':kind,'pos':list(pos),'p':p,'module':module}
        return i
    def dtype(self,i,port=None):
        n=self.nodes[i]
        if n['kind'] in processing.KINDS:return processing.dtype(n['kind'],n['p'],port)
        if n['kind']=='counter':return 'bit' if port=='reached' else 's32'
        if n['kind']=='pid':return 'float'
        if n['kind']=='fifo':
            for a,source,b,target in self.links:
                if b==i and target=='in':return self.dtype(a,source)
        return 'bit' if n['kind'] in ('condition','invert','timer') else n['p']['dtype']
    def outputs(self,i):
        n=self.nodes[i]
        if n['kind'] in processing.KINDS:return processing.outputs(n['kind'],n['p'])
        return {'constant':(),'input':('out',),'output':(),'math':('result',),'condition':('true','false'),'invert':('out',),'fifo':('last','now'),'pid':('out','error'),'display':(),'timer':('out',),'counter':('count','reached'),'logger':()}[self.nodes[i]['kind']]
    def inputs(self,i):
        n=self.nodes[i]
        if n['kind'] in processing.KINDS:return processing.inputs(n['kind'],n['p'])
        if n['kind'] in ('input','constant'):return ()
        if n['kind']=='display':return ('trigger','value','reset')
        if n['kind']=='logger':return tuple(f'in{j+1}' for j in range(n['p']['input_count']))+('trigger',)
        if n['kind']=='timer':return ('trigger','reset')
        if n['kind']=='counter':return ('up','down','enable','reset')
        if n['kind']=='pid':return ('setpoint','feedback','enable','reset')
        if n['kind'] in ('output','invert','fifo'):return ('in',)
        return tuple(name for name,binding in n['p']['variables'].items() if binding['mode']=='port')
    def input_type(self,i,port):
        n=self.nodes[i]
        if n['kind'] in processing.KINDS:return processing.input_type(n['kind'],n['p'],port)
        if self.nodes[i]['kind']=='logger':
            if port=='trigger':return 'bit'
            for a,source,b,target in self.links:
                if (b,target)==(i,port):return self.dtype(a,source)
            return 'float'
        if self.nodes[i]['kind'] in ('timer','counter'):return 'bit'
        if self.nodes[i]['kind']=='display':return 'float' if port=='value' else 'bit'
        if self.nodes[i]['kind']=='pid':return 'bit' if port in ('enable','reset') else 'float'
        return self.dtype(i) if self.nodes[i]['kind'] in ('output','invert','fifo') else self.nodes[i]['p']['variables'][port]['dtype']
    def conversion(self,i,port):
        for a,source,b,target in self.links:
            if (b,target)==(i,port):
                before,after=self.dtype(a,source),self.input_type(i,port)
                return (before,after) if before!=after else None
        return None
    def has_connections(self,i):
        return any(a==i or b==i for a,source,b,port in self.links)
    def require_unconnected(self,i):
        if self.has_connections(i):raise ValueError('Disconnect all inputs and outputs before changing this node.')
    def disconnect_node(self,i):
        self.links=[l for l in self.links if l[0]!=i and l[2]!=i];self.reset()
    def value(self,i,port=None):
        if (i,port) in self.monitor_values:return self.monitor_values[i,port]
        if self.nodes[i]['kind'] in processing.KINDS and port in self.state.get(i,{}).get('ports',{}):return self.state[i]['ports'][port]
        if self.nodes[i]['kind']=='fifo' and port=='last':return self.state[i]['last']
        if self.nodes[i]['kind']=='pid' and port=='error':return self.state[i]['error']
        if self.nodes[i]['kind']=='counter' and port=='reached':return float(self.state[i]['reached'])
        return 1.0-self.values[i] if port=='false' else self.values[i]
    def set_expression(self,i,source):
        p=self.nodes[i]['p'];new=new_variables(source,p['variables'])
        old_source,old_variables,old_links=p['expression'],p['variables'],list(self.links)
        p['expression']=source;p['variables']=new
        self.links=[l for l in self.links if l[2]!=i or l[3] in self.inputs(i)]
        try:self.validate()
        except Exception:
            p['expression']=old_source;p['variables']=old_variables;self.links=old_links;raise
        self.reset();return len(old_links)-len(self.links)
    def set_variable(self,i,name,key,value):
        binding=self.nodes[i]['p']['variables'][name];old=binding[key];old_links=list(self.links)
        binding[key]=value
        if key=='mode' and value=='constant':self.links=[l for l in self.links if l[2:]!=[i,name]]
        try:self.validate()
        except Exception:binding[key]=old;self.links=old_links;raise
        self.reset();return len(old_links)-len(self.links)
    def math_template(self,i):
        if self.nodes[i]['kind']!='math':raise ValueError('Select a Math node')
        self.validate();p=self.nodes[i]['p']
        return dict(format='plc-math-template',version=1,expression=p['expression'],
                    dtype=p['dtype'],variables=deepcopy(p['variables']),title=p.get('template_name',''))
    def save_math_template(self,i,path):
        data=self.math_template(i)
        data['title']=data['title'] or Path(path).stem
        with open(path,'w') as f:json.dump(data,f,indent=2)
        self.nodes[i]['p']['template_name']=data['title']
    def apply_math_template(self,i,data):
        if self.nodes[i]['kind']!='math':raise ValueError('Select a Math node')
        self.require_unconnected(i)
        if not isinstance(data,dict) or data.get('format')!='plc-math-template' or data.get('version')!=1:
            raise ValueError('Not a supported Math template')
        if not isinstance(data.get('expression'),str) or not isinstance(data.get('variables'),dict):
            raise ValueError('Invalid Math template expression/variables')
        for binding in data['variables'].values():
            if not isinstance(binding,dict) or not {'dtype','mode','value'}<=binding.keys():
                raise ValueError('Invalid Math template variable')
        if data.get('dtype') not in TYPES:raise ValueError('Invalid Math template result type')
        if not isinstance(data.get('title',''),str):raise ValueError('Invalid Math template name')
        old=deepcopy(self.nodes[i]['p']);old_links=list(self.links)
        p=self.nodes[i]['p'];p.update(expression=data['expression'],dtype=data['dtype'],variables=deepcopy(data['variables']),template_name=data.get('title',''))
        try:
            self.links=[l for l in self.links if l[2]!=i or l[3] in self.inputs(i)]
            self.validate()
        except Exception:
            self.nodes[i]['p']=old;self.links=old_links;raise
        self.reset();return len(old_links)-len(self.links)
    def load_math_template(self,i,path):
        with open(path) as f:data=json.load(f)
        if isinstance(data,dict):data.setdefault('title',Path(path).stem)
        return self.apply_math_template(i,data)
    def driver(self,i):
        return next(((a,source) for a,source,b,target in self.links if b==i),None)
    def driver_module(self,i):
        driver=self.driver(i)
        if not driver:return None
        source=self.nodes[driver[0]]
        return self.nodes[i].get('driver_module',source['module']) if source['p'].get('global_io') else source['module']
    def connect(self,a,b,port,source_port=None):
        source_port=source_port or (self.outputs(a)[0] if self.outputs(a) else '')
        if a==b or source_port not in self.outputs(a) or port not in self.inputs(b):raise ValueError('Connect an output port to an input port')
        if self.nodes[b]['p'].get('global_io') and self.driver(b) not in (None,(a,source_port)):
            old_source=self.driver(b)[0]
            raise ValueError('Global output already driven in '+self.modules[self.nodes[old_source]['module']]+f' / node {old_source}')
        old=list(self.links);self.links=[l for l in self.links if l[2:]!=[b,port]]+[[a,source_port,b,port]]
        try:self.order()
        except Exception:self.links=old;raise
        if self.nodes[b]['p'].get('global_io'):self.nodes[b]['driver_module']=self.view_module
        self.reset()
    def order(self):
        pending=set(self.nodes);done=[]
        while pending:
            ready=sorted(i for i in pending if all(a in done for a,source,b,p in self.links if b==i))
            if not ready:raise ValueError('Feedback cycles are not supported; FIFO now also depends on the current input')
            done.extend(ready);pending.difference_update(ready)
        return done
    def memory_pairs(self):
        groups={}
        for i,n in self.nodes.items():
            if n['kind'] not in ('memory_read','memory_write'):continue
            groups.setdefault(n['p']['memory'],{'read':[],'write':[]})[n['kind'].split('_')[1]].append(i)
        for name,group in groups.items():
            if len(group['write'])>1:raise ValueError('Memory has multiple writers: '+name)
            members=group['read']+group['write']
            if len({self.nodes[i]['p']['dtype'] for i in members})>1:raise ValueError('Memory types differ: '+name)
            values={self.parameters(i)['initial'] for i in group['read']}
            if len(values)>1:raise ValueError('Memory initial values differ: '+name)
        return groups
    def add_memory_pair(self,pos=(0,0)):
        used={n['p'].get('memory') for n in self.nodes.values()};j=1
        while 'memory'+str(j) in used:j+=1
        name='memory'+str(j);writer=self.add('memory_write',pos);reader=self.add('memory_read',(pos[0]+320,pos[1]))
        for i in (writer,reader):self.nodes[i]['p']['memory']=name
        return writer,reader
    def constants(self):
        result={}
        for i,n in self.nodes.items():
            if n['kind']!='constant':continue
            p=n['p'];name=p['name']
            if not isinstance(name,str) or not re.fullmatch(r'[a-z][a-z0-9_]*',name):raise ValueError('Constant names: lowercase letters, digits, underscores')
            if name in result:raise ValueError('Duplicate constant: @'+name)
            if type(p['value']) not in (int,float,bool) or not math.isfinite(p['value']):raise ValueError('Constant default must be a finite number')
            if p['dtype'] not in TYPES:raise ValueError('Invalid constant type')
            result[name]=convert(p['value'],p['dtype'])
        return result
    def resolve(self,value,constants=None):
        name=reference(value)
        if name is None:return value
        constants=self.constants() if constants is None else constants
        if name not in constants:raise ValueError('Unknown constant: @'+name)
        return constants[name]
    def parameters(self,i,constants=None):
        p=dict(self.nodes[i]['p'])
        for key in NUMERIC_PARAMETERS:
            if key in p:
                raw=p[key];p[key]=self.resolve(raw,constants)
                if key in TIME_PARAMETERS and reference(raw) and p[key]>=0 and math.isfinite(p[key]):p[key]=math.floor(p[key]+0.5)
                if key=='enabled' and reference(raw):p[key]=bool(p[key])
        if 'variables' in p:
            p['variables']={name:dict(binding,value=self.resolve(binding['value'],constants)) for name,binding in p['variables'].items()}
        return p
    def validate(self):
        if not self.modules or (self.view_module is not None and self.view_module not in self.modules):raise ValueError('Invalid module list or selected module')
        for i,name in self.modules.items():
            if type(i) is not int or i<0:raise ValueError('Invalid module identifier')
            self.module_name(name,i)
        from hal_bindings import validate_binding,token
        token(self.hal_thread)
        if not isinstance(self.global_positions,dict):raise ValueError('Invalid global I/O positions')
        for key,pos in self.global_positions.items():
            if not isinstance(key,str) or not isinstance(pos,(list,tuple)) or len(pos)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in pos):raise ValueError('Invalid global I/O position')
        names=set();hal_targets=set();constants=self.constants()
        for i,n in self.nodes.items():
            if 'driver_module' in n and n['driver_module'] is not None and (type(n['driver_module']) is not int or n['driver_module'] not in self.modules):raise ValueError('Invalid driver module')
            if n.get('module',0) not in self.modules:raise ValueError('Node belongs to an unknown module')
            p=self.parameters(i,constants)
            if type(p.get('global_io',False)) is not bool or p.get('global_io') and n['kind'] not in ('input','output'):raise ValueError('Invalid global I/O node')
            if n['kind'] in ('input','output'):
                validate_binding(p.get('hal_binding'),n['kind'],p['dtype'])
                if n['kind']=='output' and p.get('hal_binding'):
                    binding=p['hal_binding'];target=binding.get('signal') or binding['name']
                    if target in hal_targets:raise ValueError('Multiple project outputs drive HAL signal: '+target)
                    hal_targets.add(target)
            if not isinstance(p.get('template_name',''),str):raise ValueError('Invalid Math template name')
            if n['kind'] not in ('constant','input','output','math','condition','invert','fifo','pid','display','timer','counter','logger') + processing.KINDS:raise ValueError('Unknown node kind')
            if p['dtype'] not in TYPES or p['edge'] not in ('level','rising','falling','both'):raise ValueError('Invalid pin type or edge mode')
            for k in ('value','initial','debounce','on_delay','off_delay'):
                if not isinstance(p[k],(float,int)) or not math.isfinite(p[k]):raise ValueError('Invalid number: '+k)
            if any(p[k]<0 for k in ('debounce','on_delay','off_delay')):raise ValueError('Negative delay')
            if n['kind'] in processing.KINDS:processing.validate(n['kind'],p)
            if n['kind']=='logger':validate_config(p)
            if n['kind']=='counter':
                for key in ('initial','threshold'):
                    value=p.get(key)
                    if type(value) not in (int,float) or not math.isfinite(value) or value!=math.trunc(value) or not -2147483648<=value<=2147483647:
                        raise ValueError('Counter values must be signed 32-bit integers')
                if p['dtype']!='s32':raise ValueError('Counter type must be s32')
                if type(p.get('enabled')) is not bool:raise ValueError('Invalid Counter enable default')
            if n['kind']=='timer':
                if p.get('timer_mode') not in ('level','pulse'):raise ValueError('Invalid Timer output mode')
                duration=p.get('duration_ms')
                if type(duration) not in (int,float) or not math.isfinite(duration) or duration<0 or duration!=math.trunc(duration):
                    raise ValueError('Timer duration must be nonnegative whole milliseconds')
            if n['kind']=='display':
                if not isinstance(p.get('message'),str) or not p['message'].strip() or any(ord(c)<32 or ord(c)==127 for c in p['message']) or len(p['message'].encode('utf-8'))>200:
                    raise ValueError('Display message must be a nonempty single line (up to 200 UTF-8 bytes)')
                if type(p.get('show_value')) is not bool:raise ValueError('Invalid Display value switch')
                if type(p.get('trigger_high')) is not bool:raise ValueError('Invalid Display trigger level')
                if type(p.get('cooldown_ms')) not in (int,float) or not math.isfinite(p['cooldown_ms']) or p['cooldown_ms']<0:
                    raise ValueError('Invalid Display cooldown')
            if n['kind']=='pid':
                for key in ('kp','ki','kd','output_min','output_max','filter_ms','setpoint','feedback','ff_gain'):
                    if type(p.get(key)) not in (int,float) or not math.isfinite(p[key]):raise ValueError('Invalid PID number: '+key)
                if p['output_min']>p['output_max']:raise ValueError('PID minimum must not exceed maximum')
                if p['filter_ms']<0:raise ValueError('PID derivative filter must be nonnegative')
                if type(p.get('enabled')) is not bool:raise ValueError('Invalid PID enable default')
                if type(p.get('ff_enabled')) is not bool:raise ValueError('Invalid PID feedforward switch')
            if n['kind'] in ('input','output','constant'):
                name=p['name'].replace('_','-') if n['kind']=='constant' else p['name']
                if not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*',name):raise ValueError('Pin names: lowercase letters, digits, hyphens')
                if name in names or name.replace('-','_') in {spec[2] for spec in FUNCTIONS.values()} or re.fullmatch(r'(?:n|stable|prev|elapsed|raw|wanted|out)[0-9]+|dt',name) or name.replace('-','_').startswith('lpn_') or name.replace('-','_') in ('update','period','int','float','double','char','void','static','const','switch','case','default','if','else','for','while','do','return','struct','union','enum','typedef','sizeof','break','continue','unsigned','signed','long','short','auto','register','extern','volatile','restrict','count','personality','fabs','fmin','fmax','trunc','fmod','isfinite'):raise ValueError('Duplicate/reserved pin name: '+name)
                names.add(name)
            elif n['kind'] in ('math','condition'):
                for name in REFERENCE.findall(p['expression']):self.resolve('@'+name,constants)
                if tuple(p['variables'])!=detected_variables(p['expression']):raise ValueError('Variable list does not match expression')
                for name,binding in p['variables'].items():
                    if binding['dtype'] not in TYPES or binding['mode'] not in ('port','constant'):raise ValueError('Invalid variable type or mode: '+name)
                    if type(binding['value']) not in (int,float) or not math.isfinite(binding['value']):raise ValueError('Invalid constant: '+name)
        self.memory_pairs()
        seen=set()
        for a,source,b,port in self.links:
            if a not in self.nodes or b not in self.nodes or source not in self.outputs(a) or port not in self.inputs(b):raise ValueError('Invalid connection')
            if (b,port) in seen:raise ValueError('Multiple drivers on one port')
            seen.add((b,port))
        return self.order()
    def logger_config(self,i,base_dir=None):
        config=dict(self.parameters(i));config['node']=i;config['base_dir']=str(base_dir or getattr(self,'logger_base_dir',Path.cwd()))
        channels=[]
        for port in self.inputs(i):
            if port=='trigger':continue
            label=port+' (unconnected)'
            for a,source,b,target in self.links:
                if (b,target)==(i,port):
                    n=self.nodes[a];title=n['p']['name'] if n['kind']=='input' else n['p'].get('template_name') or f"{n['kind']} #{a}"
                    label=self.modules[n.get('module',0)]+' / '+title+'.'+source
            channels.append(dict(port=port,name=label,dtype=self.input_type(i,port)))
        config['channels']=channels
        return config
    def reset(self):self.memory={};self.state={};self.values={};self.monitor_values={};self.messages=[];self.logger_requests=[]
    def step(self,dt):
        self.messages=[];self.logger_requests=[];constants=self.constants()
        order=self.validate();memory=getattr(self,'memory',{});self.memory=memory
        for name,group in self.memory_pairs().items():
            reader=group['read'][0] if group['read'] else None
            if name not in memory:memory[name]=convert(self.parameters(reader)['initial'],self.dtype(reader)) if reader is not None else 0.0
        for i in order:
            n=self.nodes[i];p=self.parameters(i,constants);s=self.state.setdefault(i,dict(stable=False,prev=False,elapsed=0.0,out=bool(p['initial'])))
            env={port:self.value(a,source) for a,source,b,port in self.links if b==i}
            if n['kind']=='memory_read':v=memory[p['memory']]
            elif n['kind']=='memory_write':v=convert(env.get('in',0),p['dtype'])
            elif n['kind'] in processing.KINDS:v=processing.step(n['kind'],p,s,env,dt)
            elif n['kind']=='constant':v=constants[p['name']]
            elif n['kind']=='input':
                v=convert(p['value'],p['dtype'])
                if p['dtype']=='bit':
                    raw=bool(v)^p['invert']
                    s['elapsed']=s['elapsed']+dt if raw!=s['stable'] else 0.0
                    if raw!=s['stable'] and s['elapsed']>=p['debounce']/1000:s['stable']=raw;s['elapsed']=0.0
                    v=s['stable'];old=s['prev'];s['prev']=v
                    v={'level':v,'rising':v and not old,'falling':old and not v,'both':old!=v}[p['edge']]
            elif n['kind'] in ('math','condition'):
                bindings={k:convert(env.get(k,b['value']),b['dtype']) for k,b in p['variables'].items()}
                bindings.update({'lpn_ref_'+name:value for name,value in constants.items()})
                v=calc(expression(p['expression']),bindings)
                if n['kind']=='condition':v=bool(v)
                else:v=convert(v,p['dtype'])
            elif n['kind']=='invert':
                v=not bool(env.get('in',0.0))
            elif n['kind']=='fifo':
                dtype=self.dtype(i)
                s['last']=s.get('now',convert(p['initial'],dtype))
                v=convert(env.get('in',float(p['initial'])),dtype);s['now']=v
            elif n['kind']=='pid':
                v=pid_step(p,s,env,dt)
            elif n['kind']=='logger':
                if 'logger' not in s:s['logger']=SimulationLogger(self.logger_config(i))
                logger=s['logger']
                snapshot=logger.step(dt,p['sample_ms'],env.get('trigger',0),[env.get(f'in{j+1}',0.0) for j in range(p['input_count'])])
                if snapshot:self.logger_requests.append(snapshot)
                v=len(logger.collector.rows)
            elif n['kind']=='timer':
                v=timer_step(p,s,env,dt)
            elif n['kind']=='counter':
                v=counter_step(p,s,env)
            elif n['kind']=='display':
                v=bool(env.get('trigger',not p['trigger_high']))==p['trigger_high']
                cooldown=p['cooldown_ms']/1000
                reset=bool(env.get('reset',0))
                if reset and not s.get('message_reset',False):
                    s['prev']=False;s['message_elapsed']=cooldown
                s['message_reset']=reset
                s['message_elapsed']=min(cooldown,s.get('message_elapsed',cooldown)+max(dt,0))
                if v and not s['prev'] and s['message_elapsed']>=cooldown:
                    text=p['message']+(f': {env.get("value",0):.10g}' if p['show_value'] else '')
                    self.messages.append(text);s['message_elapsed']=0.0
                s['prev']=v
            else:
                v=convert(env.get('in',float(p['initial'])),p['dtype'])
                if p['dtype']=='bit':
                    wanted=bool(v);s['elapsed']=s['elapsed']+dt if wanted!=s['out'] else 0.0
                    delay=p['on_delay'] if wanted else p['off_delay']
                    if wanted!=s['out'] and s['elapsed']>=delay/1000:s['out']=wanted;s['elapsed']=0.0
                    v=s['out']^p['invert']
            self.values[i]=float(v)
        for i in order:
            if self.nodes[i]['kind']=='memory_write':memory[self.nodes[i]['p']['memory']]=self.values[i]
        return self.values
    def save(self,path):
        with open(path,'w') as f:json.dump({'version':5,'global_positions':self.global_positions,'hal_thread':self.hal_thread,'modules':self.modules,'view_module':self.view_module,'nodes':self.nodes,'links':self.links},f,indent=2)
    @classmethod
    def load(cls,path):
        with open(path) as f:d=json.load(f)
        if d.get('version') not in (1,2,3,4,5):raise ValueError('Unknown project version')
        g=cls();g.nodes={int(i):n for i,n in d['nodes'].items()}
        if d['version']>=4:
            g.modules={int(i):name for i,name in d['modules'].items()};g.view_module=d.get('view_module',min(g.modules,default=0))
        g.global_positions=d.get('global_positions',{});g.hal_thread=d.get('hal_thread','servo-thread')
        for n in g.nodes.values():
            n['p'].setdefault('global_io',False);n['p'].setdefault('hal_binding',None)
            n.setdefault('module',0)
            if n['kind']=='math':n['p'].setdefault('template_name','')
            if n['kind']=='pid':
                n['p'].setdefault('ff_enabled',False);n['p'].setdefault('ff_gain',1.0)
            if n['kind']=='display':n['p'].pop('severity',None)
        if d['version']<3:
            for n in g.nodes.values():
                if n['kind']=='math':n['p']['dtype']='float'
        if d['version']==1:
            for n in g.nodes.values():
                if n['kind'] in ('math','condition'):
                    p=n['p'];p['variables']=new_variables(p['expression'])
                    for name,binding in p['variables'].items():binding['value']=float(p.get(name,binding['value']))
            g.links=[[a,g.outputs(a)[0],b,port] for a,b,port in d['links'] if port in g.inputs(b)]
        else:g.links=d['links']
        g.validate();return g
    def export(self,path,debug=False):
        order=self.validate();name=path.stem
        from hal_bindings import bypass_nodes
        omitted=bypass_nodes(self) if not debug else set()
        order=[i for i in order if i not in omitted]
        if name=='all':raise ValueError('Reserved HAL component name: all')
        if not re.fullmatch('[a-z][a-z0-9_]*',name):raise ValueError('Export filename must use lowercase letters, digits, underscores')
        from logger_export import prepare, realtime_body, write_bundle
        loggers=[self.logger_config(i,path.resolve().parent) for i in order if self.nodes[i]['kind']=='logger']
        logger_options,logger_source=prepare(loggers,name)
        declarations=[f'component {name} "Local node PLC prototype";', 'option singleton yes;', 'license "MIT";',*logger_options]
        # halcompile requires a pin even when the HAL bundle needs no component.
        if not order and not debug:declarations.append('pin out bit lpn-hal-only = 0;')
        for i in order:
            n=self.nodes[i];p=n['p']
            if n['kind'] in ('input','output','constant'):
                default=(' = '+repr(int(convert(p['value'],p['dtype'])) if p['dtype']!='float' else p['value'])) if n['kind']=='constant' else ''
                declarations.append(f'pin {"out" if n["kind"]=="output" else "in"} {p["dtype"]} {p["name"].replace("_","-")}{default};')
        from hal_bindings import monitor_map,fingerprint,write_bundle as write_hal_bundle
        monitors=monitor_map(self,name) if debug else []
        for monitor in monitors:declarations.append(f'pin out {monitor["dtype"]} {monitor["suffix"]};')
        suffixes=[n['p']['name'].replace('_','-') for n in self.nodes.values() if n['kind'] in ('input','output','constant')]+[m['suffix'] for m in monitors]+(['lpn-debug-max-runtime-ns'] if debug else [])+['update.tmax-increased']
        if len(set(suffixes))!=len(suffixes):raise ValueError('External pin name conflicts with a debug pin')
        if any(len(name.replace('_','-')+'.'+suffix)>=48 for suffix in suffixes):raise ValueError('HAL pin name exceeds 47 characters; shorten the component or pin name')
        signature=fingerprint(self)
        signature_pins=[('lpn-debug-id'+str(j),int(signature[j*8:j*8+8],16)) for j in range(4)] if debug else []
        if debug:
            declarations += ['pin out float lpn-debug-runtime-ns;','pin out float lpn-debug-max-runtime-ns;']
        for pin,value in signature_pins:declarations.append(f'pin out u32 {pin} = 0;')
        declarations+=['function update;', ';;', '#include <math.h>', '#include <stdint.h>',
            '''static int lpn_timer(int lpn_timer_trigger,int lpn_timer_reset,double lpn_timer_dt,double lpn_timer_duration,int lpn_timer_pulse,
                int *lpn_timer_previous,int *lpn_timer_running,int *lpn_timer_done,double *lpn_timer_elapsed,double *lpn_timer_limit){
                int lpn_timer_rising=lpn_timer_trigger && !*lpn_timer_previous;
                *lpn_timer_previous=lpn_timer_trigger;
                if(lpn_timer_reset || !isfinite(lpn_timer_dt) || lpn_timer_dt<=0){
                    *lpn_timer_running=0;*lpn_timer_done=0;*lpn_timer_elapsed=0;*lpn_timer_limit=0;return 0;
                }
                int lpn_timer_expired=0;
                if(lpn_timer_rising && !*lpn_timer_running && (lpn_timer_pulse || !*lpn_timer_done)){
                    *lpn_timer_running=1;*lpn_timer_done=0;*lpn_timer_elapsed=0;*lpn_timer_limit=lpn_timer_duration;
                }else if(*lpn_timer_running)*lpn_timer_elapsed=fmin(*lpn_timer_limit,*lpn_timer_elapsed+lpn_timer_dt);
                if(*lpn_timer_running && *lpn_timer_elapsed+1e-12>=*lpn_timer_limit){
                    *lpn_timer_running=0;*lpn_timer_done=1;lpn_timer_expired=1;
                }
                return lpn_timer_pulse?lpn_timer_expired:*lpn_timer_done;
            }''',
            '''static double lpn_shift(double lpn_shift_value,double lpn_shift_count,int lpn_shift_left){
                if(!isfinite(lpn_shift_value) || !isfinite(lpn_shift_count) || lpn_shift_count<0 || lpn_shift_count>31 || lpn_shift_count!=trunc(lpn_shift_count))return 0.0;
                double lpn_shift_wrapped=fmod(trunc(lpn_shift_value),4294967296.0);
                if(lpn_shift_wrapped<0)lpn_shift_wrapped+=4294967296.0;
                uint32_t lpn_shift_bits=(uint32_t)lpn_shift_wrapped;
                unsigned int lpn_shift_amount=(unsigned int)lpn_shift_count;
                return lpn_shift_left?(double)(uint32_t)((uint64_t)lpn_shift_bits<<lpn_shift_amount):(double)(lpn_shift_bits>>lpn_shift_amount);
            }''',
            'static double lpn_div(double a,double b){return fabs(b)>1e-12?a/b:0.0;}',
            'static double lpn_mod(double a,double b){if(fabs(b)<=1e-12 || !isfinite(a) || !isfinite(b))return 0.0;double r=fmod(a,b);return r!=0.0 && ((r<0.0)!=(b<0.0))?r+b:r;}',
            'static double lpn_s32(double x){return isfinite(x)?trunc(fmin(fmax(x,-2147483648.0),2147483647.0)):0.0;}',
            'static double lpn_u32(double x){return isfinite(x)?trunc(fmin(fmax(x,0.0),4294967295.0)):0.0;}',
            'static double lpn_clamp(double x,double l,double h){return fmin(fmax(x,l),h);}',
            '''static double lpn_pid(double lpn_pid_target,double lpn_pid_feedback,int lpn_pid_enable,int lpn_pid_reset,double lpn_pid_dt,
                double lpn_pid_kp,double lpn_pid_ki,double lpn_pid_kd,double lpn_pid_low,double lpn_pid_high,double lpn_pid_tau,double lpn_pid_ff_gain,
                double *lpn_pid_integral,double *lpn_pid_derivative,double *lpn_pid_previous,int *lpn_pid_ready,double *lpn_pid_error){
                *lpn_pid_error=lpn_pid_target-lpn_pid_feedback;
                if(!lpn_pid_enable || lpn_pid_reset || !isfinite(lpn_pid_target) || !isfinite(lpn_pid_feedback) || !isfinite(*lpn_pid_error) || !isfinite(lpn_pid_dt) || lpn_pid_dt<=0){
                    *lpn_pid_integral=0;*lpn_pid_derivative=0;*lpn_pid_ready=0;*lpn_pid_error=0;return 0;
                }
                double lpn_pid_raw=*lpn_pid_ready?-(lpn_pid_feedback-*lpn_pid_previous)/lpn_pid_dt:0;
                double lpn_pid_d=*lpn_pid_derivative+lpn_pid_dt/(lpn_pid_tau+lpn_pid_dt)*(lpn_pid_raw-*lpn_pid_derivative);
                double lpn_pid_increment=lpn_pid_ki*(*lpn_pid_error)*lpn_pid_dt;
                double lpn_pid_pd=lpn_pid_kp*(*lpn_pid_error)+lpn_pid_kd*lpn_pid_d+lpn_pid_ff_gain*lpn_pid_target;
                double lpn_pid_candidate=lpn_pid_pd+*lpn_pid_integral+lpn_pid_increment;
                if(!isfinite(lpn_pid_raw) || !isfinite(lpn_pid_d) || !isfinite(lpn_pid_increment) || !isfinite(lpn_pid_pd) || !isfinite(lpn_pid_candidate)){
                    *lpn_pid_integral=0;*lpn_pid_derivative=0;*lpn_pid_ready=0;*lpn_pid_error=0;return 0;
                }
                if(lpn_pid_candidate>lpn_pid_high && lpn_pid_increment>0)
                    lpn_pid_increment=fmax(0,lpn_pid_high-(lpn_pid_pd+*lpn_pid_integral));
                else if(lpn_pid_candidate<lpn_pid_low && lpn_pid_increment<0)
                    lpn_pid_increment=fmin(0,lpn_pid_low-(lpn_pid_pd+*lpn_pid_integral));
                *lpn_pid_integral+=lpn_pid_increment;
                *lpn_pid_derivative=lpn_pid_d;*lpn_pid_previous=lpn_pid_feedback;*lpn_pid_ready=1;
                return lpn_clamp(lpn_pid_pd+*lpn_pid_integral,lpn_pid_low,lpn_pid_high);
            }''',
        ]
        for fn,(arity,_,cfn) in FUNCTIONS.items():
            params=('a','b','c')[:arity]
            declarations.append(f'static double lpn_math_{fn}('+','.join('double '+v for v in params)+
                '){if('+ ' || '.join('!isfinite('+v+')' for v in params)+
                ')return 0.0;double r='+cfn+'('+','.join(params)+');return isfinite(r)?r:0.0;}')
        # LinuxCNC 2.10 exposes output setters instead of writable pin macros.
        # Older 2.9 halcompile versions need the equivalent assignment fallback.
        for i in order:
            if self.nodes[i]['kind']=='output':
                pin=self.nodes[i]['p']['name'].replace('-','_')
                declarations += [f'#ifndef {pin}_set',
                                 f'#define {pin}_set(...) ({pin} = (__VA_ARGS__))',
                                 '#endif']
        for pin in [m['suffix'] for m in monitors]+[p for p,v in signature_pins]+(['lpn-debug-runtime-ns','lpn-debug-max-runtime-ns'] if debug else []):
            macro=pin.replace('-','_');declarations += [f'#ifndef {macro}_set',f'#define {macro}_set(...) ({macro} = (__VA_ARGS__))','#endif']
        declarations+=logger_source
        declarations+=['FUNCTION(update) {', '  double dt = period * 1e-9;']
        code=(["  long long lpn_runtime_start=rtapi_get_time();"] if debug else [])+[f'  {pin.replace(chr(45),chr(95))}_set({value}U);' for pin,value in signature_pins]
        constant_nodes={n['p']['name']:n for n in self.nodes.values() if n['kind']=='constant'}
        def cv(value,dtype=None):
            name=reference(value)
            source=cconvert(name,constant_nodes[name]['p']['dtype']) if name else repr(float(value))
            return cconvert(source,dtype) if dtype else source
        def seconds(value):return f'(fmax(0.0,floor({cv(value)}+0.5))*0.001)' if reference(value) else repr(value/1000)
        memory_names={name:'lpn_memory_'+str(j) for j,name in enumerate(self.memory_pairs())}
        for name,group in self.memory_pairs().items():
            reader=group['read'][0] if group['read'] else None
            initial=cv(self.nodes[reader]['p']['initial'],self.dtype(reader)) if reader is not None else '0'
            m=memory_names[name];code += [f'  static double {m}=0;',f'  static int {m}_init=0;',f'  if(!{m}_init) {{{m}={initial};{m}_init=1;}}']
        for i in order:
            n=self.nodes[i];p=n['p'];v=f'n{i}';pin=p['name'].replace('-','_')
            env={port:(processing.c_port(a,source) if self.nodes[a]['kind'] in processing.KINDS and self.nodes[a]['kind'] not in ('memory_read','memory_write') else f'lpn_fifo_last_{a}' if self.nodes[a]['kind']=='fifo' and source=='last' else
                       f'lpn_pid_error_{a}' if self.nodes[a]['kind']=='pid' and source=='error' else
                       f'lpn_counter_reached_{a}' if self.nodes[a]['kind']=='counter' and source=='reached' else
                       f'(!n{a})' if source=='false' else f'n{a}') for a,source,b,port in self.links if b==i}
            code.append(f'  double {v}; /* {n["kind"]}: node {i} */')
            if n['kind']=='memory_read':code.append(f'  {v}={memory_names[p["memory"]]};')
            elif n['kind']=='memory_write':code.append(f'  {v}={cconvert(env.get("in","0"),p["dtype"])};')
            elif n['kind'] in processing.KINDS:code+=processing.c_body(i,n['kind'],p,env,cv)
            elif n['kind']=='constant':code.append(f'  {v} = {cconvert(pin,p["dtype"])};')
            elif n['kind']=='input':
                if p['dtype']!='bit':code.append(f'  {v} = {cconvert(pin,p["dtype"])};')
                else:
                    code += [f'  static int stable{i}=0, prev{i}=0;',f'  static double elapsed{i}=0;',f'  int raw{i} = (!!{pin}) ^ {int(p["invert"])};',f'  elapsed{i} = raw{i} != stable{i} ? elapsed{i}+dt : 0;',f'  if(raw{i} != stable{i} && elapsed{i} >= {seconds(p["debounce"])}) {{stable{i}=raw{i}; elapsed{i}=0;}}']
                    expr={'level':f'stable{i}','rising':f'(stable{i} && !prev{i})','falling':f'(!stable{i} && prev{i})','both':f'(stable{i} != prev{i})'}[p['edge']]
                    code += [f'  {v} = {expr};',f'  prev{i} = stable{i};']
            elif n['kind'] in ('math','condition'):
                bindings={k:cconvert(env.get(k,cv(b['value'])),b['dtype']) for k,b in p['variables'].items()}
                bindings.update({'lpn_ref_'+name:cv('@'+name) for name in constant_nodes})
                exp=cexpr(expression(p['expression']),bindings)
                result=cconvert(exp,'bit' if n['kind']=='condition' else p['dtype'])
                code.append(f'  {v} = {result};')
            elif n['kind']=='invert':
                code.append(f'  {v} = !({env.get("in","0.0")});')
            elif n['kind']=='fifo':
                dtype=self.dtype(i);initial=cv(p['initial'],dtype) if reference(p['initial']) else repr(convert(p['initial'],dtype))
                code += ([f'  static double lpn_fifo_previous_{i}=0;',f'  static int lpn_fifo_initialized_{i}=0;',f'  if(!lpn_fifo_initialized_{i}) {{lpn_fifo_previous_{i}={initial};lpn_fifo_initialized_{i}=1;}}'] if reference(p['initial']) else [f'  static double lpn_fifo_previous_{i} = {initial};'])+[
                         f'  double lpn_fifo_last_{i} = lpn_fifo_previous_{i};',
                         f'  {v} = {cconvert(env.get("in",initial),dtype)};',
                         f'  lpn_fifo_previous_{i} = {v};']
            elif n['kind']=='pid':
                code += [f'  static double lpn_pid_i_{i}=0,lpn_pid_d_{i}=0,lpn_pid_previous_{i}=0;',
                         f'  static int lpn_pid_ready_{i}=0;',f'  double lpn_pid_error_{i};']
                arguments=[env.get('setpoint',cv(p['setpoint'])),env.get('feedback',cv(p['feedback'])),
                           f'!!({env.get("enable",cv(p["enabled"],"bit"))})',f'!!({env.get("reset","0")})','dt']
                arguments += [cv(p[key]) for key in ('kp','ki','kd','output_min','output_max')]+[seconds(p['filter_ms'])]
                arguments += [cv(p['ff_gain'] if p['ff_enabled'] else 0.0)]
                arguments += [f'&lpn_pid_{key}_{i}' for key in ('i','d','previous','ready','error')]
                code.append(f'  {v} = lpn_pid('+','.join(arguments)+');')
            elif n['kind']=='logger':
                code+=realtime_body(i,p,env,cv)
                code.append(f'  {v}=lpn_log_count_{i};')
            elif n['kind']=='timer':
                code += [f'  static int lpn_timer_prev_{i}=0,lpn_timer_running_{i}=0,lpn_timer_done_{i}=0;',
                         f'  static double lpn_timer_elapsed_{i}=0,lpn_timer_limit_{i}=0;',
                         f'  {v} = lpn_timer(!!({env.get("trigger","0")}),!!({env.get("reset","0")}),dt,{seconds(p["duration_ms"])},{int(p["timer_mode"]=="pulse")},'+
                         ','.join(f'&lpn_timer_{key}_{i}' for key in ('prev','running','done','elapsed','limit'))+');']
            elif n['kind']=='counter':
                initial=cv(p['initial'],'s32')
                code += [f'  static int lpn_counter_initialized_{i}=0,lpn_counter_up_prev_{i}=0,lpn_counter_down_prev_{i}=0;',
                         f'  static double lpn_counter_count_{i}=0;',
                         f'  if(!lpn_counter_initialized_{i}) {{lpn_counter_count_{i}={initial};lpn_counter_initialized_{i}=1;}}',
                         f'  int lpn_counter_up_{i}=!!({env.get("up","0")}),lpn_counter_down_{i}=!!({env.get("down","0")});',
                         f'  int lpn_counter_delta_{i}=(lpn_counter_up_{i} && !lpn_counter_up_prev_{i})-(lpn_counter_down_{i} && !lpn_counter_down_prev_{i});',
                         f'  lpn_counter_up_prev_{i}=lpn_counter_up_{i};lpn_counter_down_prev_{i}=lpn_counter_down_{i};',
                         f'  if({env.get("reset","0")}) lpn_counter_count_{i}={initial};',
                         f'  else if({env.get("enable",cv(p["enabled"],"bit"))}) lpn_counter_count_{i}=lpn_s32(lpn_counter_count_{i}+lpn_counter_delta_{i});',
                         f'  {v}=lpn_counter_count_{i};',
                         f'  int lpn_counter_reached_{i}=({v}>={cv(p["threshold"],"s32")});']
            elif n['kind']=='display':
                text=json.dumps(p['message'],ensure_ascii=False)
                cooldown=seconds(p['cooldown_ms'])
                trigger=env.get('trigger',str(int(not p['trigger_high'])))
                code += [f'  static int lpn_display_previous_{i}=0;']+([f'  static double lpn_display_elapsed_{i}=0;',f'  static int lpn_display_initialized_{i}=0;',f'  if(!lpn_display_initialized_{i}) {{lpn_display_elapsed_{i}={cooldown};lpn_display_initialized_{i}=1;}}'] if reference(p['cooldown_ms']) else [f'  static double lpn_display_elapsed_{i}={cooldown};'])+[
                         f'  static int lpn_display_reset_previous_{i}=0;',
                         f'  int lpn_display_reset_{i}=!!({env.get("reset","0")});',
                         f'  if(lpn_display_reset_{i} && !lpn_display_reset_previous_{i}) {{lpn_display_previous_{i}=0;lpn_display_elapsed_{i}={cooldown};}}',
                         f'  lpn_display_reset_previous_{i}=lpn_display_reset_{i};',
                         f'  lpn_display_elapsed_{i}=fmin({cooldown},lpn_display_elapsed_{i}+(dt>0?dt:0));',
                         f'  {v}=(!!({trigger}) == {int(p["trigger_high"])});',
                         f'  if({v} && !lpn_display_previous_{i} && lpn_display_elapsed_{i}>={cooldown}) {{',
                         f'    lpn_display_elapsed_{i}=0;']
                if p['show_value']:code.append(f'    rtapi_print_msg(RTAPI_MSG_ERR,"%s: %.10g\\n",{text},(double)({env.get("value","0.0")}));')
                else:code.append(f'    rtapi_print_msg(RTAPI_MSG_ERR,"%s\\n",{text});')
                code += ['  }',f'  lpn_display_previous_{i}={v};']
            else:
                source=env.get('in',cv(p['initial']))
                if p['dtype']!='bit':code.append(f'  {v} = {cconvert(source,p["dtype"])};')
                else:
                    code += ([f'  static int out{i}=0;',f'  static int lpn_output_initialized_{i}=0;',f'  if(!lpn_output_initialized_{i}) {{out{i}={cv(p["initial"],"bit")};lpn_output_initialized_{i}=1;}}'] if reference(p['initial']) else [f'  static int out{i}={int(p["initial"])};'])+[f'  static double elapsed{i}=0;',f'  int wanted{i}=!!({source});',f'  elapsed{i}=wanted{i}!=out{i}?elapsed{i}+dt:0;',f'  if(wanted{i}!=out{i} && elapsed{i}>=(wanted{i}?{seconds(p["on_delay"])}:{seconds(p["off_delay"])})) {{out{i}=wanted{i};elapsed{i}=0;}}',f'  {v}=out{i} ^ {int(p["invert"])};']
                code.append(f'  {pin}_set({v});')
            for monitor in monitors:
                if monitor['node']!=i:continue
                port=monitor['port'];source=f'lpn_fifo_last_{i}' if n['kind']=='fifo' and port=='last' else f'lpn_pid_error_{i}' if n['kind']=='pid' and port=='error' else f'(!{v})' if port=='false' else v
                if n['kind']=='counter' and port=='reached':source=f'lpn_counter_reached_{i}'
                if n['kind'] in processing.KINDS and n['kind'] not in ('memory_read','memory_write'):source=processing.c_port(i,port)
                code.append(f'  {monitor["suffix"].replace(chr(45),chr(95))}_set({cconvert(source,monitor["dtype"])});')
        for i in order:
            n=self.nodes[i]
            if n['kind']=='memory_write':code.append(f'  {memory_names[n["p"]["memory"]]}=n{i};')
        if debug:code += ['  double lpn_runtime_ns=rtapi_get_time()-lpn_runtime_start;', '  static double lpn_runtime_max=0;', '  if(lpn_runtime_ns>lpn_runtime_max) lpn_runtime_max=lpn_runtime_ns;', '  lpn_debug_runtime_ns_set(lpn_runtime_ns);','  lpn_debug_max_runtime_ns_set(lpn_runtime_max);']
        generated='\n'.join(declarations+code+['}'])+'\n'
        header,body=generated.split(';;\n',1)
        generated=header+';;\n'+re.sub(r'\b(?:n[0-9]+|stable[0-9]+|prev[0-9]+|elapsed[0-9]+|raw[0-9]+|wanted[0-9]+|out[0-9]+|dt)\b',lambda m:'lpn_'+m.group(),body)
        with open(path,'w') as f:f.write(generated)
        write_bundle(path,name,loggers)
        write_hal_bundle(self,path,debug)
        # Retire helper files owned by older exports; new exports need only the .comp.
        metadata=path.with_suffix('.display.json')
        if metadata.exists():
            try:old=json.loads(metadata.read_text())
            except (ValueError,OSError):old=None
            if isinstance(old,dict) and old.get('component')==name.replace('_','-')+'-display' and isinstance(old.get('messages'),list):
                for suffix in ('.display.py','.display.hal','.display.json'):path.with_suffix(suffix).unlink(missing_ok=True)


def demo():
    g=Graph();a=g.add('input',(20,20));g.nodes[a]['p'].update(name='pressure',dtype='float',value=4.0)
    b=g.add('math',(260,20));g.set_expression(b,'pressure * scale')
    g.set_variable(b,'scale','mode','constant');g.set_variable(b,'scale','value',2.0)
    c=g.add('condition',(20,220));g.set_expression(c,'pressure >= minimum')
    g.set_variable(c,'minimum','mode','constant');g.set_variable(c,'minimum','value',5.0)
    d=g.add('output',(260,220));g.nodes[d]['p'].update(name='pump',on_delay=200.0,off_delay=1000.0)
    g.connect(a,b,'pressure');g.connect(b,c,'pressure');g.connect(c,d,'in','true');return g


# Continuous direction computation only; this is not a complete toolchanger.
def circular_demo():
    g=Graph()
    actual=g.add('input',(0,0));g.nodes[actual]['p'].update(name='actual-position',dtype='u32',value=11)
    target=g.add('input',(0,140));g.nodes[target]['p'].update(name='target-position',dtype='u32',value=0)
    delta=g.add('math',(270,40))
    g.set_expression(delta,'((target - actual + stations / 2) % stations + stations) % stations - stations / 2')
    for var in ('actual','target','stations'):g.set_variable(delta,var,'dtype','u32')
    g.set_variable(delta,'stations','mode','constant');g.set_variable(delta,'stations','value',12)
    g.connect(actual,delta,'actual');g.connect(target,delta,'target')
    zero=g.add('condition',(540,0));g.set_expression(zero,'delta == 0');g.connect(delta,zero,'delta')
    moving=g.add('invert',(810,0));g.connect(zero,moving,'in','true')
    direction=g.add('condition',(540,180));g.set_expression(direction,'delta > 0');g.connect(delta,direction,'delta')
    cw=g.add('condition',(810,150));g.set_expression(cw,'moving and positive')
    g.connect(moving,cw,'moving');g.connect(direction,cw,'positive','true')
    ccw=g.add('condition',(810,320));g.set_expression(ccw,'moving and negative')
    g.connect(moving,ccw,'moving');g.connect(direction,ccw,'negative','false')
    for name,node,pos in [('at-position',zero,(1080,0)),('motor-cw',cw,(1080,170)),('motor-ccw',ccw,(1080,350))]:
        out=g.add('output',pos);g.nodes[out]['p']['name']=name;g.connect(node,out,'in','true')
    return g
