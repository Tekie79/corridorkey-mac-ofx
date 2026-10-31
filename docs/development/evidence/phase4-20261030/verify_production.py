import hashlib,json,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'worker'))
from ckmac.maintenance import verify_files
root=Path('/Library/Application Support/HarvestPictures/CorridorKeyMac')
m=json.loads((root/'install-manifest.json').read_text());verify_files(Path('/'),m['inventory'],protected=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=[root/'active.json',root/'install-manifest.json',root/'repair-policy.json',Path('/Library/OFX/Plugins/CorridorKeyMac.ofx.bundle/Contents/MacOS/CorridorKeyMac.ofx')]
record=dict(verified_inventory_records=len(m['inventory']),hashes={str(p):sha(p) for p in paths},receipts=[x for x in subprocess.run(['/usr/sbin/pkgutil','--pkgs'],capture_output=True,text=True).stdout.splitlines() if x.startswith('org.harvestpictures.CorridorKeyMac')])
Path(sys.argv[1]).write_text(json.dumps(record,indent=2)+'\n')
print('Production inventory verified:',len(m['inventory']))
