"""Versioned, checksummed data cache. No pickle, paths supplied by clients, or partial promotion."""
from contextlib import contextmanager
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import threading
import time
import fcntl

import numpy as np

MAGIC = b'CKCACHE3'
MAX_PIXELS = 33554432


class DiskCache:
    def __init__(self, root: Path, budget=20 * 2**30, ram_budget=512 * 2**20, temporary_root=None):
        self.root = root
        self.temporary_root = Path(temporary_root) if temporary_root is not None else root
        self.budget = budget
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.pins = {}
        self.ram_budget = ram_budget
        self.ram_bytes = 0
        self.ram = OrderedDict()
        self.verified = OrderedDict()
        self.access = OrderedDict()
        self.writer_lock = root / '.writer.lock'
        try:
            fd=os.open(self.writer_lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        except FileExistsError:pass
        self.stats=dict(ram_hits=0,disk_hits=0,metadata_hits=0,staged_bytes=0,
                        puts=0,put_dedup=0,cache_bytes_written=0,cache_bytes_evicted=0)

    @contextmanager
    def transaction(self):
        # One worker owns a cache, but also serialize diagnostic/repair clients.
        with self.lock, self.writer_lock.open('rb') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield

    def accessed(self,key):
        self.access[key]=time.monotonic_ns()
        self.access.move_to_end(key)
        while len(self.access)>16384:self.access.popitem(last=False)

    def signature(self, key):
        """Changes to file contents, replacement, truncation or removal invalidate RAM."""
        try:
            s = self.path(key).lstat()
            import stat
            if not stat.S_ISREG(s.st_mode):return None
            return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        except OSError:return None

    def _remember(self,key,signature,value):
        self.verified[key]=signature
        self.verified.move_to_end(key)
        while len(self.verified)>4096:self.verified.popitem(last=False)
        old=self.ram.pop(key,None)
        if old is not None:self.ram_bytes-=old.nbytes
        if value.nbytes<=self.ram_budget:
            value.flags.writeable=False
            self.ram[key]=value;self.ram_bytes+=value.nbytes
            while self.ram_bytes>self.ram_budget:
                _,old=self.ram.popitem(last=False);self.ram_bytes-=old.nbytes

    def valid(self,key):
        """Checksum once per immutable file version; never trust existence alone."""
        with self.lock:
            signature=self.signature(key)
            if signature is not None and self.verified.get(key)==signature:
                self.stats['metadata_hits']+=1
                return True
            return self.get(key) is not None

    def pin(self,keys):
        with self.lock:
            for k in keys:self.pins[k]=self.pins.get(k,0)+1

    def unpin(self,keys):
        with self.lock:
            for k in keys:
                self.pins[k]-=1
                if not self.pins[k]:del self.pins[k]

    def path(self, key):
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('Invalid content identity')
        return self.root / (key + '.ckf')

    def get(self, key):
        with self.lock:
            try:
                path = self.path(key)
                signature=self.signature(key)
                if signature is None:return None
                self.accessed(key)
                if signature is not None and self.verified.get(key)==signature and key in self.ram:
                    result=self.ram.pop(key);self.ram[key]=result
                    self.stats['ram_hits']+=1
                    return result
                with path.open('rb') as f:
                    if f.read(8) != MAGIC:
                        return None
                    shape_header=f.read(16)
                    h, w, size = struct.unpack('>IIQ', shape_header)
                    if not h or not w or h > 8192 or w > 8192 or h*w > MAX_PIXELS or size != h*w*16:
                        return None
                    digest = f.read(32)
                    if path.stat().st_size != size + 56:
                        return None
                    data = f.read(size)
                    checksum=hashlib.sha256(MAGIC+shape_header);checksum.update(data)
                    if checksum.digest() != digest:
                        return None
                result = np.frombuffer(data, dtype='<f4').reshape(h,w,4)
                if not np.isfinite(result).all():
                    return None
                if self.signature(key)!=signature:return None
                self._remember(key,signature,result)
                self.stats['disk_hits']+=1
                return result
            except (OSError, ValueError, struct.error):
                return None

    def put(self, key, value):
        a = np.array(value, dtype='<f4',order='C',copy=True)
        if a.ndim != 3 or a.shape[2] != 4 or min(a.shape[:2])<1 or max(a.shape[:2])>8192 or a.shape[0]*a.shape[1] > MAX_PIXELS or not np.isfinite(a).all():
            raise ValueError('Invalid cached image')
        data = memoryview(a).cast('B')
        with self.transaction():
            path = self.path(key)
            existing=self.get(key)
            if existing is not None:
                if existing.shape!=a.shape or existing.tobytes()!=a.tobytes():
                    raise ValueError('Immutable cache key already contains different pixels')
                self.stats['put_dedup']+=1
                return False
            old_size=path.stat().st_size if path.is_file() and not path.is_symlink() else 0
            self.pin([key])
            temp=None
            try:
                # A replacement must not evict its own valid previous entry.
                # Logical budget accounts for the new committed size; free disk
                # separately accommodates the full temporary write.
                self.reserve(max(0,a.nbytes+56-old_size))
                if shutil.disk_usage(self.root).free<a.nbytes+56+5*2**30:
                    raise OSError('Insufficient space for an atomic cache replacement')
                fd,temp=tempfile.mkstemp(prefix='.writing-',dir=self.root)
                with os.fdopen(fd, 'wb') as f:
                    header=MAGIC+struct.pack('>IIQ',*a.shape[:2],a.nbytes)
                    checksum=hashlib.sha256(header);checksum.update(data)
                    f.write(header+checksum.digest())
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp, path)
                directory=os.open(self.root,os.O_RDONLY)
                try:os.fsync(directory)
                finally:os.close(directory)
                self.stats['staged_bytes']+=a.nbytes
                self.stats['puts']+=1
                self.stats['cache_bytes_written']+=a.nbytes+56
                # Own immutable bytes: a caller may reuse/mutate its input array.
                stored=np.frombuffer(bytes(data),dtype='<f4').reshape(a.shape)
                self._remember(key,self.signature(key),stored)
                self.accessed(key)
                return True
            finally:
                if temp is not None:Path(temp).unlink(missing_ok=True)
                self.unpin([key])

    def reserve(self, size):
        with self.lock:self._reserve(size)

    def _reserve(self, size):
        if size > self.budget:
            raise OSError('This analysis exceeds the cache budget. Select a shorter shot range.')
        all_files=list(self.root.glob('*.ckf'))
        files = sorted((p for p in all_files if p.stem not in self.pins), key=lambda p: self.access.get(p.stem,0))
        total = sum(p.stat().st_size for p in all_files)
        while files and total + size > self.budget:
            p = files.pop(0)
            evicted_size=p.stat().st_size
            total -= evicted_size
            p.unlink(missing_ok=True)
            self.stats['cache_bytes_evicted']+=evicted_size
        if total+size>self.budget:raise OSError('Active temporal inputs occupy the cache budget; select a shorter range')
        if shutil.disk_usage(self.root).free < size + 5 * 2**30:
            raise OSError('Insufficient cache space; keep at least 5 GiB free for Resolve and macOS.')

    def remove(self,keys):
        with self.lock:
            paths=[self.path(k) for k in keys]
            if any(k in self.pins for k in keys):raise RuntimeError('Active analysis still uses this cache entry')
            count=0
            for p in paths:
                if p.exists():p.unlink();count+=1
                self.verified.pop(p.stem,None)
                value=self.ram.pop(p.stem,None)
                if value is not None:self.ram_bytes-=value.nbytes
            return count
