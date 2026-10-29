#!/usr/bin/env python3
"""Real-MPS temporal pipeline and reverse-access probe, using the owner's clip."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
os.environ.update(PYTORCH_ENABLE_MPS_FALLBACK='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
ap=argparse.ArgumentParser();ap.add_argument('--count',type=int,default=8);ap.add_argument('--width',type=int,default=1920);ap.add_argument('--height',type=int,default=1080);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'worker'))
import cv2
import numpy as np
from PIL import Image
from ckmac.backend import CorridorKeyBackend
from ckmac.cache import DiskCache
from ckmac.temporal import TemporalProcessor
a.output.mkdir(parents=True,exist_ok=True)
cache=DiskCache(a.output/'cache');keys=[]
c=cv2.VideoCapture('/Users/harvest/Documents/Ysew_Project/Green screen/GS02.mp4')
for i in range(a.count):
    ok,bgr=c.read();assert ok
    h,w=bgr.shape[:2];scale=min(a.width/w,a.height/h);nw,nh=round(w*scale),round(h*scale)
    rgb=cv2.resize(bgr,(nw,nh),interpolation=cv2.INTER_AREA)[...,::-1].copy().astype(np.float32)/255
    rgba=np.zeros((a.height,a.width,4),dtype=np.float32);rgba[...,3]=1;y,x=(a.height-nh)//2,(a.width-nw)//2;rgba[y:y+nh,x:x+nw,:3]=rgb
    key=hashlib.sha256(rgba.tobytes()).hexdigest();cache.put(key,rgba);keys.append(key)
c.release()
b=CorridorKeyBackend(root/'.deps/CorridorKey2.0',root/'.build/models').load()
t=TemporalProcessor(b,cache,'QA-upstream-f32-v1')
s=dict(input_space='srgb',hint_mode='none',hint_quality=.95,despill_strength=0.)
started=time.perf_counter()
record=dict(status='Failed',profile='float32 continuous RVM, Hann baton window4/stride2, full-resolution stage2',dimensions=[a.width,a.height],frames=a.count)
try:
    result=t.run(keys,s,0,progress=lambda p:print(f'Progress {p:.3f}',flush=True))
    record['analysis_seconds']=time.perf_counter()-started
    marker=next(cache.root.glob('*.analysis.json'));m=json.loads(marker.read_text())
    expected=[hashlib.sha256(cache.get(k).tobytes()).hexdigest() for k in m['outputs']]
    times=[]
    for i in reversed(range(a.count)):
        started=time.perf_counter();out=t.run(keys,s,i);times.append(time.perf_counter()-started)
        assert hashlib.sha256(out.tobytes()).hexdigest()==expected[i]
    for i in (0,a.count-1):
        out=cache.get(m['outputs'][i]);np.save(a.output/f'straight-{i:04d}.npy',out,allow_pickle=False)
        Image.fromarray((out[...,3]*255).astype('uint8')).save(a.output/f'alpha-{i:04d}.png')
    record.update(status='Passed',reverse_bit_identical=True,cached_reverse_seconds=times,identity=m['identity'],backend=b.diagnostics())
finally:
    (a.output/'temporal.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2),flush=True)
