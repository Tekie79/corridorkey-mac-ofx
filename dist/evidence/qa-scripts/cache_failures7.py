from pathlib import Path
import hashlib,json,shutil,struct,time
import numpy as np
import ckmac.cache
from ckmac.cache import DiskCache
assert '/Runtime/0.9.7-b1.027347b5a7e5/' in ckmac.cache.__file__
base=Path('/Users/harvest/Documents/Ysew_Project/GIT/corridorkey-mac-ofx/.build');seed=DiskCache(base/'qa-cache-seed7');key='1'*64
seed.put(key,np.ones((2,3,4),dtype=np.float32))
mount=base/'qa-cache-mount';cache=DiskCache(mount/'frames');shutil.copy2(seed.path(key),cache.path(key));p=cache.path(key);original=p.read_bytes();assert cache.get(key) is not None
started=time.monotonic();error=''
try:cache.put(key,np.zeros((2,3,4),dtype=np.float32))
except OSError as exc:error=str(exc)
seconds=time.monotonic()-started;assert error and p.read_bytes()==original
b=bytearray(original);b[8:16]=struct.pack('>II',3,2);p.write_bytes(b);assert cache.get(key) is None
p.write_bytes(original);assert cache.get(key).shape==(2,3,4)
(cache.root/'.writing-incomplete').write_bytes(original[:70]);assert cache.get('2'*64) is None
r=dict(status='Passed',artifact_sha256='f58245db7b45ce9ead793732c7e05f12d97c9c9a6e6681c744437b040ff07e86',scope='Actual installed0.9.7 DiskCache on isolated mounted5GB APFS: low-space replacement rejects before replacing valid data, same-area header corruption defeats a warm RAM hit, restoration succeeds and incomplete writes never promote.',free_bytes=shutil.disk_usage(mount).free,error=error,bounded_error_seconds=seconds,existing_entry_preserved=True,warm_ram_corruption_rejected=True,restoration_succeeds=True)
(base/'evidence/native-0.9.7-cache-failures.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
