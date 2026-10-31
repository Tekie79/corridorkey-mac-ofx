import hashlib
import json
import os
import sys
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '.build'
sys.path.insert(0,str(ROOT/'worker'))
from ckmac.installation import PROFILES
PROFILE = PROFILES[os.environ.get('CKMAC_BUILD_PROFILE','personal')]
PRODUCT = PROFILE.root
VERSION = '0.9.8-qa.2' if PROFILE.name=='qa' else '0.9.8-beta.2'
BUILD = VERSION
# Previous candidates are immutable, including the production beta.1.
OUT = ROOT / 'dist' / VERSION
MODEL_SET = 'ck2-cf44a8db3f02'
PYTHON = dict(name='cpython-3.12.16+20261026-aarch64-apple-darwin-install_only.tar.gz',
              sha256='fbf4afef53c2a6b72bb741bc06d5671a9dfaf87bd84e5aa73ac9b3d0d589f14e',
              size=25172086,
              url='https://github.com/astral-sh/python-build-standalone/releases/download/20261026/cpython-3.12.16%2B20261026-aarch64-apple-darwin-install_only.tar.gz')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')


def run(*args, **kw):
    print('+', ' '.join(map(str,args)),flush=True)
    return subprocess.run(list(map(str,args)),check=True,**kw)


def inventory(root):
    records=[]
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            records.append(dict(path=p.relative_to(root).as_posix(),symlink=str(p.readlink())))
        elif p.is_file():
            records.append(dict(path=p.relative_to(root).as_posix(),size=p.stat().st_size,sha256=sha(p)))
    return records


def source_identity():
    h=hashlib.sha256()
    h.update(b'CMakeLists.txt');h.update(bytes.fromhex(sha(ROOT/'CMakeLists.txt')))
    for folder in ('src','include','worker','scripts/release','cmake'):
        for p in sorted((ROOT/folder).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.whl'):
                h.update(p.relative_to(ROOT).as_posix().encode());h.update(bytes.fromhex(sha(p)))
    return h.hexdigest()
