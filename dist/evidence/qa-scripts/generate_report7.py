from pathlib import Path
import runpy,sys,json
sys.path.insert(0,'scripts/release')
names=['USER_GUIDE.md','KNOWN_LIMITATIONS.md','PERFORMANCE.md'];before={n:(Path('dist')/n).read_bytes() for n in names}
runpy.run_path('scripts/release/report.py',run_name='__main__')
for n,b in before.items():(Path('dist')/n).write_bytes(b)
p=Path('dist/NATIVE_QUALIFICATION.md');s=p.read_text();r=json.loads(Path('dist/qualification.json').read_text());u=[x for x in r['acceptance'] if x['class']=='U'];count=sum(x['status']=='Passed' for x in u)
intro=f'''**Exact installed artifact: 0.9.7-beta.1, build 0.9.7-b1.027347b5a7e5.**

{count} of {len(u)} universal acceptance gates currently pass. Real MPS, both 60-frame
1080p modes, native Fusion Merge/Deliver, 30000/1001 timing, source-edit safety,
crash recovery and cached playback ran on this Mac. Remaining rows below are
explicit; owner-account installation and per-process IP denial do not establish
clean-account or globally offline acceptance. A physical Mac reboot is also
outstanding for DONE-08. This remains a beta, with no fully qualified combination.

Full 1080p model inference remains offline (representative distinct frame 2.822 s).
Temporal analysis of 60 frames took 245.895 s. Actual unlocked Fusion disk-cache
playback measured 24.681 fps on the 25 fps loop. Cached playback is separate from
uncached inference; a component cache benchmark is not an end-to-end speedup.

The illustrated offline [user book](CorridorKey2.0-hp-beta-User-Book.html) has 12
bookmarked chapters and five embedded actual screenshots. Static anchors, PNGs,
JavaScript syntax and offline asset checks pass. Browser visual preview was
blocked by Browser Use policy; screenshots themselves were inspected. The HTML
and delivery Markdown are a later documentation revision; the source ZIP retains
the exact packaged build source and its original embedded documentation.

'''
s=s.replace('UNQUALIFIED PERSONAL BETA\n\n','UNQUALIFIED PERSONAL BETA\n\n'+intro,1)
s=s.replace('`.build/evidence/','`evidence/')
p.write_text(s)
print('Updated exact-artifact report:',count,'/',len(u))
# Retain only durable local references in the development index.
for item in r['development_and_partial_evidence']:
 old=Path(item['file']);n=old.name
 direct=Path('dist/evidence')/n
 historical=Path('dist/evidence/development')/old.relative_to('.build/evidence') if str(old).startswith('.build/evidence/') else None
 target=direct if direct.is_file() else historical
 if target and target.is_file():item['file']=str(target);item['_delivered']=True
r['development_and_partial_evidence']=[{k:v for k,v in x.items() if k!='_delivered'} for x in r['development_and_partial_evidence'] if x.get('_delivered')]
Path('dist/qualification.json').write_text(json.dumps(r,indent=2)+'\n')
s=p.read_text();start=s.find('## Actual model and partial native evidence');end=s.find('\nSee `USER_GUIDE.md`',start)
if start>=0:
 s=s[:start]+'## Durable native evidence\n\nEvery acceptance row has exact-artifact evidence paths and SHA-256 hashes in\n`qualification.json`. Compact historical development/reference records retain\ntheir original build identity under `evidence/development/`; they do not silently\nqualify this installer. Heavy test exports and caches were removed as requested.\nThe render-file inventory preserves their hashes before cleanup.\n\nThe measured compatibility boundary and performance are in `KNOWN_LIMITATIONS.md`\nand `PERFORMANCE.md`. The physical Mac handoff steps are in\n`COMPLETE_NATIVE_QUALIFICATION.md`.\n'+(s[end:] if end>=0 else '')
p.write_text(s)
