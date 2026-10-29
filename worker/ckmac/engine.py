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
from collections import OrderedDict

import numpy as np
from .backend import CorridorKeyBackend, INPUT_SPACES
from .cache import DiskCache
from .protocol import recv_exact
from .server import prepare_socket
from .temporal import TemporalProcessor
from .profiles import Profile

LOG = logging.getLogger('ckmac.engine')


class Engine:
    def __init__(self, manifest, cache,installation_inventory=None):
        self.manifest = manifest
        self.build = manifest['build_id']
        self.backend = CorridorKeyBackend(manifest['code_root'], manifest['model_root'])
        self.cache = DiskCache(cache / 'frames')
        self.lock = threading.Lock()
        self.state = 'loading_model'
        self.error = ''
        self.last_activity = time.monotonic()
        self.active = 0
        self.completed = 0
        self.cache_hits = 0
        self.fixture_passed = False
        self.stopping = False
        self.facts = {}
        self.temporal = TemporalProcessor(self.backend,self.cache,self.build)
        self.owners=OrderedDict()
        self.owner_lock=threading.Lock()
        self.installation_inventory=installation_inventory

    def remember(self,owner,keys):
        if not isinstance(owner,str) or not 1<=len(owner)<=128:return
        with self.owner_lock:
            previous=self.owners.pop(owner,set())
            self.owners[owner]=set(list(previous.union(keys))[-1024:])
            while len(self.owners)>128:self.owners.popitem(last=False)

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
            fixture = np.zeros((128,128,4), dtype=np.float32)
            fixture[...,1] = .5
            fixture[...,3] = 1
            fixture[24:104,40:88,:3] = [.6,.2,.1]
            t = time.perf_counter()
            output = self.backend.infer(fixture)
            if not np.isfinite(output).all():
                raise RuntimeError('GPU fixture returned non-finite data')
            self.fixture_passed = True
            self.facts.update(fixture_seconds=time.perf_counter()-t, backend=self.backend.diagnostics())
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
        return dict(state=self.state,error=self.error,fixture_passed=self.fixture_passed,
                    model_loaded=self.backend._model is not None,user_frames_completed=self.completed,
                    cache_hits=self.cache_hits, active_jobs=self.active, pid=os.getpid(), facts=self.facts,
                    cache=dict(self.cache.stats,ram_bytes=self.cache.ram_bytes,ram_limit=self.cache.ram_budget))

    def frame(self, req, data=None):
        if self.stopping:
            raise RuntimeError('Maintenance is draining this GPU engine; retry after maintenance completes')
        if self.state not in ('ready', 'processing'):
            raise RuntimeError(self.error or 'Engine is preparing. Please wait, then retry.')
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
        identity = json.dumps([self.build,w,h,settings,asdict(profile)], sort_keys=True, allow_nan=False).encode()
        if data is None:
            source_key=req['source_key']
            self.cache.path(source_key)  # Strictly validate the data identifier.
            key=hashlib.sha256(identity+b':source-key:'+bytes.fromhex(source_key)).hexdigest()
        else:key = hashlib.sha256(identity + data).hexdigest()
        self.remember(req.get('session_id'),[key])
        cached = self.cache.get(key)
        if cached is not None and cached.shape==(h,w,4):
            self.cache_hits += 1
            return cached
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
                if e.state not in ('ready','error') or not e.lock.acquire(False):
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
                present=e.cache.valid(key)
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
                e.cache.put(key,value)
                answer={'key':key}
            elif op=='clear_shot' and n==0:
                if not e.lock.acquire(False):raise RuntimeError('Finish or cancel active processing before clearing this node cache')
                try:
                    with e.owner_lock:
                        owned=e.owners.pop(req.get('session_id'),set())
                        shared=set().union(*e.owners.values()) if e.owners else set()
                        count=e.cache.remove(owned-shared)
                    answer={'removed_entries':count,'shared_entries_preserved':len(owned&shared)}
                finally:e.lock.release()
            elif op == 'temporal' and n==0:
                w,h=req['width'],req['height']
                if type(w) is not int or type(h) is not int or min(w,h)<1 or max(w,h)>8192 or w*h>33554432:raise ValueError('Invalid temporal canvas')
                if e.state!='ready' or e.stopping:raise RuntimeError(e.error or 'GPU engine is preparing or busy')
                if not e.lock.acquire(timeout=10):raise RuntimeError('GPU queue is busy')
                try:
                    e.active+=1;e.state='processing'
                    settings=dict(input_space=INPUT_SPACES[req['input_space']],hint_mode='source_alpha' if req['hint'] else 'none',hint_quality=float(req['quality']),despill_strength=float(req['despill']))
                    def canceled():
                        return bool(select.select([c],[],[],0)[0] and c.recv(1,socket.MSG_PEEK)==b'')
                    def progress(value):e.facts['temporal_progress']=value
                    t=time.perf_counter();completed_before=e.backend._temporal_completed
                    profile=Profile.from_request(req)
                    e.temporal.last_outputs=set()
                    image=e.temporal.run(req['keys'],settings,req['requested'],revision=req['revision'],first_hint=req.get('first_hint',False),provenance=req.get('provenance'),cancel=canceled,progress=progress,profile=profile,expected_shape=(h,w,4))
                    e.remember(req.get('session_id'),e.temporal.last_outputs)
                    e.facts['last_temporal_request_seconds']=time.perf_counter()-t
                    if e.backend._temporal_completed>completed_before:e.facts['last_temporal_analysis_seconds']=e.facts['last_temporal_request_seconds']
                    e.facts['temporal_algorithm']=f'float32 continuous RVM / Hann baton {profile.window}/{max(1,profile.window//2)} / stage2'
                    e.facts['profile']=asdict(profile)
                    e.facts['backend']=e.backend.diagnostics()
                    result=memoryview(np.ascontiguousarray(image,dtype='<f4')).cast('B')
                    answer={'state':'ready','alpha':'straight','width':image.shape[1],'height':image.shape[0]}
                finally:
                    e.active-=1;e.state='ready';e.last_activity=time.monotonic();e.lock.release()
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
    threading.Thread(target=e.load,daemon=True).start()
    signal.signal(signal.SIGTERM,lambda *_:threading.Thread(target=server.shutdown,daemon=True).start())
    try:
        server.serve_forever(poll_interval=.25)
    finally:
        server.server_close()
        args.socket.unlink(missing_ok=True)
        if e.active==0 and (e.stopping or e.state=='ready'):
            marker=Path(str(args.socket)+f'.clean-{os.getpid()}')
            try:
                with marker.open('x') as f:f.write(e.build);f.flush();os.fsync(f.fileno())
                marker.chmod(0o600);os.replace(marker,Path(str(args.socket)+'.clean'))
            finally:marker.unlink(missing_ok=True)
        os.close(fd)


if __name__=='__main__':
    main()
