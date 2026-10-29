#!/usr/bin/env python3
"""Test packaged engine IPC with real MPS. Does not claim native supervisor/Resolve tests."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import time

ap=argparse.ArgumentParser()
ap.add_argument('--root',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args()
import numpy as np
from PIL import Image
base=a.root
work=base/'ipc-test';work.mkdir(mode=0o700,exist_ok=True)
endpoint=work/'e.sock';token=secrets.token_hex(32)
(work/'token').write_text(token);(work/'token').chmod(0o600)
manifest=dict(build_id='qa-relocated',protocol=2,code_root=str(base/'runtime/upstream'),model_root=str(base/'models'))
(work/'active.json').write_text(json.dumps(manifest))
env=dict(PATH='/usr/bin:/bin',HOME=str(Path.home()),HF_HOME=str(work/'cache/huggingface'),PYTORCH_ENABLE_MPS_FALLBACK='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
log=(work/'engine.log').open('w')
child=subprocess.Popen([str(base/'runtime/bin/python3'),'-I','-B','-u','-m','ckmac.engine','--manifest',str(work/'active.json'),'--socket',str(endpoint),'--token-file',str(work/'token')],env=env,stdout=log,stderr=subprocess.STDOUT)
def exact(c,n):
    out=bytearray()
    while len(out)<n:
        b=c.recv(n-len(out))
        if not b:raise RuntimeError('Truncated engine response')
        out.extend(b)
    return out
def request(op,payload=b'',**fields):
    msg=dict(op=op,protocol=2,build_id='qa-relocated',token=token,payload_bytes=len(payload),**fields)
    data=json.dumps(msg,allow_nan=False).encode()
    with socket.socket(socket.AF_UNIX) as c:
        c.settimeout(180)
        c.connect(str(endpoint));c.sendall(b'CKJ2'+struct.pack('>I',len(data))+data+payload)
        n=struct.unpack('>I',exact(c,4))[0];assert n<=65536
        answer=json.loads(exact(c,n))
        if not answer['ok']:raise RuntimeError(answer['error'])
        return answer,bytes(exact(c,answer['payload_bytes']))
record=dict(status='Failed',scope='real packaged Python engine IPC in a relocated directory; not installed native supervisor or Resolve')
try:
    started=time.perf_counter();states=[]
    while time.perf_counter()-started<180:
        if child.poll() is not None:raise RuntimeError('Engine exited: '+(work/'engine.log').read_text())
        if endpoint.exists():
            h,_=request('health');states.append(h['state'])
            if h['state']=='ready':break
            if h['state']=='error':raise RuntimeError(h['error'])
        time.sleep(.1)
    else:raise TimeoutError('Real engine initialization')
    im=Image.open(Path(__file__).resolve().parents[2]/'.build/fixtures/GS02-first.png').convert('RGB').resize((512,270))
    rgb=np.asarray(im,dtype=np.float32)/255
    frame=np.concatenate([rgb,np.ones((*rgb.shape[:2],1),dtype=np.float32)],axis=2).astype('<f4')
    times=[];outputs=[]
    for i in range(2):
        t=time.perf_counter();meta,data=request('frame',frame.tobytes(),width=512,height=270,input_space=0,hint=False,quality=.95,despill=0)
        times.append(time.perf_counter()-t);outputs.append(data)
    assert outputs[0]==outputs[1]
    h,_=request('health')
    assert h['fixture_passed'] and h['user_frames_completed']==1 and h['cache_hits']==1
    assert 'loading_model' in states or 'checking_gpu' in states
    request('release');child.wait(timeout=10)
    assert not endpoint.exists()
    record.update(status='Passed',states=list(dict.fromkeys(states)),startup_seconds=time.perf_counter()-started,
                  real_frame_seconds=times[0],cached_frame_seconds=times[1],cache_bit_identical=True,health=h,
                  release_exit_code=child.returncode)
finally:
    if child.poll() is None:
        child.terminate();child.wait(timeout=10)
    log.close();a.output.write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2),flush=True)
