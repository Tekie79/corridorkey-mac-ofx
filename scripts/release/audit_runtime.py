"""Audit each native image's arm64 slice, minimum OS, and linked library roots."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from common import write_json

ap=argparse.ArgumentParser()
ap.add_argument('root',type=Path)
ap.add_argument('--output',type=Path,required=True)
ap.add_argument('--sign',action='store_true')
ap.add_argument('--fix',action='store_true')
args=ap.parse_args()
images=[]
errors=[]
for p in sorted(args.root.rglob('*')):
    if p.is_symlink() or not p.is_file():continue
    with p.open('rb') as f:magic=f.read(4)
    if magic not in (b'\xcf\xfa\xed\xfe',b'\xca\xfe\xba\xbe',b'\xfe\xed\xfa\xcf',b'\xbe\xba\xfe\xca'):continue
    arch=subprocess.check_output(['/usr/bin/lipo','-archs',str(p)],text=True).strip()
    deps=subprocess.check_output(['/usr/bin/otool','-L',str(p)],text=True)
    commands=subprocess.check_output(['/usr/bin/otool','-l',str(p)],text=True)
    minimum=re.findall(r'\bminos\s+(\d+\.\d+(?:\.\d+)?)',commands)
    if 'arm64' not in arch.split():errors.append(f'No arm64: {p}')
    if any(tuple(map(int,v.split('.')[:2]))>(14,0) for v in minimum):errors.append(f'Deployment target exceeds 14.0: {p}: {minimum}')
    libraries=[]
    own_id=re.search(r'cmd LC_ID_DYLIB\n\s+cmdsize \d+\n\s+name (.*?) \(offset',commands)
    own_id=own_id.group(1) if own_id else None
    if args.fix and own_id and own_id.startswith('/'):
        subprocess.run(['/usr/bin/install_name_tool','-id','@rpath/'+p.name,str(p)],check=True,capture_output=True)
    for line in deps.splitlines()[1:]:
        lib=line.strip().split(' (')[0]
        if not lib or line.endswith(':'):continue
        if lib==own_id:continue
        libraries.append(lib)
        if lib.startswith('/') and not lib.startswith(('/System/Library/','/usr/lib/')):
            errors.append(f'External non-system dependency: {p}: {lib}')
    rpaths=re.findall(r'cmd LC_RPATH\n\s+cmdsize \d+\n\s+path (.*?) \(offset',commands)
    for path in rpaths:
        if path.startswith('/') and not path.startswith(('/System/Library/','/usr/lib/')):
            if args.fix:
                subprocess.run(['/usr/bin/install_name_tool','-delete_rpath',path,str(p)],check=True,capture_output=True)
            else:
                errors.append(f'Absolute rpath: {p}: {path}')
    images.append(dict(path=str(p.relative_to(args.root)),architecture=arch,minimum_os=minimum,libraries=libraries,rpaths=rpaths))
if not errors and args.sign:
    for item in images:
        p=args.root/item['path']
        subprocess.run(['/usr/bin/codesign','--force','--sign','-','--timestamp=none',str(p)],check=True,capture_output=True)
        subprocess.run(['/usr/bin/codesign','--verify','--strict',str(p)],check=True,capture_output=True)
write_json(args.output,dict(status='Failed' if errors else 'Passed',images=images,errors=errors))
print(f'Audited {len(images)} native images; {len(errors)} errors')
for error in errors:print(error)
raise SystemExit(bool(errors))
