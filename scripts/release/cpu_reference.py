#!/usr/bin/env python3
"""QA-only CPU reference. Not imported or exposed by the installed GPU engine."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',XFORMERS_DISABLED='1')
ap=argparse.ArgumentParser()
ap.add_argument('--width',type=int,default=512)
ap.add_argument('--reference',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args()
root=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(root/'worker'),str(root/'.deps/CorridorKey2.0')]
import numpy as np
import torch
from PIL import Image
from ckmac.backend import prepare_frame,finish_frame
from corridorkey import runtime

# Fixed before comparison: float32 CPU/MPS tolerance, not a quality guarantee.
policy=dict(alpha_mae=0.005,alpha_p99=0.03,alpha_max=0.1,foreground_mae=0.01)
a.output.mkdir(parents=True,exist_ok=True)
(a.output/'comparison-policy.json').write_text(json.dumps(policy,indent=2))
torch.set_num_threads(12)
paths=runtime.RuntimePaths.from_package(root/'.build/models')
paths.package_root=root/'.deps/CorridorKey2.0'
model=runtime.load_model(paths,device='cpu').requires_grad_(False).eval()
runtime.configure_low_vram_inference(model,runtime.InferenceConfig())
im=Image.open(root/'.build/fixtures/GS02-first.png').convert('RGB')
if a.width:im=im.resize((a.width,round(im.height*a.width/im.width)))
rgb=np.asarray(im,dtype=np.float32)/255
rgba=np.concatenate([rgb,np.ones((*rgb.shape[:2],1),dtype=np.float32)],axis=2)
p=prepare_frame(rgba)
def tensor(x):return torch.from_numpy(x.transpose(2,0,1).copy())[None,None]
x=tensor(p['model']);hint=tensor(p['hint']);proxy=tensor(p['display'])
h,w=proxy.shape[-2:]
radio=torch.nn.functional.interpolate(proxy.flatten(0,1),size=(h//4,w//4),mode='area')[None]
moge=torch.nn.functional.interpolate(proxy.flatten(0,1),size=(h*7//32,w*7//32),mode='area')[None]
t=time.perf_counter()
with torch.inference_mode():
    o=model(rgb=x,hint=hint,rgb_cradio=radio,rgb_moge=moge,hint_quality=torch.tensor([[-1.]]),t_stride=1.)
fg=o['fg'][0,0].permute(1,2,0).numpy();alpha=o['alpha'][0,0].permute(1,2,0).numpy()
result=finish_frame(fg,alpha,p,input_space='srgb')
ref=np.load(a.reference,allow_pickle=False)
delta=np.abs(result-ref)
metrics=dict(alpha_mae=float(delta[...,3].mean()),alpha_p99=float(np.quantile(delta[...,3],.99)),alpha_max=float(delta[...,3].max()),foreground_mae=float(delta[...,:3].mean()))
record=dict(status='Passed' if all(metrics[k]<=policy[k] for k in policy) else 'Failed',policy=policy,metrics=metrics,cpu_seconds=time.perf_counter()-t,dimensions=[result.shape[1],result.shape[0]],reference=str(a.reference))
np.save(a.output/'cpu_straight.npy',result,allow_pickle=False)
Image.fromarray((result[...,3]*255).astype('uint8')).save(a.output/'cpu_alpha.png')
(a.output/'comparison.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2),flush=True)
