import os,sys,json,time
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',XFORMERS_DISABLED='1',OPENCV_IO_ENABLE_OPENEXR='1')
root=Path.cwd();sys.path[:0]=[str(root/'worker'),str(root/'.deps/CorridorKey2.0')]
import cv2,numpy as np,torch
from ckmac.backend import prepare_frame,finish_frame
from corridorkey import runtime
out=root/'.build/evidence/native-0.9.1-cpu-reference';out.mkdir(exist_ok=True)
policy=dict(alpha_mae=.005,alpha_p99=.03,alpha_max=.1,foreground_mae=.01)
(out/'policy.json').write_text(json.dumps(policy,indent=2)+'\n')
source=cv2.imread('/private/tmp/ckmac-native-qualification/gs-source/GSRaw00000030.exr',-1)[...,[2,1,0,3]].copy()
fg=cv2.imread('/private/tmp/ckmac-native-qualification/gs-source/GSStraight00000030.exr',-1)[...,[2,1,0,3]]
matte=cv2.imread('/private/tmp/ckmac-native-qualification/single/frame0030.exr',-1)[...,3:4]
reference=np.concatenate((fg[...,:3],matte),2)
torch.set_num_threads(12)
paths=runtime.RuntimePaths.from_package(root/'.build/models');paths.package_root=root/'.deps/CorridorKey2.0'
t=time.perf_counter();model=runtime.load_model(paths,device='cpu').requires_grad_(False).eval();runtime.configure_low_vram_inference(model,runtime.InferenceConfig())
load=time.perf_counter()-t;p=prepare_frame(source)
def tensor(x):return torch.from_numpy(x.transpose(2,0,1).copy())[None,None]
x=tensor(p['model']);hint=tensor(p['hint']);proxy=tensor(p['display']);h,w=proxy.shape[-2:]
radio=torch.nn.functional.interpolate(proxy.flatten(0,1),size=(h//4,w//4),mode='area')[None]
moge=torch.nn.functional.interpolate(proxy.flatten(0,1),size=(h*7//32,w*7//32),mode='area')[None]
t=time.perf_counter()
with torch.inference_mode():o=model(rgb=x,hint=hint,rgb_cradio=radio,rgb_moge=moge,hint_quality=torch.tensor([[-1.]]),t_stride=1.)
result=finish_frame(o['fg'][0,0].permute(1,2,0).numpy(),o['alpha'][0,0].permute(1,2,0).numpy(),p,input_space='srgb')
d=np.abs(result-reference)
metrics=dict(alpha_mae=float(d[...,3].mean()),alpha_p99=float(np.quantile(d[...,3],.99)),alpha_max=float(d[...,3].max()),foreground_mae=float(d[...,:3].mean()))
record=dict(status='Passed' if all(metrics[k]<=policy[k] for k in policy) else 'Failed',scope='Same-version float32 CPU QA reference against actual native Fusion input and installed MPS output; no CPU production fallback',installer_sha256='50042b7882b77913e4cdd70ac62e470aaf0afdb8778bea14e862fe1394da7b0c',dimensions=[1920,1080],policy=policy,metrics=metrics,load_seconds=load,cpu_inference_seconds=time.perf_counter()-t)
np.save(out/'cpu_straight.npy',result,allow_pickle=False);(out/'comparison.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2),flush=True)
