#!/usr/bin/env python3
"""Export a reproducible processing workload and standalone native timing harness.
The harness measures computation time, NOT HAL wakeup jitter or physical I/O.
"""
import argparse,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import Graph

def workload(repeats=8):
 g=Graph();pulse=g.add('input');g.nodes[pulse]['p'].update(name='heartbeat',dtype='bit')
 sensor=g.add('input');g.nodes[sensor]['p'].update(name='sensor',dtype='float')
 reset=g.add('input');g.nodes[reset]['p'].update(name='clear',dtype='bit')
 variants=[('latch',{}),('hysteresis',dict(low=-1,high=1)),('watchdog',dict(timeout_ms=10,latched=False)),('ramp',{}),('filter',dict(filter_mode='lowpass')),('filter',dict(filter_mode='average',window=63)),('filter',dict(filter_mode='median',window=63)),('sequencer',{})]
 for rep in range(repeats):
  module=g.add_module('Bank '+str(rep+1))
  for k,(kind,params) in enumerate(variants):
   i=g.add(kind,(k%4*430,k//4*360),module=module);g.nodes[i]['p'].update(params)
   for port in g.inputs(i):
    if port=='enable':continue
    source=reset if port=='reset' else sensor if port=='in' else pulse
    g.connect(source,i,port)
   for j,port in enumerate(g.outputs(i)):
    out=g.add('output',module=module);g.nodes[out]['p'].update(name=f'b{rep}-n{k}-o{j}',dtype=g.dtype(i,port));g.connect(i,out,'in',port)
 g.view_module=1;return g

def generate(folder,repeats):
 folder.mkdir(parents=True,exist_ok=True);g=workload(repeats);path=folder/'processing_bench.comp';g.save(folder/'processing_bench.json');g.export(path)
 header,body=path.read_text().split(';;\n',1)
 pins=re.findall(r'^pin (in|out) (bit|s32|u32|float) ([\w-]+)',header,re.M)
 code=['#define _POSIX_C_SOURCE 200809L','#include <stdint.h>','#include <stdlib.h>','#include <stdio.h>','#include <time.h>','long period=1000000;']
 for direction,t,name in pins:
  n=name.replace('-','_');typ={'bit':'int','s32':'int32_t','u32':'uint32_t','float':'double'}[t]
  code += [f'{"volatile " if direction=="out" else ""}{typ} storage_{n};',f'#define {n} (0+storage_{n})']
  if direction=='out':code += [f'#define {n}_set(v) (storage_{n}=(v))']
 code+=[body.replace('FUNCTION(update)','void update(void)'),r'''
static uint64_t ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC_RAW,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
static int compare(const void*a,const void*b){uint64_t x=*(const uint64_t*)a,y=*(const uint64_t*)b;return (x>y)-(x<y);}
int main(int argc,char **argv){
 unsigned samples=argc>1?(unsigned)strtoul(argv[1],NULL,10):60000;
 if(samples<100 || samples>10000000)return 2;
 uint64_t *times=malloc(samples*sizeof(*times));if(!times)return 3;
 uint32_t rng=123456789;long double sum=0;
 for(unsigned i=0;i<samples+1000;i++){
  rng=rng*1664525U+1013904223U;storage_sensor=((double)(rng%200001)-100000)/1000;
  storage_heartbeat=(i/3)%2;storage_clear=(i%97)==0;
  uint64_t start=ns();update();uint64_t elapsed=ns()-start;
  if(i>=1000){times[i-1000]=elapsed;sum+=elapsed;}
 }
 qsort(times,samples,sizeof(*times),compare);
 printf("{\"samples\":%u,\"warmup\":1000,\"period_ns\":1000000,\"mean_us\":%.6Lf,\"p50_us\":%.6f,\"p99_us\":%.6f,\"max_us\":%.6f}\n",samples,sum/samples/1000.0L,times[samples/2]/1000.,times[(samples*99+99)/100-1]/1000.,times[samples-1]/1000.);
 free(times);return 0;
}''']
 (folder/'processing_bench.c').write_text('\n'.join(code))
 (folder/'workload.json').write_text(json.dumps(dict(processing_nodes=repeats*8,filter_window=63,graph_nodes=len(g.nodes),metric='standalone computation duration; not wakeup jitter',period_ms=1),indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--repeats',type=int,default=8);a=p.parse_args()
 if not 1<=a.repeats<=64:p.error('repeats must be 1..64')
 generate(a.output,a.repeats)
