"""Actual crash/lock recovery, node scope, retry and unknown-data protection."""
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from ckmac.cache import DiskCache
from ckmac.generations import Generations
from ckmac.temporal_scratch import scratch,clear_scratch
from ckmac.bake_transaction import BakeTransaction


def orphan(root,owner='a',generation='g'):
    script=('import os;from pathlib import Path;from ckmac.temporal_scratch import scratch;'
            f'job=scratch(Path({str(root)!r}),{owner!r},{generation!r},"test-build");'
            'p=job.__enter__();(p/"features.npz").write_bytes(b"partial features");os._exit(0)')
    subprocess.run([sys.executable,'-B','-c',script],check=True)


@pytest.mark.parametrize('fail',[False,True])
def test_normal_and_exception_paths_remove_only_their_scratch(tmp_path,fail):
    cache=DiskCache(tmp_path/'frames');unrelated=tmp_path/'source';unrelated.write_bytes(b'precious')
    try:
        with scratch(cache.root,'a','g','build') as p:
            (p/'features.npz').write_bytes(b'features')
            if fail:raise RuntimeError('model failed')
    except RuntimeError:pass
    assert not list((cache.root/'.temporal-work').glob('.staging-*'))
    assert unrelated.read_bytes()==b'precious'


def test_crashed_jobs_are_filtered_by_node_and_generation(tmp_path):
    c=DiskCache(tmp_path/'frames');orphan(c.root,'a','g1');orphan(c.root,'a','g2');orphan(c.root,'b','g1')
    answer=clear_scratch(c.root,'a','g1')
    assert answer['removed_scratch_jobs']==1 and answer['other_scratch_jobs_preserved']==2
    answer=Generations(DiskCache(c.root)).clear('a')
    assert answer['cleanup_complete'] and answer['removed_scratch_jobs']==1 and answer['reclaimed_scratch_bytes']>len(b'partial features')
    assert answer['removed_entries']==answer['reclaimed_bytes']==0 and answer['other_scratch_jobs_preserved']==1
    assert Generations(c).clear('b')['removed_scratch_jobs']==1


def test_active_scratch_is_retained_and_cleanup_cannot_claim_complete(tmp_path):
    c=DiskCache(tmp_path/'frames');r=Generations(c)
    with scratch(c.root,'a','g','build') as p:
        answer=r.clear('a')
        assert not answer['cleanup_complete'] and answer['active_scratch_jobs_preserved']==1 and p.exists()
        other=r.clear('b');assert other['cleanup_complete'] and other['other_scratch_jobs_preserved']==1
    assert r.clear('a')['cleanup_complete']


def test_legacy_and_symlink_roots_are_never_deleted(tmp_path):
    c=DiskCache(tmp_path/'frames');legacy=c.root/'.temporal-legacy';legacy.mkdir();(legacy/'features').write_bytes(b'old')
    answer=Generations(c).clear('a')
    assert not answer['cleanup_complete'] and answer['unmarked_scratch_directories_preserved']==1 and (legacy/'features').exists()
    outside=tmp_path/'outside';outside.mkdir();precious=outside/'source';precious.write_bytes(b'precious')
    (c.root/'.temporal-work').symlink_to(outside,target_is_directory=True)
    answer=Generations(c).clear('a');assert not answer['cleanup_complete'] and answer['scratch_failures']
    assert precious.read_bytes()==b'precious'


def test_failed_scratch_cleanup_is_retryable_after_restart(tmp_path):
    c=DiskCache(tmp_path/'frames');orphan(c.root)
    with patch('ckmac.bake_transaction.shutil.rmtree',side_effect=OSError('volume unavailable')):
        answer=Generations(c).clear('a');assert not answer['cleanup_complete'] and answer['removed_scratch_jobs']==0
    answer=Generations(DiskCache(c.root)).clear('a');assert answer['cleanup_complete'] and answer['removed_scratch_jobs']==1


def test_scratch_cleanup_refuses_a_durable_bake_root(tmp_path):
    c=DiskCache(tmp_path/'frames')
    with BakeTransaction(c.root/'.temporal-work') as job:
        (job.staging/'precious.exr').write_bytes(b'baked');job.promote();final=job.final/'precious.exr'
    answer=Generations(c).clear('a')
    assert not answer['cleanup_complete'] and answer['scratch_failures'] and final.read_bytes()==b'baked'
