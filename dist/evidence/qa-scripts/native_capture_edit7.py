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
 r=dict(op='health',protocol=2,build_id=m['build_id'],token=token,payload_bytes=0);b=json.dumps(r).encode()
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(10);s.connect(str(endpoint));s.sendall(b'CKJ2'+struct.pack('>I',len(b))+b);n=struct.unpack('>I',exact(s,4))[0];assert n<=65536;h=json.loads(exact(s,n));assert h['ok'];return h
c=project.GetTimelineByIndex(1).GetItemListInTrack('video',1)[0].GetFusionCompByIndex(1);assert not c.IsRendering()
c.Lock()
for s in c.GetToolList(False,'Saver').values():s.SetAttrs({'TOOLB_PassThrough':True})
e=c.FindTool('AcquisitionEditQA');e.Gain.SetExpression('1.10')
k=c.FindTool('AcquisitionKeyQA');k.FindMainOutput(1).EnableDiskCache(False)
for n,v in {'processingMode':1,'internalResolution':3,'analysisStart':0,'analysisEnd':11,'useAlphaHint':0,'outputMode':0}.items():k.SetInput(n,v)
k.SetInput('processShot',0);k.SetInput('processShot',1)
s=c.FindTool('AcquisitionSaverQA');s.SetInput('Clip','/private/tmp/ckmac-native-qualification/0.9.7-capture-edit/rgba0000.exr');s.SetAttrs({'TOOLB_PassThrough':False});c.Unlock()
h0=health();assert h0['active_jobs']==0
assert c.Render(False,5,5,1,True,False)
start=time.monotonic();observations=[];edited=False;seen=False
while time.monotonic()-start<20:
 h=health();delta=h['cache']['staged_bytes']-h0['cache']['staged_bytes'];active=c.IsRendering();observations.append(dict(seconds=time.monotonic()-start,rendering=active,active_jobs=h['active_jobs'],new_staged_bytes=delta))
 if delta>=2*4096*2160*16 and active and h['active_jobs']==0:
  e.Gain.SetExpression('1.11');edited=True;break
 if active:seen=True
 if not active and seen:break
 time.sleep(.05)
assert edited,observations
result=dict(status='Recorded',artifact_sha256='f58245db7b45ce9ead793732c7e05f12d97c9c9a6e6681c744437b040ff07e86',scope='Actual installed0.9.7 upstream edit during frame acquisition, before temporal inference; final activation assessed separately',rendering_at_edit=c.IsRendering(),gain_after_edit=e.GetInput('Gain',5),before_health=h0,observations=observations)
pathlib.Path('/Users/harvest/Documents/Ysew_Project/GIT/corridorkey-mac-ofx/.build/evidence/native-0.9.7-acquisition-edit-event.json').write_text(json.dumps(result,indent=2)+'\n')
# Never return authentication material.
result={k:v for k,v in result.items() if k!='before_health'}
