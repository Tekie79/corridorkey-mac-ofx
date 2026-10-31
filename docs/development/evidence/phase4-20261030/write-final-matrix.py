import json,re,hashlib
from pathlib import Path
repo=Path.cwd();work=repo/'.build/evidence/phase4-install';out=repo/'docs/development/evidence/phase4-20261030';out.mkdir(parents=True,exist_ok=True)
if not work.exists():work=out
context=json.loads((work/'qualification-context.json').read_text())
versions={'original':'0.9.8-beta.1','qa1':'0.9.8-qa.1','qa2':'0.9.8-qa.2','qa3':'0.9.8-qa.3','qa4':'0.9.8-qa.4'}
artifacts={k:json.loads((repo/'dist'/v/'artifact.json').read_text()) for k,v in versions.items()}
builds={'original':'0.9.8-b1.32baa56c3837','qa1':'0.9.8-qa1.9a72e0ba5e4b','qa2':'0.9.8-qa2.bc3c1fd474fa','qa3':'0.9.8-qa3.efc225cfab3d','qa4':'0.9.8-qa4.f1f98dd88eee'}
def row(artifact,ident,scenario,expected,status,actual,evidence,environment='isolated QA install',gate_class=None):
 a=artifacts[artifact]
 return dict(id=ident,gate_class=gate_class,scenario=scenario,expected=expected,machine=context['machine'],macos=context['macos']+' '+context['macos_build'],resolve=context['resolve'],artifact_sha256=a['sha256'],artifact=a['filename'],environment=environment,installed_identity=builds[artifact] if environment=='isolated QA install' else None,status=status,actual=actual,evidence=evidence,defects=[])
# A broad universal gate is not passed by a narrower functional observation.
observed={
 'QA-01':('qa4-package-verification.json','Complete final archive/executable policy and 27,151 installed protected files verified; installed MPS uses local assets.'),
 'QA-05':('qa4-installed-offline.json','Packaged isolated Python ignored deliberately conflicting PYTHONHOME/PYTHONPATH/Conda values.'),
 'QA-06':('qa4-package-verification.json','Native arm64 package audit and actual installed MPS execution; no Rosetta required.'),
 'QA-07':('qa4-native-install-and-ui.json','Normal Resolve restart registered the installed QA bundle; scan and baked reads started no worker.'),
 'QA-09':('qa4-installed-offline.json','Cache-ready/model-unloaded and fixture-completed/inference states were distinct, including model-free restart hits.'),
 'QA-19':('qa4-saver-verification.json','Float RGBA preserved negative/HDR RGB and exactly one premultiplication; full 60-frame Saver and Deliver checked.'),
 'QA-22':('qa4-cache-replay-verification.json','300 actual live analyzed requests forward/reverse/shuffled; zero neural calls, blob puts, bytes written or timestamp changes.'),
 'QA-27':('qa4-corrupt-cache.json','One-bit temporary result corruption rejected without inference, old bake usable, exact bytes restored. Native low-space refusal and incomplete-EXR relink also preserved prior bake.'),
 'QA-31':('qa4-deliver-verification.json','Actual 60-frame float RGBA Deliver output matched the bake exactly with Source disconnected, worker stopped and analysis cleared.'),
 'QA-34':('qa4-installed-offline.json','Protected runtime/models inventory and file set unchanged after installed inference and restart under checkout read denial.'),
 'QA-35':('qa4-native-install-and-ui.json','Normal GUI QA.3 to QA.4 upgrade retained UUID, revision, generation reference, controls and verified bakes.'),
 'QA-39':('qa4-native-install-and-ui.json','Local unsigned-package/ad-hoc-code install and Resolve load succeeded through normal Installer; protections retained. No transferred-package claim.'),
 'QA-11':('qa4-worker-crash.json','Controlled crash of authenticated same-user QA worker; prior baked output survived and native cleanup recovered its inactive scratch.'),
 'QA-13':('qa4-cancel.json','Actual native in-flight Cancel returned promptly; old bake and another node remained usable without unintended rerun.'),
 'QA-37':('qa4-repair.json','GUI Manager detected a missing protected QA asset, validated the matching relocated package, and normal Installer restored it; full inventory passed.'),
 'QA-38':('qa4-maintenance.json','Both QA Keep Models and Remove All removal packages tested, followed by reinstall verification. Production and original data were preserved.'),
 'QA-41':('qa4-two-pass-reanalysis.json','Native Analyze/Resume retained revision, detected only source input 17 changed, completed a new generation, and activated a new verified bake without changing the old version.'),
 'QA-43':('qa4-maintenance.json','QA-only maintenance drained affected workers and preserved production; host-running preflight refused before mutation.'),
}
notes={
 'QA-02':('Blocked','A clean independent macOS/Resolve environment is unavailable; this host contains developer tools. Normal QA Installer flow is a separate passed functional case.'),
 'QA-03':('Blocked','Per-process installed-worker IP denial passed; whole-Mac offline Resolve automatic first use and clean account were not performed.'),
 'QA-04':('Not Run','Installed worker passed checkout-read denial. A complete Resolve session with the checkout physically relocated/deleted was not run.'),
 'QA-08':('Not Run','Genuine MPS float32 ran all learned networks with fallback disabled. A fresh Metal trace for this exact candidate was not captured.'),
 'QA-10':('Not Run','Native duplicate reused one completed generation without inference and received a unique UUID; simultaneous cold first-use/cancel isolation was not fully exercised.'),
 'QA-12':('Not Run','Explicit QA worker release and maintenance draining were tested. Full crash/lease-expiry timing was not repeated.'),
 'QA-14':('Not Run','Duplicate/save/close/reopen passed; the complete disable/delete/undo/leak lifecycle matrix was not repeated.'),
 'QA-15':('Not Run','HD and full source-sized 4096x2160 export/composite passed. Odd origins, proxy/stride and transformed/PAR host variants remain unqualified.'),
 'QA-16':('Not Run','Declared sRGB workflow tested; native linear and gamma-2.4 comparison matrix not repeated.'),
 'QA-17':('Not Run','S-Log3 camera-transform workflow not repeated for this installed artifact.'),
 'QA-18':('Not Run','Native Saver/Deliver and source alpha composite were sample-exact; the full black/white/saturated-background fine-edge review matrix was not repeated.'),
 'QA-20':('Not Run','No-hint profile tested; full/source/first-frame/matte-clip hint combinations remain unqualified for this artifact.'),
 'QA-21':('Not Run','Actual continuous-RVM/Hann temporal profile completed; fresh independent CPU-reference parity was not repeated.'),
 'QA-23':('Not Run','Full 60-frame shot checked; separate cut/boundary stress fixtures were not repeated.'),
 'QA-24':('Not Run','25 fps, Fusion 0–59 and source numbering 30–89 verified; 30000/1001 matrix not repeated.'),
 'QA-25':('Not Run','Pixel-17 two-pass source invalidation tested separately; the complete color/hint/range/model change matrix was not repeated.'),
 'QA-26':('Not Run','No replacement preview/final profile qualification claimed.'),
 'QA-28':('Not Run','No new actual OOM/memory-pressure qualification claimed; no automatic quality or CPU fallback used.'),
 'QA-29':('Not Run','Temporal 60-frame full-HD analysis/export passed. A full 60-frame Single Frame sequence was not repeated.'),
 'QA-30':('Not Run','Native UHD neural quality/profile combination is not claimed. 4096x2160 alpha is explicitly resampled from HD.'),
 'QA-32':('Not Run','Representative green-screen shot checked; full blue-screen/glass/motion-blur/lighting fixture matrix was not repeated.'),
 'QA-33':('Not Run','Cold/load, temporal, cached and export timings recorded; complete physical-memory/Metal-trace performance matrix remains incomplete.'),
 'QA-36':('Blocked','Native transaction rollback fixtures passed, but actual interrupted privileged activation requires an independent disposable OS/snapshot environment.'),
 'QA-40':('Blocked','No independent second Apple Silicon Mac/Resolve installation is available.'),
 'QA-42':('Not Run','Stable two-pass source edit and cancellation tested; exact capture-time upstream mutation race was not fully repeated.'),
 'QA-44':('Not Run','Archive hook target guards verified; an actual alternate-volume installation attempt was not performed.'),
 'QA-45':('Not Run','Native buttons/pickers and cancellation observed. No blanket responsiveness pass: earlier long SDK image waits delayed AX responses.'),
}
rows=[]
for line in (repo/'docs/PERSONAL_INSTALLER_SPEC.md').read_text().splitlines():
 m=re.match(r'^\| (QA-\d+) \| ([UC]) \| ([^|]+) \| ([^|]+) \|$',line)
 if not m:continue
 ident,kind,scenario,expected=m.groups()
 rows.append(row('original',ident,scenario.strip(),expected.strip(),'Blocked','Independent environment unavailable; production preservation prevents installation.',[],environment='unmodified production-path package installation',gate_class=kind))
 status,actual=notes.get(ident,('Not Run','No completed artifact-specific observation recorded.'));evidence=[]
 if ident in observed:
  name,actual_observed=observed[ident];path=work/name
  if path.exists() and json.loads(path.read_text()).get('status')=='Passed':status='Passed';actual=actual_observed;evidence=[name]
 rows.append(row('qa4',ident,scenario.strip(),expected.strip(),status,actual,evidence,gate_class=kind))
assert len(rows)==90
# Functional observations have narrower scope than the universal release gates.
for artifact,prefix in [('qa2','qa2-'),('qa3','qa3-'),('qa4','qa4-')]:
 for p in sorted(work.glob(prefix+'*.json')):
  value=json.loads(p.read_text())
  if not isinstance(value,dict) or value.get('status') not in ('Passed','Failed'):continue
  if value.get('artifact_sha256')!=artifacts[artifact]['sha256']:continue
  scope=value.get('scope') or value.get('scenario') or p.stem
  if artifact in ('qa2','qa3'):
   scope+=' Historical Source=None assignment is not accepted as independent proof of Source disconnection; QA.4 explicitly rechecked ConnectInput/GetConnectedOutput.'
  rows.append(row(artifact,'F-'+p.stem,scope,'Observed behavior matches this narrowly stated native/worker scenario.',value['status'],scope,[p.name],environment=value.get('environment','isolated QA install')))
rows.append(row('qa1','F-DISCOVERY','Normal GUI installation and Resolve discovery','Installed QA bundle registers successfully.','Failed','Installer completed and 27,151 records verified, but Resolve rejected the bundle: executable basename did not match. Superseded by QA.2.',['qa1-native-install.json']))
for name in versions:
 f={'original':'original-package-verification.json','qa1':'qa-package-verification.json','qa2':'qa2-package-verification.json','qa3':'qa3-package-verification.json','qa4':'qa4-package-verification.json'}[name]
 rows.append(row(name,'ARCHIVE', 'Final archive inventory, executable policy and code signatures','Fresh exact package expansion verifies all policy records and code signatures.','Passed' if (work/f).exists() else 'Not Run','Archive verification is separate from installation qualification.',[f] if (work/f).exists() else [],environment='archive audit'))
data=dict(release_status='UNQUALIFIED PERSONAL BETA',context=context,artifacts=artifacts,builds=builds,acceptance=rows,categories=['archive audit','extracted payload','isolated QA install','unmodified production-path package installation'],note='No broad gate inherits a pass from source tests, a narrower functional case, an earlier artifact, or per-process checks. Original and all QA packages remain immutable. Native MLX/default switch is outside this MPS qualification.')
(out/'qualification.json').write_text(json.dumps(data,indent=2)+'\n')
print('Wrote artifact-specific rows:',len(rows))
