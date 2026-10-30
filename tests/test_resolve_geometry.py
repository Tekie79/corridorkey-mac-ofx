"""Metadata probing must occur after the OFX request, without model loading."""
from unittest.mock import patch,MagicMock
import sys
import pytest
from ckmac.resolve_geometry import GeometryCache,query


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
        assert len(callbacks)==1 and restarted.get('node',generation) is None
        callbacks.pop()()  # Persisted dimensions need a live owner/chain check.
        assert restarted.get('node',generation)==[4096,2160]
        assert restarted.get('other-node',generation) is None
        assert restarted.get('node','b'*64) is None
        assert cache.path.stat().st_mtime_ns==before


@pytest.mark.parametrize('replaces_module',[False,True])
def test_query_executes_sdk_without_prepopulated_public_module(tmp_path,monkeypatch,replaces_module):
    media=tmp_path/'source.mov';media.touch()
    source=MagicMock();source.ID='MediaIn';source.GetAttrs.return_value={'TOOLS_Name':'MediaIn1','TOOLI_Clip_Width':4096,'TOOLI_Clip_Height':2160,'TOOLS_Clip_Path':str(media)}
    key=MagicMock();key.ID='ofx.org.harvestpictures.CorridorKeyMac';key.GetInput.return_value='wanted-owner'
    key.FindMainInput.return_value.GetConnectedOutput.return_value.GetTool.return_value=source
    comp=MagicMock();comp.GetToolList.return_value={1:key}
    resolve=MagicMock();resolve.Fusion.return_value.GetCurrentComp.return_value=comp
    sdk=MagicMock();sdk.scriptapp.return_value=resolve
    monkeypatch.setattr('builtins._ckmac_test_sdk',sdk,raising=False)
    path=tmp_path/'sdk.py'
    path.write_text('import sys\nfrom builtins import _ckmac_test_sdk\n'+('sys.modules[__name__]=_ckmac_test_sdk\n' if replaces_module else 'def scriptapp(name): return _ckmac_test_sdk.scriptapp(name)\n'))
    monkeypatch.setattr('ckmac.resolve_geometry.SDK_PATH',path)
    monkeypatch.delitem(sys.modules,'DaVinciResolveScript',raising=False)
    assert query('wanted-owner')==[4096,2160]
    assert 'DaVinciResolveScript' not in sys.modules and '_ckmac_resolve_sdk' not in sys.modules
    assert query('different-owner') is None
    comp.GetToolList.return_value={1:key,2:key}
    assert query('wanted-owner') is None  # Never choose between duplicated IDs.
    comp.GetToolList.return_value={1:key}
    source.ID='Crop';assert query('wanted-owner') is None
    source.ID='MediaIn';source.GetAttrs.return_value['TOOLI_Clip_Aspect']=1.3
    assert query('wanted-owner') is None
    source.GetAttrs.return_value['TOOLI_Clip_Aspect']=1;media.unlink()
    assert query('wanted-owner') is None
