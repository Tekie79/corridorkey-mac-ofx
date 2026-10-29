"""Read-only verification and package validation for the native Manager."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import platform
import time
import zipfile

ROOT=Path('/Library/Application Support/HarvestPictures/CorridorKeyMac')

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def verify_files(root,records,protected=False):
    errors=[]
    for record in records:
        p=root/record['path']
        if not p.is_relative_to(root) or '..' in p.parts:raise ValueError('Unsafe inventory path')
        if protected:
            try:st=p.lstat()
            except OSError:errors.append(str(p));continue
            if st.st_uid!=0 or (not p.is_symlink() and st.st_mode&0o022):errors.append(str(p));continue
        if 'symlink' in record:
            if not p.is_symlink() or str(p.readlink())!=record['symlink']:errors.append(str(p))
        elif p.is_symlink() or not p.is_file() or p.stat().st_size!=record['size'] or sha(p)!=record['sha256']:
            errors.append(str(p))
    if errors:raise RuntimeError('Missing or changed files:\n'+'\n'.join(errors))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('command',choices=['verify','validate-repair','validate-uninstall','storage','diagnostics'])
    ap.add_argument('--package',type=Path)
    ap.add_argument('--cache-root',type=Path)
    a=ap.parse_args()
    m=json.loads((ROOT/'install-manifest.json').read_text())
    if a.command in ('storage','diagnostics'):
        cache=a.cache_root or Path.home()/'Library/Caches/org.harvestpictures.CorridorKeyMac'
        if not cache.is_absolute():raise ValueError('Invalid cache root')
        def size(p):return sum(q.stat().st_size for q in p.rglob('*') if q.is_file() and not q.is_symlink()) if p.exists() else 0
        active=json.loads((ROOT/'active.json').read_text())
        details=dict(build_id=active['build_id'],macos=platform.mac_ver()[0],architecture=platform.machine(),
                     runtime_bytes=size(ROOT/'Runtime'),models_bytes=size(ROOT/'Models'),cache_bytes=size(cache),
                     cache_budget_bytes=20*2**30,free_bytes=shutil.disk_usage(cache if cache.exists() else cache.parent).free,
                     cache_location=str(cache).replace(str(Path.home()),'~'))
        if a.command=='storage':print(json.dumps(details,indent=2));return
        report=Path.home()/'Library/Logs/org.harvestpictures.CorridorKeyMac/Reports'
        report.mkdir(parents=True,exist_ok=True,mode=0o700)
        destination=report/f'CorridorKey-hp-support-{time.time_ns()}.zip'
        with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('system-and-storage.json',json.dumps(details,indent=2))
            z.writestr('versions.json',json.dumps(active,indent=2).replace(str(Path.home()),'~'))
            log=cache/'engine.log'
            if log.is_file() and not log.is_symlink():z.writestr('engine.log',log.read_bytes()[-2**20:].decode('utf-8',errors='replace').replace(str(Path.home()),'~'))
        destination.chmod(0o600)
        print(f'Created local diagnostics: {destination}\nIncludes product logs, versions and device/storage facts. No project media, screenshots or tokens. Nothing was uploaded.')
        return
    if a.command=='verify':
        verify_files(Path('/'),m['inventory'],protected=True)
        print(f"Verified {len(m['inventory'])} installed files.\nBuild: {m['build_id']}\nThis is integrity verification, not GPU or Resolve qualification.")
    elif a.command=='validate-uninstall':
        p=a.package.resolve()
        if p.parent!=ROOT/'Maintenance' or p.name not in m['uninstall_packages']:
            raise ValueError('Unsupported removal package')
        if sha(p)!=m['uninstall_packages'][p.name]:raise ValueError('Uninstaller integrity mismatch; repair first')
        print('Verified installed removal package. Opening macOS Installer. Close Resolve first.')
    else:
        p=a.package.resolve()
        if not p.is_file() or p.suffix!='.pkg':raise ValueError('Select the matching offline .pkg')
        with tempfile.TemporaryDirectory(prefix='ckmac-repair-') as tmp:
            expanded=Path(tmp)/'expanded'
            subprocess.run(['/usr/sbin/pkgutil','--expand-full',str(p),str(expanded)],check=True,capture_output=True)
            # Whole expanded archive inventory includes Distribution, hook scripts,
            # nested PackageInfo, BOM and payload. No selected-package code runs.
            policy=json.loads((ROOT/'repair-policy.json').read_text())
            expected=policy['expanded_inventory']
            verify_files(expanded,expected)
            def excluded(q):
                rel=q.relative_to(expanded).as_posix()
                return rel in policy['excluded_paths']
            actual={q.relative_to(expanded).as_posix() for q in expanded.rglob('*') if (q.is_file() or q.is_symlink()) and not excluded(q)}
            if actual!={r['path'] for r in expected}:raise ValueError('Unexpected selected-package contents')
            for rel,digest in policy['component_definitions'].items():
                doc=ET.parse(expanded/rel)
                for item in doc.iter():
                    if 'installKBytes' in item.attrib:item.set('installKBytes','0')
                if hashlib.sha256(ET.tostring(doc.getroot())).hexdigest()!=digest:raise ValueError('Component definition changed')
            definitions={q.relative_to(expanded).as_posix() for q in expanded.rglob('PackageInfo')}
            if (expanded/'Distribution').exists():definitions.add('Distribution')
            if definitions!=set(policy['component_definitions']):raise ValueError('Unexpected component definitions')
            for q in expanded.rglob('repair-policy.json'):
                if q.read_bytes()!=(ROOT/'repair-policy.json').read_bytes():raise ValueError('Repair policy differs')
            for q in expanded.rglob('install-manifest.json'):
                if q.read_bytes()!=(ROOT/'install-manifest.json').read_bytes():raise ValueError('Install manifest differs')
        print('Verified complete matching offline package, including executable installer logic. Opening Installer.')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(f'Unable to proceed: {e}')
        raise SystemExit(1)
