"""Installed, authenticated, same-user GPU engine. The development v1 server stays separate."""
import argparse
import ctypes
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import signal
import select
import socket
import socketserver
import struct
import threading
import time
import traceback
from dataclasses import asdict
from collections import OrderedDict,defaultdict

import numpy as np
from .backend import INPUT_SPACES
from .backends import create_backend
from .cache import DiskCache
from .protocol import recv_exact
from .server import prepare_socket
from .temporal import TemporalProcessor
from .profiles import Profile
from .resolve_geometry import GeometryCache,SDK_PATH

LOG = logging.getLogger('ckmac.engine')


class Engine:
    def __init__(self, manifest, cache,installation_inventory=None):
        self.manifest = manifest
        self.build = manifest['build_id']
        self.backend = create_backend(manifest)
        self.cache = DiskCache(cache / 'frames',temporary_root=cache)
        self.lock = threading.RLock()
        self.state = 'cache_ready'
        self.error = ''
        self.last_activity = time.monotonic()
        self.active = 0
        self.completed = 0
        self.cache_hits = 0
        self.fixture_passed = False
        self.stopping = False
        self.facts = {}
        self.temporal = TemporalProcessor(self.backend,self.cache,self.build)
        self.records=self.temporal.records
        self.installation_inventory=installation_inventory
        self.counters=dict(input_stage_attempts=0,input_stage_new=0,input_stage_dedup=0)
        self.node_counters=defaultdict(dict)
        self.metrics_lock=threading.Lock()
        self.source_geometry=GeometryCache(cache)

    def count(self,owner,generation,**counts):
        if not isinstance(owner,str) or not 1<=len(owner)<=128:return
        with self.metrics_lock:
            bucket=self.node_counters[(owner,generation or 'capture')]
            for key,value in counts.items():bucket[key]=bucket.get(key,0)+int(value)

    def remember(self,owner,keys,kind='capture'):
        self.records.remember(owner,keys,kind)

    def settings(self,req):
        space=req['input_space']
        if type(space) is not int or not 0<=space<len(INPUT_SPACES):raise ValueError('Invalid input encoding')
        return dict(input_space=INPUT_SPACES[space],hint_mode='source_alpha' if req['hint'] else 'none',
                    hint_quality=float(req['quality']),despill_strength=float(req['despill']))

    def analysis_status(self,req):
        profile=Profile.from_request(req)
        if hasattr(self.backend,'validate_canvas'):self.backend.validate_canvas(req['height'],req['width'],profile)
        identity=self.temporal.identity(req['keys'],self.settings(req),req['revision'],req.get('first_hint',False),req.get('provenance'),profile)
        from .generations import digest
        generation=digest(identity)
        record=self.records.record(generation)
        # Playback queries validate only the requested output. A full audit is
        # available separately; eviction elsewhere does not invalidate this frame.
        if record is None:
            reasons=['not_analyzed']
            previous=self.records.owned_generations(req.get('session_id'))
            if previous:
                old=self.records.record(previous[0])['identity']
                reasons=[name+'_changed' for name in ('inputs','backend','profile','settings','revision','provenance','build') if old.get(name)!=identity.get(name)] or ['generation_not_completed']
            return dict(state='Unanalyzed',generation=generation,miss_reasons=reasons)
        self.records.lease(req.get('session_id'),generation)
        try:self.records.result(generation,req['requested'],(req['height'],req['width'],4))
        except RuntimeError:return dict(state='Stale',generation=generation,miss_reasons=[self.cache.miss_reason(record['outputs'][req['requested']])])
        if req.get('audit',False) and self.records.status(generation)['state']!='Analyzed':
            return dict(state='Stale',generation=generation,miss_reasons=['analysis_outputs_incomplete'])
        return dict(state='Analyzed',generation=generation)

    def load(self):
        try:
            t = time.perf_counter()
            if self.installation_inventory is not None:
                self.state='checking_installation'
                from .maintenance import verify_files
                try:
                    inventory=self.installation_inventory
                    if isinstance(inventory,Path):
                        installed=json.loads(inventory.read_text())
                        if installed['build_id']!=self.build:raise ValueError('Installation manifest generation mismatch')
                        inventory=installed['inventory']
                    verify_files(Path('/'),inventory,protected=True)
                except Exception as exc:raise RuntimeError(f'CK-ASSET-INTEGRITY: installed files changed. Repair from the offline installer. {exc}') from exc
                self.facts['installation_verification_seconds']=time.perf_counter()-t
                self.state='loading_model';t=time.perf_counter()
            self.backend.load()
            self.facts['model_load_seconds'] = time.perf_counter()-t
            self.state = 'checking_gpu'
            fixture = np.zeros((*getattr(self.backend,'fixture_shape',(128,128)),4), dtype=np.float32)
            fixture[...,1] = .5
            fixture[...,3] = 1
            fixture[24:104,40:88,:3] = [.6,.2,.1]
            t = time.perf_counter()
            output = self.backend.infer(fixture)
            if not np.isfinite(output).all():
                raise RuntimeError('GPU fixture returned non-finite data')
            self.fixture_passed = True
            self.facts.update(fixture_seconds=time.perf_counter()-t, backend=self.backend.diagnostics())
            self.error=''
            self.state = 'ready'
        except Exception as exc:
            self.error = f'{type(exc).__name__}: {exc}'
            self.state = 'error'
            LOG.exception('Engine initialization failed')

    def health(self):
        torch=self.backend._torch
        if torch is not None and self.backend._model is not None:
            try:
                memory=dict(current_bytes=int(torch.mps.current_allocated_memory()),driver_bytes=int(torch.mps.driver_allocated_memory()),recommended_bytes=int(torch.mps.recommended_max_memory()))
                self.facts['live_mps_memory']=memory
                self.facts['maximum_observed_driver_bytes']=max(memory['driver_bytes'],self.facts.get('maximum_observed_driver_bytes',0))
            except (AttributeError,RuntimeError):pass
        with self.metrics_lock:node_stats=[dict(node=k[0],generation=k[1],counters=dict(v)) for k,v in self.node_counters.items()]
        return dict(state=self.state,error=self.error,fixture_passed=self.fixture_passed,
                    model_loaded=self.backend._model is not None,user_frames_completed=self.completed,
                    cache_hits=self.cache_hits, active_jobs=self.active, pid=os.getpid(), facts=self.facts,
                    cache=dict(self.cache.stats,ram_bytes=self.cache.ram_bytes,ram_limit=self.cache.ram_budget),
                    counters=dict(self.counters,**self.temporal.stats,model_network_invocations=sum(getattr(self.backend,'_network_calls',{}).values())),node_counters=node_stats,cache_domains=['temporary captures/results','Resolve playback cache (host controlled)','durable EXR bake'])

    def frame(self, req, data=None):
        with self.lock:return self._frame(req,data)

    def frame_key(self,req,data=None):
        w,h=req["width"],req["height"]
        if hasattr(self.backend,'validate_canvas'):self.backend.validate_canvas(h,w,Profile.from_request(req))
        identity=json.dumps([self.build,getattr(self.backend,"identity",{"backend":"mps","precision":"float32"}),"adapter-math-v3",w,h,self.settings(req),asdict(Profile.from_request(req))],sort_keys=True,allow_nan=False).encode()
        if data is not None:return hashlib.sha256(identity+data).hexdigest()
        self.cache.path(req["source_key"])
        return hashlib.sha256(identity+b":source-key:"+bytes.fromhex(req["source_key"])).hexdigest()

    def _frame(self, req, data=None):
        if self.stopping:
            raise RuntimeError('Maintenance is draining this GPU engine; retry after maintenance completes')
        w,h = req['width'],req['height']
        if type(w) is not int or type(h) is not int or min(w,h)<1 or max(w,h)>8192 or w*h>33554432 or (data is not None and len(data)!=w*h*16):
            raise ValueError('Invalid frame extent or payload')
        space = req['input_space']
        if type(space) is not int or not 0 <= space < len(INPUT_SPACES):
            raise ValueError('Invalid input encoding')
        settings = dict(input_space=INPUT_SPACES[space], hint_mode='source_alpha' if req['hint'] else 'none',
                        hint_quality=float(req['quality']), despill_strength=float(req['despill']))
        profile=Profile.from_request(req)
        profile.dimensions(h,w)
        key=self.frame_key(req,data)
        if data is None:source_key=req['source_key']
        self.remember(req.get('session_id'),[key],'result')
        cached = self.cache.get(key)
        if cached is not None and cached.shape==(h,w,4):
            self.cache_hits += 1
            return cached
        if self.backend._model is None:self.load()
        if self.state not in ('ready','processing'):raise RuntimeError(self.error or 'Engine is preparing')
        if data is None:
            rgba=self.cache.get(source_key)
            if rgba is None:raise RuntimeError('Captured input was evicted or changed. Render again to recapture it.')
            if rgba.shape!=(h,w,4):raise ValueError('Captured input dimensions do not match')
        else:rgba = np.frombuffer(data,dtype='<f4').reshape(h,w,4)
        if not np.isfinite(rgba).all():
            raise ValueError('Source contains non-finite data')
        self.state = 'processing'
        self.active += 1
        try:
            t = time.perf_counter()
            profile.configure(self.backend)
            result = self.backend.infer(profile.resize(rgba,settings['input_space']), **settings)
            result = profile.restore(result,(h,w),settings['input_space'])
            self.facts['profile']=asdict(profile)
            self.facts['last_distinct_frame_seconds'] = time.perf_counter()-t
            self.facts['backend'] = self.backend.diagnostics()
            self.completed += 1
            # Cache exhaustion must not invalidate an already valid inference.
            try:
                self.cache.put(key,result)
            except OSError:
                LOG.exception('Could not cache completed frame')
            return result
        finally:
            self.active -= 1
            self.state = 'ready'
            self.last_activity = time.monotonic()


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        c = self.request
        c.settimeout(10)
        e = self.server.engine
        try:
            libc = ctypes.CDLL(None)
            uid,gid = ctypes.c_uint(),ctypes.c_uint()
            if libc.getpeereid(c.fileno(),ctypes.byref(uid),ctypes.byref(gid)) or uid.value not in (0,os.getuid()):
                raise PermissionError('Foreign IPC peer')
            if recv_exact(c,4) != b'CKJ2':
                raise ValueError('Unsupported protocol; reinstall a matching plugin/runtime')
            n = struct.unpack('>I',recv_exact(c,4))[0]
            if not 1 <= n <= 65536:
                raise ValueError('Invalid control size')
            req = json.loads(recv_exact(c,n))
            if req.get('protocol') != 2 or req.get('build_id') != e.build or not hmac.compare_digest(req.get('token',''),self.server.token):
                raise PermissionError('Incompatible or unauthenticated engine connection')
            e.last_activity = time.monotonic()
            op = req.get('op')
            if uid.value == 0 and op != 'release':
                raise PermissionError('Root may only request maintenance drain')
            n = req.get('payload_bytes')
            if type(n) is not int or not 0 <= n <= 33554432*16:
                raise ValueError('Invalid binary size')
            result = b''
            if op == 'health' and n == 0:
                answer = e.health()
            elif op == 'release' and n == 0:
                if e.state not in ('ready','cache_ready','error') or not e.lock.acquire(False):
                    raise RuntimeError('Maintenance blocked: GPU work is active')
                try:
                    e.stopping=True
                    e.state='stopping'
                    answer = {'state':'stopping','pid':os.getpid()}
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                finally:
                    e.lock.release()
            elif op == 'input_lookup' and n==0:
                key=req['key']
                e.counters['input_stage_attempts']+=1
                present=e.cache.valid(key)
                if present:e.counters['input_stage_dedup']+=1
                e.count(req.get('session_id'),None,input_stage_attempts=1,input_stage_dedup=int(present))
                if present:e.remember(req.get('session_id'),[key])
                answer={'present':present,'key':key}
            elif op == 'inputs_lookup' and n==0:
                keys=req['keys']
                if not isinstance(keys,list) or len(keys)>480:raise ValueError('Invalid input set')
                present=[key for key in keys if e.cache.valid(key)]
                e.remember(req.get('session_id'),present)
                answer={'present':present}
            elif op == 'stage':
                w,h=req['width'],req['height']
                if type(w) is not int or type(h) is not int or min(w,h)<1 or max(w,h)>8192 or w*h>33554432 or n!=w*h*16:
                    raise ValueError('Invalid temporal input geometry')
                data=recv_exact(c,n)
                key=hashlib.sha256(struct.pack('>II',w,h)+data).hexdigest()
                if key!=req['key']:raise ValueError('Temporal input fingerprint mismatch')
                value=np.frombuffer(data,dtype='<f4').reshape(h,w,4)
                if not np.isfinite(value).all():raise ValueError('Non-finite temporal input')
                e.remember(req.get('session_id'),[key])
                new=e.cache.put(key,value)
                e.counters['input_stage_new' if new else 'input_stage_dedup']+=1
                e.count(req.get('session_id'),None,input_stage_new=int(new),input_stage_dedup=int(not new),cache_bytes_written=(value.nbytes+56) if new else 0)
                answer={'key':key,'new':new}
            elif op=='clear_shot' and n==0:
                if not e.lock.acquire(False):raise RuntimeError('Finish or cancel active processing before clearing this node cache')
                try:
                    answer=e.records.clear(req.get('session_id'),req.get('generation'))
                finally:e.lock.release()
            elif op=='diagnostic_counters' and n==0:
                allowed={'source_frames_fetched','bake_reads'}
                counts=req.get('counts',{})
                if not isinstance(counts,dict) or set(counts)-allowed or any(type(v) is not int or not 0<=v<=100000 for v in counts.values()):raise ValueError('Invalid diagnostic counters')
                e.count(req.get('session_id'),req.get('generation'),**counts)
                answer=dict(recorded=True)
            elif op=='frame_lookup' and n==0:
                key=e.frame_key(req)
                image=e.cache.get(key)
                answer=dict(present=image is not None,key=key,miss_reason=None if image is not None else e.cache.miss_reason(key))
            elif op=='analyze_status' and n==0:
                answer=e.analysis_status(req)
            elif op=='result_get' and n==0:
                try:
                    record=e.records.record(req['generation'])
                    if record is None:raise RuntimeError('Analysis generation missing; use Analyze/Resume')
                    identity=record['identity']
                    # Client supplies a verified causal snapshot, not just an ID.
                    if req.get('source_keys')!=identity['inputs']:raise ValueError('Source snapshot does not match analysis')
                    e.records.lease(req.get('session_id'),req['generation'])
                    image=e.records.result(req['generation'],req['requested'],(req['height'],req['width'],4))
                    e.temporal.stats['result_cache_hits']+=1
                    e.count(req.get('session_id'),req['generation'],result_cache_hits=1)
                except RuntimeError:
                    e.temporal.stats['result_cache_misses']+=1
                    raise
                result=memoryview(np.ascontiguousarray(image,dtype='<f4')).cast('B')
                answer=dict(state='ready',alpha='straight',width=image.shape[1],height=image.shape[0],generation=req['generation'],cache_hit=True)
            elif op=='bake' and n==0:
                if not e.lock.acquire(False):raise RuntimeError('Finish active analysis before baking')
                previous_state=e.state;e.state='baking';e.active+=1
                try:
                    from .bake import bake,bake_from_manifest
                    generation=req.get('generation');owned=generation in e.records.owned_generations(req.get('session_id'))
                    source_size=req.get('source_size')
                    source_basis='user_explicit' if req.get('source_size_explicit',False) else 'captured_source'
                    original_size=None
                    if source_size==[0,0]:source_size=None
                    if source_size is not None and (not isinstance(source_size,list) or len(source_size)!=2 or any(type(v) is not int or v<1 for v in source_size)):raise ValueError('Invalid source-footage dimensions')
                    if not req.get('source_size_explicit',False):
                        original_size=e.source_geometry.get(req.get('session_id',''),generation or '')
                        if original_size:source_size=original_size;source_basis='resolve_sdk'
                    if owned:
                        record=e.records.record(generation);sample=e.records.result(generation,0)
                        if source_size is None:source_size=record['identity'].get('provenance',{}).get('source_size') or [sample.shape[1],sample.shape[0]]
                    else:
                        source_manifest=Path(req.get('source_manifest',''))
                        if not source_manifest.is_absolute():raise ValueError('Analyze this node or relink a verified bake before exporting')
                        source_record=json.loads(source_manifest.read_text())
                        if source_size is None:source_size=source_record.get('source_size') or source_record.get('analysis_size') or [source_record['width'],source_record['height']]
                        if not req.get('source_size_explicit',False) and not original_size and source_record.get('source_size_basis') in ('resolve_sdk','user_explicit'):
                            source_size=source_record['source_size'];source_basis=source_record['source_size_basis']
                    mode=req.get('size_mode',0)
                    if type(mode) is not int or mode not in range(5):raise ValueError('Invalid bake size option')
                    if mode==0 and req.get('resolve_host',False) and source_basis=='captured_source':
                        e.source_geometry.schedule(req.get('session_id'),generation)
                        raise RuntimeError(e.source_geometry.reason(req.get('session_id',''),generation or '')+' Set both Original Source dimensions explicitly only after verifying alignment. The previous bake is preserved.')
                    target=source_size if mode==0 else None if mode==1 else [3840,2160] if mode==2 else [4096,2160] if mode==3 else req.get('output_size')
                    if mode==4 and target is None:raise ValueError('Custom export dimensions are required')
                    destination=Path(req['destination'])
                    if destination.resolve()==e.cache.temporary_root.resolve() or e.cache.temporary_root.resolve() in destination.resolve().parents:raise ValueError('Durable media cannot use the temporary cache')
                    if owned:answer=bake(e.records,generation,destination,req['kind'],req.get('precision','half'),req.get('post'),target,source_size,source_basis)
                    else:answer=bake_from_manifest(source_manifest,destination,req['kind'],req.get('precision','half'),target,source_size,generation,source_basis)
                    answer['temporary_owned']=owned
                finally:e.active-=1;e.state=previous_state;e.lock.release()
            elif op == 'temporal' and n==0:
                w,h=req['width'],req['height']
                if type(w) is not int or type(h) is not int or min(w,h)<1 or max(w,h)>8192 or w*h>33554432:raise ValueError('Invalid temporal canvas')
                if e.state not in ('ready','cache_ready','error') or e.stopping:raise RuntimeError(e.error or 'GPU engine is preparing or busy')
                if not e.lock.acquire(timeout=10):raise RuntimeError('GPU queue is busy')
                try:
                    e.active+=1;e.state='processing'
                    settings=e.settings(req)
                    status=e.analysis_status(req)
                    need_model=status['state']=='Unanalyzed' or (req.get('resume',False) and e.records.status(status['generation'])['state']=='Stale')
                    if need_model and e.backend._model is None:
                        e.load()
                        if e.state=='error':raise RuntimeError(e.error)
                    e.state='processing'
                    def canceled():
                        return bool(select.select([c],[],[],0)[0] and c.recv(1,socket.MSG_PEEK)==b'')
                    def progress(value):e.facts['temporal_progress']=value
                    t=time.perf_counter();completed_before=e.backend._temporal_completed
                    stats_before=dict(e.temporal.stats);calls_before=sum(e.backend._network_calls.values());writes_before=e.cache.stats['cache_bytes_written'];evicted_before=e.cache.stats['cache_bytes_evicted']
                    profile=Profile.from_request(req)
                    e.temporal.last_outputs=set()
                    image=e.temporal.run(req['keys'],settings,req['requested'],revision=req['revision'],first_hint=req.get('first_hint',False),provenance=req.get('provenance'),cancel=canceled,progress=progress,profile=profile,expected_shape=(h,w,4),resume=req.get('resume',False),owner=req.get('session_id'))
                    e.remember(req.get('session_id'),e.temporal.last_outputs,'result')
                    e.count(req.get('session_id'),e.temporal.last_generation,**{k:e.temporal.stats[k]-stats_before[k] for k in stats_before},model_network_invocations=sum(e.backend._network_calls.values())-calls_before,cache_bytes_written=e.cache.stats['cache_bytes_written']-writes_before,cache_bytes_evicted=e.cache.stats['cache_bytes_evicted']-evicted_before)
                    e.facts['last_temporal_request_seconds']=time.perf_counter()-t
                    if e.backend._temporal_completed>completed_before:e.facts['last_temporal_analysis_seconds']=e.facts['last_temporal_request_seconds']
                    e.facts['temporal_algorithm']=f'float32 continuous RVM / Hann baton {profile.window}/{max(1,profile.window//2)} / stage2'
                    e.facts['profile']=asdict(profile)
                    e.facts['backend']=e.backend.diagnostics()
                    result=memoryview(np.ascontiguousarray(image,dtype='<f4')).cast('B')
                    answer={'state':'ready','alpha':'straight','width':image.shape[1],'height':image.shape[0],'generation':e.temporal.last_generation,'cache_hit':e.backend._temporal_completed==completed_before}
                finally:
                    e.active-=1
                    if e.state!='error':e.state='ready' if e.backend._model is not None else 'cache_ready'
                    e.last_activity=time.monotonic();e.lock.release()
            elif op == 'frame' or (op=='frame_cached' and n==0):
                # Serialize before receiving pixels: a bounded number of header-only waiters.
                if not e.lock.acquire(timeout=10):
                    raise RuntimeError('Engine is busy. Retry after the current job completes.')
                try:
                    c.settimeout(1800)
                    data = recv_exact(c,n) if op=='frame' else None
                    if select.select([c],[],[],0)[0] and c.recv(1,socket.MSG_PEEK) == b'':
                        return
                    result = memoryview(np.ascontiguousarray(e.frame(req,data),dtype='<f4')).cast('B')
                finally:
                    e.lock.release()
                answer = {'state':'ready','width':req['width'],'height':req['height'],'alpha':'straight'}
            else:
                raise ValueError('Unsupported engine operation')
            answer.update(ok=True,protocol=2,build_id=e.build,payload_bytes=len(result),session_id=req.get('session_id'),request_id=req.get('request_id'),effect_generation=req.get('effect_generation'))
            header=json.dumps(answer,allow_nan=False).encode()
            c.sendall(struct.pack('>I',len(header))+header)
            if result:
                c.sendall(result)
            # The vendor SDK cannot recursively inspect a Fusion graph while
            # Resolve waits for this OFX request. Probe once the host can return
            # from Render, then retain geometry by immutable analysis generation.
            e.source_geometry.schedule(req.get('session_id'),answer.get('generation') or req.get('generation'))
        except (BrokenPipeError,ConnectionError):
            LOG.info('Client canceled or disconnected')
        except Exception as exc:
            LOG.exception('Request failed')
            answer=json.dumps(dict(ok=False,protocol=2,build_id=e.build,payload_bytes=0,error=f'{type(exc).__name__}: {exc}')).encode()[:65536]
            try:
                c.sendall(struct.pack('>I',len(answer))+answer)
            except OSError:
                pass


class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
    daemon_threads=True
    request_queue_size=8
    def __init__(self,path,engine,token):
        self.engine,self.token=engine,token
        self.slots=threading.BoundedSemaphore(8)
        super().__init__(path,Handler)
    def process_request(self,request,address):
        if not self.slots.acquire(False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request,address)
        except BaseException:
            self.slots.release()
            raise
    def process_request_thread(self,request,address):
        try:
            super().process_request_thread(request,address)
        finally:
            self.slots.release()
    def service_actions(self):
        e=self.engine
        if not e.active and time.monotonic()-e.last_activity > 600:
            threading.Thread(target=self.shutdown,daemon=True).start()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--socket',type=Path,required=True)
    ap.add_argument('--token-file',type=Path,required=True)
    ap.add_argument('--verify-installation',action='store_true')
    args=ap.parse_args()
    if os.getuid()==0:
        ap.error('Inference must run as the editing user, never root')
    os.environ.update(PYTORCH_ENABLE_MPS_FALLBACK='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    manifest=json.loads(args.manifest.read_text())
    if manifest['protocol']!=2:
        ap.error('Incompatible manifest')
    cache=Path(os.environ['HF_HOME']).parent
    inventory=args.manifest.with_name('install-manifest.json') if args.verify_installation else None
    e=Engine(manifest,cache,inventory)
    fd=prepare_socket(args.socket)
    os.umask(0o077)
    token=args.token_file.read_text()
    server=Server(str(args.socket),e,token)
    os.chmod(args.socket,0o600)
    # Cached generation reads and bake export need no model, fixture or GPU.
    # The serialized first genuinely uncached job initializes the backend.
    signal.signal(signal.SIGTERM,lambda *_:threading.Thread(target=server.shutdown,daemon=True).start())
    try:
        server.serve_forever(poll_interval=.25)
    finally:
        server.server_close()
        args.socket.unlink(missing_ok=True)
        if e.active==0 and (e.stopping or e.state in ('ready','cache_ready')):
            marker=Path(str(args.socket)+f'.clean-{os.getpid()}')
            try:
                with marker.open('x') as f:f.write(e.build);f.flush();os.fsync(f.fileno())
                marker.chmod(0o600);os.replace(marker,Path(str(args.socket)+'.clean'))
            finally:marker.unlink(missing_ok=True)
        os.close(fd)


if __name__=='__main__':
    main()
