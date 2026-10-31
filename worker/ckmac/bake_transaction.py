"""Owned export/scratch transactions and scoped inactive-job recovery."""
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import shutil
import stat
import time
import uuid
from .generations import atomic_json

PRODUCT='org.harvestpictures.CorridorKeyMac.bake'
ROOT_MARKER='.ckmac-bake-root.json'
TRANSACTION='.ckmac-transaction.json'


def owned_file(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o022 or info.st_size>4096:
            raise ValueError('Unsafe bake ownership record')
        with os.fdopen(fd) as stream:fd=None;return json.load(stream)
    finally:
        if fd is not None:os.close(fd)


@contextmanager
def root_lock(root,create=False):
    fd=os.open(root/'.ckmac-bake.lock',os.O_RDWR|os.O_NOFOLLOW|(os.O_CREAT if create else 0),0o600)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o022:raise ValueError('Unsafe bake destination lock')
        fcntl.flock(fd,fcntl.LOCK_EX)
        yield
    finally:os.close(fd)


def root_record(root,product=PRODUCT):
    record=owned_file(root/ROOT_MARKER)
    if record.get('product')!=product or record.get('version')!=1 or record.get('uid')!=os.getuid():raise ValueError('Destination is not a registered product folder')
    return record


def transaction_record(path,root):
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid():raise ValueError('Unsafe staging directory')
    record=owned_file(path/TRANSACTION)
    ident=record.get('id','')
    if len(ident)!=32 or any(c not in '0123456789abcdef' for c in ident) or path.name!='.staging-'+ident:
        raise ValueError('Staging transaction identity mismatch')
    if record.get('product')!=root['product'] or record.get('uid')!=os.getuid() or record.get('root')!=root['id']:
        raise ValueError('Staging ownership mismatch')
    return record


class BakeTransaction:
    def __init__(self,destination,*,product=PRODUCT,context=None):
        self.root=Path(destination).resolve();self.id=uuid.uuid4().hex
        self.staging=self.root/('.staging-'+self.id);self.final=self.root/('bake-'+self.id)
        self.active=None;self.promoted=False
        self.product=product;self.context=context

    def __enter__(self):
        self.root.mkdir(parents=True,exist_ok=True)
        with root_lock(self.root,True):
            if not (self.root/ROOT_MARKER).exists():
                atomic_json(self.root/ROOT_MARKER,dict(product=self.product,version=1,uid=os.getuid(),id=uuid.uuid4().hex))
            root=root_record(self.root,self.product)
            self.staging.mkdir(mode=0o700)
            try:
                self.active=os.open(self.staging/'.active.lock',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                fcntl.flock(self.active,fcntl.LOCK_EX)
                record=dict(product=self.product,version=1,uid=os.getuid(),root=root['id'],id=self.id,created=time.time())
                if self.context is not None:record['context']=self.context
                atomic_json(self.staging/TRANSACTION,record)
            except BaseException:
                if self.active is not None:os.close(self.active);self.active=None
                shutil.rmtree(self.staging);raise
        return self

    def promote(self):
        with root_lock(self.root):
            transaction_record(self.staging,root_record(self.root,self.product))
            if self.final.exists():raise FileExistsError('Immutable bake version already exists')
            os.rename(self.staging,self.final);self.promoted=True
            fd=os.open(self.root,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)

    def __exit__(self,kind,error,tb):
        try:
            if not self.promoted:
                try:
                    with root_lock(self.root):
                        transaction_record(self.staging,root_record(self.root,self.product))
                        shutil.rmtree(self.staging)
                except (OSError,ValueError) as cleanup:
                    if error is None:raise
                    error.add_note('Temporary job could not be removed; reconnect storage and retry cleanup: '+str(cleanup))
        finally:
            if self.active is not None:os.close(self.active)


def recover_staging(destination,minimum_age=24*3600,now=None,*,product=PRODUCT,expected_context=None):
    """Remove only old, unlocked, same-user transactions in a registered root.

    Unmarked legacy directories and symlinks are refused. Final bake-* versions
    are never considered, including a verified version not yet host-activated.
    """
    if not math.isfinite(minimum_age) or minimum_age<0:raise ValueError('Recovery age must be finite and nonnegative')
    root=Path(destination).resolve();now=time.time() if now is None else now
    report=dict(removed_transactions=0,reclaimed_bytes=0,skipped_active=0,skipped_recent=0,skipped_scope=0,refused=0,failures=[])
    with root_lock(root):
        owner=root_record(root,product)
        for path in root.glob('.staging-*'):
            active=None
            try:
                record=transaction_record(path,owner)
                if expected_context is not None:
                    if not isinstance(record.get('context'),dict):report['refused']+=1;continue
                    if any(record['context'].get(k)!=v for k,v in expected_context.items()):report['skipped_scope']+=1;continue
                active=os.open(path/'.active.lock',os.O_RDWR|os.O_NOFOLLOW)
                lock_stat=os.fstat(active)
                if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid!=os.getuid():raise ValueError('Unsafe transaction lock')
                try:fcntl.flock(active,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:report['skipped_active']+=1;continue
                if not isinstance(record.get('created'),(int,float)) or not math.isfinite(record['created']):raise ValueError('Invalid staging age')
                latest=max(record['created'],path.stat().st_mtime)
                if now-latest<minimum_age:report['skipped_recent']+=1;continue
                # Recheck the scope while holding both root and job locks.
                transaction_record(path,owner)
                size=sum(p.lstat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink())
                shutil.rmtree(path);report['removed_transactions']+=1;report['reclaimed_bytes']+=size
            except (ValueError,KeyError,TypeError):report['refused']+=1
            except FileNotFoundError:report['refused']+=1
            except OSError as exc:report['failures'].append(dict(transaction=path.name,error=str(exc)))
            finally:
                if active is not None:os.close(active)
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--older-than-hours',type=float,default=24)
    args=parser.parse_args()
    print(json.dumps(recover_staging(args.destination,args.older_than_hours*3600),indent=2))
