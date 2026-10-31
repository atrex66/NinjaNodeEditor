"""Input-only debug test worker. The Qt editor launches this as a subprocess (MIT)."""
import argparse
import json
import math
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import select
import signal
import shutil
import subprocess
import sys
import time
from hal_bindings import Catalogue,command,wiring_plan
from model import Graph

LOG=logging.getLogger('NinjaNodeEditor.live_hal')
LOG.addHandler(logging.NullHandler())

def configure_log():
    root=Path(os.environ.get('PLC_STATE_DIR') or Path(__file__).parent/'.state')
    path=(root/'logs'/'live-hal.log').resolve();path.parent.mkdir(parents=True,exist_ok=True)
    handler=RotatingFileHandler(path,maxBytes=1024*1024,backupCount=3,encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    LOG.setLevel(logging.INFO);LOG.propagate=False;LOG.addHandler(handler)
    return path,handler

def logged_command(*args):
    LOG.info('HAL command: %s',args)
    try:result=command(*args)
    except Exception:
        LOG.exception('HAL command failed');raise
    if result.strip():LOG.info('HAL response:\n%s',result.rstrip())
    return result

def install_component(source,install,emit,which=shutil.which,request_password=None):
    compiler=which('halcompile')
    if not compiler:raise RuntimeError('HAL development tool halcompile was not found.')
    argv=[compiler,'--install',str(source)]
    result=install(argv)
    permission_errors=('permission denied','operation not permitted')
    if result.returncode and any(error in result.stderr.lower() for error in permission_errors):
        sudo=which('sudo')
        if sudo:result=install([sudo,'-n',*argv])
        authentication_errors=(*permission_errors,'a password is required','a terminal is required','not allowed','not in the sudoers')
        if result.returncode and any(error in result.stderr.lower() for error in authentication_errors):
            if sudo and request_password:
                password=request_password()
                if password is None:raise RuntimeError('HAL installation authorization cancelled.')
                try:result=install([sudo,'-S','-p','',*argv],password=password)
                finally:password=None
                if result.returncode:
                    detail=(result.stderr+result.stdout).strip()
                    auth_failed=any(error in result.stderr.lower() for error in ('incorrect password','sorry, try again','no password was provided','not in the sudoers','not allowed to execute'))
                    reason='HAL installation authorization failed. Check the sudo password and installation permission.' if auth_failed else 'HAL component build/install failed after sudo authorization.'
                    raise RuntimeError(detail+'\n'+reason)
                return
            pkexec=which('pkexec')
            if not pkexec:raise RuntimeError('HAL installation requires administrator authorization. No graphical authentication tool (pkexec) is available.')
            emit('log',message='Authorize HAL installation in the system authentication window…')
            # Use the desktop agent; never read passwords from the worker's
            # stdin, which carries editor commands.
            result=install([pkexec,'--disable-internal-agent',*argv])
            if result.returncode:raise RuntimeError((result.stderr+result.stdout).strip()+'\nHAL installation authorization failed or was cancelled. A desktop polkit authentication agent is required.')
    if result.returncode:raise RuntimeError((result.stderr+result.stdout).strip()+'\nInstall needs HAL development tools and permission to install realtime modules.')

class LiveSession:
    def __init__(self,graph,component,manifest,catalogue,run=command):
        self.graph=graph;self.component=component;self.manifest=manifest;self.run=run;self.undo=[]
        self.steps=wiring_plan(graph,component,inputs_only=True,catalogue=catalogue,loggers=any(n['kind']=='logger' for n in graph.nodes.values()),path=Path(manifest['source']))
    def start(self):
        try:
            for step in self.steps:
                self.run(*step['command']);self.undo.append(step['undo'])
        except Exception as e:
            failures=self.close()
            if failures:raise RuntimeError(str(e)+' | HAL cleanup: '+'; '.join(failures)) from e
            raise
    def close(self):
        failures=[]
        for commands in reversed(self.undo):
            for args in commands:
                try:self.run(*args)
                except Exception as e:failures.append(str(e))
        self.undo=[];return failures
    def set_input(self,i,value):
        n=self.graph.nodes[i]
        if n['kind'] not in ('input','constant') or n['p'].get('hal_binding'):raise ValueError('Only unbound test inputs can be changed')
        from model import convert
        value=convert(value,n['p']['dtype'])
        if not math.isfinite(value):raise ValueError('Input value must be finite')
        self.run('setp',self.component.replace('_','-')+'.'+n['p']['name'].replace('_','-'),format(value,'.17g'))
    def sample(self,read):
        values=[dict(node=m['node'],port=m['port'],value=read(m['pin'])) for m in self.manifest['monitors']]
        inputs={str(i):read(self.component.replace('_','-')+'.'+n['p']['name'].replace('_','-')) for i,n in self.graph.nodes.items() if n['kind'] in ('input','constant')}
        return dict(event='values',values=values,inputs=inputs,time_ns=read(self.manifest['runtime_pin']),tmax_ns=read(self.manifest['max_runtime_pin']),hal_time=read(self.manifest['time_pin']),hal_tmax=read(self.manifest['tmax_param']))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('project',type=Path);parser.add_argument('component',type=Path);parser.add_argument('--base-dir',type=Path,default=Path.cwd());args=parser.parse_args()
    def emit(event,**fields):
        if event!='values':LOG.info('Event %s: %s',event,fields)
        print(json.dumps(dict(event=event,**fields),allow_nan=False),flush=True)
    try:log_path,log_handler=configure_log()
    except OSError as e:
        emit('error',message='Cannot create Live HAL log: '+str(e));emit('stopped');return
    LOG.info('Starting Live HAL test: component=%s project=%s cwd=%s',args.component,args.project,Path.cwd())
    running=True;session=None;observer=None
    def stop(*unused):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        import hal
        g=Graph.load(args.project)
        for n in g.nodes.values():
            if n['kind']=='logger':
                filename=Path(n['p']['filename']).expanduser()
                if not filename.is_absolute():n['p']['filename']=str(args.base_dir/filename)
        catalogue=Catalogue.discover(run=logged_command)
        observer=hal.component(args.component.stem+f'-view-{os.getpid()}');observer.ready()
        if hal.component_exists(args.component.stem) or hal.component_exists(args.component.stem.replace('_','-')):raise RuntimeError('Another Live HAL test is already running for this user')
        g.export(args.component,debug=True);manifest=json.loads(args.component.with_suffix('.hal.json').read_text());manifest['source']=str(args.component)
        # Validate every input against the current machine before installation/loading.
        session=LiveSession(g,args.component.stem,manifest,catalogue,run=logged_command)
        emit('log',message='Building and installing debug test component…')
        def install(argv,password=None):
            # Root cannot access a user-mounted SSHFS working directory.
            # Both normal and privileged builds run beside the temporary source.
            LOG.info('Build/install command: %s; cwd=%s',argv,args.component.resolve().parent)
            child=subprocess.Popen(argv,cwd=str(args.component.resolve().parent),stdin=subprocess.PIPE if password is not None else subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,LC_ALL='C'))
            secret=password
            pending=(password+'\n') if password is not None else None;password=None
            deadline=time.monotonic()+60
            while running and time.monotonic()<deadline:
                try:
                    stdout,stderr=child.communicate(input=pending,timeout=.1)
                    if secret:stdout=stdout.replace(secret,'[redacted]');stderr=stderr.replace(secret,'[redacted]')
                    secret=None
                    LOG.info('Build/install exit=%s\nstdout:\n%s\nstderr:\n%s',child.returncode,stdout,stderr)
                    return subprocess.CompletedProcess(argv,child.returncode,stdout,stderr)
                except subprocess.TimeoutExpired:pending=None
            child.terminate()
            try:child.communicate(timeout=3)
            except subprocess.TimeoutExpired:child.kill();child.communicate()
            raise RuntimeError('Live HAL installation cancelled or timed out')
        def request_password():
            emit('authorization')
            deadline=time.monotonic()+180;data=b''
            while running and time.monotonic()<deadline:
                if not select.select([sys.stdin],[],[],.1)[0]:continue
                chunk=os.read(sys.stdin.fileno(),65536)
                if not chunk:return None
                data+=chunk
                if b'\n' not in data:continue
                line,data=data.split(b'\n',1);reply=json.loads(line)
                if reply.get('cmd')=='authorize':return reply.get('password')
                if reply.get('cmd')=='stop':return None
            return None
        install_component(args.component,install,emit,request_password=request_password)
        if not running:return
        session.start()
        for i,n in g.nodes.items():
            if n['kind']=='input' and not n['p'].get('hal_binding'):session.set_input(i,g.resolve(n['p']['value']))
        # Wait for the first RT update, and verify the code actually loaded.
        deadline=time.monotonic()+3
        while running:
            expected=[int(manifest['fingerprint'][j*8:j*8+8],16) for j in range(4)]
            actual=[hal.get_value(args.component.stem.replace('_','-')+'.lpn-debug-id'+str(j)) for j in range(4)]
            if expected==actual:break
            if time.monotonic()>deadline:raise RuntimeError('Debug component is not executing in the selected thread')
            time.sleep(.02)
        if not running:return
        emit('ready',component=args.component.stem)
        buffer=b''
        while running:
            if select.select([sys.stdin],[],[],.05)[0]:
                data=os.read(sys.stdin.fileno(),65536)
                if not data:break
                buffer+=data
                while b'\n' in buffer:
                    line,buffer=buffer.split(b'\n',1);request=json.loads(line)
                    if request.get('cmd')=='stop':running=False;break
                    if request.get('cmd')=='set':
                        try:session.set_input(int(request['node']),request['value'])
                        except (ValueError,KeyError,RuntimeError) as e:emit('log',message=str(e))
            if running:emit(**session.sample(hal.get_value))
    except Exception as e:
        LOG.exception('Live HAL test failed')
        emit('error',message=str(e)+'\nLog file: '+str(log_path))
    finally:
        if session:
            errors=session.close()
            if errors:emit('error',message='HAL cleanup: '+'; '.join(errors)+'\nLog file: '+str(log_path))
        if observer:observer.exit()
        emit('stopped')
        LOG.removeHandler(log_handler);log_handler.close()

if __name__=='__main__':main()
