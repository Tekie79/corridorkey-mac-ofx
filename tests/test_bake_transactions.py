"""Faults and recovery must never delete final versions or another export."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import numpy as np
import pytest
from ckmac.bake import write_sequence
from ckmac.bake_transaction import BakeTransaction,recover_staging,TRANSACTION


def export(root):
    metadata=dict(generation='a'*64,start=0,end=1,fps=25,rgb_encoding='linear')
    return write_sequence(lambda _:np.ones((3,5,1),np.float32),2,metadata,root,'alpha','half')


@pytest.mark.parametrize('failure',['write','read','promote'])
def test_transaction_failure_cleans_only_its_staging_and_retry_works(tmp_path,failure):
    previous=Path(export(tmp_path)['manifest']);before=previous.read_bytes()
    target={'write':'ckmac.bake.exr.write','read':'ckmac.bake.exr.read','promote':'ckmac.bake_transaction.os.rename'}[failure]
    with patch(target,side_effect=OSError('simulated disk full/readback/removal')):
        with pytest.raises(OSError):export(tmp_path)
    assert not list(tmp_path.glob('.staging-*')) and previous.read_bytes()==before
    assert Path(export(tmp_path)['manifest']).exists()
    assert len(list(tmp_path.glob('bake-*')))==2


def test_active_recent_unowned_and_symlink_staging_are_never_recovered(tmp_path):
    with BakeTransaction(tmp_path) as job:
        (job.staging/'partial.exr').write_bytes(b'partial')
        report=recover_staging(tmp_path,minimum_age=0)
        assert report['skipped_active']==1 and job.staging.exists()
        unrelated=tmp_path/'.staging-unowned';unrelated.mkdir();(unrelated/'precious').touch()
        link=tmp_path/'.staging-link';link.symlink_to(unrelated,target_is_directory=True)
        report=recover_staging(tmp_path,minimum_age=0)
        assert report['refused']==2 and (unrelated/'precious').exists()
    assert not job.staging.exists() and unrelated.exists() and link.is_symlink()


def test_crash_orphan_recovery_requires_scope_age_and_released_job_lock(tmp_path):
    # Real process exit leaves an owned staging marker and releases flock.
    script='from pathlib import Path;import os;from ckmac.bake_transaction import BakeTransaction; t=BakeTransaction(Path('+repr(str(tmp_path))+')); t.__enter__(); (t.staging/"partial.exr").write_bytes(b"partial"); os._exit(0)'
    subprocess.run([sys.executable,'-B','-c',script],check=True)
    orphan=next(tmp_path.glob('.staging-*'))
    assert recover_staging(tmp_path)['skipped_recent']==1
    previous=Path(export(tmp_path)['manifest']);before=previous.read_bytes()
    report=recover_staging(tmp_path,now=time.time()+2*86400)
    assert report['removed_transactions']==1 and report['reclaimed_bytes']>7
    assert not orphan.exists() and previous.read_bytes()==before
    assert recover_staging(tmp_path,minimum_age=0)['removed_transactions']==0


def test_two_concurrent_bakes_have_independent_immutable_versions(tmp_path):
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:export(tmp_path),range(2)))
    assert len({x['manifest'] for x in results})==2
    assert not list(tmp_path.glob('.staging-*'))
    assert all(json.loads(Path(x['manifest']).read_text())['state']=='Verified' for x in results)


def test_unregistered_root_and_mismatched_transaction_are_refused(tmp_path):
    with pytest.raises(OSError):recover_staging(tmp_path)
    with BakeTransaction(tmp_path) as job:
        marker=job.staging/TRANSACTION;record=json.loads(marker.read_text());record['root']='different-root'
        marker.write_text(json.dumps(record))
        assert recover_staging(tmp_path,minimum_age=0)['refused']==1
        record['root']=json.loads((tmp_path/'.ckmac-bake-root.json').read_text())['id'];marker.write_text(json.dumps(record))
