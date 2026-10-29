#!/usr/bin/env python3
"""Distinct-frame MPS sequence qualification (not a Resolve export test)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
os.environ.update(PYTORCH_ENABLE_MPS_FALLBACK='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
ap=argparse.ArgumentParser()
ap.add_argument('clip',type=Path)
ap.add_argument('--count',type=int,default=60)
ap.add_argument('--width',type=int,default=1920)
ap.add_argument('--height',type=int,default=1080)
ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args()
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'worker'))
import cv2
import numpy as np
from PIL import Image
from ckmac.backend import CorridorKeyBackend
a.output.mkdir(parents=True,exist_ok=True)
b=CorridorKeyBackend(root/'.deps/CorridorKey2.0',root/'.build/models')
t=time.perf_counter();b.load();load_seconds=time.perf_counter()-t
c=cv2.VideoCapture(str(a.clip))
frames=[];identities=set()
try:
    for i in range(a.count):
        ok,frame=c.read()
        if not ok:raise RuntimeError(f'Missing source frame {i}')
        # Explicit QA canvas: fit source into 1920x1080, with letterbox. This is
        # the requested input size, never a memory-driven inference reduction.
        h,w=frame.shape[:2];scale=min(a.width/w,a.height/h)
        new_w,new_h=round(w*scale),round(h*scale)
        rgb=cv2.resize(frame,(new_w,new_h),interpolation=cv2.INTER_AREA)[...,::-1].copy().astype(np.float32)/255
        rgba=np.zeros((a.height,a.width,4),dtype=np.float32);rgba[...,3]=1
        y,x=(a.height-new_h)//2,(a.width-new_w)//2
        rgba[y:y+new_h,x:x+new_w,:3]=rgb
        identity=hashlib.sha256(rgba.tobytes()).hexdigest();identities.add(identity)
        t=time.perf_counter();result=b.infer(rgba)
        entry=dict(frame=i,seconds=time.perf_counter()-t,input_sha256=identity,output_sha256=hashlib.sha256(result.tobytes()).hexdigest(),
            alpha_min=float(result[...,3].min()),alpha_max=float(result[...,3].max()),mps_current=b._torch.mps.current_allocated_memory(),mps_driver=b._torch.mps.driver_allocated_memory())
        frames.append(entry)
        if i in (0,29,59):
            np.save(a.output/f'frame-{i:04d}.npy',result,allow_pickle=False)
            Image.fromarray((result[...,3]*255).astype('uint8')).save(a.output/f'alpha-{i:04d}.png')
        (a.output/'progress.json').write_text(json.dumps(dict(completed=len(frames),last=entry),indent=2))
        print(f'{i+1}/{a.count}: {entry["seconds"]:.3f}s, MPS driver {entry["mps_driver"]/2**30:.2f} GiB',flush=True)
    record=dict(status='Passed',scope='direct backend only; not Resolve/Fusion/Deliver qualification',
        clip=str(a.clip),input_dimensions=[a.width,a.height],source_fit='aspect fit with black letterbox; no spatial inference proxy',
        load_seconds=load_seconds,distinct_frames=len(identities),frames=frames,backend=b.diagnostics())
except Exception as exc:
    record=dict(status='Failed',error=str(exc),frames=frames)
    raise
finally:
    c.release()
    (a.output/'sequence.json').write_text(json.dumps(record,indent=2))
