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

import subprocess,signal
control=pathlib.Path('/private/tmp/ckmac-qa7-control')
c=project.GetTimelineByIndex(1).GetItemListInTrack('video',1)[0].GetFusionCompByIndex(1);assert not c.IsRendering()
c.Lock()
for s in c.GetToolList(False,'Saver').values():s.SetAttrs({'TOOLB_PassThrough':True})
k=c.FindTool('CorridorKeyMac1');k.SetInput('processShot',0);k.SetInput('processShot',1);s=c.FindTool('Saver1');s.SetInput('Clip','/private/tmp/ckmac-native-qualification/0.9.7-recovery/crash0000.exr');s.SetAttrs({'TOOLB_PassThrough':False});c.Unlock()
assert c.Render(False,2,2,1,True,False)
start=time.monotonic();active=None
while time.monotonic()-start<20:
 h=health()
 if h['active_jobs']==1 and h['facts'].get('temporal_progress',1)<1 and c.IsRendering():active=h;break
 time.sleep(.05)
assert active
(control/'begin').write_text('authorized checkout relocation during native crash recovery')
start=time.monotonic()
while time.monotonic()-start<5:
 if (control/'state.json').exists() and json.loads((control/'state.json').read_text())['state']=='away':break
 time.sleep(.02)
assert not pathlib.Path('/Users/harvest/Documents/Ysew_Project/GIT/corridorkey-mac-ofx').exists()
pid=active['pid'];cmd=subprocess.run(['/bin/ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
assert 'ckmac.engine' in cmd and '0.9.7-b1.027347b5a7e5' in cmd
latest=health();assert latest['active_jobs']==1 and c.IsRendering()
os.kill(pid,signal.SIGKILL)
start=time.monotonic()
while c.IsRendering() and time.monotonic()-start<8:time.sleep(.05)
assert not c.IsRendering()
result=dict(status='Recorded',worker_killed=pid,active_progress_at_kill=latest['facts'].get('temporal_progress'),checkout_absent=True,host_survived=True,failed_output_exists=pathlib.Path('/private/tmp/ckmac-native-qualification/0.9.7-recovery/crash0002.exr').exists())
(control/'crash-event.json').write_text(json.dumps(result,indent=2)+'\n')
