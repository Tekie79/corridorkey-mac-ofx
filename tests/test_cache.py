from pathlib import Path
import hashlib
import tempfile
from unittest.mock import patch
import numpy as np
import pytest
from ckmac.cache import DiskCache


def test_corrupt_truncated_and_wrong_extent_are_cache_misses(tmp_path):
    c=DiskCache(tmp_path)
    key=hashlib.sha256(b'frame').hexdigest()
    a=np.full((3,5,4),.25,dtype=np.float32)
    a[0,0,0]=-2;a[0,0,1]=16
    c.put(key,a)
    np.testing.assert_array_equal(c.get(key),a)
    path=c.path(key)
    original=path.read_bytes()
    path.write_bytes(original[:-1]);assert c.get(key) is None
    path.write_bytes(original[:30]+b'Z'+original[31:]);assert c.get(key) is None
    path.write_bytes(original[:8]+b'\xff'*8+original[16:]);assert c.get(key) is None


def test_failed_atomic_promotion_preserves_old_valid_entry(tmp_path):
    c=DiskCache(tmp_path)
    key=hashlib.sha256(b'frame').hexdigest()
    a=np.ones((3,5,4),dtype=np.float32)
    c.put(key,a)
    with patch('ckmac.cache.os.replace',side_effect=OSError('simulated full disk')):
        with pytest.raises(ValueError,match='Immutable'):c.put(key,a*.5)
    np.testing.assert_array_equal(c.get(key),a)
    assert not list(tmp_path.glob('.writing-*'))


def test_nonfinite_and_untrusted_paths_never_enter_cache(tmp_path):
    c=DiskCache(tmp_path)
    with pytest.raises(ValueError):c.path('../anything')
    a=np.ones((3,5,4),dtype=np.float32);a[0,0,0]=np.nan
    with pytest.raises(ValueError):c.put('a'*64,a)
    assert not list(tmp_path.glob('*.ckf'))


def test_failed_replacement_at_budget_preserves_existing_data(tmp_path):
    c=DiskCache(tmp_path,budget=320)
    key='c'*64
    a=np.ones((3,5,4),dtype=np.float32)
    c.put(key,a)
    with patch('ckmac.cache.os.replace',side_effect=OSError('simulated write failure')):
        with pytest.raises(ValueError,match='Immutable'):c.put(key,a*.25)
    np.testing.assert_array_equal(c.get(key),a)


def test_ram_hits_still_detect_same_size_corruption_and_replacement(tmp_path):
    c=DiskCache(tmp_path)
    key='d'*64;a=np.ones((3,5,4),dtype=np.float32)
    c.put(key,a)
    assert c.valid(key)
    with patch('ckmac.cache.hashlib.sha256',side_effect=AssertionError('RAM hit rehashed pixels')):
        np.testing.assert_array_equal(c.get(key),a)
        assert c.valid(key)
    path=c.path(key);data=bytearray(path.read_bytes());data[-1]^=1
    path.write_bytes(data)
    assert not c.valid(key)
    assert c.get(key) is None
    c.put(key,a*.5)
    np.testing.assert_array_equal(c.get(key),a*.5)
    path.unlink()
    assert not c.valid(key)
    assert c.get(key) is None


def test_bounded_ram_does_not_alias_mutable_callers(tmp_path):
    c=DiskCache(tmp_path,ram_budget=240)
    a=np.ones((3,5,4),dtype=np.float32)
    c.put('a'*64,a);a[:]=2
    np.testing.assert_array_equal(c.get('a'*64),np.ones_like(a))
    assert not c.get('a'*64).flags.writeable
    c.put('b'*64,a)
    assert c.ram_bytes==240 and len(c.ram)==1
    # A validated file outside the RAM LRU can be checked without rereading it.
    with patch.object(c,'get',side_effect=AssertionError('set validation reread pixels')):
        assert c.valid('a'*64)
    np.testing.assert_array_equal(c.get('a'*64),np.ones_like(a))


@pytest.mark.parametrize('warm',[False,True])
def test_corrupt_extent_with_unchanged_area_is_a_cache_miss(tmp_path,warm):
    import struct
    c=DiskCache(tmp_path)
    key='e'*64;a=np.ones((3,5,4),dtype=np.float32)
    c.put(key,a)
    if not warm:c=DiskCache(tmp_path)
    path=c.path(key);data=bytearray(path.read_bytes())
    data[8:16]=struct.pack('>II',5,3)
    path.write_bytes(data)
    assert c.get(key) is None


def test_failed_new_atomic_write_preserves_other_valid_content(tmp_path):
    c=DiskCache(tmp_path);a=np.ones((3,5,4),np.float32)
    c.put('a'*64,a);before=c.path('a'*64).read_bytes()
    with patch('ckmac.cache.os.replace',side_effect=OSError('simulated disk failure')):
        with pytest.raises(OSError):c.put('b'*64,a*.5)
    assert c.path('a'*64).read_bytes()==before
    assert not c.path('b'*64).exists() and not list(tmp_path.glob('.writing-*'))


def test_eviction_reserves_the_incoming_size_across_multiple_smaller_entries(tmp_path):
    c=DiskCache(tmp_path,budget=800)
    small=np.ones((3,5,4),np.float32)  # 296 bytes including header.
    c.put('a'*64,small);c.put('b'*64,small)
    big=np.ones((5,8,4),np.float32)  # 696 bytes; both smaller entries must go.
    c.put('c'*64,big)
    assert [p.stem for p in tmp_path.glob('*.ckf')]==['c'*64]
    assert sum(p.stat().st_size for p in tmp_path.glob('*.ckf'))<=c.budget
    assert c.stats['cache_bytes_evicted']==592
    np.testing.assert_array_equal(c.get('c'*64),big)
    assert c.miss_reason('a'*64)=='evicted_for_cache_budget'


def test_cache_miss_causes_are_precise_without_invented_eviction_history(tmp_path):
    c=DiskCache(tmp_path);key='a'*64;a=np.ones((3,5,4),np.float32)
    assert c.miss_reason(key)=='missing_blob_cause_unknown'
    c.put(key,a);c.path(key).write_bytes(b'corrupted')
    assert c.get(key) is None and c.miss_reason(key)=='corrupt_or_invalid_blob'
    c.remove([key]);assert c.miss_reason(key)=='explicit_temporary_cleanup'
    restarted=DiskCache(tmp_path)
    assert restarted.miss_reason(key)=='missing_blob_cause_unknown'
    restarted.volume=-1;assert restarted.miss_reason(key)=='cache_volume_changed'
