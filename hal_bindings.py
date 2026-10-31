"""HAL discovery, saved bindings and reproducible wiring plans (MIT)."""
from pathlib import Path
import hashlib
import json
import math
import re
import subprocess

TYPES=('bit','float','s32','u32')
TYPE_ALIASES={'bool':'bit','real':'float','si32':'s32','ui32':'u32'}
NAME=re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.:\-\[\]]*')

def token(value):
    if not isinstance(value,str) or not NAME.fullmatch(value):raise ValueError('Invalid HAL name: '+str(value))
    return value

def number(value):
    if value.upper() in ('TRUE','FALSE'):return float(value.upper()=='TRUE')
    return float(int(value,16)) if value.lower().startswith(('0x','-0x')) else float(value)

def command(*args):
    result=subprocess.run(['halcmd',*args],capture_output=True,text=True,timeout=10)
    if result.returncode:raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'halcmd failed')
    return result.stdout

class Catalogue:
    def __init__(self,pins=(),signals=()):
        self.pins={p['name']:dict(p) for p in pins};self.signals={s['name']:dict(s) for s in signals}
        for pin in self.pins.values():
            token(pin['name']);token(pin.get('signal')) if pin.get('signal') else None
            if pin['dtype'] not in TYPES or pin['direction'] not in ('IN','OUT','IO'):raise ValueError('Invalid HAL catalogue pin')
        for sig in self.signals.values():
            token(sig['name'])
            if sig['dtype'] not in TYPES:raise ValueError('Invalid HAL catalogue signal')
            sig['pins']=[dict(p) for p in sig.get('pins',[])]
            for p in sig['pins']:
                token(p['name'])
                if p['direction'] not in ('IN','OUT','IO'):raise ValueError('Invalid HAL signal member')
    @classmethod
    def parse(cls,pin_text,signal_text):
        pins=[];signals=[]
        for line in pin_text.splitlines():
            parts=line.split()
            if len(parts)<5:continue # pin alias listings have two fields
            owner,dtype,direction,value,name,*connection=parts;dtype=TYPE_ALIASES.get(dtype,dtype)
            if dtype not in TYPES:continue
            # halcmd prints HAL_IO as "I/O"; catalogues use "IO" internally.
            direction={'I/O':'IO'}.get(direction,direction)
            if direction not in ('IN','OUT','IO'):raise ValueError('Unrecognized halcmd pin direction: '+direction+' ('+name+')')
            pins.append(dict(name=name,dtype=dtype,direction=direction,value=number(value),owner=owner,signal=connection[-1] if connection else ''))
        for line in signal_text.splitlines():
            parts=line.split()
            if len(parts)<3:continue
            dtype,value,name,*members=parts;dtype=TYPE_ALIASES.get(dtype,dtype)
            if dtype not in TYPES:continue
            if len(members)%2:raise ValueError('Unrecognized halcmd signal listing')
            directions={'<==':'OUT','==>':'IN','<=>':'IO'}
            connections=[]
            for arrow,pin in zip(members[::2],members[1::2]):
                if arrow not in directions:raise ValueError('Unrecognized HAL signal direction: '+arrow)
                connections.append(dict(name=pin,direction=directions[arrow]))
            signals.append(dict(name=name,dtype=dtype,value=number(value),pins=connections))
        return cls(pins,signals)
    @classmethod
    def discover(cls,run=command):return cls.parse(run('-s','show','pin'),run('-s','show','sig'))
    def data(self):return dict(format='NinjaNodeEditor HAL catalogue',version=1,pins=list(self.pins.values()),signals=list(self.signals.values()))
    def save(self,path):Path(path).write_text(json.dumps(self.data(),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    @classmethod
    def load(cls,path):
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data,dict) or data.get('format')!='NinjaNodeEditor HAL catalogue' or data.get('version')!=1:raise ValueError('Not a NinjaNodeEditor HAL catalogue')
        return cls(data['pins'],data['signals'])
    def binding(self,kind,name,role):
        if kind not in ('pin','signal'):raise ValueError('Invalid HAL binding kind')
        items=self.pins if kind=='pin' else self.signals
        if name not in items:raise ValueError('HAL '+kind+' not found: '+name)
        item=items[name]
        signal=item.get('signal','') if kind=='pin' else name
        if signal and signal not in self.signals:raise ValueError('Connected HAL signal missing from catalogue: '+signal)
        sig=self.signals.get(signal,{})
        members=sig.get('pins',[])
        writers=[p['name'] for p in members if p['direction'] in ('OUT','IO')]
        direction=item.get('direction','')
        if role=='input' and kind=='pin' and direction!='OUT' and not signal:raise ValueError('Input source must be an OUT pin or a connected signal')
        if role=='output' and (writers or (kind=='pin' and direction!='IN')):raise ValueError('Output target already has a writer or is not an IN pin')
        return dict(kind=kind,name=name,dtype=item['dtype'],signal=signal,direction=direction,writers=writers)


def validate_binding(binding,role,dtype):
    if not binding:return
    if not isinstance(binding,dict) or binding.get('kind') not in ('pin','signal'):raise ValueError('Invalid HAL binding')
    token(binding.get('name'))
    if binding.get('signal'):token(binding['signal'])
    if binding.get('dtype')!=dtype:raise ValueError('HAL binding type differs from node type')
    writers=binding.get('writers',[])
    if not isinstance(writers,list):raise ValueError('Invalid HAL writer list')
    for name in writers:token(name)
    if role=='output' and (writers or binding['kind']=='pin' and binding.get('direction')!='IN'):raise ValueError('Output target already has a writer or is not an IN pin')
    if role=='input' and binding['kind']=='pin' and binding.get('direction')!='OUT' and not binding.get('signal'):raise ValueError('Input source must be an OUT pin or a connected signal')


def fingerprint(graph):
    nodes={}
    for i,n in graph.nodes.items():
        p=dict(n['p'])
        if n['kind']=='input':p.pop('value',None)
        nodes[i]=dict(kind=n['kind'],p=p)
    return hashlib.sha256(json.dumps(dict(nodes=nodes,links=sorted(graph.links)),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def monitor_map(graph,component):
    prefix=component.replace('_','-');result=[]
    for i,n in graph.nodes.items():
        for port in graph.outputs(i) or (None,):
            dtype='u32' if n['kind']=='logger' else graph.dtype(i,port)
            suffix=f'debug-n{i}-{port or "value"}'
            result.append(dict(node=i,port=port,pin=prefix+'.'+suffix,suffix=suffix,dtype=dtype))
    return result


def direct_connections(graph,bindings=None):
    """External, type-preserving wires with no input/output processing."""
    bindings=bindings if bindings is not None else {i:n['p'].get('hal_binding') for i,n in graph.nodes.items()}
    result={}
    for a,source,b,port in graph.links:
        left,right=graph.nodes[a],graph.nodes[b];p,q=left['p'],right['p']
        if left['kind']!='input' or right['kind']!='output' or not bindings.get(a) or not bindings.get(b):continue
        if source!='out' or port!='in' or p['dtype']!=q['dtype']:continue
        if p['dtype']=='bit' and (p['invert'] or p['edge']!='level' or p['debounce']!=0 or q['invert'] or q['on_delay']!=0 or q['off_delay']!=0):continue
        def net(binding):return binding.get('signal') or (binding['name'] if binding['kind']=='signal' else '')
        # Existing distinct signals cannot be merged by a HAL net command.
        if net(bindings[a]) and net(bindings[b]) and net(bindings[a])!=net(bindings[b]):continue
        result[b]=a
    for a in set(result.values()):
        targets=[bindings[b] for b,src in result.items() if src==a]
        signals={net(binding) for binding in targets if net(binding)}
        if len(signals)>1:result={b:src for b,src in result.items() if src!=a}
    return result

def bypass_nodes(graph,direct=None):
    direct=direct_connections(graph) if direct is None else direct
    omitted=set(direct)
    for a in set(direct.values()):
        if all(b in direct for source,_,b,_ in graph.links if source==a):omitted.add(a)
    return omitted

def wiring_plan(graph,component,inputs_only=False,catalogue=None,loggers=False,path=None,excluded=(),preserve_inputs=False):
    """Each mutation has its own inverse, including partial-start rollback."""
    token(component)
    if component=='all':raise ValueError('Reserved HAL component name: all')
    prefix=component.replace('_','-');steps=[];nets={};output_writers={}
    def add(args,undo=()):steps.append(dict(command=list(args),undo=[list(x) for x in undo]))
    bindings={i:(catalogue.binding(n['p']['hal_binding']['kind'],n['p']['hal_binding']['name'],n['kind']) if catalogue is not None else n['p']['hal_binding']) for i,n in graph.nodes.items() if n['kind'] in ('input','output') and n['p'].get('hal_binding') and not (inputs_only and n['kind']=='output')}
    for i,binding in bindings.items():validate_binding(binding,graph.nodes[i]['kind'],graph.nodes[i]['p']['dtype'])
    direct=direct_connections(graph,bindings) if not inputs_only else {}
    omitted=(set(direct) if preserve_inputs else bypass_nodes(graph,direct))|set(excluded)
    component_required=preserve_inputs or not (direct or excluded) or any(i not in omitted for i in graph.nodes)
    if component_required:add(('loadrt',component),(('unloadrt',component),))
    source_nets={}
    for b,a in direct.items():
        left,right=bindings[a],bindings[b];dtype=graph.nodes[a]['p']['dtype']
        target_signals=[bindings[target].get('signal') or (bindings[target]['name'] if bindings[target]['kind']=='signal' else '') for target,src in direct.items() if src==a]
        preferred=next((signal for signal in target_signals if signal),'')
        net=source_nets.get(a) or left.get('signal') or (left['name'] if left['kind']=='signal' else '') or preferred or prefix+'.io-'+hashlib.sha256(left['name'].encode()).hexdigest()[:10]
        # All destinations of one source must share the same existing net.
        target_net=right.get('signal') or (right['name'] if right['kind']=='signal' else '')
        if target_net and target_net!=net:raise ValueError('Direct HAL connection cannot merge existing signals: '+net+' / '+target_net)
        if net not in nets:
            nets[net]=dtype
            existing=left.get('signal') or left['kind']=='signal' or preferred
            if not existing:add(('newsig',net,dtype),(('delsig',net),))
            if left['kind']=='pin' and not left.get('signal'):add(('net',net,left['name']),(('unlinkp',left['name']),))
        if right['kind']=='pin' and not right.get('signal'):add(('net',net,right['name']),(('unlinkp',right['name']),))
        source_nets[a]=net
    for i,n in graph.nodes.items():
        if i in omitted:continue
        p=n['p'];role=n['kind']
        if role=='constant':
            from model import convert
            add(('setp',prefix+'.'+p['name'].replace('_','-'),format(convert(p['value'],p['dtype']),'.17g')));continue
        if role not in ('input','output') or inputs_only and role=='output':continue
        binding=p.get('hal_binding')
        if not binding:
            if inputs_only and role=='input':
                from model import convert
                value=convert(graph.resolve(p['value']),p['dtype'])
                add(('setp',prefix+'.'+p['name'],format(value,'.17g')))
            continue
        binding=bindings[i]
        validate_binding(binding,role,p['dtype'])
        target=binding['name'];net=source_nets.get(i) or binding.get('signal') or (target if binding['kind']=='signal' else '')
        if not net:net=prefix+'.io-'+hashlib.sha256(target.encode()).hexdigest()[:10]
        if role=='output':
            if net in output_writers:raise ValueError('Multiple project outputs drive HAL signal: '+net)
            output_writers[net]=i
        generated=not binding.get('signal') and binding['kind']=='pin'
        if net not in nets:
            nets[net]=p['dtype']
            if generated:add(('newsig',net,p['dtype']),(('delsig',net),))
            if generated:add(('net',net,target),(('unlinkp',target),))
        elif nets[net]!=p['dtype']:raise ValueError('HAL signal type conflict: '+net)
        own=prefix+'.'+p['name']
        add(('net',net,own),(('unlinkp',own),))
    if loggers:
        def quoted(v):
            v=str(v)
            if any(c in v for c in ('"','\n','\r','\\')):raise ValueError('Unsupported Logger bundle path')
            return '"'+v+'"'
        add(('loadusr','-Wn',component+'-logger','/usr/bin/python3',str(path.with_suffix('.logger.py').resolve()),str(path.with_suffix('.logger.json').resolve())),(('unloadusr',component+'-logger'),))
    if component_required:add(('addf',prefix+'.update',graph.hal_thread),(('delf',prefix+'.update',graph.hal_thread),))
    return steps


def render_commands(commands):
    def quote(value):
        value=str(value)
        if any(c in value for c in ('\n','\r','"','\\')):raise ValueError('Unsupported HAL command argument')
        return '"'+value+'"' if any(c.isspace() for c in value) else value
    return '\n'.join(' '.join(quote(v) for v in command) for command in commands)+'\n'


def write_bundle(graph,path,debug=False):
    name=path.stem;has_loggers=any(n['kind']=='logger' for n in graph.nodes.values())
    normal=wiring_plan(graph,name,loggers=has_loggers,path=path,preserve_inputs=debug)
    test=wiring_plan(graph,name,inputs_only=True,loggers=has_loggers,path=path,excluded=() if debug else bypass_nodes(graph))
    for suffix,steps in (('.hal',normal),('.test.hal',test)):
        header='# Generated by NinjaNodeEditor. '+('Input-only live test.' if suffix=='.test.hal' else 'Project wiring.')+'\n'
        path.with_suffix(suffix).write_text(header+render_commands(s['command'] for s in steps),encoding='utf-8')
        cleanup=[u for step in reversed(steps) for u in step['undo']]
        path.with_suffix(suffix.replace('.hal','.unload.hal')).write_text('# Unload only after this project setup completed successfully.\n'+render_commands(cleanup),encoding='utf-8')
    manifest=dict(format='NinjaNodeEditor HAL export',version=1,component=name,fingerprint=fingerprint(graph),debug=debug,monitors=monitor_map(graph,name) if debug else [],time_pin=name.replace('_','-')+'.update.time',tmax_param=name.replace('_','-')+'.update.tmax',runtime_pin=name.replace('_','-')+'.lpn-debug-runtime-ns' if debug else None,max_runtime_pin=name.replace('_','-')+'.lpn-debug-max-runtime-ns' if debug else None,thread=graph.hal_thread)
    path.with_suffix('.hal.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest
