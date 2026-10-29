#!/usr/bin/env python3
"""Run with the relocated interpreter; intentionally imports no checkout module."""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time

ap=argparse.ArgumentParser()
ap.add_argument('--root',type=Path,required=True)
ap.add_argument('--image',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args()
import numpy as np
from PIL import Image
from ckmac.backend import CorridorKeyBackend
import ckmac
assert Path(ckmac.__file__).is_relative_to(a.root/'runtime')
denied=False
with socket.socket() as s:
    s.settimeout(1)
    try:s.connect(('1.1.1.1',443))
    except OSError as e:denied=e.errno in (errno.EPERM,errno.EACCES)
assert denied,'This qualification requires outbound IP denied by the OS process sandbox'
b=CorridorKeyBackend(a.root/'runtime/upstream',a.root/'models')
im=Image.open(a.image).convert('RGB').resize((512,270))
x=np.asarray(im,dtype=np.float32)/255
rgba=np.concatenate([x,np.ones((*x.shape[:2],1),dtype=np.float32)],axis=2)
t=time.perf_counter();result=b.infer(rgba)
record=dict(status='Passed',scope='relocated standalone runtime with OS-denied outbound IP; not a clean-account Installer test',
    isolated_mode=bool(sys.flags.isolated),ckmac_module=ckmac.__file__,sys_path=sys.path,
    outbound_ip_denied=denied,dimensions=[512,270],seconds=time.perf_counter()-t,
    output_sha256=hashlib.sha256(result.tobytes()).hexdigest(),backend=b.diagnostics())
a.output.write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2),flush=True)
