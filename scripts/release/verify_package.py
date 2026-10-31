#!/usr/bin/env python3
"""Expand and verify the complete final package, including executable installer logic."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET
from common import ROOT,WORK,OUT,sha,run,write_json
sys.path.insert(0,str(ROOT/'worker'))
from ckmac.maintenance import verify_files
ap=argparse.ArgumentParser();ap.add_argument('package',type=Path);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
expanded=WORK/('candidate-expanded-'+a.package.stem)
if expanded.exists():shutil.rmtree(expanded)
run('/usr/sbin/pkgutil','--expand-full',a.package,expanded)
release=a.package.resolve().parent
policy=json.loads((release/'repair-policy.json').read_text())
verify_files(expanded,policy['expanded_inventory'])
actual={p.relative_to(expanded).as_posix() for p in expanded.rglob('*') if (p.is_file() or p.is_symlink()) and p.relative_to(expanded).as_posix() not in policy['excluded_paths']}
assert actual=={r['path'] for r in policy['expanded_inventory']},'Unexpected archive contents'
for rel,digest in policy['component_definitions'].items():
    doc=ET.parse(expanded/rel)
    for item in doc.iter():
        if 'installKBytes' in item.attrib:item.set('installKBytes','0')
    assert hashlib.sha256(ET.tostring(doc.getroot())).hexdigest()==digest,rel
for name in ('repair-policy.json','install-manifest.json'):
    for p in expanded.rglob(name):assert p.read_bytes()==(release/name).read_bytes(),str(p)
bundles=list(expanded.rglob('*.ofx.bundle'))+list(expanded.rglob('*Manager.app'))
assert len(bundles)==2,'Expected exactly one OFX and one Manager bundle'
for p in bundles:run('/usr/bin/codesign','--verify','--strict',p)
write_json(a.output,dict(status='Passed',package=a.package.name,size=a.package.stat().st_size,sha256=sha(a.package),expanded_inventory_records=len(actual),payload_and_executable_logic_verified=True,code_signatures='ad hoc; verified',package_signature='unsigned'))
print('Final package inventory, executable logic and contained bundle signatures verified',flush=True)
