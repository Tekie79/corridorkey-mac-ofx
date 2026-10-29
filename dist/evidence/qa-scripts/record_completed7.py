from pathlib import Path
import json,hashlib,shutil
root=Path('.').resolve();ep=root/'.build/qualification-events.json';events=json.loads(ep.read_text());sha='f58245db7b45ce9ead793732c7e05f12d97c9c9a6e6681c744437b040ff07e86';ev=root/'.build/evidence';out=root/'dist/evidence';out.mkdir(exist_ok=True)
for p in ev.glob('native-0.9.7*'):
 if p.is_file():shutil.copy2(p,out/p.name)
for n in ['build-0.9.7.log','verify-0.9.7.log']:
 shutil.copy2(root/'.build'/n,out/n)
for p in ev.glob('*QA-0.9.7.drp'):shutil.copy2(p,out/p.name)
shutil.copy2(ev/'user-book-validation.json',out/'user-book-validation.json')
def row(i,note,*names,status='Passed'):
 records=[]
 for n in names:
  p=out/(n if '.' in n else 'native-0.9.7-'+n+'.json');assert p.is_file(),p
  records.append(dict(path=str(p.relative_to(root)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
 events['QA-'+str(i).zfill(2)]=dict(status=status,artifact_sha256=sha,note=note,evidence=records)
row(4,'During a real native temporal request the worker was killed and the complete checkout renamed away. Automatic restart produced the correct frame while the checkout was absent.','native-0.9.7-crash-checkout.json')
row(5,'Production native supervisor launched the installed worker under poisoned PYTHONHOME/PYTHONPATH/Conda, requested fallback1 and online flags. Actual MPS inference succeeded; OS denied outbound IP. This is not the clean-account/global-offline gate.','native-0.9.7-concurrent.json','native-0.9.7-environment-startup.json')
row(9,'Native startup was observed checking installation before Ready. Real hardware fixture, actual MPS network counters and completed user frames are separate from loaded state.','native-0.9.7-environment-startup.json','native-0.9.7-single-active-health.json','native-0.9.7-concurrent.json')
row(10,'Two simultaneous production C++ supervisor clients and an actual copied Resolve keyer shared one cold worker. Clearing one owner retained the other result; native cancellation and deletion preserved the other copied node.','native-0.9.7-concurrent.json','native-0.9.7-environment-startup.json','native-0.9.7-host-cancel.json','native-0.9.7-lifecycle.json')
row(11,'Verified worker killed during actual Full1080 temporal inference; Resolve survived and automatically restarted one worker. The same render completed correctly within26.446s.','native-0.9.7-crash-checkout.json')
row(13,'Actual host AbortRender ended the wait in0.040s with no obsolete output, while the other copied node remained usable. An executing GPU operation may finish later.','native-0.9.7-host-cancel.json')
row(14,'Actual add/copy, disable/re-enable, deletion/Undo, saved-project close/reopen all completed; pixel comparisons exact and other copied node retained.','native-0.9.7-lifecycle.json')
row(15,'Actual odd385x217 native MPS/Fusion output and preview/final geometry; arm64 production pixel tests cover nonzero origins, negative stride, orientation and bounds. Synthetic layouts are unit evidence, not invented host layouts.','native-0.9.7-hints-reference.json','native-0.9.7-preview-final.json','native-0.9.7-geometry-units.json','build-0.9.7.log')
row(16,'Actual native sRGB, scene-linear709 and gamma2.4 fixtures agree within1e-4 RGBA; largest measured error5.543e-6.','native-0.9.7-color-hdr-slog.json')
row(17,'Actual native synthetic SLog3 transfer removal followed by linear709 keying matches declared reference within1e-4. Unchanged Rec709 primaries; no untested camera-gamut claim.','native-0.9.7-color-hdr-slog.json')
row(18,'Actual float Fusion Merge over black, white and saturated red agrees with exactly-once premultiplication within1.02e-6.','native-0.9.7-alpha-merge.json','native-0.9.7-quality-review.json')
row(19,'Actual native float path retains finite RGB from-0.00746 to18.1633.','native-0.9.7-color-hdr-slog.json')
row(20,'72 real odd-size temporal native outputs cover None, source alpha all/reference0/reference4, separate Hint Alpha and Luma. Reference semantics and nonreference edit invalidation checked.','native-0.9.7-hints-reference.json','native-0.9.7-small-invalidation.json')
row(21,'Actual ordered continuous RVM/Hann8/4/stage2 agrees with retained pinned upstream CPU golden within8.56e-6; a separate blue cut reference agrees within1.36e-5. Full1080 temporal60 also completed.','native-0.9.7-hints-reference.json','native-0.9.7-time-cuts.json','native-0.9.7-temporal60.json')
row(22,'Actual shuffled/reverse requests59,41,3,30,0 exactly match the sequential analyzed output.','native-0.9.7-random.json')
row(23,'Actual first/last/window boundaries and independent green/blue shots across a cut preserve stamped source identity and upstream temporal reference; no shared recurrence across keyers.','native-0.9.7-time-cuts.json','native-0.9.7-hints-reference.json')
row(24,'Actual25fps60frames and30000/1001 nonzero timeline/source starts preserve frame stamps, order and frame counts in EXR and ProRes4444alpha Deliver.','native-0.9.7-time-cuts.json','native-0.9.7-time-movie-probe.json','native-0.9.7-single-deliver60.json')
row(25,'Native early-frame edit changes a later unchanged-input temporal result. Color/range/hint edits invalidate expected outputs; nonreference hints are ignored correctly. Model/profile cache identity covered by production tests.','native-0.9.7-causal-invalidation.json','native-0.9.7-small-invalidation.json','build-0.9.7.log')
row(26,'Quarter preview then Full native1080 Deliver in the same Resolve session: exported frames5/6 exactly match proper Full output.','native-0.9.7-preview-final.json')
row(29,'Both required modes completed60 consecutive Full1920x1080 native float RGBA frames and actual Deliver sequences with exact equality; real MPS telemetry retained.','native-0.9.7-single60.json','native-0.9.7-single-deliver60.json','native-0.9.7-temporal60.json','native-0.9.7-temporal-deliver60.json','native-0.9.7-temporal-near-complete-health.json')
row(31,'Actual Resolve Deliver60frame float RGBA EXRs in each mode exactly match native Saver; actual12frame30000/1001 ProRes4444alpha export has correct timing/count.','native-0.9.7-single-deliver60.json','native-0.9.7-temporal-deliver60.json','native-0.9.7-time-cuts.json','native-0.9.7-time-movie-probe.json')
row(32,'Fresh native1080 green/blue/glass source/matte/composites visually inspected. Hair, green clothing, propeller blur and partial glass alpha retained; refraction/backing color may need manual despill.','native-0.9.7-quality-review.json','native-0.9.7-quality-review.jpg')
row(33,'Cold verification/model/fixture, actual distinct-frame, cached sequence, temporal60 timing and sampled memory recorded with Resolve open. Native unlocked Fusion cache playback24.681fps at25fps; offline inference is not real-time.','native-0.9.7-performance-partial.json','native-0.9.7-single-active-health.json','native-0.9.7-temporal-deliver60.json','native-0.9.7-single-deliver60.json','native-0.9.7-fusion-cached-playback.json')
row(41,'Native unchanged-settings explicit reanalysis advanced revision with identical inputs and new output identities. Viewer/Saver/Deliver consumed the new result; safe source-UID refresh retry is documented.','native-0.9.7-reanalysis.json')
row(45,'Actual Render acquisition/progress, source-edit rejection, reanalysis and prompt host AbortRender recorded. Source and host-suite tests enforce action-scoped callbacks; no background host image retention.','native-0.9.7-host-cancel.json','native-0.9.7-acquisition-safety.json','native-0.9.7-reanalysis.json','build-0.9.7.log')
# Normalize already verified evidence paths into the durable delivery folder.
for v in events.values():
 if not isinstance(v,dict):continue
 for r in v.get('evidence',[]):
  p=root/r['path']
  if p.is_file() and '.build/evidence/' in r['path']:
   target=out/p.name;shutil.copy2(p,target);r.update(path=str(target.relative_to(root)),sha256=hashlib.sha256(target.read_bytes()).hexdigest())
events['QA-12'].update(status='Not run',note='Resolve has been closed; actual600s idle expiry observation is pending. Reboot is also an outstanding DONE-08 action, not inferred from a worker restart.')
for n in ['36','37','38','43']:events['QA-'+n].update(note='Native0.9.7 root maintenance qualification is prepared; fresh local Installer authorization is currently pending.')
ep.write_text(json.dumps(events,indent=2)+'\n');print('Recorded',sum(isinstance(v,dict) and v.get('status')=='Passed' for v in events.values()),'passed gates')
