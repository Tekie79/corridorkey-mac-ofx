import hashlib
from pathlib import Path
import sys
from unittest.mock import patch
import pytest
from ckmac.engine import Engine
from ckmac.maintenance import verify_files

def test_changed_inventory_fails_before_gpu_load(tmp_path):
    engine=Engine(dict(build_id='qualification',code_root=str(tmp_path),model_root=str(tmp_path)),tmp_path/'cache',tmp_path/'missing.json')
    with patch.object(engine.backend,'load',side_effect=AssertionError('GPU load must not start')) as load:
        engine.load()
    assert not load.called
    health=engine.health()
    assert health['state']=='error'
    assert 'CK-ASSET-INTEGRITY' in health['error']
    assert not health['fixture_passed'] and not health['model_loaded']

def test_protected_inventory_rejects_user_writable_payload(tmp_path):
    path=tmp_path/'payload';path.write_bytes(b'payload');path.chmod(0o666)
    record=dict(path=path.relative_to('/').as_posix(),size=7,sha256=hashlib.sha256(b'payload').hexdigest())
    verify_files(Path('/'),[record])
    with pytest.raises(RuntimeError,match='Missing or changed'):verify_files(Path('/'),[record],protected=True)

@pytest.mark.skipif(sys.platform!='darwin',reason='macOS root-owned system symlink')
def test_protected_symlink_uses_owner_and_target_not_meaningless_link_write_bits():
    path=Path('/var')
    assert path.is_symlink() and path.lstat().st_uid==0
    verify_files(Path('/'),[dict(path='var',symlink=str(path.readlink()))],protected=True)
