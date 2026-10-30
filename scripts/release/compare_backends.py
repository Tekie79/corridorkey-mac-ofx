#!/usr/bin/env python3
"""Run in an isolated process per backend; same .npy owned frame inputs/settings.

This is native neural/float evidence, not Resolve or installer qualification.
Thresholds are declared before measurements in docs/development/MLX_CACHE_BAKE.md.
"""
import argparse,json,os,sys,time,resource,hashlib,ctypes,threading
from pathlib import Path
os.environ.update(PYTORCH_ENABLE_MPS_FALLBACK='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--backend',choices=['mps','mlx_v2'],required=True);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--temporal',action='store_true');args=ap.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
from ckmac.backends import create_backend
from ckmac.profiles import Profile
manifest=json.loads(args.manifest.read_text());manifest['backend']=args.backend
b=create_backend(manifest)
record=dict(backend=args.backend,status='Failed',source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),thresholds=dict(alpha_mae=.001,alpha_p99=.01,alpha_max=.05,foreground_mae=.01,foreground_p99=.05),scope='Native standalone process, not Resolve')
t=time.perf_counter()
class Usage(ctypes.Structure):
    _fields_=[('uuid',ctypes.c_uint8*16)]+[(n,ctypes.c_uint64) for n in ['user','system','idle','wakeups','pageins','wired','resident','footprint','start','exit']]
physical=[];stop=threading.Event()
def sample_memory():
    lib=ctypes.CDLL('/usr/lib/libproc.dylib')
    while not stop.wait(.05):
        info=Usage()
        if lib.proc_pid_rusage(os.getpid(),0,ctypes.byref(info))==0:physical.append(info.footprint)
monitor=threading.Thread(target=sample_memory,daemon=True);monitor.start()
try:
    frames=np.load(args.source,allow_pickle=False)
    record['shape']=list(frames.shape)
    load=time.perf_counter();b.load();record['load_seconds']=time.perf_counter()-load
    settings=dict(input_space='linear',hint_mode='none',hint_quality=.75,despill_strength=0.)
    if args.temporal:
        from ckmac.cache import DiskCache
        from ckmac.temporal import TemporalProcessor
        from ckmac.generations import digest
        import tempfile
        with tempfile.TemporaryDirectory(prefix='ckmac-native-temporal-') as tmp:
            c=DiskCache(Path(tmp));keys=[]
            for i,frame in enumerate(frames):
                k=digest([record['source_sha256'],i]);c.put(k,frame);keys.append(k)
            p=TemporalProcessor(b,c,'native-compare-v1')
            start=time.perf_counter();p.run(keys,settings,0,profile=Profile(),expected_shape=tuple(frames[0].shape),owner='native-probe',provenance=dict(start=0,end=len(keys)-1,fps=25))
            record['temporal_seconds']=time.perf_counter()-start
            outputs=np.stack([p.records.result(p.last_generation,i) for i in range(len(keys))])
            before_calls=dict(b._network_calls)
            before_files={x.name:(x.stat().st_size,x.stat().st_mtime_ns,x.stat().st_ctime_ns) for x in c.root.iterdir() if x.is_file()}
            replay=time.perf_counter()
            for order in [range(len(keys)),reversed(range(len(keys))),np.random.default_rng(42).permutation(len(keys))]:
                for index in order:
                    value=p.run(keys,settings,int(index),profile=Profile(),expected_shape=tuple(frames[0].shape),owner='native-probe',provenance=dict(start=0,end=len(keys)-1,fps=25))
                    if not np.array_equal(value,outputs[index]):raise ValueError('Cached native output changed')
            after_files={x.name:(x.stat().st_size,x.stat().st_mtime_ns,x.stat().st_ctime_ns) for x in c.root.iterdir() if x.is_file()}
            if before_files!=after_files or before_calls!=b._network_calls:raise ValueError('Native replay wrote files or invoked networks')
            record['cached_replay_seconds']=time.perf_counter()-replay
            record['cached_replay_frames']=len(keys)*3
            record['replay_no_new_files_or_timestamp_changes']=True
            record['replay_no_neural_work']=True
            record['cache_counters']=dict(c.stats,**p.stats)
    else:
        outputs=[];times=[]
        for i,frame in enumerate([frames[0],frames[0],*frames]):
            start=time.perf_counter();value=b.infer(frame,**settings);times.append(time.perf_counter()-start)
            if i>=2:outputs.append(value)
        outputs=np.stack(outputs);record['single_frame_seconds']=times;record['cold_seconds']=times[0];record['warm_seconds']=times[1]
    np.save(args.output/'outputs.npy',outputs,allow_pickle=False)
    record.update(status='Passed',diagnostics=b.diagnostics(),alpha_range=[float(outputs[...,3].min()),float(outputs[...,3].max())],foreground_range=[float(outputs[...,:3].min()),float(outputs[...,:3].max())])
except Exception as exc:
    import traceback
    record['error']=str(exc);record['traceback']=traceback.format_exc();traceback.print_exc()
finally:
    stop.set();monitor.join(1)
    record['sampled_peak_physical_footprint_bytes']=max(physical,default=0)
    record['physical_sample_interval_ms']=50
    record['total_seconds']=time.perf_counter()-t;record['process_peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    (args.output/'result.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2),flush=True)
if record['status']!='Passed':raise SystemExit(1)
