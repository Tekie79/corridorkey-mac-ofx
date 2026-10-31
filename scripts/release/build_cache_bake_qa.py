#!/usr/bin/env python3
"""Build a separate local test OFX identity; never overwrite/install production.

The QA supervisor accepts exactly the supplied same-user manifest. An already
running matching QA worker is required. This exception exists only in generated
.build source, never in production src/worker_manager.mm or a release package.
"""
import argparse,hashlib,json,plistlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser();ap.add_argument('--sdk',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);args=ap.parse_args()
original=(ROOT/'src/ofx_plugin.cpp').read_text()
if '#include "ckmac/installation.hpp"' in original:
    raise SystemExit('Legacy source-rewrite overlays are incompatible with installation profiles. Use scripts/release/build_personal_installer.sh --profile qa --verify. No legacy QA evidence was changed.')
p=ROOT/'.build/resolve-bake-qa';p.mkdir(parents=True,exist_ok=True)
source=original.replace('org.harvestpictures.CorridorKeyMac','org.harvestpictures.CorridorKeyMac.CacheBakeQA').replace('"CorridorKey2.0 hp beta"','"CorridorKey Cache Bake QA"')
(p/'ofx_plugin_qa.cpp').write_text(source)
s=(ROOT/'src/worker_manager.mm').read_text()
manifest=str(args.manifest.resolve())
s=s.replace('"/Library/Application Support/HarvestPictures/CorridorKeyMac/active.json"',json.dumps(manifest))
s=s.replace('s.st_uid!=0||',f'(s.st_uid!=0&&!(path=={json.dumps(manifest)}&&s.st_uid==getuid()))||')
(p/'worker_manager_qa.mm').write_text(s)
bundle=p/'CorridorKeyBakeQA.ofx.bundle';(bundle/'Contents/MacOS').mkdir(parents=True,exist_ok=True)
(bundle/'Contents/Info.plist').write_bytes(plistlib.dumps(dict(CFBundleExecutable='CorridorKeyBakeQA.ofx',CFBundleIdentifier='org.harvestpictures.CorridorKeyMac.CacheBakeQA',CFBundleName='CorridorKey Cache Bake QA',CFBundlePackageType='BNDL',CFBundleShortVersionString='0.0.1',CFBundleVersion='1')))
exe=bundle/'Contents/MacOS/CorridorKeyBakeQA.ofx'
subprocess.run(['clang++','-std=c++17','-O2','-shared','-fPIC','-fvisibility=hidden','-fobjc-arc','-pthread','-I'+str(ROOT/'include'),'-I'+str(args.sdk/'include'),'-DCKMAC_INSTALLED_RUNTIME',str(p/'ofx_plugin_qa.cpp'),*[str(ROOT/'src'/x) for x in ['protocol.cpp','pixels.cpp','creative.cpp']],str(p/'worker_manager_qa.mm'),str(ROOT/'src/bake.mm'),'-framework','Foundation','-framework','AppKit','-framework','Security','-o',str(exe)],check=True)
subprocess.run(['codesign','--force','--sign','-','--timestamp=none',str(bundle)],check=True)
(p/'artifact.json').write_text(json.dumps(dict(scope='Local QA alias; not installed production or qualified package',manifest=manifest,sha256=hashlib.sha256(exe.read_bytes()).hexdigest()),indent=2)+'\n')
print(exe)
