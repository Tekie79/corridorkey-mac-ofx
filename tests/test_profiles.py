import numpy as np
import pytest
from ckmac.profiles import Profile

def test_explicit_profiles_restore_host_geometry_without_clipping_light():
    a=np.ones((9,17,4),np.float32);a[...,:3]=[-2,16,.5]
    p=Profile(resolution=2)
    small=p.resize(a,'linear');assert small.shape==(4,8,4)
    restored=p.restore(small,a.shape[:2],'linear')
    assert restored.shape==a.shape
    np.testing.assert_allclose(restored,a,rtol=1e-6,atol=1e-6)

def test_display_profiles_filter_in_linear_light_and_align_alpha():
    a=np.array([[[0,0,0,0],[1,1,1,1]],[[0,0,0,0],[1,1,1,1]]],np.float32)
    b=Profile(resolution=2).resize(a,'srgb')
    np.testing.assert_allclose(b[0,0,:3],.73535698,atol=1e-6)
    assert b[0,0,3]==.5

def test_unqualified_native_4k_is_refused_and_quality_changes_are_explicit():
    with pytest.raises(ValueError,match='never silently reduced'):Profile().dimensions(2160,3840)
    assert Profile(resolution=2).dimensions(2160,3840)==(1080,1920)

@pytest.mark.parametrize('value',[{'window':0},{'window':49},{'window':True},{'resolution':4},{'memory_limit':6},{'low_memory':1},{'internal_hint_quality':float('nan')}])
def test_invalid_profiles_are_rejected_before_inference(value):
    with pytest.raises(ValueError):Profile.from_request({'profile':value})

def test_reference_hint_window_one_is_rejected_before_network_access():
    from ckmac.temporal import TemporalProcessor
    processor=TemporalProcessor(None,None,'test')
    with pytest.raises(ValueError,match='Window of 2'):
        processor.run(['a'*64,'b'*64],{'hint_mode':'source_alpha'},1,first_hint=True,profile=Profile(window=1))
