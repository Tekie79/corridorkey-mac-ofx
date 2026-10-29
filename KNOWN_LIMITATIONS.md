# Personal beta limitations

No Mac/Resolve combination is a fully qualified release combination yet. The
exact installer identity and every acceptance result are in `qualification.json`
and `NATIVE_QUALIFICATION.md` beside the installer.

The measured Mac is an Apple M5 Pro MacBook Pro, 20-core GPU, 48 GB unified
memory, macOS 26.3.2 (25D2150), Resolve Studio 21.1.1 build 10.

## Capture safety

The 0.9.6 acquisition-phase edit test exposed a mixed-source temporal result.
The 0.9.7 implementation requires an identical complete causal capture in a
separate Render action before submitting a newly observed shot. A first pass
can stop with “Capture ready”; keep inputs unchanged and render again. This
replacement needs its own actual installed-artifact acceptance result. Do not
edit upstream media, grades, hints or timing while analysis is running.

## Actual evidence and its limits

0.9.6 completed genuine MPS float32 Single Frame and Temporal 60-frame 1080p
Fusion/Deliver sequences. EXR exports matched native Saver outputs exactly.
Actual tests also covered 30000/1001 nonzero source starts, independent shots
across a cut, alpha Merge, color/HDR, reference hints, random access, causal
invalidation, cancellation, worker crash recovery and recoverable memory/disk
failures. These are historical evidence, not automatic passes for a replacement
installer. No portable or mock test establishes native GPU or Resolve success.

Clean-account normal installation, globally offline first use, reboot, and
installed repair/uninstall are separate gates. The report states which are
Passed, Failed, Blocked or Not run. A per-process outbound-IP denial test does
not establish clean-account or whole-Mac offline qualification.

## Quality and performance

Native internal sizes above 2048×1152 are refused after direct 4K numerical
quality failure. Choose Half/Quarter explicitly for a larger canvas; they
upscale a smaller key and are saved quality choices. There is no automatic
resolution, window or precision downgrade and no CPU neural fallback.

Full 1080p float32 is offline processing, around 3 seconds per distinct Single
Frame on this Mac. Live temporal viewing remains slow even with plugin results
cached because Resolve still acquires the causal input set. Actual unlocked
Fusion Cache to Disk reached approximately 24.5 fps in the 25 fps test. Use
completed native playback cache for editing. Restore the intended final
profile and reanalyze after preview changes.

Hair, green/blue screen, motion blur and glass were visually reviewed on real
1080p fixtures. Glass/refraction can retain backing color and need shot-specific
despill. No arbitrary-footage perfect-matte claim is made.

## Controls and support scope

The UI exposes the requested creative groups with compact labels. The public
upstream repository supplies model/orchestration source, not the proprietary
native plugin implementation. Control semantics are documented in the guide;
control presence does not qualify every window/memory/resolution combination.
No activation, payment, telemetry or public online updater is included.

Only the documented transfer functions with Rec.709/sRGB primaries are accepted
by the adapter. Transform log/wide-gamut footage deliberately before the keyer.
The M2 Mac Studio, native UHD, other OS/Resolve versions, free Resolve and
transferred-package trust routes are unqualified.
