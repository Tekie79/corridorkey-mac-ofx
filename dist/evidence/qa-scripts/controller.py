import os,time,pathlib,json
control=pathlib.Path('/private/tmp/ckmac-qa7-control');root=pathlib.Path('/Users/harvest/Documents/Ysew_Project/GIT/corridorkey-mac-ofx');away=root.with_name('corridorkey-mac-ofx.qa-away-0.9.7')
def state(s,**data):
 p=control/'state.json';temp=control/'state.tmp';temp.write_text(json.dumps(dict(state=s,unix=time.time(),**data)));os.replace(temp,p)
state('waiting')
try:
 start=time.monotonic()
 while not (control/'begin').exists():
  if time.monotonic()-start>600:raise TimeoutError('No native test trigger')
  time.sleep(.05)
 assert root.is_dir() and not root.is_symlink() and not away.exists()
 os.rename(root,away);state('away',root_absent=not root.exists())
 start=time.monotonic()
 while not (control/'restore').exists() and time.monotonic()-start<120:time.sleep(.05)
finally:
 if away.exists() and not root.exists():os.rename(away,root)
 state('restored' if root.is_dir() and not away.exists() else 'needs_attention',root_exists=root.is_dir(),away_exists=away.exists())
