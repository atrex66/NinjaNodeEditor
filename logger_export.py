"""Generate a bounded HAL stream and its userspace Logger collector (MIT)."""
from pathlib import Path
import json
import zlib


def prepare(loggers,name):
    if not loggers:return [],[]
    source=[];keys=set()
    for config in loggers:
        i=config['node'];key=0x4e000000 | (zlib.crc32(f'{name}:{i}'.encode()) & 0xffffff)
        if key in keys:raise ValueError('Logger stream key collision')
        keys.add(key);config.update(key=key,stream_format='fbb'+'f'*config['input_count'])
        source+= [f'static hal_stream_t lpn_stream_{i};',f'static int lpn_stream_ready_{i}=0;']
    source+=['EXTRA_CLEANUP() {']
    for config in loggers:
        i=config['node'];source.append(f'  if(lpn_stream_ready_{i}) {{hal_stream_destroy(&lpn_stream_{i});lpn_stream_ready_{i}=0;}}')
    source+=['}','EXTRA_SETUP() {','  int lpn_result;']
    for config in loggers:
        i=config['node'];depth=max(256,min(config['buffer_length']*2,16384))
        source+= [f'  lpn_result=hal_stream_create(&lpn_stream_{i},comp_id,{config["key"]},{depth},"{config["stream_format"]}");',
                  '  if(lpn_result<0) { extra_cleanup();return lpn_result; }',f'  lpn_stream_ready_{i}=1;']
    source+=['  return 0;','}']
    return ['option extra_setup yes;','option extra_cleanup yes;'],source


def realtime_body(i,p,env,cv):
    # All values fit exactly into float64, including signed/unsigned 32-bit data.
    count=p['input_count']
    code=[f'  static unsigned lpn_log_count_{i}=0;',f'  static double lpn_log_time_{i}=0,lpn_log_phase_{i}=0;',f'  static int lpn_log_prev_{i}=0;',
          f'  int lpn_log_trigger_{i}=!!({env.get("trigger","0")});',
          f'  int lpn_log_save_{i}=lpn_log_trigger_{i} && !lpn_log_prev_{i};',
          f'  lpn_log_prev_{i}=lpn_log_trigger_{i};',
          f'  double lpn_log_interval_{i}=fmax(1.0,floor({cv(p["sample_ms"])}+0.5));',
          f'  if(isfinite(dt) && dt>0) {{',f'    lpn_log_time_{i}+=dt*1000;lpn_log_phase_{i}+=dt*1000;',
          f'    int lpn_log_sample_{i}=lpn_log_phase_{i}+1e-9>=lpn_log_interval_{i};',
          f'    if(lpn_log_sample_{i} && lpn_log_count_{i}<{p["buffer_length"]}) ++lpn_log_count_{i};',f'    if(lpn_log_sample_{i}) lpn_log_phase_{i}=fmod(lpn_log_phase_{i},lpn_log_interval_{i});',
          f'    if(lpn_log_sample_{i} || lpn_log_save_{i}) {{',f'      union hal_stream_data lpn_record_{i}[{count+3}];',
          f'      lpn_record_{i}[0].f=lpn_log_time_{i};',f'      lpn_record_{i}[1].b=lpn_log_sample_{i};',f'      lpn_record_{i}[2].b=lpn_log_save_{i};']
    code += [f'      lpn_record_{i}[{j+3}].f={env.get(f"in{j+1}","0.0")};' for j in range(count)]
    code += [f'      hal_stream_write(&lpn_stream_{i},lpn_record_{i});','    }','  }']
    return code


def write_bundle(path,name,loggers):
    manifest=path.with_suffix('.logger.json')
    if not loggers:
        if manifest.exists():
            try:old=json.loads(manifest.read_text())
            except (ValueError,OSError):return
            if isinstance(old,dict) and old.get('generator')=='NinjaNodeEditor Logger' and old.get('component')==name:
                for suffix in ('.logger.py','.logger.json','.logger.hal'):path.with_suffix(suffix).unlink(missing_ok=True)
        return
    data=dict(generator='NinjaNodeEditor Logger',component=name,loggers=loggers)
    manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    helper=path.with_suffix('.logger.py');helper.write_text(Path(__file__).with_name('logger_runtime.py').read_text(),encoding='utf-8')
    def quoted(value):
        value=str(value)
        if any(c in value for c in ('"','\n','\r')):raise ValueError('Logger export path cannot contain quotes or newlines')
        return '"'+value+'"'
    setup=f'# Generated Logger setup: source this instead of duplicate loadrt/addf commands.\nloadrt {name}\nloadusr -Wn {name}-logger /usr/bin/python3 {quoted(helper.resolve())} {quoted(manifest.resolve())}\naddf {name.replace("_","-")}.update servo-thread\n'
    path.with_suffix('.logger.hal').write_text(setup,encoding='utf-8')
