"""Node-owned, locked scratch jobs; explicit clear recovers only inactive jobs."""
from contextlib import contextmanager
import os
import stat

from .bake_transaction import BakeTransaction,recover_staging

PRODUCT='org.harvestpictures.CorridorKeyMac.temporal-scratch'


def scratch_root(root):
    path=root/'.temporal-work'
    if path.exists() or path.is_symlink():
        info=path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid():raise ValueError('Unsafe temporal scratch root')
    return path


@contextmanager
def scratch(root,owner,generation,build):
    context=dict(owner=owner,generation=generation,build=build)
    with BakeTransaction(scratch_root(root),product=PRODUCT,context=context) as job:
        yield job.staging


def clear_scratch(root,owner,generation=None):
    report=dict(removed_scratch_jobs=0,reclaimed_scratch_bytes=0,active_scratch_jobs_preserved=0,
                other_scratch_jobs_preserved=0,unmarked_scratch_directories_preserved=0,scratch_failures=[])
    # Legacy folders have no durable owner/job lock. Never infer ownership from
    # their filename, even if they are in this user's cache.
    report['unmarked_scratch_directories_preserved']=sum(1 for pattern in ('.temporal-*','.mlx-features-*')
        for p in root.glob(pattern) if p.name!='.temporal-work')
    try:
        path=scratch_root(root)
        if not path.exists():return report
        context=dict(owner=owner)
        if generation is not None:context['generation']=generation
        result=recover_staging(path,minimum_age=0,product=PRODUCT,expected_context=context)
        report.update(removed_scratch_jobs=result['removed_transactions'],reclaimed_scratch_bytes=result['reclaimed_bytes'],
                      active_scratch_jobs_preserved=result['skipped_active'],other_scratch_jobs_preserved=result['skipped_scope'],scratch_failures=result['failures'])
        if result['refused']:report['scratch_failures'].append(dict(error='Unrecognized scratch transaction retained',count=result['refused']))
    except (OSError,ValueError) as exc:report['scratch_failures'].append(dict(error=str(exc)))
    return report
