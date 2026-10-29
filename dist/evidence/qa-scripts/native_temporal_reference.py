#!/usr/bin/env python3
"""QA-only float32 CPU execution of the pinned upstream Hann function.

The small, retained source adaptation changes CUDA contexts to CPU, and float16
disk/hint quantization to the declared float32 reference. Window/carry/taper/
baton orchestration is executed from upstream source, not the new temporal module.
"""
import difflib
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import time
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',XFORMERS_DISABLED='1')
root=Path('/Users/harvest/Documents/Ysew_Project/GIT/corridorkey-mac-ofx');sys.path[:0]=[str(root/'worker'),str(root/'.deps/CorridorKey2.0')]
import numpy as np
import torch
from ckmac.backend import prepare_frame,finish_frame
from ckmac.cache import DiskCache
from corridorkey import runtime
torch.set_num_threads(12)
out=root/'.build/evidence/native-0.9.6-temporal-reference';out.mkdir(parents=True,exist_ok=True)
policy=dict(alpha_mae=.005,alpha_p99=.03,alpha_max=.1,foreground_mae=.01)
(out/'policy.json').write_text(json.dumps(policy,indent=2))
cache=DiskCache(Path('/Users/harvest/Library/Caches/org.harvestpictures.CorridorKeyMac/frames'))
marker=cache.root/'a3bb57c2475d360f0a15f742f4e076d6d59e7e61bbf2fe0b2d69dddb6cf1a305.analysis.json';record=json.loads(marker.read_text());keys=record['identity']['inputs']
ps=[prepare_frame(cache.get(k)) for k in keys];h,w=ps[0]['model'].shape[:2];count=len(keys)
paths=runtime.RuntimePaths.from_package(root/'.build/models');paths.package_root=root/'.deps/CorridorKey2.0'
model=runtime.load_model(paths,device='cpu').requires_grad_(False).eval();runtime.configure_low_vram_inference(model,runtime.InferenceConfig())
original=inspect.getsource(runtime.hann_stage1_stream)
adapted=original.replace('with torch.autocast("cuda", dtype=torch.bfloat16):','with torch.no_grad():').replace('torch.cuda.synchronize()','pass # CPU execution is synchronous').replace('torch.cuda.empty_cache()','pass # no CUDA allocator in this reference').replace('np.float16','np.float32').replace('torch.bfloat16','torch.float32')
(out/'upstream-reference.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),adapted.splitlines(True),fromfile='pinned/runtime.py:hann_stage1_stream',tofile='QA/float32_cpu_reference')))
scope=dict(runtime.__dict__);exec(compile(adapted,'<pinned-upstream-float32-reference>','exec'),scope)
reference=scope['hann_stage1_stream'];results={}
def cpu(x):return torch.from_numpy(x.transpose(2,0,1).copy())
class Reader:
    def __init__(self,source,meta):pass
    def window(self,start,end):return torch.stack([cpu(p['model']) for p in ps[start:end]]),torch.stack([cpu(p['display']) for p in ps[start:end]]),None
    def close(self):pass
def refine(items):
    with torch.inference_mode():
        for i,baton,frame in items:
            logits=model.stage2(frame[None,None],torch.from_numpy(baton.copy())[None,None])
            if isinstance(logits,tuple):logits=logits[0]
            fg=logits[0,0,1:4].permute(1,2,0).numpy();alpha=logits[0,0,0:1].permute(1,2,0).numpy()
            results[i]=finish_frame(fg,alpha,ps[i],input_space='srgb')
start=time.perf_counter()
with tempfile.TemporaryDirectory(prefix='cpu-reference-',dir=out) as tmp:
    tmp=Path(tmp);features=[];state=None
    with torch.inference_mode():
        for p in ps:
            proxy=cpu(p['display'])[None]
            radio=torch.nn.functional.interpolate(proxy,size=(h//4,w//4),mode='area')
            moge=torch.nn.functional.interpolate(proxy,size=(h*7//32,w*7//32),mode='area')
            rvm=torch.nn.functional.interpolate(proxy,size=(h//4,w//4),mode='bilinear',align_corners=False)[None]
            f=model.foundations(rgb_cradio=radio,rgb_moge=moge,rgb_rvm=rvm,rvm_state=state);state=f['rvm_state']
            features.append({k:v.numpy().copy() for k,v in f.items() if k in ('cradio','moge','rvm')})
    foundation_paths={}
    for k in ('cradio','moge','rvm'):
        values=np.concatenate([v[k] for v in features],axis=0).astype(np.float32);path=tmp/(k+'.f32');values.tofile(path)
        if k!='rvm':foundation_paths[k]=str(path);foundation_paths[k+'_shape']=values.shape
    reference(model,'owned host fixtures',dict(num_frames=count,shape_hw=(h,w)),reader_cls=Reader,reader_kind='frame_dir',chunk=8,stride=4,baton_path=tmp/'baton.f32',initial_hint=None,initial_hint_quality=.95,full_hint_video_path=None,full_hint_quality=.95,rvm_path=tmp/'rvm.f32',foundation_paths=foundation_paths,carry_hint_from_aux=True,carry_hint_quality=.95,on_baton_frames=refine)
metrics=[]
for i in range(count):
    gpu=cache.get(record['outputs'][i]);d=np.abs(gpu-results[i]);m=dict(frame=i,alpha_mae=float(d[...,3].mean()),alpha_p99=float(np.quantile(d[...,3],.99)),alpha_max=float(d[...,3].max()),foreground_mae=float(d[...,:3].mean()));metrics.append(m)
    np.save(out/f'cpu-{i:04d}.npy',results[i],allow_pickle=False)
answer=dict(status='Passed' if all(m[k]<=policy[k] for m in metrics for k in policy) else 'Failed',policy=policy,metrics=metrics,seconds=time.perf_counter()-start,upstream_function_sha256=hashlib.sha256(original.encode()).hexdigest(),declared_variant='float32 CPU; same upstream window/carry/taper/baton order; no half/bfloat16 quantization')
(out/'comparison.json').write_text(json.dumps(answer,indent=2));print(json.dumps(answer,indent=2),flush=True)
