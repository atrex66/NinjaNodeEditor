"""UTF-8 UI catalogs; identifiers, formulas and saved projects stay language-neutral."""
import json
import os
from pathlib import Path
import re
import string
import tempfile
from functools import lru_cache

LANGUAGES={'en':'English','hu':'Magyar','de':'Deutsch','fr':'Français','pl':'Polski','sr':'Srpski','es':'Español'}
ROOT=Path(__file__).parent/'locales'
_language='en'
_messages={}
_patterns=[]
_prefixes=[]

def set_language(code):
    global _language,_messages,_patterns,_prefixes
    if code not in LANGUAGES:raise ValueError('Unsupported language: '+str(code))
    data=json.loads((ROOT/(code+'.json')).read_text(encoding='utf-8'))
    _messages=data['messages'];_language=code;_patterns=[]
    for source,target in _messages.items():
        if '{' not in source:continue
        parts=[];seen=set()
        for literal,name,spec,conversion in string.Formatter().parse(source):
            parts.append(re.escape(literal))
            if name is not None:
                parts.append('(?P='+name+')' if name in seen else '(?P<'+name+'>.*?)');seen.add(name)
        _patterns.append((re.compile(''.join(parts),re.DOTALL),target))
    _patterns.sort(key=lambda item:len(item[0].pattern),reverse=True)
    _prefixes=sorted((source for source in _messages if source.endswith((': ',' • '))),key=len,reverse=True)
    tr.cache_clear()

def language():return _language

@lru_cache(maxsize=4096)
def tr(text):
    text=str(text)
    if text in _messages:return _messages[text]
    for pattern,target in _patterns:
        match=pattern.fullmatch(text)
        if match:
            values=match.groupdict()
            if 'error' in values:values['error']=tr(values['error'])
            if 'kind' in values:values['kind']=tr(values['kind'])
            return target.format(**values)
    if '\n' in text:return '\n'.join(tr(line) for line in text.split('\n'))
    for source in _prefixes:
        if text.startswith(source):return _messages[source]+text[len(source):]
    return text

def settings_path():return Path(os.environ.get('PLC_STATE_DIR') or Path(__file__).parent/'.state')/'ui.json'

def preferred_language(explicit=None):
    if explicit:return explicit
    try:code=json.loads(settings_path().read_text(encoding='utf-8')).get('language','en')
    except (OSError,ValueError,AttributeError):code='en'
    return code if code in LANGUAGES else 'en'

def remember_language(code):
    if code not in LANGUAGES:raise ValueError('Unsupported language')
    path=settings_path();path.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,prefix='.ui-',delete=False) as file:
            temporary=Path(file.name);json.dump({'language':code},file)
        temporary.replace(path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
