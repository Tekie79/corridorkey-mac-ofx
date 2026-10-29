import json,os,pathlib,subprocess,secrets,socket,struct,time
import numpy as np
from PIL import Image
m=json.loads(pathlib.Path('/Library/Application Support/HarvestPictures/CorridorKeyMac/active.json').read_text());assert m['build_id']=='0.9.6-b1.8e66e8a42b10'
w=pathlib.Path('/private/tmp/ckmac-conflict');w.mkdir(mode=0o700,exist_ok=True);(w/'poison').mkdir(exist_ok=True);(w/'poison/torch.py').write_text("raise RuntimeError('FOREIGN_PYTHONPATH_WAS_USED')\n")
token=secrets.token_hex(32);tf=w/'token';tf.write_text(token);tf.chmod(0o600);endpoint=w/'engine.sock'
env=dict(PATH='/usr/bin:/bin',HOME=str(pathlib.Path.home()),HF_HOME=str(w/'cache/huggingface'),PYTHONPATH=str(w/'poison'),PYTHONHOME=str(w/'poison/missing-python'),CONDA_PREFIX=str(w/'poison'),PYTORCH_ENABLE_MPS_FALLBACK='1',HF_HUB_OFFLINE='0',TRANSFORMERS_OFFLINE='0')
policy='(version 1)(allow default)(deny network-outbound (remote ip "*:*"))'
check=subprocess.run(['/usr/bin/sandbox-exec','-p',policy,m['python'],'-I','-B','-c',"import socket,errno; s=socket.socket(); s.settimeout(1)\ntry:s.connect(('1.1.1.1',443));raise RuntimeError('outbound allowed')\nexcept OSError as e:assert e.errno in (errno.EPERM,errno.EACCES);print('OS denied outbound IP')"],env=env,text=True,capture_output=True);assert check.returncode==0,check.stderr
log=(w/'engine.log').open('w');child=subprocess.Popen(['/usr/bin/sandbox-exec','-p',policy,m['python'],'-I','-B','-u','-m','ckmac.engine','--manifest','/Library/Application Support/HarvestPictures/CorridorKeyMac/active.json','--socket',str(endpoint),'--token-file',str(tf),'--verify-installation'],env=env,stdout=log,stderr=subprocess.STDOUT)
def exact(c,n):
 b=bytearray()
 while len(b)<n:
  q=c.recv(n-len(b));assert q;b.extend(q)
 return b
def request(op,payload=b'',**kwargs):
 msg=dict(op=op,protocol=2,build_id=m['build_id'],token=token,payload_bytes=len(payload),session_id='qualification-env-conflict',request_id=secrets.token_hex(8),effect_generation=1,**kwargs);b=json.dumps(msg).encode()
 with socket.socket(socket.AF_UNIX) as c:
  c.settimeout(60);c.connect(str(endpoint));c.sendall(b'CKJ2'+struct.pack('>I',len(b))+b+payload);n=struct.unpack('>I',exact(c,4))[0];assert n<=65536;a=json.loads(exact(c,n));assert a['ok'],a.get('error');return a,bytes(exact(c,a['payload_bytes']))
r={'status':'Failed','artifact_sha256':'7a023538ad322b9eee26357b3dd2c2aecc16c292f6feb44837e3ffa00d590c0a','scope':'Actual installed private interpreter and production engine entrypoint under conflicting PYTHONHOME/PYTHONPATH/Conda, hostile torch.py, requested fallback1 and offline flags0; OS denies outbound IP. Isolated QA process, not native supervisor or clean-account installation.'}
try:
 start=time.monotonic();states=[]
 while time.monotonic()-start<120:
  assert child.poll() is None,(w/'engine.log').read_text()
  if endpoint.exists():
   h,_=request('health');states.append(h['state'])
   if h['state']=='ready':break
   assert h['state']!='error',h['error']
  time.sleep(.1)
 else:raise TimeoutError('Private engine startup')
 im=Image.open('/private/tmp/ckmac-conflict/frame.png').convert('RGB').resize((256,144));rgb=np.asarray(im,dtype=np.float32)/255;x=np.concatenate([rgb,np.ones((*rgb.shape[:2],1),np.float32)],axis=2).astype('<f4')
 _,data=request('frame',x.tobytes(),width=256,height=144,input_space=0,hint=False,quality=.75,despill=0,profile=dict(resolution=0,window=4,memory_limit=0,low_memory=False,internal_hint_quality=.95,reference_index=0));out=np.frombuffer(data,dtype='<f4').reshape(144,256,4);h,_=request('health');assert h['user_frames_completed']==1 and h['facts']['backend']['device']=='mps' and not h['facts']['backend']['automatic_cpu_model_fallback'] and np.isfinite(out).all()
 r.update(status='Passed',states=list(dict.fromkeys(states)),outbound_ip_denied=True,private_python=m['python'],hostile_pythonpath_ignored=True,backend=h['facts']['backend'],finite=True,frame_shape=list(out.shape),source_checkout_absent=not pathlib.Path('/Users/harvest/Documents/Ysew_Project/GIT/corridorkey-mac-ofx').exists());request('release');child.wait(timeout=10)
finally:
 if child.poll() is None:child.terminate();child.wait(timeout=10)
 log.close();(w/'result.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2),flush=True)
