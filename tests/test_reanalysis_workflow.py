"""60-frame storage workflow with an explicitly fake causal neural backend.

The independent native state-machine test covers the two host captures; actual
Fusion/Deliver qualification is recorded separately, never inferred here.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from ckmac.bake import bake
from ckmac.cache import DiskCache
from ckmac.generations import digest
from ckmac.temporal import TemporalProcessor
from ckmac import exr


class FakeCausalNetwork:
    identity={'backend':'explicit-test-fake','precision':'float32'}
    def __init__(self):self.calls=0
    def analyze_ordered_shot(self,provider,count,settings,profile,write,cancel,progress,root):
        self.calls+=1;carry=0.
        for i in range(count):
            if cancel():raise RuntimeError('Test cancellation')
            value=provider(i).copy();carry+=float(value[0,0,0])
            value[...,0]=carry;value[...,3]=.5;write(i,value)


def tree_bytes(root):
    return {p.name:(p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ctime_ns,
                    hashlib.sha256(p.read_bytes()).hexdigest()) for p in root.glob('*') if p.is_file()}


def test_60_frame_reanalysis_after_bake_clean_and_causal_edit(tmp_path):
    cache=DiskCache(tmp_path/'frames',ram_budget=0);network=FakeCausalNetwork()
    processor=TemporalProcessor(network,cache,'fixed-build')
    settings=dict(input_space='linear',hint_mode='none',hint_quality=.75,despill_strength=0.)
    provenance=dict(start=30,end=89,fps=25,origin=[0,0],pixel_aspect=1.)
    frames=[np.full((3,5,4),[.1+i*.001,.8,.2,1.],np.float32) for i in range(60)]
    def stage():
        keys=[digest(['source',i,a.tobytes().hex()]) for i,a in enumerate(frames)]
        for key,value in zip(keys,frames):cache.put(key,value)
        return keys
    keys=stage()
    processor.run(keys,settings,59,owner='a',provenance=provenance)
    old=processor.last_generation
    first=Path(bake(processor.records,old,tmp_path/'durable','rgba')['manifest'])
    immutable=tree_bytes(first.parent)
    cleanup=processor.records.clear('a',old)
    assert cleanup['cleanup_complete'] and cleanup['removed_captures']==cleanup['removed_results']==60
    assert not list(cache.root.glob('*.ckf'))
    # Durable playback needs no processor/cache; signed straight RGB is retained.
    manifest=json.loads(first.read_text())
    for i in [*range(60),*reversed(range(60)),*np.random.default_rng(17).permutation(60)]:
        pixels,channels,types,origin=exr.read(first.parent/manifest['files'][int(i)]['name'])
        assert channels==['A','B','G','R'] and types==[1]*4 and np.all(pixels[...,0]==.5)
    assert network.calls==1 and tree_bytes(first.parent)==immutable
    # One early-frame edit changes every later causal output identity.
    frames[17][...,0]=.9;keys=stage()
    processor.run(keys,settings,59,owner='a',provenance=provenance,resume=True)
    revised=processor.last_generation
    assert revised!=old and network.calls==2
    assert tree_bytes(first.parent)==immutable
    record=processor.records.record(revised)
    cache.remove(record['identity']['inputs'])
    before=tree_bytes(cache.root);puts=cache.stats['puts']
    # Ordinary resume of complete results does not need input blobs or inference.
    for i in [59,0,31,17,2]:processor.run(keys,settings,i,owner='a',provenance=provenance,resume=True)
    assert network.calls==2 and cache.stats['puts']==puts and tree_bytes(cache.root)==before
    second=Path(bake(processor.records,revised,tmp_path/'durable','rgba','float')['manifest'])
    processor.records.lease('duplicate',revised)
    assert processor.records.clear('a',revised)['shared_entries_preserved']==60
    assert processor.records.clear('duplicate',revised)['removed_results']==60
    # Reopen the durable sequence after cache deletion; previous version immutable.
    reopened=json.loads(second.read_text());assert reopened['generation']==revised
    assert [e['frame'] for e in reopened['files']]==list(range(30,90)) and reopened['fps']==25
    assert exr.read(second.parent/reopened['files'][59]['name'])[2]==[2]*4
    assert tree_bytes(first.parent)==immutable and not list(cache.root.glob('*.ckf'))


@pytest.mark.parametrize('cancelled',[False,True])
def test_failed_reanalysis_preserves_previous_durable_version(tmp_path,cancelled):
    cache=DiskCache(tmp_path/'frames');network=FakeCausalNetwork()
    processor=TemporalProcessor(network,cache,'fixed-build')
    settings=dict(input_space='linear',hint_mode='none',hint_quality=.75,despill_strength=0.)
    provenance=dict(start=0,end=1,fps=25,origin=[0,0],pixel_aspect=1.)
    keys=[digest(i) for i in range(2)]
    for key in keys:cache.put(key,np.ones((3,5,4),np.float32))
    processor.run(keys,settings,0,owner='a',provenance=provenance)
    first=Path(bake(processor.records,processor.last_generation,tmp_path/'durable','rgba')['manifest'])
    immutable=tree_bytes(first.parent)
    if not cancelled:cache.remove([keys[1]])
    with pytest.raises(RuntimeError):processor.run(keys,settings,0,owner='a',revision=1,provenance=provenance,cancel=lambda:cancelled,resume=True)
    assert tree_bytes(first.parent)==immutable
