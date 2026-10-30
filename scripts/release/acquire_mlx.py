#!/usr/bin/env python3
"""Build-time acquisition of a pinned FP32 profile, never installed-runtime I/O.

Downloads only into an explicit destination, verifies actual SHA-256 bytes
before atomic promotion, and retains the separate model licenses. This does
not build an installer or qualify a profile.
"""
import argparse,hashlib,json,os,urllib.request
from pathlib import Path
LOCK=Path(__file__).with_name('mlx-v2-lock.json')

def checksum(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(8*1024*1024):h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--destination',type=Path,required=True);ap.add_argument('--profile',choices=['768x1280','1024x1536'],required=True);args=ap.parse_args()
    lock=json.loads(LOCK.read_text());root=args.destination.resolve();root.mkdir(parents=True,exist_ok=True)
    entries=[x for x in lock['model_files'] if x['path'].startswith(args.profile+'-')]+lock['model_license_files']
    for e in entries:
        path=root/e['path'];path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if checksum(path)!=e['sha256']:raise RuntimeError(f'Existing asset differs: {path}')
        else:
            temp=path.with_name(path.name+'.partial')
            try:
                url=f'https://huggingface.co/{lock["model_repo"]}/resolve/{lock["model_revision"]}/{e["path"]}'
                urllib.request.urlretrieve(url,temp)
                if checksum(temp)!=e['sha256'] or ('bytes' in e and temp.stat().st_size!=e['bytes']):raise RuntimeError(f'Asset verification failed: {e["path"]}')
                os.replace(temp,path)
            finally:temp.unlink(missing_ok=True)
        print('Verified',e['path'],flush=True)
    (root/'ckmac-profile-lock.json').write_text(json.dumps(dict(profile=args.profile,model_revision=lock['model_revision'],files=entries),indent=2)+'\n')
if __name__=='__main__':main()
