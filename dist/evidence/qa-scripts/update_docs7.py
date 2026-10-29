from pathlib import Path
import re,base64,io
from PIL import Image
p=Path('dist/CorridorKey2.0-hp-beta-User-Book.html');s=p.read_text()
s=s.replace('Capture safety is under validation','Capture safety checked in 0.9.7')
s=s.replace('An acquisition-phase upstream edit exposed a mixed-source bug in 0.9.6. The acceptance report identifies whether the delivered revision passed its replacement test. Do not edit the source, grade, hints or timing during analysis. A verification prompt is not a finished key.','The installed 0.9.7 test rejected a source edit during acquisition and produced an exact stable retry. New or changed shots require two matching captures in separate render requests. Keep source, grade, hints and timing stable during analysis. A verification prompt is not a finished key.')
s=s.replace('Keep upstream settings unchanged and repeat the render to verify the same input set before processing.','Keep upstream settings unchanged. Move the playhead one frame and back, or repeat the native pre-render, to verify the same input set. Do not click Analyze Shot again just to acknowledge this prompt: that advances another revision.')
s=s.replace('The actual 0.9.6 test reached approximately <strong>24.5 fps</strong>','The actual installed 0.9.7 test reached <strong>24.68 fps</strong>')
s=s.replace('Live temporal viewing with plugin results already cached was only about 1.6–1.9 fps because the host still acquired the shot.','Historical live temporal viewing with plugin results already cached was only about 1.6–1.9 fps because the host still acquired the shot.')
s=s.replace('Manager → Verify. The build identifier in this capture is a historical qualification build.','Manager → Verify after installing 0.9.7. All 27,113 installed files were verified.')
s=s.replace('Keep upstream settings unchanged and render again. Check the acquisition-safety status in the report before relying on Temporal.','Keep upstream settings unchanged and request another frame, or repeat pre-render. Resolve can refresh source identities after analysis; a safe rejection needs another render after it settles. Repeated Analyze Shot clicks create new revisions.')
s=s.replace('Open <strong>CorridorKey2.0 hp beta Manager</strong>','Open <strong>CorridorKey Mac Manager</strong> (window: CorridorKey2.0 hp beta Manager)')
for alt,file in [('Manager with a successful installed-file verification','manager-verify-0.9.7.jpg'),('Manager refusing GPU release while a model job is active','manager-busy-0.9.7.jpg')]:
 b=io.BytesIO();Image.open(Path('.build/evidence/guide-screenshots')/file).convert('RGB').save(b,format='PNG');data=base64.b64encode(b.getvalue()).decode()
 pattern=r'(<img\b[^>]*src=")data:image/png;base64,[^"<>]+(" alt="'+re.escape(alt)+r'")'
 s,n=re.subn(pattern,lambda m:m[1]+'data:image/png;base64,'+data+m[2],s);assert n==1,(alt,n)
p.write_text(s)
p=Path('dist/KNOWN_LIMITATIONS.md');s=p.read_text().replace('This\nreplacement needs its own actual installed-artifact acceptance result.','The\nactual installed 0.9.7 acquisition-edit test passed: no mixed capture was\nsubmitted, and all 12 stable captured inputs and output frames matched exactly.')
s=s.replace('0.9.6 completed genuine','0.9.7 completed genuine').replace('These are historical evidence, not automatic passes for a replacement\ninstaller.','These are bound to the delivered installer SHA-256 in the acceptance report.')
s=s.replace('approximately 24.5 fps','24.68 fps on 0.9.7')
s += '\nResolve can refresh image identifiers during temporal processing even when pixels\nremain unchanged. The plugin safely rejects that generation. Keep inputs stable\nand request another frame or repeat pre-render after Resolve settles; do not\nclick Analyze Shot repeatedly unless you intend to start another analysis revision.\n'
p.write_text(s)
p=Path('dist/PERFORMANCE.md');s=p.read_text();intro='''# Performance — installed 0.9.7 personal beta

Measured on M5 Pro / 20 GPU cores / 48 GB, macOS 26.3.2, Resolve Studio 21.1.1 build 10.
Installed artifact SHA-256: `f58245db7b45ce9ead793732c7e05f12d97c9c9a6e6681c744437b040ff07e86`.

| Actual 0.9.7 measurement | Observed |
| --- | --- |
| Cold installation verification | 3.309 s |
| Cold model load in native session | 31.088 s; a later restart was 6.794 s with warm filesystem cache |
| Real-model hardware fixture | 0.277 s |
| Full 1080p temporal analysis, 60 frames, 4/2 overlap | 245.895 s |
| Cached temporal Fusion Saver, 60 float RGBA frames | 34.460 s |
| Temporal Deliver, 60 float RGBA EXRs after analysis | 49.958 s, exact equality to native Saver |
| Single Frame Deliver, 60 cached float RGBA EXRs | 6.224 s, exact equality to native Saver |
| Native Fusion disk-cache playback, 60-frame 25 fps loop | 24.681 fps, 100 frames advanced in 4.052 s |
| Maximum sampled MPS driver allocation in 60-frame run | 18,455,724,032 bytes (17.19 GiB); sampled high-water value, not whole-system peak |
| Host cancellation wait | 0.040 s; an executing GPU operation can finish later |
| Native worker crash and automatic recovery | Correct output within 26.446 s while checkout was absent |

Full inference remains offline. Disk-cached playback and already-analyzed exports
measure different work from uncached inference. The 59× result below is a cache
component microbenchmark, not an end-to-end playback speedup. Half/Quarter are
explicitly lower spatial profiles, never automatic final-quality substitutions.

The following retained development measurements explain the optimization and
workflow. Their older overlay/build identities are preserved deliberately.

'''
p.write_text(intro+s.replace('# Performance work — personal beta','# Historical optimization measurements',1))
print('Updated out-of-band delivery documentation; packaged source/runtime untouched')
