import os
os.environ.update(PYTORCH_ENABLE_MPS_FALLBACK='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OPENCV_IO_ENABLE_OPENEXR='1')
import json,pathlib,time,cv2,numpy as np
from ckmac.engine import Engine
manifest=json.loads(pathlib.Path('/Library/Application Support/HarvestPictures/CorridorKeyMac/active.json').read_text())
out=pathlib.Path('.build/evidence/native-0.9.6-memory-pressure.json')
e=Engine(manifest,pathlib.Path('/private/tmp/ckmac-native-qualification/oom-cache'));e.load()
assert e.state=='ready',e.error
original=e.backend.infer;torch=e.backend._torch;torch.mps.empty_cache()
ceiling=(torch.mps.current_allocated_memory()+2**20)/torch.mps.recommended_max_memory()
def limited(*args,**kwargs):
 torch.mps.set_per_process_memory_fraction(ceiling)
 return original(*args,**kwargs)
e.backend.infer=limited
x=cv2.imread('/private/tmp/ckmac-native-qualification/gs-source/GSRaw00000030.exr',-1);x=cv2.resize(x,(512,512))[...,[2,1,0,3]].copy();x[...,3]=1
request=dict(width=512,height=512,input_space=0,hint=False,quality=.75,despill=0,session_id='qualification-memory-pressure',profile=dict(resolution=0,window=4,memory_limit=0,low_memory=False,internal_hint_quality=.95,reference_index=0))
start=time.perf_counter();error=''
try:e.frame(request,x.astype('<f4').tobytes())
except Exception as exc:error=str(exc)
error_seconds=time.perf_counter()-start
state_after=e.state;active_after=e.active
e.backend.infer=original;torch.mps.empty_cache();start=time.perf_counter();recovered=e.frame(request,x.astype('<f4').tobytes());seconds=time.perf_counter()-start
r=dict(status='Passed' if 'out of memory' in error.lower() and state_after=='ready' and active_after==0 and np.isfinite(recovered).all() else 'Failed',artifact_sha256='7a023538ad322b9eee26357b3dd2c2aecc16c292f6feb44837e3ffa00d590c0a',scope='Installed production Engine.frame/backend MPS paths in isolated qualification process: tightened allocator ceiling induces real MPS OOM, restores normal profile and retries identical full512x512 float32 request; Resolve remains open. No production worker or source changed.',injected_allocator_fraction=ceiling,error=error[:1000],error_seconds=error_seconds,state_after_error=state_after,active_jobs_after_error=active_after,recovered_seconds=seconds,recovered_shape=list(recovered.shape),recovered_finite=bool(np.isfinite(recovered).all()),backend=e.backend.diagnostics())
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2),flush=True)
