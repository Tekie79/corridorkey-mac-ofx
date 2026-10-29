#!/usr/bin/env python3
"""Acquire only immutable, hash-locked build inputs. Downloads never run in the installed product."""
import json
from pathlib import Path
import shutil
import sys
import tarfile
from common import ROOT,WORK,PYTHON,sha,run


def download(url,path,digest,size=None):
    if path.is_file() and sha(path)==digest and (size is None or path.stat().st_size==size):return
    path.parent.mkdir(parents=True,exist_ok=True)
    part=path.with_name(path.name+'.part')
    # Only complete verified assets resume across build stages. Partial byte
    # streams are restarted, avoiding unchecked Range/ETag assumptions.
    run('/usr/bin/curl','--fail','--location','--retry','3','--connect-timeout','30','--output',part,url)
    if sha(part)!=digest or (size is not None and part.stat().st_size!=size):
        raise RuntimeError('Publisher asset hash/size mismatch: '+url)
    part.replace(path)


def main():
    run(sys.executable,ROOT/'scripts/fetch_sources.py')
    archive=WORK/'downloads'/PYTHON['name']
    download(PYTHON['url'],archive,PYTHON['sha256'],PYTHON['size'])
    runtime=WORK/'runtime'
    if not (runtime/'bin/python3').exists():
        staging=WORK/'standalone-extraction';staging.mkdir(parents=True,exist_ok=True)
        with tarfile.open(archive) as tf:tf.extractall(staging,filter='data')
        (staging/'python').rename(runtime)
        staging.rmdir()
    wheels=WORK/'wheelhouse';wheels.mkdir(exist_ok=True)
    for wheel in (ROOT/'scripts/release/vendor-wheels').glob('*.whl'):shutil.copy2(wheel,wheels/wheel.name)
    requirements=ROOT/'scripts/release/requirements.lock'
    run(runtime/'bin/python3','-I','-m','pip','download','--require-hashes','--only-binary=:all:',
        '--find-links',ROOT/'scripts/release/vendor-wheels','--dest',wheels,'-r',requirements)
    run(runtime/'bin/python3','-I','-m','pip','install','--no-index','--require-hashes','--find-links',wheels,'-r',requirements)
    manifest=json.loads((ROOT/'scripts/release/model-lock.json').read_text())
    for asset in manifest['files']:
        p=WORK/'models'/asset['path']
        download(asset['source'],p,asset['sha256'],asset['size'])
    print('All offline inputs verified',flush=True)

if __name__=='__main__':main()
