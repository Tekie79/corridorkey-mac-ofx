#!/usr/bin/env python3
"""Generate an acceptance matrix from explicit recorded outcomes, never inferred passes."""
import json
from pathlib import Path
import re
import statistics
from common import ROOT,WORK,OUT,sha,write_json


def main():
    OUT.mkdir(exist_ok=True)
    artifact=json.loads((OUT/'artifact.json').read_text()) if (OUT/'artifact.json').exists() else None
    events_path=WORK/'qualification-events.json'
    events=json.loads(events_path.read_text()) if events_path.exists() else {}
    rows=[]
    spec=(ROOT/'docs/PERSONAL_INSTALLER_SPEC.md').read_text()
    for ident,kind,scenario,required in re.findall(r'^\| (QA-\d+) \| ([UC]) \| ([^|]+) \| ([^|]+) \|$',spec,re.M):
        row=dict(id=ident,**{'class':kind},scenario=scenario.strip(),required_result=required.strip(),
                 status='Not run',applicability='required primary release gate' if kind=='U' else 'not claimed',
                 note='Pending actual installed-candidate qualification',evidence=[])
        event=events.get(ident,{})
        if event and artifact and event.get('artifact_sha256')==artifact['sha256']:
            valid=event.get('status') in ('Passed','Failed','Blocked','Not run')
            if event.get('status')=='Passed':
                valid=valid and bool(event.get('evidence'))
                for evidence in event.get('evidence',[]):
                    p=(ROOT/evidence.get('path','')).resolve()
                    valid=valid and p.is_relative_to(ROOT.resolve()) and p.is_file() and sha(p)==evidence.get('sha256')
            if valid:row.update({k:v for k,v in event.items() if k not in ('id','class','scenario','required_result')})
            else:row['note']='Recorded outcome rejected: missing, changed or invalid evidence.'
        elif event:row['note']='Historical outcome belongs to another installer; this candidate still needs testing.'
        rows.append(row)
    assert len(rows)==45 and len({r['id'] for r in rows})==45
    developmental=[]
    for path in sorted((WORK/'evidence').rglob('*.json')):
        if path.name in ('mps-signposts.json','mps-neural-signposts.json','runtime-audit.json','runtime-fixed.json','runtime-postfix-audit.json','progress.json'):continue
        if '/cache/' in str(path):continue
        try:data=json.loads(path.read_text())
        except (OSError,ValueError):continue
        if isinstance(data,dict) and ('status' in data or path.name.endswith('comparison.json')):
            developmental.append(dict(file=str(path.relative_to(ROOT)),sha256=sha(path),status=data.get('status','recorded'),scope=data.get('scope','See the evidence; not automatically an installed-product acceptance result')))
    complete=all(r['status']=='Passed' for r in rows if r['class']=='U' or r['applicability']=='claimed')
    combinations=events.get('_qualified_combinations',[]) if complete else []
    report=dict(release_status='QUALIFIED PERSONAL BETA' if complete and combinations and artifact and artifact.get('qualified') else 'UNQUALIFIED PERSONAL BETA',artifact=artifact,
        primary=dict(model='MacBook Pro Mac17,8',chip='Apple M5 Pro',cpu_cores=18,gpu_cores=20,unified_memory_bytes=48*2**30,macos='26.3.2',macos_build='25D2150',architecture='arm64',resolve='DaVinci Resolve Studio 21.1.1 build 10'),
        qualified_combinations=combinations,unqualified_combinations=['M2 Mac Studio: unavailable','Other OS/Resolve versions','Native UHD / 4096×2160: numerical quality failure under investigation','Free Resolve / other host contexts: not qualified','Transferred-package Gatekeeper route: not qualified'],
        acceptance=rows,development_and_partial_evidence=developmental,
        no_cpu_production_fallback=True,notes=['Portable/mock tests are not Resolve/GPU acceptance.','Per-process outbound-IP denial is recorded separately from clean-account installation.','Only explicitly recorded applicable Passed gates can qualify a final release.'])
    write_json(OUT/'qualification.json',report)
    lines=['# Native qualification — personal beta','',report['release_status'],'']
    if artifact:lines += [f"Installer: `{artifact['filename']}`",f"Bytes: {artifact['size']}",f"SHA-256: `{artifact['sha256']}`",'']
    lines += ['Primary: Apple M5 Pro MacBook Pro (20-core GPU, 48 GB), macOS 26.3.2 (25D2150), Resolve Studio 21.1.1 build 10.','No fully qualified release combination is claimed while universal gates remain incomplete.','','| Gate | Class | Result | Evidence / limitation |','| --- | --- | --- | --- |']
    for row in rows:lines.append(f"| {row['id']}: {row['scenario']} | {row['class']} | {row['status']} | {row['note'].replace('|','/')} |")
    lines += ['','## Actual model and partial native evidence','']
    for e in developmental:lines.append(f"- `{e['file']}` — {e['status']}. {e['scope']}")
    p=WORK/'evidence/GS02-single-1080p/sequence.json'
    if p.exists():
        s=json.loads(p.read_text());times=[f['seconds'] for f in s.get('frames',[])]
        if times:lines += ['',f"Direct Single Frame: {len(times)} distinct 1920×1080 frames, median {statistics.median(times):.3f} s, range {min(times):.3f}–{max(times):.3f} s. This excludes model loading and is not Deliver timing."]
    lines += ['','See `USER_GUIDE.md`, `KNOWN_LIMITATIONS.md`, source references and the original specification. Each evidence file preserves its actual scope.','']
    (OUT/'NATIVE_QUALIFICATION.md').write_text('\n'.join(lines))
    for name in ('USER_GUIDE.md','KNOWN_LIMITATIONS.md'): (OUT/name).write_bytes((ROOT/name).read_bytes())
    (OUT/'PERFORMANCE.md').write_bytes((ROOT/'docs/PERFORMANCE.md').read_bytes())
    print('Report generated; universal passes:',sum(r['class']=='U' and r['status']=='Passed' for r in rows),'of',sum(r['class']=='U' for r in rows))

if __name__=='__main__':main()
