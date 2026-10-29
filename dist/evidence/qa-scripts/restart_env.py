import json,os,pathlib,socket,struct,time
assert project.GetName()=='CorridorKeyMac Native Qualification 0.9.1'
m=json.loads(pathlib.Path('/Library/Application Support/HarvestPictures/CorridorKeyMac/active.json').read_text());assert m['build_id']=='0.9.7-b1.027347b5a7e5'
endpoint=pathlib.Path('/private/tmp')/('ckmac-'+str(os.getuid()))/(m['build_id']+'.sock');token_unused=None
def exact(s,n):
 b=bytearray()
 while len(b)<n:
  x=s.recv(n-len(b));assert x;b.extend(x)
 return bytes(b)
def health():
 token=pathlib.Path(str(endpoint)+'.token').read_text()
 b=json.dumps(dict(op='health',protocol=2,build_id=m['build_id'],token=token,payload_bytes=0)).encode()
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(10);s.connect(str(endpoint));s.sendall(b'CKJ2'+struct.pack('>I',len(b))+b);n=struct.unpack('>I',exact(s,4))[0];assert n<=65536;h=json.loads(exact(s,n));assert h['ok'];return h

import subprocess
control=pathlib.Path('/private/tmp/ckmac-qa7-control');assert pathlib.Path('/Users/harvest/Documents/Ysew_Project/GIT/corridorkey-mac-ofx').is_dir()
c=project.GetTimelineByIndex(1).GetItemListInTrack('video',1)[0].GetFusionCompByIndex(1);assert not c.IsRendering()
c.Lock();c.FindTool('Saver1').SetInput('Clip','/private/tmp/ckmac-native-qualification/0.9.7-recovery/recovered0000.exr');s=c.FindTool('PeerSaver7');s.SetInput('Clip','/private/tmp/ckmac-native-qualification/0.9.7-recovery/peer-recovered0000.exr');s.SetAttrs({'TOOLB_PassThrough':False});c.Unlock()
env=dict(HOME=str(pathlib.Path.home()),PATH='/usr/bin:/bin:/usr/sbin:/sbin',TMPDIR='/private/tmp',PYTHONHOME=str(control/'poison/missing-python'),PYTHONPATH=str(control/'poison'),CONDA_PREFIX=str(control/'poison'),PYTORCH_ENABLE_MPS_FALLBACK='1',HF_HUB_OFFLINE='0',TRANSFORMERS_OFFLINE='0')
log=(control/'concurrent.json').open('w');err=(control/'concurrent.stderr').open('w')
child=subprocess.Popen(['/usr/bin/sandbox-exec','-p','(version 1)(allow default)(deny network-outbound (remote ip "*:*"))',str(control/'worker-concurrency7'),str(control/'fixture.rgba')],env=env,stdout=log,stderr=err,start_new_session=True)
start=time.monotonic();startup=None
while time.monotonic()-start<20:
 assert child.poll() is None,(control/'concurrent.stderr').read_text()
 try:
  h=health()
  if h['state'] not in ('stopping','error'):startup=h;break
 except (OSError,AssertionError):pass
 time.sleep(.05)
assert startup and startup['state']!='ready',startup
assert c.Render(False,2,2,1,True,False)
result=dict(status='Recorded',native_retry_started_during_private_worker_startup=True,startup_state=startup['state'],new_worker_pid=startup['pid'],concurrent_client_pid=child.pid,checkout_absent=False,poisoned_python_environment=True,outbound_ip_denial_policy=True)
(control/'env-restart-event.json').write_text(json.dumps(result,indent=2)+'\n')
