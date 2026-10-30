#!/usr/bin/env python3
"""Isolated native-host fault injection. Never used by the installed launcher.

Only an explicit same-user QA manifest is accepted. The fault file is read at
the temporal request boundary; OOM/cancel are simulated, crash exits this QA
worker, and missing_capture removes one disposable QA capture before analysis.
"""
import argparse
import json
import os
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--fault-file',type=Path,required=True)
parser.add_argument('engine_args',nargs=argparse.REMAINDER)
args=parser.parse_args();engine_args=args.engine_args
if engine_args and engine_args[0]=='--':engine_args=engine_args[1:]
manifest_path=Path(engine_args[engine_args.index('--manifest')+1]).resolve()
manifest=json.loads(manifest_path.read_text())
if '-qa-' not in manifest['build_id'] or manifest_path.stat().st_uid!=os.getuid():
    parser.error('A same-user isolated -qa- manifest is required')
if manifest_path.is_relative_to('/Library'):
    parser.error('Installed manifests cannot be used for fault injection')
qa_cache=os.environ.get('HF_HOME')
if not qa_cache or not Path(qa_cache).resolve().is_relative_to(manifest_path.parent):
    parser.error('HF_HOME must be inside this isolated QA manifest folder')
if not args.fault_file.resolve().is_relative_to(manifest_path.parent):
    parser.error('The fault file must be inside this isolated QA manifest folder')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
from ckmac.temporal import TemporalProcessor
original=TemporalProcessor.run

def faulted(self,keys,*pos,**kw):
    mode=json.loads(args.fault_file.read_text()).get('mode') if args.fault_file.exists() else None
    if mode=='oom':raise RuntimeError('QA injected MPS out-of-memory failure; no physical memory exhaustion')
    if mode=='cancel':raise RuntimeError('QA injected canceled analysis')
    if mode=='error':raise RuntimeError('QA injected temporal exception')
    if mode=='crash':os._exit(87)
    if mode=='missing_capture':self.cache.remove([keys[0]])
    return original(self,keys,*pos,**kw)

TemporalProcessor.run=faulted
from ckmac.generations import Generations
clear=Generations.clear
def faulted_clear(self,*pos,**kw):
    mode=json.loads(args.fault_file.read_text()).get('mode') if args.fault_file.exists() else None
    if mode=='cleanup_error':raise OSError('QA injected temporary-cleanup failure after verified activation')
    return clear(self,*pos,**kw)
Generations.clear=faulted_clear
sys.argv=[sys.argv[0],*engine_args]
from ckmac.engine import main
main()
