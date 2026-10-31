#!/usr/bin/env python3
"""Exercise the installed isolated QA worker under kernel-enforced IP/checkout denial.

This starts the protected packaged launcher manually. It does not qualify
Resolve automatic startup, a clean account, reboot, or whole-Mac offline use.
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

ROOT=Path('/Users/harvest/Documents/Ysew_Project/GIT/corridorkey-mac-ofx')
sys.path.insert(0,str(ROOT/'scripts/release'))
sys.path.insert(0,str(ROOT/'worker'))
from ckmac.maintenance import verify_files
from common import sha

POLICY='(version 1)(allow default)(deny network-outbound (remote ip "*:*"))'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--artifact',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if sys.platform!='darwin' or os.getuid()==0:parser.error('Run as the editing user on Apple Silicon macOS')
    product=Path('/Library/Application Support/HarvestPictures/CorridorKeyMacQA')
    installed=json.loads((product/'install-manifest.json').read_text());assert installed['installation_profile']=='qa'
    tree=Path('/')
    if installed.get('backend')!='mps':raise ValueError('This qualifier requires the explicit MPS release')
    artifact=json.loads(args.artifact.read_text())
    package=args.artifact.parent/artifact['filename']
    if package.stat().st_size!=artifact['size'] or sha(package)!=artifact['sha256']:raise ValueError('Candidate package bytes changed')
    runtime=tree/Path(installed['python']).relative_to('/');code=tree/Path(installed['code_root']).relative_to('/')
    models=tree/Path(installed['model_root']).relative_to('/')
    args.output.resolve().parent.mkdir(parents=True,exist_ok=True)
    work=Path('/private/tmp')/('ckmac-qa-offline-'+secrets.token_hex(4));work.mkdir(mode=0o700)
    assert not work.is_relative_to(product)
    verify_files(tree,installed['inventory'],protected=True)
    paths_before={str(p) for folder in ('Runtime','Models') for p in (product/folder).rglob('*')}
    sockdir=Path('/private/tmp')/('ckmac-qa-'+str(os.getuid()))
    sockdir.mkdir(mode=0o700,exist_ok=True)
    endpoint=sockdir/(installed['build_id'][:32]+'.sock');tf=Path(str(endpoint)+'.token')
    assert not endpoint.exists(),'Release the QA worker first'
    if tf.exists():
        import stat
        info=tf.lstat();assert stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and not info.st_mode&0o077
        token=tf.read_text()
    else:
        token=secrets.token_hex(32);tf.write_text(token);tf.chmod(0o600)
    active=installed
    manifest=product/'active.json'
    assert json.loads(manifest.read_text())['build_id']==installed['build_id']
    env=dict(PATH='/usr/bin:/bin',HOME=str(Path.home()),HF_HOME=str(work/'cache/huggingface'),
             HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTORCH_ENABLE_MPS_FALLBACK='0',
             PYTHONPATH='/__ckmac_invalid_pythonpath__',PYTHONHOME='/__ckmac_invalid_pythonhome__',CONDA_PREFIX='/__ckmac_invalid_conda__')
    policy=POLICY+'(deny file-read* (subpath '+json.dumps(str(ROOT))+'))'
    isolated=['/usr/bin/sandbox-exec','-p',policy]
    deny="import socket,errno; s=socket.socket(); s.settimeout(1)\ntry:s.connect(('192.0.2.1',443));raise RuntimeError('Outbound IP allowed')\nexcept OSError as e:assert e.errno in (errno.EPERM,errno.EACCES);print(e.errno)"
    check=subprocess.run([*isolated,str(runtime),'-I','-B','-c',deny],env=env,cwd=work,text=True,capture_output=True,check=True)
    probe=subprocess.run([*isolated,str(runtime),'-I','-B','-c','import sys,platform,json,ckmac;print(json.dumps(dict(machine=platform.machine(),isolated=sys.flags.isolated,prefix=sys.prefix,path=sys.path,worker=ckmac.__file__)))'],env=env,cwd=work,text=True,capture_output=True,check=True)
    denied_repo=subprocess.run([*isolated,str(runtime),'-I','-B','-c',"from pathlib import Path\ntry:Path("+repr(str(Path.cwd()/'CMakeLists.txt'))+").read_bytes();raise RuntimeError('Checkout readable')\nexcept PermissionError:pass"],env=env,cwd=work,text=True,capture_output=True,check=True)
    interpreter=json.loads(probe.stdout);assert interpreter['machine']=='arm64' and interpreter['isolated']==1
    assert Path(interpreter['worker']).resolve().is_relative_to(product/'Runtime')
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
                        '--manifest',str(manifest),'--socket',str(endpoint),'--token-file',str(tf),'--verify-installation'],env=env,cwd=work,stdout=log,stderr=subprocess.STDOUT,check=True)
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
    record=dict(status='Failed',scope='Actual installed isolated QA worker under per-process outbound-IP and source-checkout read denial; manual packaged launcher, not Resolve automatic startup or whole-Mac offline qualification',
                artifact_sha256=artifact['sha256'],package_build_id=installed['build_id'],outbound_ip_denied_errno=int(check.stdout.strip()),source_checkout_read_denied=True,policy=policy,interpreter=interpreter)
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
        stop();verify_files(tree,installed['inventory'],protected=True)
        assert paths_before=={str(p) for folder in ('Runtime','Models') for p in (product/folder).rglob('*')},'Generated files inside protected payload'
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
