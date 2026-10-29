#!/usr/bin/env python3
"""Build the offline personal beta; --final requires every applicable acceptance gate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET
from common import ROOT,WORK,OUT,PRODUCT,VERSION,BUILD,MODEL_SET,PYTHON,sha,write_json,run,inventory,source_identity


def copy(src,dst):
    if dst.exists():shutil.rmtree(dst)
    shutil.copytree(src,dst,symlinks=True,ignore=shutil.ignore_patterns('.git','.cache','__pycache__','*.pyc','.DS_Store'))


def hook(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('#!/bin/bash\nset -euo pipefail\n'+text+'\n')
    path.chmod(0o755)


PREFLIGHT='''
if [[ "${3:-}" != / ]]; then echo 'Only the startup volume is supported.' >&2; exit 1; fi
if [[ "$(/usr/bin/uname -m)" != arm64 ]]; then echo 'Native Apple Silicon is required.' >&2; exit 1; fi
os_major="$(/usr/bin/sw_vers -productVersion | /usr/bin/cut -d. -f1)"
if (( os_major < 14 )); then echo 'macOS 14 or newer is required.' >&2; exit 1; fi
if /usr/bin/pgrep -x Resolve >/dev/null || /usr/bin/pgrep -x Fusion >/dev/null; then
  echo 'Close DaVinci Resolve and Fusion, then retry. No host was stopped.' >&2; exit 1
fi
'''


def components(tree):
    return dict(package_version=VERSION,build_id=BUILD,model_set_id=MODEL_SET,protocol=2,
        component_versions=dict(plugin='0.9.7',worker=5,manager=2,adapter_math=3,cache_format=3,temporal='upstream-float32-continuous-RVM-configurable-Hann-v2'),
        python=str(PRODUCT/'Runtime'/BUILD/'bin/python3'),
        code_root=str(PRODUCT/'Runtime'/BUILD/'upstream'),model_root=str(PRODUCT/'Models'/MODEL_SET),
        inventory=inventory(tree))


def build(a):
    global BUILD
    if a.final:
        finalize();return
    BUILD='0.9.7-b1.'+source_identity()[:12]
    if platform.system()!='Darwin' or platform.machine()!='arm64':raise RuntimeError('Build natively on Apple Silicon')
    OUT.mkdir(exist_ok=True);WORK.mkdir(exist_ok=True)
    if not (WORK/'runtime/bin/python3').exists() or not (WORK/'models/weights/corridorkey_v2.safetensors').exists():
        run(sys.executable,ROOT/'scripts/release/acquire.py')
    run(sys.executable,ROOT/'scripts/release/lock_assets.py')
    cmake=WORK/'runtime/bin/cmake'
    run(cmake,'-S',ROOT,'-B',ROOT/'build','-DOPENFX_SDK_ROOT='+str(ROOT/'.deps/openfx'),'-DCMAKE_BUILD_TYPE=Release','-DBUILD_TESTING=ON')
    run(cmake,'--build',ROOT/'build','--parallel','6')
    if a.verify:
        run(WORK/'runtime/bin/ctest','--test-dir',ROOT/'build','--output-on-failure')
        env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'worker')
        run(WORK/'runtime/bin/python3','-m','pytest',ROOT/'tests','-q',env=env)
    stage=WORK/'package';incoming=stage/PRODUCT.relative_to('/')/'Incoming'/BUILD
    if stage.exists():shutil.rmtree(stage)
    tree=incoming/'tree';tree.mkdir(parents=True)
    runtime=tree/PRODUCT.relative_to('/')/'Runtime'/BUILD
    copy(WORK/'runtime',runtime)
    for p in (runtime/'bin').iterdir():
        if not p.name.startswith('python'):
            if p.is_dir():shutil.rmtree(p)
            else:p.unlink()
    copy(ROOT/'worker/ckmac',runtime/'lib/python3.12/site-packages/ckmac')
    code=runtime/'upstream';code.mkdir()
    shutil.copy2(ROOT/'build/ckmac-engine-launcher',runtime/'bin/ckmac-engine-launcher')
    copy(ROOT/'.deps/CorridorKey2.0/corridorkey',code/'corridorkey')
    copy(ROOT/'.deps/CorridorKey2.0/third_party',code/'third_party')
    for name in ('LICENSE','THIRD_PARTY_NOTICES.md','requirements.txt'):
        shutil.copy2(ROOT/'.deps/CorridorKey2.0'/name,code/name)
    models=tree/PRODUCT.relative_to('/')/'Models'/MODEL_SET
    copy(WORK/'models',models)
    copy(ROOT/'licenses',runtime/'licenses')
    for name in ('model-manifest.json','runtime-lock.json','requirements.lock'):
        shutil.copy2(OUT/name,runtime/name)
    copy(ROOT/'build/CorridorKeyMac.ofx.bundle',tree/'Library/OFX/Plugins/CorridorKeyMac.ofx.bundle')
    copy(ROOT/'build/CorridorKey Mac Manager.app',tree/'Applications/CorridorKey Mac Manager.app')
    maintenance=tree/PRODUCT.relative_to('/')/'Maintenance';maintenance.mkdir(parents=True)
    for name in ('USER_GUIDE.md','KNOWN_LIMITATIONS.md'):shutil.copy2(ROOT/name,maintenance/name)
    shutil.copy2(ROOT/'docs/PERFORMANCE.md',maintenance/'PERFORMANCE.md')
    shutil.copy2(ROOT/'build/ckmac-installer-tool',maintenance/'ckmac-installer-tool')
    run(sys.executable,ROOT/'scripts/release/audit_runtime.py',runtime,'--fix','--sign','--output',OUT/'native-dependencies.json')
    for p in (tree/'Library/OFX/Plugins/CorridorKeyMac.ofx.bundle',tree/'Applications/CorridorKey Mac Manager.app',maintenance/'ckmac-installer-tool'):
        run('/usr/bin/codesign','--force','--sign','-','--timestamp=none',p)
        run('/usr/bin/codesign','--verify','--strict',p)
    # Narrow installed removal packages contain no model/runtime payload.
    uninstalls={}
    for choice,op in [('KeepModels','uninstall-keep'),('RemoveAll','uninstall-all')]:
        hooks=WORK/('uninstall-'+choice);hooks.mkdir(exist_ok=True)
        hook(hooks/'preinstall',PREFLIGHT+f'\nexec "{PRODUCT}/Maintenance/ckmac-installer-tool" {op} "$3"')
        hook(hooks/'postinstall','/usr/sbin/pkgutil --forget org.harvestpictures.CorridorKeyMac.personal >/dev/null 2>&1 || true')
        pkg=OUT/f'CorridorKeyMac-Uninstall-{choice}.pkg'
        run('/usr/bin/pkgbuild','--nopayload','--scripts',hooks,'--identifier','org.harvestpictures.CorridorKeyMac.uninstall.'+choice,'--version','0.9.7',pkg)
        shutil.copy2(pkg,maintenance/pkg.name);uninstalls[pkg.name]=sha(pkg)
    active=components(tree);active.pop('inventory')
    write_json(tree/PRODUCT.relative_to('/')/'active.json',active)
    manifest=components(tree);manifest['uninstall_packages']=uninstalls
    write_json(incoming/'install-manifest.json',manifest)
    write_json(tree/PRODUCT.relative_to('/')/'install-manifest.json',manifest)
    write_json(tree/PRODUCT.relative_to('/')/'repair-policy.json',{})
    hooks=WORK/'install-hooks';hooks.mkdir(exist_ok=True)
    payload_size=sum(p.stat().st_size for p in tree.rglob('*') if p.is_file())
    required_kb=(payload_size*3+5*2**30)//1024
    hook(hooks/'preinstall',PREFLIGHT+f'''
free_kb="$(/bin/df -k / | /usr/bin/awk 'NR==2 {{print $4}}')"
if (( free_kb < {required_kb} )); then echo 'Insufficient space for staging, installation and rollback.' >&2; exit 1; fi
''')
    hook(hooks/'postinstall',PREFLIGHT+f'\nexec "{PRODUCT}/Incoming/{BUILD}/tree{PRODUCT}/Maintenance/ckmac-installer-tool" activate "$3" "{PRODUCT}/Incoming/{BUILD}"')
    resources=WORK/'installer-resources';resources.mkdir(exist_ok=True)
    (resources/'welcome.html').write_text(f'<html><body><h1>CorridorKey2.0 hp beta</h1><p>Offline arm64 build {VERSION}. Native workflow qualification is incomplete.</p><p>Installed files: {payload_size/2**30:.2f} GiB. Allow {required_kb/2**20:.2f} GiB free for staging and rollback. Close Resolve and Fusion before installation.</p></body></html>')
    (resources/'conclusion.html').write_text('<html><body><p>Installation complete. Open DaVinci Resolve and add CorridorKey2.0 hp beta. Its GPU engine starts automatically.</p><p>This is an unqualified personal beta. Read the native qualification report before relying on its output.</p></body></html>')
    distribution=WORK/'Distribution.xml'
    distribution.write_text('''<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2"><title>CorridorKey2.0 hp beta</title>
<welcome file="welcome.html" mime-type="text/html"/><conclusion file="conclusion.html" mime-type="text/html"/>
<options customize="never" require-scripts="false" hostArchitectures="arm64" rootVolumeOnly="true"/>
<domains enable_localSystem="true" enable_currentUserHome="false" enable_anywhere="false"/>
<allowed-os-versions><os-version min="14.0"/></allowed-os-versions>
<choices-outline><line choice="default"/></choices-outline><choice id="default" visible="false"><pkg-ref id="org.harvestpictures.CorridorKeyMac.personal"/></choice>
<pkg-ref id="org.harvestpictures.CorridorKeyMac.personal" version="0.9.7" onConclusion="none">payload.pkg</pkg-ref>
</installer-gui-script>''')
    pkg=OUT/f'CorridorKeyMac-{VERSION}-arm64-Offline.pkg'
    def package():
        components=WORK/'components.plist'
        run('/usr/bin/pkgbuild','--analyze','--root',stage,components)
        definitions=plistlib.loads(components.read_bytes())
        for d in definitions:
            d['BundleIsRelocatable']=False;d['BundleIsVersionChecked']=False
        components.write_bytes(plistlib.dumps(definitions))
        run('/usr/bin/pkgbuild','--root',stage,'--component-plist',components,'--scripts',hooks,'--identifier','org.harvestpictures.CorridorKeyMac.personal','--version','0.9.7','--install-location','/','--ownership','recommended','--compression','latest','--min-os-version','14.0',WORK/'payload.pkg')
        run('/usr/bin/productbuild','--distribution',distribution,'--resources',resources,'--package-path',WORK,pkg)
    package()
    # Protect executable package logic without a circular final-package hash.
    expanded=WORK/'expanded'
    if expanded.exists():shutil.rmtree(expanded)
    run('/usr/sbin/pkgutil','--expand-full',pkg,expanded)
    records=[];definitions={};excluded=[]
    for record in inventory(expanded):
        p=Path(record['path'])
        if p.name in ('Bom','PackageInfo','Distribution','repair-policy.json','install-manifest.json'):
            excluded.append(record['path'])
            if p.name in ('PackageInfo','Distribution'):
                doc=ET.parse(expanded/p)
                for item in doc.iter():
                    if 'installKBytes' in item.attrib:item.set('installKBytes','0')
                definitions[str(p)]=hashlib.sha256(ET.tostring(doc.getroot())).hexdigest()
        else:records.append(record)
    policy=dict(expanded_inventory=records,component_definitions=definitions,excluded_paths=excluded,
                bom_policy='BOM is metadata; every payload and executable script is independently verified.')
    write_json(tree/PRODUCT.relative_to('/')/'repair-policy.json',policy)
    # Same manifest bytes appear in the activation envelope and installed tree.
    package()
    shutil.copy2(incoming/'install-manifest.json',OUT/'install-manifest.json')
    shutil.copy2(tree/PRODUCT.relative_to('/')/'repair-policy.json',OUT/'repair-policy.json')
    checks=[]
    for p in sorted(OUT.glob('*.pkg')):checks.append(f'{sha(p)}  {p.name}')
    (OUT/'release-checksums.txt').write_text('\n'.join(checks)+'\n')
    write_json(OUT/'artifact.json',dict(filename=pkg.name,size=pkg.stat().st_size,sha256=sha(pkg),signing_profile='Personal Local: contained code ad-hoc signed; package unsigned',qualified=False,installed_bytes=payload_size))
    print(f'Built {pkg} ({pkg.stat().st_size} bytes); this beta is not a qualified 1.0 release',flush=True)

def finalize():
    """Promote only the exact already-built and qualified candidate; never rebuild it."""
    import re
    artifact=json.loads((OUT/'artifact.json').read_text())
    pkg=OUT/artifact['filename']
    if pkg.stat().st_size!=artifact['size'] or sha(pkg)!=artifact['sha256']:raise RuntimeError('Candidate bytes differ from the artifact record')
    q=json.loads((OUT/'qualification.json').read_text())
    if not q.get('artifact') or q['artifact']['sha256']!=artifact['sha256']:raise RuntimeError('Qualification belongs to a different artifact')
    expected=dict(re.findall(r'^\| (QA-\d+) \| ([UC]) \|', (ROOT/'docs/PERSONAL_INSTALLER_SPEC.md').read_text(),re.M))
    rows={r['id']:r for r in q['acceptance']}
    if len(expected)!=45 or len(q['acceptance'])!=45 or set(rows)!=set(expected):raise RuntimeError('The complete 45-row matrix is required')
    for ident,kind in expected.items():
        r=rows[ident]
        if r['class']!=kind:raise RuntimeError('Acceptance gate classification changed: '+ident)
        required=kind=='U' or r.get('applicability')=='claimed'
        if not required:continue
        if r['status']!='Passed' or r.get('artifact_sha256')!=artifact['sha256'] or not r.get('evidence'):raise RuntimeError('Required artifact-bound gate is incomplete: '+ident)
        for evidence in r['evidence']:
            p=ROOT/evidence['path']
            if not p.is_file() or sha(p)!=evidence['sha256']:raise RuntimeError('Missing/changed evidence for '+ident)
    if not q.get('qualified_combinations'):raise RuntimeError('No exact qualified hardware/OS/host combination was recorded')
    artifact['qualified']=True;write_json(OUT/'artifact.json',artifact)
    q['release_status']='QUALIFIED PERSONAL BETA';q['artifact']=artifact;write_json(OUT/'qualification.json',q)
    run(sys.executable,ROOT/'scripts/release/report.py')
    print('Qualified unchanged installer:',pkg)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile',choices=['personal'],default='personal')
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--final',action='store_true')
    build(ap.parse_args())
