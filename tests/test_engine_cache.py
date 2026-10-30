"""Cache routing only. These fixtures do not establish model/GPU correctness."""
import hashlib
import struct
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from ckmac.engine import Engine


def test_staged_frame_reuses_result_without_neural_work_and_invalidates(tmp_path):
    e=Engine({'build_id':'cache-routing-test','code_root':str(tmp_path),'model_root':str(tmp_path)},tmp_path)
    e.state='ready'
    calls=[]
    def infer(a,**settings):
        calls.append(a.copy())
        return a.copy()
    e.backend=SimpleNamespace(infer=infer,diagnostics=lambda:{},_model=object())
    req=dict(width=5,height=3,input_space=0,hint=False,quality=.75,despill=0,session_id='node-a')
    a=np.ones((3,5,4),dtype=np.float32)
    def stage(a):
        k=hashlib.sha256(struct.pack('>II',5,3)+a.tobytes()).hexdigest()
        e.cache.put(k,a);return k
    req['source_key']=stage(a)
    with patch('ckmac.profiles.Profile.configure'):
        np.testing.assert_array_equal(e.frame(req),a)
        assert len(calls)==1
        # Completed results can still be served after raw capture eviction.
        e.cache.remove([req['source_key']])
        np.testing.assert_array_equal(e.frame(req),a)
        assert len(calls)==1 and e.cache_hits==1
        changed=a*.5;changed[...,3]=1
        req['source_key']=stage(changed)
        np.testing.assert_array_equal(e.frame(req),changed)
        assert len(calls)==2
        req['input_space']=1
        e.frame(req)
        assert len(calls)==3
        req['source_key']='../untrusted'
        with pytest.raises(ValueError):e.frame(req)


def test_cold_cached_result_never_loads_model(tmp_path):
    e=Engine({'build_id':'lazy-test','code_root':str(tmp_path),'model_root':str(tmp_path)},tmp_path)
    e.backend=SimpleNamespace(_model=None,load=lambda:(_ for _ in ()).throw(AssertionError('cached read loaded model')))
    req=dict(width=5,height=3,input_space=1,hint=False,quality=.75,despill=0.,session_id='node-a',source_key='a'*64)
    a=np.ones((3,5,4),dtype=np.float32)
    e.cache.put(e.frame_key(req),a)
    assert e.state=='cache_ready'
    np.testing.assert_array_equal(e.frame(req),a)
    assert e.backend._model is None and e.cache_hits==1
