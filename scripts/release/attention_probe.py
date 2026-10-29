#!/usr/bin/env python3
"""Validate only the scoped contiguous-query MPS adaptation against the retained CPU reference."""
import json
import os
from pathlib import Path
import sys
import time
os.environ.update(PYTORCH_ENABLE_MPS_FALLBACK='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'worker'))
import numpy as np
from PIL import Image
from ckmac.backend import CorridorKeyBackend
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mps_compat_experiment import install_contiguous_attention
b=CorridorKeyBackend(root/'.deps/CorridorKey2.0',root/'.build/models').load()
changed=install_contiguous_attention(b._model)
rgb=np.asarray(Image.open(root/'.build/fixtures/GS02-first.png').convert('RGB'),dtype=np.float32)/255
rgba=np.concatenate([rgb,np.ones((*rgb.shape[:2],1),dtype=np.float32)],axis=2)
t=time.perf_counter();output=b.infer(rgba)
ref=np.load(root/'.build/evidence/cpu-GS02-native/cpu_straight.npy',allow_pickle=False)
d=np.abs(output-ref)
policy=dict(alpha_mae=.005,alpha_p99=.03,alpha_max=.1,foreground_mae=.01)
metrics=dict(alpha_mae=float(d[...,3].mean()),alpha_p99=float(np.quantile(d[...,3],.99)),alpha_max=float(d[...,3].max()),foreground_mae=float(d[...,:3].mean()))
record=dict(status='Passed' if all(metrics[k]<=policy[k] for k in policy) else 'Failed',changed_modules=changed,
    policy=policy,metrics=metrics,seconds=time.perf_counter()-t,backend=b.diagnostics())
np.save(root/'.build/evidence/mps-contiguous-attention.npy',output,allow_pickle=False)
Image.fromarray((output[...,3]*255).astype('uint8')).save(root/'.build/evidence/mps-contiguous-attention-alpha.png')
(root/'.build/evidence/mps-contiguous-attention.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2),flush=True)
