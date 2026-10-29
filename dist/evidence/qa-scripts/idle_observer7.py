import os,socket,struct,json,time,subprocess
from pathlib import Path
root=Path('/Users/harvest/Documents/Ysew_Project/GIT/corridorkey-mac-ofx');m=json.loads(Path('/Library/Application Support/HarvestPictures/CorridorKeyMac/active.json').read_text());ep=Path('/private/tmp')/('ckmac-'+str(os.getuid()))/(m['build_id']+'.sock')
assert subprocess.run(['/usr/bin/pgrep','-x','Resolve'],capture_output=True).returncode==1,'Close Resolve before starting idle observation.'
def exact(s,n):
 b=b''
 while len(b)<n:
  q=s.recv(n-len(b));assert q;b+=q
 return b
h=dict(op='health',protocol=2,build_id=m['build_id'],token=Path(str(ep)+'.token').read_text(),payload_bytes=0);b=json.dumps(h).encode()
with socket.socket(socket.AF_UNIX) as s:
 s.settimeout(10);s.connect(str(ep));s.sendall(b'CKJ2'+struct.pack('>I',len(b))+b);n=struct.unpack('>I',exact(s,4))[0];assert n<=65536;h=json.loads(exact(s,n))
assert h['state']=='ready' and h['active_jobs']==0 and h['user_frames_completed']>=1
pid=h['pid'];start=time.monotonic();unix=time.time();out=root/'.build/evidence/native-0.9.7-idle-expiry.json';r=dict(status='Recorded',artifact_sha256='f58245db7b45ce9ead793732c7e05f12d97c9c9a6e6681c744437b040ff07e86',scope='Actual host quit after fresh native MPS inference; unmodified installed worker600s idle deadline. A single initial health request resets activity, then only process/socket existence is observed. No release, signal, fake clock or repeated health requests.',pid=pid,host_closed=True,start_unix=unix,initial_health=h)
out.write_text(json.dumps(r,indent=2)+'\n');print('Observing actual600s idle expiry of worker',pid,flush=True)
last=0
while time.monotonic()-start<630:
 try:os.kill(pid,0);alive=True
 except ProcessLookupError:alive=False
 elapsed=time.monotonic()-start
 if not alive:
  r.update(status='Passed' if 599<=elapsed<=630 and not ep.exists() else 'Failed',elapsed_seconds=elapsed,worker_gone=True,socket_removed=not ep.exists(),clean_marker_present=Path(str(ep)+'.clean').is_file(),end_unix=time.time());out.write_text(json.dumps(r,indent=2)+'\n');print({k:v for k,v in r.items() if k!='initial_health'},flush=True);break
 if elapsed-last>=30:print('Idle observation',round(elapsed),'seconds',flush=True);last=elapsed
 time.sleep(1)
else:
 r.update(status='Failed',elapsed_seconds=time.monotonic()-start,worker_gone=False);out.write_text(json.dumps(r,indent=2)+'\n');print('Worker exceeded the measured idle bound.',flush=True)
