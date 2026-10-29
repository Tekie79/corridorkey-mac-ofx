#!/usr/bin/env python3
"""Localize native-size MPS numerical differences to actual foundation outputs."""
import json
import os
from pathlib import Path
import sys
os.environ.update(PYTORCH_ENABLE_MPS_FALLBACK='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'worker'))
import numpy as np
import torch
from PIL import Image
from ckmac.backend import CorridorKeyBackend,prepare_frame
b=CorridorKeyBackend(root/'.deps/CorridorKey2.0',root/'.build/models').load()
rgb=np.asarray(Image.open(root/'.build/fixtures/GS02-first.png').convert('RGB'),dtype=np.float32)/255
rgba=np.concatenate([rgb,np.ones((*rgb.shape[:2],1),dtype=np.float32)],axis=2)
p=prepare_frame(rgba);proxy=torch.from_numpy(p['display'].transpose(2,0,1).copy())[None]
h,w=proxy.shape[-2:]
radio=torch.nn.functional.interpolate(proxy,size=(h//4,w//4),mode='area')
moge=torch.nn.functional.interpolate(proxy,size=(h*7//32,w*7//32),mode='area')
results={}
for device in ('mps','cpu'):
    b._model.to(device);torch.set_num_threads(12)
    with torch.inference_mode():
        f=b._model.foundations(rgb_cradio=radio.to(device),rgb_moge=moge.to(device),rgb_rvm=radio[None].to(device))
    results[device]={k:v.detach().cpu().numpy().copy() for k,v in f.items() if k in ('cradio','moge','rvm')}
    print(device,{k:list(v.shape) for k,v in results[device].items()},flush=True)
record={}
for k,v in results['cpu'].items():
    delta=np.abs(results['mps'][k]-v)
    record[k]=dict(mae=float(delta.mean()),max=float(delta.max()),cpu_absmean=float(np.abs(v).mean()),shape=list(v.shape))
out=root/'.build/evidence/foundation-native-comparison.json'
out.write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2),flush=True)
