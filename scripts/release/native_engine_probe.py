"""Qualification-only inspection of the installed same-user engine (no token output)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import time

parser=argparse.ArgumentParser()
parser.add_argument('--operation',choices=('health','release'),default='health')
parser.add_argument('--output',type=Path)
args=parser.parse_args()
manifest=Path('/Library/Application Support/HarvestPictures/CorridorKeyMac/active.json')
m=json.loads(manifest.read_text())
endpoint=Path(f'/private/tmp/ckmac-{os.getuid()}')/(m['build_id']+'.sock')
request=dict(op=args.operation,token=Path(str(endpoint)+'.token').read_text(),
             build_id=m['build_id'],protocol=2,payload_bytes=0)
payload=json.dumps(request).encode()
def read(s,n):
    b=bytearray()
    while len(b)<n:
        v=s.recv(n-len(b))
        if not v:raise EOFError('Engine disconnected')
        b.extend(v)
    return bytes(b)
with socket.socket(socket.AF_UNIX) as s:
    s.settimeout(10);s.connect(str(endpoint))
    s.sendall(b'CKJ2'+struct.pack('!I',len(payload))+payload)
    size=struct.unpack('!I',read(s,4))[0]
    if size>65536:raise ValueError('Invalid response size')
    response=json.loads(read(s,size))
record=dict(observed_unix=time.time(),installed_manifest=m,response=response)
if args.output:
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(response,indent=2))
