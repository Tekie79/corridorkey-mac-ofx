"""Storage/protocol contract evidence. No assertion here qualifies Resolve/MLX."""
import hashlib
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import numpy as np
import pytest
from ckmac.cache import DiskCache
from ckmac.generations import Generations,digest
from ckmac.temporal import TemporalProcessor
from ckmac.bake import bake
from ckmac import exr


def fixture(tmp_path,count=60):
    c=DiskCache(tmp_path/'frames',ram_budget=0);r=Generations(c)
    a=np.ones((3,5,4),np.float32);a[...,:3]=[-2,.125,16];a[...,3]=np.linspace(0,1,15).reshape(3,5)
    inputs=[];outputs=[]
    for i in range(count):
        k=digest(['source',i]);o=digest(['result',i]);c.put(k,a);c.put(o,a);inputs.append(k);outputs.append(o)
    identity=dict(inputs=inputs,settings=dict(input_space='linear'),provenance=dict(start=100,end=100+count-1,fps=25.,origin=[-2,3],pixel_aspect=1.))
    generation=digest(identity);r.complete(generation,identity,outputs,'node-a')
    return c,r,generation,a


def signatures(root):
    return {str(p.relative_to(root)):(p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ctime_ns,hashlib.sha256(p.read_bytes()).hexdigest()) for p in root.iterdir() if p.is_file()}


def test_60_frame_random_reverse_playback_is_read_only_across_restart(tmp_path):
    c,r,g,a=fixture(tmp_path)
    before=signatures(c.root)
    r=Generations(DiskCache(c.root,ram_budget=0))
    rng=np.random.default_rng(42)
    for order in [range(60),reversed(range(60)),rng.permutation(60)]:
        for i in order:
            r.lease('node-a',g)
            np.testing.assert_array_equal(r.result(g,int(i)),a)
    assert signatures(c.root)==before
    assert r.cache.stats['puts']==0 and r.cache.stats['disk_hits']==180


def test_eviction_and_corruption_do_not_invalidate_unrelated_completed_frame(tmp_path):
    c,r,g,a=fixture(tmp_path,4)
    record=r.record(g)
    c.remove([record['outputs'][-1]])
    np.testing.assert_array_equal(r.result(g,0),a)
    assert r.status(g)['missing']==[3]
    with pytest.raises(RuntimeError,match='Stale'):r.result(g,3)
    path=c.path(record['outputs'][1]);payload=bytearray(path.read_bytes());payload[-1]^=1;path.write_bytes(payload)
    with pytest.raises(RuntimeError,match='Stale'):r.result(g,1)
    np.testing.assert_array_equal(r.result(g,0),a)


def test_durable_cleanup_preserves_other_owner_and_markers(tmp_path):
    c,r,g,a=fixture(tmp_path,4);r.lease('node-b',g)
    r=Generations(DiskCache(c.root))
    result=r.clear('node-a',g)
    assert result['removed_entries']==0 and result['shared_entries_preserved']==8
    assert (c.root/(g+'.analysis.json')).exists()
    assert r.record(g)
    assert r.clear('node-b',g)['removed_entries']==8
    assert not list(c.root.glob('*.ckf')) and not list(c.root.glob('*.analysis.json'))


def test_concurrent_idempotent_put_and_old_timestamps_never_change(tmp_path):
    c=DiskCache(tmp_path,ram_budget=0);a=np.ones((3,5,4),np.float32);k='a'*64
    with ThreadPoolExecutor(8) as pool:assert sum(pool.map(lambda _:c.put(k,a),range(32)))==1
    p=c.path(k);os.utime(p,ns=(1_000_000_000,1_000_000_000));before=signatures(tmp_path)
    for _ in range(10):np.testing.assert_array_equal(c.get(k),a)
    assert signatures(tmp_path)==before
    assert c.stats['puts']==1 and c.stats['put_dedup']==31


@pytest.mark.parametrize('kind',['alpha','rgba'])
@pytest.mark.parametrize('precision',['half','float'])
def test_bake_exact_frames_signed_hdr_and_independent_readback(tmp_path,kind,precision):
    c,r,g,a=fixture(tmp_path,4)
    result=bake(r,g,tmp_path/'durable',kind,precision)
    path=Path(result['manifest']);assert path.exists()
    import json
    manifest=json.loads(path.read_text())
    assert manifest['start']==100 and manifest['end']==103 and manifest['fps']==25
    assert manifest['origin']==[-2,3] and manifest['pixel_aspect']==1
    assert len(manifest['files'])==4 and len(list(path.parent.glob('*.exr')))==4
    for entry in manifest['files']:
        p=path.parent/entry['name'];read,channels,types,origin=exr.read(p)
        assert channels==(['A'] if kind=='alpha' else ['A','B','G','R'])
        assert types==[1 if precision=='half' else 2]*len(channels)
        expected=a[...,3:4] if kind=='alpha' else a[...,[3,2,1,0]]
        if precision=='half':expected=expected.astype(np.float16).astype(np.float32)
        np.testing.assert_array_equal(read,expected)
        # OpenCV's independent OpenEXR decoder agrees, not just our own codec.
        os.environ['OPENCV_IO_ENABLE_OPENEXR']='1'
        import cv2
        external=cv2.imread(str(p),cv2.IMREAD_UNCHANGED)
        if kind=='rgba':np.testing.assert_array_equal(external,a[...,[2,1,0,3]].astype(np.float16).astype(np.float32) if precision=='half' else a[...,[2,1,0,3]])
    before=signatures(path.parent)
    r.clear('node-a',g)
    assert signatures(path.parent)==before
    assert not list(c.root.glob('*.ckf'))


def test_failed_bake_never_activates_or_cleans_and_previous_is_immutable(tmp_path):
    c,r,g,a=fixture(tmp_path,4)
    first=Path(bake(r,g,tmp_path/'durable','rgba')['manifest']);before=signatures(first.parent)
    with patch('ckmac.bake.exr.write',side_effect=OSError('disk full')):
        with pytest.raises(OSError):bake(r,g,tmp_path/'durable','alpha')
    assert signatures(first.parent)==before and r.status(g)['state']=='Analyzed'
    assert len(list((tmp_path/'durable').glob('bake-*')))==1


def test_half_overflow_is_refused_full_float_preserves_it(tmp_path):
    a=np.array([[[-1e7,1e10,.1,.5]]],np.float32)
    with pytest.raises(ValueError,match='overflow'):exr.write(tmp_path/'bad.exr',a)
    exr.write(tmp_path/'good.exr',a,precision='float')
    np.testing.assert_array_equal(exr.read(tmp_path/'good.exr')[0],a[...,[3,2,1,0]])


def test_temporal_cached_run_never_enters_backend_and_missing_needs_resume(tmp_path):
    from ckmac.profiles import Profile
    p=TemporalProcessor(object(),DiskCache(tmp_path),'unit')
    keys=['a'*64,'b'*64];settings=dict(input_space='linear',hint_mode='none',hint_quality=.75,despill_strength=0.)
    identity=p.identity(keys,settings);g=digest(identity);outputs=[hashlib.sha256(f'{g}:{i}'.encode()).hexdigest() for i in range(2)]
    a=np.ones((3,5,4),np.float32);p.cache.put(outputs[0],a);p.cache.put(outputs[1],a)
    p.records.complete(g,identity,outputs,'owner')
    p.cache.remove([outputs[1]])
    np.testing.assert_array_equal(p.run(keys,settings,0,owner='owner'),a)
    with pytest.raises(RuntimeError,match='Stale'):p.run(keys,settings,1,owner='owner')
    assert p.stats['analysis_starts']==0 and p.stats['result_cache_hits']==1


def test_causal_early_frame_edit_invalidates_unchanged_later_frame(tmp_path):
    from ckmac.profiles import Profile
    class ExplicitFakeCausalBackend:
        identity=dict(backend='unit-fake',precision='float32')
        def __init__(self):self.calls=0
        def analyze_ordered_shot(self,provider,count,settings,profile,write,cancel,progress,root):
            self.calls+=1;carry=0.
            for i in range(count):
                a=provider(i).copy();carry+=float(a[0,0,0]);a[...,0]=carry;write(i,a)
    c=DiskCache(tmp_path);b=ExplicitFakeCausalBackend();p=TemporalProcessor(b,c,'unit')
    a=np.ones((3,5,4),np.float32);keys=[]
    for i in range(4):
        k=digest(['input',i]);c.put(k,a);keys.append(k)
    settings=dict(input_space='linear',hint_mode='none',hint_quality=.75,despill_strength=0.)
    original=p.run(keys,settings,3,owner='owner');old=p.last_generation
    p.run(keys,settings,3,owner='owner');assert b.calls==1
    changed=a.copy();changed[...,0]=.5;k=digest('edited early frame');c.put(k,changed)
    new=p.run([k,*keys[1:]],settings,3,owner='owner')
    assert p.last_generation!=old and b.calls==2 and not np.array_equal(original,new)
    # The last source frame was identical: all earlier causal hashes matter.
    np.testing.assert_array_equal(c.get(keys[-1]),a)


def test_root_cleanup_includes_unshared_reference_passes(tmp_path):
    c,r,g,a=fixture(tmp_path,4);identity=r.record(g)['identity'];child=digest('reference-pass')
    outputs=[digest(['reference-result',i]) for i in range(4)]
    for k in outputs:c.put(k,a)
    r.complete(child,identity,outputs,'node-a')
    root=digest('root-reference');root_out=[digest(['root',i]) for i in range(4)]
    for k in root_out:c.put(k,a)
    r.complete(root,identity,root_out,'node-a',children=[child])
    r.clear('node-a',root)
    assert r.record(root) is None and r.record(child) is None
    # The separate earlier generation still owns shared captures/results.
    assert r.record(g) and all(c.valid(k) for k in r.record(g)['outputs'])


def test_reexport_scaled_alpha_after_cleanup_preserves_source_size_and_frame_mapping(tmp_path):
    from ckmac.bake import bake_from_manifest,resize_pixels
    import json
    c,r,g,a=fixture(tmp_path,4)
    original=Path(bake(r,g,tmp_path/'durable','rgba',source_size=[10,6])['manifest'])
    original_files=signatures(original.parent)
    r.clear('node-a',g)
    result=bake_from_manifest(original,tmp_path/'durable','alpha',size=[10,6],source_size=[10,6],generation=g)
    manifest=json.loads(Path(result['manifest']).read_text())
    assert manifest['width']==10 and manifest['height']==6 and manifest['source_size']==[10,6]
    assert manifest['analysis_size']==[5,3] and manifest['resampling']['applied']
    assert [e['frame'] for e in manifest['files']]==[100,101,102,103] and manifest['fps']==25
    expected=resize_pixels(a[...,3:4].astype(np.float16).astype(np.float32),[10,6]).astype(np.float16).astype(np.float32)
    for entry in manifest['files']:
        read,channels,types,origin=exr.read(Path(result['manifest']).parent/entry['name'])
        assert channels==['A'] and types==[1]
        np.testing.assert_array_equal(read,expected)
    assert signatures(original.parent)==original_files and not list(c.root.glob('*.ckf'))
    # Retain a native-size export option, without a second resample.
    native=Path(bake_from_manifest(original,tmp_path/'durable','alpha')['manifest'])
    native_manifest=json.loads(native.read_text());assert [native_manifest['width'],native_manifest['height']]==[5,3]
    assert not native_manifest['resampling']['applied']
    with pytest.raises(ValueError,match='foreground'):bake_from_manifest(native,tmp_path/'durable','rgba')


def test_rgba_scaling_resamples_linear_light_without_clipping_hdr(tmp_path):
    from ckmac.bake import resize_pixels
    from ckmac.backend import encode_output_rgb,decode_input_rgb
    a=np.array([[[-2.,16.,.2,0.],[8.,4.,-.3,1.]]],np.float32)
    encoded=np.concatenate((encode_output_rgb(a[...,:3],'srgb'),a[...,3:4]),axis=2)
    out=resize_pixels(encoded,[3,1],'srgb')
    linear=decode_input_rgb(out[...,:3],'srgb')
    np.testing.assert_allclose(linear[0,1],(a[0,0,:3]+a[0,1,:3])*.5,rtol=2e-6,atol=2e-6)
    assert out[...,0].min()<0 and out[...,1].max()>1 and out[0,1,3]==.5
    for size in ([0,1],[8192,8192],[-1,3]):
        with pytest.raises(ValueError):resize_pixels(a,size)
