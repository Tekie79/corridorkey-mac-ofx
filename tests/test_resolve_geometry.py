"""Metadata probing must occur after the OFX request, without model loading."""
from unittest.mock import patch
from ckmac.resolve_geometry import GeometryCache


def test_deferred_generation_scoped_geometry_survives_restart(tmp_path):
    callbacks=[]
    class Timer:
        def __init__(self,delay,callback):
            assert delay>0;callbacks.append(callback)
        def start(self):pass
    with patch('ckmac.resolve_geometry.SDK_PATH') as sdk,patch('ckmac.resolve_geometry.threading.Timer',Timer),patch('ckmac.resolve_geometry.source_size',return_value=[4096,2160]) as probe:
        sdk.exists.return_value=True
        cache=GeometryCache(tmp_path);generation='a'*64
        cache.schedule('node',generation);cache.schedule('node',generation)
        assert len(callbacks)==1 and not probe.called
        callbacks.pop()()
        assert probe.call_count==1 and cache.get('node',generation)==[4096,2160]
        before=cache.path.stat().st_mtime_ns
        restarted=GeometryCache(tmp_path)
        restarted.schedule('node',generation)
        assert not callbacks and restarted.get('node',generation)==[4096,2160]
        assert restarted.get('other-node',generation) is None
        assert restarted.get('node','b'*64) is None
        assert cache.path.stat().st_mtime_ns==before
