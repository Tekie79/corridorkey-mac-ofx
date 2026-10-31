#!/usr/bin/env python3
"""Run exact extracted MPS payload offline; never install or modify production.

This is relocated-payload evidence, not installed-Resolve qualification. The
packaged native launcher starts its packaged isolated Python. Outbound IP is
denied by macOS; inherited Python/Conda settings are deliberately conflicting.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'worker'))
from ckmac.maintenance import verify_files
from common import sha

POLICY='(version 1)(allow default)(deny network-outbound (remote ip "*:*"))'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expanded-root',type=Path,required=True)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--artifact',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if sys.platform!='darwin' or os.getuid()==0:parser.error('Run as the editing user on Apple Silicon macOS')
    envelopes=[p for p in args.expanded_root.rglob('install-manifest.json') if p.parent.parent.name=='Incoming']
    if len(envelopes)!=1:raise ValueError('Expected one verified package envelope')
    installed=json.loads(envelopes[0].read_text());tree=envelopes[0].parent/'tree'
    if installed.get('backend')!='mps':raise ValueError('This qualifier requires the explicit MPS release')
    artifact=json.loads(args.artifact.read_text())
    package=args.artifact.parent/artifact['filename']
    if package.stat().st_size!=artifact['size'] or sha(package)!=artifact['sha256']:raise ValueError('Candidate package bytes changed')
    runtime=tree/Path(installed['python']).relative_to('/');code=tree/Path(installed['code_root']).relative_to('/')
    models=tree/Path(installed['model_root']).relative_to('/')
    args.output.resolve().parent.mkdir(parents=True,exist_ok=True)
    work=args.output.resolve().parent/('runtime-qa-'+secrets.token_hex(4));work.mkdir(mode=0o700)
    if work.is_relative_to(tree.resolve()):raise ValueError('QA data must remain outside the payload')
    verify_files(tree,installed['inventory'])
    paths_before={p.relative_to(tree).as_posix() for p in tree.rglob('*')}
    sockdir=Path('/private/tmp')/('ckmac-'+str(os.getuid()))
    sockdir.mkdir(mode=0o700,exist_ok=True)
    endpoint=sockdir/('payload-qa-'+secrets.token_hex(5)+'.sock');tf=Path(str(endpoint)+'.token')
    token=secrets.token_hex(32);tf.write_text(token);tf.chmod(0o600)
    active=dict(installed,python=str(runtime.resolve()),code_root=str(code.resolve()),model_root=str(models.resolve()),
                build_id='payload-qa-'+artifact['sha256'][:12])
    manifest=work/'active.json';manifest.write_text(json.dumps(active,indent=2)+'\n')
    env=dict(PATH='/usr/bin:/bin',HOME=str(Path.home()),HF_HOME=str(work/'cache/huggingface'),
             HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTORCH_ENABLE_MPS_FALLBACK='0',
             PYTHONPATH='/__ckmac_invalid_pythonpath__',PYTHONHOME='/__ckmac_invalid_pythonhome__',CONDA_PREFIX='/__ckmac_invalid_conda__')
    isolated=['/usr/bin/sandbox-exec','-p',POLICY]
    deny="import socket,errno; s=socket.socket(); s.settimeout(1)\ntry:s.connect(('192.0.2.1',443));raise RuntimeError('Outbound IP allowed')\nexcept OSError as e:assert e.errno in (errno.EPERM,errno.EACCES);print(e.errno)"
    check=subprocess.run([*isolated,str(runtime),'-I','-B','-c',deny],env=env,text=True,capture_output=True,check=True)
    probe=subprocess.run([*isolated,str(runtime),'-I','-B','-c','import sys,platform,json,ckmac;print(json.dumps(dict(machine=platform.machine(),isolated=sys.flags.isolated,prefix=sys.prefix,path=sys.path,worker=ckmac.__file__)))'],env=env,text=True,capture_output=True,check=True)
    interpreter=json.loads(probe.stdout);assert interpreter['machine']=='arm64' and interpreter['isolated']==1
    assert Path(interpreter['worker']).resolve().is_relative_to(tree.resolve())
    launcher=runtime.parent/'ckmac-engine-launcher'
    log=(work/'engine.log').open('w');pid=None;request_id=0
    def exact(c,n):
        data=bytearray()
        while len(data)<n:
            part=c.recv(n-len(data))
            if not part:raise RuntimeError('Truncated worker response')
            data.extend(part)
        return data
    def request(op,payload=b'',**extra):
        nonlocal request_id
        request_id+=1
        message=dict(op=op,protocol=2,build_id=active['build_id'],token=token,payload_bytes=len(payload),
                     session_id='payload-qa',request_id=request_id,effect_generation=1,**extra)
        data=json.dumps(message,allow_nan=False).encode()
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as c:
            c.settimeout(180);c.connect(str(endpoint));c.sendall(b'CKJ2'+struct.pack('>I',len(data))+data+payload)
            n=struct.unpack('>I',exact(c,4))[0];assert 0<n<=65536
            answer=json.loads(exact(c,n));body=bytes(exact(c,answer['payload_bytes']))
            if not answer['ok']:raise RuntimeError(answer.get('error','Worker failure'))
            return answer,body
    def start():
        nonlocal pid
        begin=time.perf_counter()
        subprocess.run([*isolated,str(launcher),str(runtime.resolve()),'-I','-B','-u','-m','ckmac.engine',
                        '--manifest',str(manifest),'--socket',str(endpoint),'--token-file',str(tf)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        while time.perf_counter()-begin<30:
            if endpoint.exists():
                health,_=request('health');pid=health['pid']
                if health['state']=='cache_ready':return health,time.perf_counter()-begin
                if health['state']=='error':raise RuntimeError(health['error'])
            time.sleep(.1)
        raise TimeoutError('Packaged launcher did not start its engine')
    def stop():
        nonlocal pid
        if pid is None:return
        request('release');deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            try:os.kill(pid,0)
            except ProcessLookupError:pid=None;return
            time.sleep(.1)
        raise TimeoutError('Packaged engine did not exit after release')
    record=dict(status='Failed',scope='Exact extracted payload; not installed supervisor, Installer GUI or Resolve qualification',
                artifact_sha256=artifact['sha256'],package_build_id=installed['build_id'],outbound_ip_denied_errno=int(check.stdout.strip()),interpreter=interpreter)
    try:
        initial,startup=start();assert not initial['model_loaded']
        frame=np.load(args.fixture,allow_pickle=False);assert frame.shape==(1080,1920,4) and frame.dtype==np.float32
        data=np.ascontiguousarray(frame,dtype='<f4').tobytes();key=hashlib.sha256(struct.pack('>II',1920,1080)+data).hexdigest()
        base=dict(width=1920,height=1080,input_space=0,hint=False,quality=.95,despill=0.)
        request('stage',data,key=key,width=1920,height=1080)
        started=time.perf_counter();_,first=request('frame_cached',source_key=key,**base);cold=time.perf_counter()-started
        output=np.frombuffer(first,dtype='<f4').reshape(frame.shape)
        assert np.isfinite(output).all() and np.ptp(output[...,3])>.01 and output[...,3].min()<.95 and output[...,3].max()>.05
        started=time.perf_counter();_,second=request('frame_cached',source_key=key,**base);cached=time.perf_counter()-started
        health,_=request('health');assert first==second and health['fixture_passed'] and health['user_frames_completed']==1
        stop();restarted,restart_time=start();assert not restarted['model_loaded']
        _,third=request('frame_cached',source_key=key,**base);after,_=request('health')
        assert third==first and not after['model_loaded'] and after['counters']['model_network_invocations']==0
        cleanup,_=request('clear_shot');assert cleanup['cleanup_complete']
        stop();verify_files(tree,installed['inventory'])
        assert paths_before=={p.relative_to(tree).as_posix() for p in tree.rglob('*')},'Generated files inside payload'
        record.update(status='Passed',startup_cache_ready_seconds=startup,first_load_and_inference_seconds=cold,
                      cached_read_seconds=cached,restart_cache_ready_seconds=restart_time,first_health=health,restarted_health=after,
                      cleanup=cleanup,alpha_range=[float(output[...,3].min()),float(output[...,3].max())],
                      payload_unchanged_after_inference=True,cache_bit_identical_after_restart=True)
    finally:
        if pid is not None:
            try:stop()
            except (OSError,RuntimeError,TimeoutError):
                command=subprocess.run(['/bin/ps','-ww','-p',str(pid),'-o','command='],text=True,capture_output=True).stdout
                if str(manifest) in command and 'ckmac.engine' in command:
                    try:os.kill(pid,15)
                    except ProcessLookupError:pass
        log.close();args.output.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:record[k] for k in ('status','scope','artifact_sha256','first_load_and_inference_seconds','cached_read_seconds')},indent=2))


if __name__=='__main__':main()
