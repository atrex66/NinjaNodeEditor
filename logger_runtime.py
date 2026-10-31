"""Bounded history and file writing outside the realtime thread (MIT)."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import math
import os
import re
import tempfile
import string


def validate_config(config):
    for key,low,high in (('input_count',1,18),('buffer_length',1,100000)):
        if type(config.get(key)) is not int or not low<=config[key]<=high:
            raise ValueError(f'Logger {key} must be {low}–{high}')
    interval=config.get('sample_ms')
    if type(interval) not in (int,float) or not math.isfinite(interval) or interval<1 or interval!=int(interval):
        raise ValueError('Logger sample interval must be positive whole milliseconds')
    if config.get('file_format') not in ('csv','tsv','jsonl'):
        raise ValueError('Invalid Logger file format')
    if not isinstance(config.get('number_format'),str) or not re.fullmatch(r'\.(?:[0-9]|1[0-7])[gef]',config['number_format']):
        raise ValueError('Logger number format must be .0g–.17g, .0f–.17f or .0e–.17e')
    filename=config.get('filename')
    if not isinstance(filename,str) or not filename.strip() or any(ord(c)<32 for c in filename):
        raise ValueError('Invalid Logger filename')
    try:
        for _,field,spec,conversion in string.Formatter().parse(filename):
            if field is not None and (field not in ('timestamp','sequence','node') or spec or conversion):raise ValueError('Invalid placeholder')
        filename.format(timestamp='timestamp',sequence=1,node=1)
    except (ValueError,KeyError,IndexError,AttributeError) as error:
        raise ValueError('Logger filename supports {timestamp}, {sequence} and {node}') from error


class Collector:
    def __init__(self,config):
        self.config=dict(config);self.rows=deque(maxlen=config['buffer_length']);self.sequence=0

    def accept(self,record):
        time_ms,sampled,save,*values=record
        if sampled:self.rows.append((float(time_ms),tuple(values)))
        if not save:return None
        self.sequence+=1
        return dict(config=self.config,sequence=self.sequence,rows=tuple(self.rows),trigger_ms=float(time_ms))


class SimulationLogger:
    def __init__(self,config):
        self.collector=Collector(config);self.time_ms=0.0;self.phase_ms=0.0;self.previous=False

    def step(self,dt,interval,trigger,values):
        rising=bool(trigger) and not self.previous;self.previous=bool(trigger)
        if not math.isfinite(dt) or dt<=0:return None
        self.time_ms+=dt*1000;self.phase_ms+=dt*1000
        sampled=self.phase_ms+1e-9>=interval
        if sampled:self.phase_ms=math.fmod(self.phase_ms,interval)
        return self.collector.accept((self.time_ms,sampled,rising,*values))


def write_snapshot(snapshot):
    config=snapshot['config'];timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    path=Path(config['filename'].format(timestamp=timestamp,sequence=snapshot['sequence'],node=config['node']))
    path=path.expanduser()
    if not path.is_absolute():path=Path(config.get('base_dir','.') or '.')/path
    path.parent.mkdir(parents=True,exist_ok=True)
    channels=config['channels'];number_format=config['number_format']
    temporary=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',newline='',dir=path.parent,prefix='.'+path.name+'.',delete=False) as stream:
            temporary=Path(stream.name)
            if config['file_format']=='jsonl':
                for time_ms,values in snapshot['rows']:
                    signals=[]
                    for channel,value in zip(channels,values):
                        if not math.isfinite(value):value=None
                        elif channel['dtype']!='float':value=int(value)
                        else:
                            value=float(format(value,number_format))
                            if not math.isfinite(value):value=None
                        signals.append(dict(input=channel['port'],symbol=channel['name'],type=channel['dtype'],value=value))
                    stream.write(json.dumps(dict(time_ms=time_ms,signals=signals),ensure_ascii=False,allow_nan=False)+'\n')
            else:
                writer=csv.writer(stream,delimiter='\t' if config['file_format']=='tsv' else ',')
                writer.writerow(['time_ms']+[c['port']+' = '+c['name']+' ['+c['dtype']+']' for c in channels])
                for time_ms,values in snapshot['rows']:
                    writer.writerow([format(time_ms,'.10g')]+[str(int(value)) if channel['dtype']!='float' and math.isfinite(value) else format(value,number_format) for channel,value in zip(channels,values)])
        os.replace(temporary,path)
        return path
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


class SnapshotWriter:
    """At most one in-flight snapshot per logger; collecting never waits on disk."""
    def __init__(self):
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='node-logger');self.futures={}

    def submit(self,snapshot):
        key=snapshot['config']['node']
        if key in self.futures:return False
        self.futures[key]=self.executor.submit(write_snapshot,snapshot);return True

    def poll(self):
        results=[]
        for key,future in list(self.futures.items()):
            if future.done():
                del self.futures[key]
                try:results.append((key,str(future.result()),None))
                except Exception as error:results.append((key,None,str(error)))
        return results

    def close(self):self.executor.shutdown(wait=False)


def main():
    import argparse
    import signal
    import sys
    import time
    import hal
    parser=argparse.ArgumentParser();parser.add_argument('manifest',type=Path);args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    component=hal.component(manifest['component']+'-logger')
    writer=SnapshotWriter();streams=[];running=True
    def stop(*unused):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        for config in manifest['loggers']:
            stream=hal.stream(component,config['key'],config['stream_format'])
            streams.append((stream,Collector(config)))
        component.ready()
        while running:
            for key,path,error in writer.poll():
                print(f'Logger {key}: '+(error or 'saved '+path),file=sys.stderr,flush=True)
            for stream,collector in streams:
                for _ in range(2048):
                    record=stream.read()
                    if record is None:break
                    snapshot=collector.accept(record)
                    if snapshot and not writer.submit(snapshot):
                        print('Logger save busy: snapshot skipped',file=sys.stderr,flush=True)
                lost=stream.num_overruns
                if lost!=getattr(collector,'overruns',0):
                    print(f'Logger {collector.config["node"]}: stream overruns={lost}; samples/save triggers may be lost',file=sys.stderr,flush=True)
                    collector.overruns=lost
            time.sleep(.002)
    finally:
        writer.close();streams.clear();stream=None;component.exit()


if __name__=='__main__':main()
