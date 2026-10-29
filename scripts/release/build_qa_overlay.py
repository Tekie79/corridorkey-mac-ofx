#!/usr/bin/env python3
"""Local iteration only. An overlay is never a qualified full offline artifact."""
import hashlib
import json
import plistlib
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=Path('/Library/Application Support/HarvestPictures/CorridorKeyMac')
active=json.loads((BASE/'active.json').read_text())
manifest=json.loads((BASE/'install-manifest.json').read_text())
work=ROOT/'.build/performance-overlay';root=work/'root'
if root.exists():shutil.rmtree(root)
plugin=Path('Library/OFX/Plugins/CorridorKeyMac.ofx.bundle')
shutil.copytree(ROOT/'build'/plugin.name,root/plugin,symlinks=True)
subprocess.run(['codesign','--force','--sign','-','--timestamp=none',str(root/plugin)],check=True)
worker=Path(active['python']).parent.parent.relative_to('/')/'lib/python3.12/site-packages/ckmac'
for name in ('cache.py','temporal.py','engine.py'):
    dest=root/worker/name;dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'worker/ckmac'/name,dest)
for item in manifest['inventory']:
    p=root/item['path']
    if p.is_file() and not p.is_symlink():
        item.update(size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
dest=root/BASE.relative_to('/')/'install-manifest.json'
dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
scripts=work/'scripts';scripts.mkdir(exist_ok=True)
(scripts/'preinstall').write_text('''#!/bin/bash
set -euo pipefail
[[ "${3:-}" == / ]] || exit 1
if /usr/bin/pgrep -x Resolve >/dev/null || /usr/bin/pgrep -x Fusion >/dev/null; then echo 'Close Resolve before this qualification-only update.' >&2; exit 1; fi
if /usr/bin/find /private/tmp/ckmac-[0-9]* -maxdepth 1 -name '*.sock' 2>/dev/null | /usr/bin/grep -q .; then echo 'Release the affected engine before this qualification-only update.' >&2; exit 1; fi
''')
(scripts/'preinstall').chmod(0o755)
subprocess.run(['pkgbuild','--analyze','--root',str(root),str(work/'components.plist')],check=True)
definitions=plistlib.loads((work/'components.plist').read_bytes())
for d in definitions:d.update(BundleIsRelocatable=False,BundleIsVersionChecked=False)
(work/'components.plist').write_bytes(plistlib.dumps(definitions))
pkg=work/'CorridorKeyMac-QA-Performance.pkg'
subprocess.run(['pkgbuild','--root',str(root),'--component-plist',str(work/'components.plist'),'--scripts',str(scripts),'--ownership','recommended','--identifier','org.harvestpictures.CorridorKeyMac.qa.performance','--version','0.9.4.2','--install-location','/',str(pkg)],check=True)
record=dict(scope='Qualification-only overlay; not a full offline release',baseline_build=active['build_id'],sha256=hashlib.sha256(pkg.read_bytes()).hexdigest(),files=[str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()])
(work/'overlay.json').write_text(json.dumps(record,indent=2)+'\n')
print(record['sha256'])
