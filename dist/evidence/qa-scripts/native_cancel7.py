import json,os,pathlib,socket,struct,time
assert project.GetName()=='CorridorKeyMac Native Qualification 0.9.1'
m=json.loads(pathlib.Path('/Library/Application Support/HarvestPictures/CorridorKeyMac/active.json').read_text());assert m['build_id']=='0.9.7-b1.027347b5a7e5'
endpoint=pathlib.Path('/private/tmp')/('ckmac-'+str(os.getuid()))/(m['build_id']+'.sock');token=pathlib.Path(str(endpoint)+'.token').read_text()
def exact(s,n):
 b=bytearray()
 while len(b)<n:
  x=s.recv(n-len(b));assert x;b.extend(x)
 return bytes(b)
def health():
 b=json.dumps(dict(op='health',protocol=2,build_id=m['build_id'],token=token,payload_bytes=0)).encode()
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(10);s.connect(str(endpoint));s.sendall(b'CKJ2'+struct.pack('>I',len(b))+b);n=struct.unpack('>I',exact(s,4))[0];assert n<=65536;h=json.loads(exact(s,n));assert h['ok'];return h
c=project.GetTimelineByIndex(1).GetItemListInTrack('video',1)[0].GetFusionCompByIndex(1);assert not c.IsRendering()
c.Lock()
for s in c.GetToolList(False,'Saver').values():s.SetAttrs({'TOOLB_PassThrough':True})
k=c.FindTool('CorridorKeyMac1');k.SetInput('processShot',0);k.SetInput('processShot',1);s=c.FindTool('Saver1');s.SetInput('Clip','/private/tmp/ckmac-native-qualification/0.9.7-recovery/cancelled0000.exr');s.SetAttrs({'TOOLB_PassThrough':False});c.Unlock()
assert c.Render(False,2,2,1,True,False)
start=time.monotonic();active=None
while time.monotonic()-start<15:
 h=health()
 if h['active_jobs']==1 and h['facts'].get('temporal_progress',1)<1 and c.IsRendering():active=h;break
 time.sleep(.05)
assert active is not None,'No active temporal operation observed'
t=time.monotonic();c.AbortRender();call_seconds=time.monotonic()-t
while c.IsRendering() and time.monotonic()-t<5:time.sleep(.02)
latency=time.monotonic()-t;assert not c.IsRendering() and latency<2,latency
output=pathlib.Path('/private/tmp/ckmac-native-qualification/0.9.7-recovery/cancelled0002.exr');assert not output.exists()
result=dict(status='Recorded',artifact_sha256='f58245db7b45ce9ead793732c7e05f12d97c9c9a6e6681c744437b040ff07e86',scope='Actual installed0.9.7 host AbortRender during genuine Full1080 temporal work; peer output is checked separately',worker_pid=active['pid'],active_temporal_progress=active['facts']['temporal_progress'],abort_call_seconds=call_seconds,host_wait_cancel_seconds=latency,obsolete_output_exists=output.exists())
pathlib.Path('/Users/harvest/Documents/Ysew_Project/GIT/corridorkey-mac-ofx/.build/evidence/native-0.9.7-host-cancel.json').write_text(json.dumps(result,indent=2)+'\n')
