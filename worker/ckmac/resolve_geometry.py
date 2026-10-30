"""Read original media geometry through the installed, official Resolve SDK.

No image evaluation, media reopening, model imports, project edits or footage
contents. A separate bounded process avoids coupling SDK state to GPU runtime.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading

SDK_PATH=Path('/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/DaVinciResolveScript.py')


class GeometryCache:
    """Probe after Render returns, never recursively inside an OFX callback.

    Geometry belongs to the analyzed generation, and survives worker restarts
    and removal of temporary pixel blobs. New bakes carry it in their manifest.
    """
    def __init__(self,root):
        self.path=root/'source-geometry.json'
        self.lock=threading.Lock();self.pending=set()
        try:
            self.sizes=json.loads(self.path.read_text())
            if not isinstance(self.sizes,dict):self.sizes={}
        except (OSError,ValueError):self.sizes={}

    def get(self,owner,generation):
        if not isinstance(owner,str) or not isinstance(generation,str):return None
        with self.lock:return self.sizes.get(owner+':'+generation)

    def schedule(self,owner,generation):
        if not SDK_PATH.exists() or not isinstance(owner,str) or not owner or not isinstance(generation,str) or len(generation)!=64:return
        key=owner+':'+generation
        with self.lock:
            if key in self.sizes or key in self.pending:return
            self.pending.add(key)
        def probe():
            try:
                size=source_size(owner)
                if size:
                    from .generations import atomic_json
                    with self.lock:
                        self.sizes[key]=size;atomic_json(self.path,self.sizes)
            finally:
                with self.lock:self.pending.discard(key)
        timer=threading.Timer(.25,probe);timer.daemon=True;timer.start()


def query(owner):
    spec=importlib.util.spec_from_file_location('DaVinciResolveScript',SDK_PATH)
    sdk=importlib.util.module_from_spec(spec);spec.loader.exec_module(sdk)
    resolve=sys.modules['DaVinciResolveScript'].scriptapp('Resolve')
    if resolve is None:return None
    comp=resolve.Fusion().GetCurrentComp()
    if comp is None:return None
    key=None
    for tool in comp.GetToolList(False).values():
        if 'CorridorKey' in str(tool.ID) and tool.GetInput('shotUUID')==owner:key=tool;break
    if key is None:return None
    input_=key.FindMainInput(1);connection=input_.GetConnectedOutput() if input_ else None
    tool=connection.GetTool() if connection else None
    for _ in range(64):
        if tool is None:break
        attrs=tool.GetAttrs()
        w,h=attrs.get('TOOLI_Clip_Width'),attrs.get('TOOLI_Clip_Height')
        if w and h:
            w,h=int(w),int(h)
            if 0<w<=8192 and 0<h<=8192 and w*h<=33554432:return [w,h]
        input_=tool.FindMainInput(1);connection=input_.GetConnectedOutput() if input_ else None
        tool=connection.GetTool() if connection else None
    return None


def source_size(owner):
    try:
        result=subprocess.run([sys.executable,'-I','-B',str(Path(__file__).resolve()),'--owner',owner],capture_output=True,text=True,timeout=4,check=True)
        size=json.loads(result.stdout.strip().splitlines()[-1]).get('size')
        if isinstance(size,list) and len(size)==2 and all(type(v) is int and 0<v<=8192 for v in size):return size
    except (OSError,subprocess.SubprocessError,ValueError,IndexError):pass
    return None

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--owner',required=True);args=ap.parse_args()
    try:print(json.dumps(dict(size=query(args.owner))))
    except Exception as exc:print(json.dumps(dict(size=None,error=type(exc).__name__)))
