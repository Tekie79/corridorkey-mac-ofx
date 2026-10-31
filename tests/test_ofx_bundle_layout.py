"""Real Mac bundle regression: codesign alone did not prove OFX discovery."""
import ctypes
import os
from pathlib import Path
import plistlib
import sys
import pytest


@pytest.mark.skipif(sys.platform!='darwin',reason='macOS OFX bundle layout')
def test_native_bundle_executable_matches_ofx_bundle_basename():
    path=os.environ.get('CKMAC_BUILT_BUNDLE')
    if not path:pytest.skip('Set CKMAC_BUILT_BUNDLE to the native build being tested')
    bundle=Path(path)
    expected=bundle.name.removesuffix('.bundle')
    info=plistlib.loads((bundle/'Contents/Info.plist').read_bytes())
    assert info['CFBundleExecutable']==expected
    executable=bundle/'Contents/MacOS'/expected
    assert executable.is_file()
    assert {p.name for p in executable.parent.iterdir()}=={expected},'Stale native executables in generated bundle'
    class Plugin(ctypes.Structure):
        _fields_=[('api',ctypes.c_char_p),('api_version',ctypes.c_int),('identifier',ctypes.c_char_p)]
    lib=ctypes.CDLL(str(executable.resolve()))
    lib.OfxGetPlugin.restype=ctypes.POINTER(Plugin)
    assert lib.OfxGetNumberOfPlugins()==1
    assert lib.OfxGetPlugin(0).contents.identifier.decode()==info['CFBundleIdentifier']
