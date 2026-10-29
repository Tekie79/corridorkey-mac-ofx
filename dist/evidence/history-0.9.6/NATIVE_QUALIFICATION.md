# Native qualification — personal beta

UNQUALIFIED PERSONAL BETA

Installer: `CorridorKeyMac-0.9.6-beta.1-arm64-Offline.pkg`
Bytes: 4050878032
SHA-256: `7a023538ad322b9eee26357b3dd2c2aecc16c292f6feb44837e3ffa00d590c0a`

Primary: Apple M5 Pro MacBook Pro (20-core GPU, 48 GB), macOS 26.3.2 (25D2150), Resolve Studio 21.1.1 build 10.
No fully qualified release combination is claimed while universal gates remain incomplete.

| Gate | Class | Result | Evidence / limitation |
| --- | --- | --- | --- |
| QA-01: Offline package inventory | U | Passed | Exact offline archive:27117 verified expanded records, executable hooks and pinned assets. |
| QA-02: Clean-account installation | U | Not run | Pending actual installed-candidate qualification |
| QA-03: First use offline | U | Not run | Pending actual installed-candidate qualification |
| QA-04: Relocated/deleted checkout | U | Passed | Whole checkout temporarily renamed away; automatic installed worker rendered a genuine Full1080 frame while absent. Exact output match. |
| QA-05: Conflicting Python environment | U | Not run | Pending actual installed-candidate qualification |
| QA-06: Native architecture | U | Passed | Actual installed arm64 dependency audit:273 Mach-O images, zero architecture/loader/minimum-OS errors; actual arm64 host inference. |
| QA-07: Plugin discovery | U | Not run | Pending actual installed-candidate qualification |
| QA-08: Real MPS inference | U | Passed | Actual installed MPS float32 all foundation/stage networks, fallback disabled, native Metal/MPSGraph stack and finite meaningful native outputs. |
| QA-09: Readiness truth | U | Passed | Actual Manager readiness during processing separates loaded, fixture, active jobs and completed user frames. |
| QA-10: Multiple nodes | U | Not run | Pending actual installed-candidate qualification |
| QA-11: Worker crash | U | Passed | Verified worker killed during real analysis, Resolve responsive, no fallback export; normal retry starts one matching nonroot worker and completes. |
| QA-12: Host crash/quit | U | Not run | Pending actual installed-candidate qualification |
| QA-13: Cancellation | U | Passed | Actual Resolve AbortRender stops host wait0.128s; no obsolete output; other node still matches expected result. |
| QA-14: Lifecycle | U | Passed | Actual add/copy/disable/delete/undo/close/reopen; surviving duplicate retains independent output and settings. |
| QA-15: Geometry | U | Passed | Actual odd385x217 Resolve/MPS frames plus native production-pixel tests for origins, negative/padded strides and windows. Synthetic geometry is identified as component verification. |
| QA-16: Color inputs | U | Passed | Actual native Loader->MPS->linear Saver sRGB/linear/gamma2.4 reference agreement. |
| QA-17: S-Log3 workflow | U | Passed | Synthetic S-Log3 transfer on Rec709 primaries removed by native Fusion Loader, correct linear input/output; no camera-gamut claim. |
| QA-18: Alpha association | U | Passed | Actual float32 linear Fusion Merge over black,white,saturated red, no double premultiplication. |
| QA-19: HDR and negatives | U | Passed | Actual native float HDR135x256 retains finite negativeRGB and >1 values. |
| QA-20: Hints | U | Passed | Actual12-frame8/4 source-alpha/all/reference0/reference4, connected Hint Alpha/Luma; nonreference hints ignored only in reference mode. |
| QA-21: True temporal algorithm | U | Passed | Real ordered recurrent context and overlapping baton/stage2 processing; actual installed12-frame8/4 result agrees with pinned upstream CPU QA reference. |
| QA-22: Random access | U | Passed | Native shuffled/reverse59,41,3,30,0 match sequential60-frame temporal result exactly. |
| QA-23: Temporal boundaries | U | Passed | Separate keyers across an actual two-shot cut, all12 exact aligned native outputs; fresh ordered CPU cut reference agrees. Window ends and first/last frames included. |
| QA-24: Time mapping | U | Passed | Integer25fps60 and30000/1001 nonzero source1001..1012/timeline01:00:00:00; actual EXR sequence and12-frame alpha movie with exact source stamps. |
| QA-25: Source invalidation | U | Passed | Actual earlier-pixel recurrent invalidation, hint semantics, color interpretation and range identity. Acquisition-phase mutation is separately Failed QA42. |
| QA-26: Preview/final cache | U | Passed | Quarter preview then Full1080 Deliver in the same Resolve session; final exactly matches prior Full result. |
| QA-27: Cache corruption/full disk | U | Passed | Actual isolated constrained APFS volume guard, cached header-corruption rejection, preserved valid data and incomplete-write handling. |
| QA-28: Memory pressure | U | Passed | Actual installed Engine.frame real MPS OOM under safe tighter ceiling; same full512 float32 request recovers with normal ceiling. |
| QA-29: 1080p sequence | U | Passed | Actual installed60 consecutive Full1920x1080 frames both modes, real temporal251.552s, Fusion and Deliver finite matched outputs. |
| QA-30: UHD target | C | Failed | Native internal UHD is explicitly refused in this beta after earlier real4K numerical-quality failure; no native UHD support claimed. |
| QA-31: Final export | U | Passed | Actual60floatRGBA Deliver EXRs in each required mode, maximum error0 against native Fusion Saver. |
| QA-32: Frame-quality review | U | Passed | Real green/blue screen, hair, plane-propeller blur and glass/stream reviewed at1080; remaining glass/refraction color limitations documented. |
| QA-33: Performance report | U | Passed | Exact candidate: cold load32.431s, distinctFullSF2.839s, real60temporal251.552s, peakdriver18.125GB, cached Fusion24.496fps; cache/export timings separated. |
| QA-34: Read-only payload | U | Passed | After native inference and analysis, all27113 protected installed files still verify; caches user-local. |
| QA-35: Upgrade | U | Passed | Normal GUI upgrade installed exact6, historical saved qualification project opened with retained parameter meanings and real both-mode renders. |
| QA-36: Interrupted activation | U | Not run | Pending actual installed-candidate qualification |
| QA-37: Repair | U | Not run | Pending actual installed-candidate qualification |
| QA-38: Uninstall | U | Not run | Pending actual installed-candidate qualification |
| QA-39: Signing/provenance | U | Passed | Actual local normal Installer route and native Resolve load, ad-hoc contained code; package unsigned, not notarized; transferred trust route not claimed. |
| QA-40: Second Mac | C | Blocked | Second Mac unavailable and not claimed. |
| QA-41: Host analysis cache | U | Passed | Actual native Analyze Shot event advances saved revision1->2 with unchanged creative/source settings; actual Deliver matches revision2 exactly. |
| QA-42: Source changes during analysis | U | Failed | Actual acquisition-phase upstream gain edit produced and activated mixed-source temporal input. Candidate is unqualified; replacement capture guard is awaiting native validation. |
| QA-43: Maintenance and workers | U | Not run | Pending actual installed-candidate qualification |
| QA-44: Installer destination | U | Not run | Pending actual installed-candidate qualification |
| QA-45: Progress and host calls | U | Not run | Pending actual installed-candidate qualification |

## Actual model and partial native evidence

- `dist/evidence/GS02-single-1080p/sequence.json` — Passed. direct backend only; not Resolve/Fusion/Deliver qualification
- `dist/evidence/cpu-GS02-1920/comparison.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/cpu-GS02-native/comparison.json` — Failed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/foundation-native-comparison.json` — recorded. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/mps-GS02-1920/probe.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/mps-GS02-512/probe.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/mps-GS02-native/probe.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/mps-contiguous-attention.json` — Failed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/mps-real-512/probe.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/mps-smoke/probe.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/native-0.9.1-blue.json` — Passed. Actual installed Single Frame blue-screen Fusion/Deliver, 60 native 1080p frames; visual review recorded separately
- `dist/evidence/native-0.9.1-cpu-reference/comparison.json` — Passed. Same-version float32 CPU QA reference against actual native Fusion input and installed MPS output; no CPU production fallback
- `dist/evidence/native-0.9.1-glass.json` — Passed. Actual installed Single Frame glass/pouring-water Fusion and Deliver; native 1080p key from explicitly resized 4K source
- `dist/evidence/native-0.9.1-idle-exit.json` — Passed. Actual installed engine after normal Resolve quit, no explicit worker termination
- `dist/evidence/native-0.9.1-summary.json` — Partial. Actual installed 0.9.1 native MPS/Fusion/Deliver qualification. This is historical evidence, not a complete release or proof for another artifact.
- `dist/evidence/native-0.9.2-install-failure.json` — Failed. Actual native Installer upgrade; refused before activation, preserving previous active build
- `dist/evidence/native-0.9.5-linear-merge-zero-alpha-tolerance.json` — Failed. Exact installed0.9.5 actual Fusion LinearOutput and Merge -> Deliver60floatRGBA, reference signed sRGB decode of independent cachedmodel output
- `dist/evidence/native-0.9.5-linear-merge.json` — Passed. Exact installed0.9.5 actual Fusion LinearOutput and Merge -> Deliver60floatRGBA, reference signed sRGB decode of independent cachedmodel output
- `dist/evidence/native-0.9.5-single.json` — Passed. Actual unmodified installed 0.9.5 offline package, Fusion Saver, 60 Full 1080p Single Frame outputs; not full acceptance matrix completion
- `dist/evidence/native-0.9.5-unlocked-cache-invalidation.json` — Passed. Exact installed0.9.5 native unlocked Fusion Cache to Disk, source0edit requested2unchanged input, actual temporal recomputation
- `dist/evidence/native-0.9.6-acquisition12-source-edit.json` — Failed. Actual 0.9.6 Resolve acquisition-phase edit activated a mixed-source result. Supersedes the earlier inconclusive same-action checks.
- `dist/evidence/native-0.9.6-active-maintenance-blocked.json` — Passed. Actual Manager Release GPU invoked while installed worker reported processing/active_jobs1; operation refused and did not stop the worker or modify installed assets. Idle root maintenance drain still tested separately.
- `dist/evidence/native-0.9.6-alpha-merge-half-background.json` — Failed. Actual native Fusion linear-light Merge of installed premultiplied keyer output over black,white,saturated red; comparison to foreground + background*(1-alpha)
- `dist/evidence/native-0.9.6-alpha-merge.json` — Passed. Actual native Fusion float32 linear-light Merge of installed premultiplied keyer output over black,white,saturated red; comparison to foreground + background*(1-alpha)
- `dist/evidence/native-0.9.6-architecture.json` — Passed. Read-only audit of actual installed273 native runtime images: arm64, deployment targets and loader roots; native installed OFX and Manager arm64; actual ResolveMPS load already exercised
- `dist/evidence/native-0.9.6-cache-failures.json` — Passed. Installed production DiskCache on actual mounted isolated5GB APFS volume: free-space safety rejection preserves old valid image; same-area extent header corruption invalidates already-RAM-cached data; restoration succeeds; incomplete writer is never treated as a committed entry. Source footage and main Mac volume unchanged.
- `dist/evidence/native-0.9.6-causal-invalidation.json` — Passed. Actual installed native1080 temporal4-frame earlier-source0 edit; requestedframe2 source unchanged. Native unlocked disk cache discarded old four files and rebuilt frame2 with actual neural processing; Saver then exported same new model result after native cache disabled.
- `dist/evidence/native-0.9.6-checkout-independence.json` — Passed. Actual native Resolve first use with normal automatic worker startup while entire build checkout is renamed away; companion installed private runtime runs real MPS under conflicting Python settings and OS-denied outbound IP.
- `dist/evidence/native-0.9.6-color.json` — Passed. Actual native Loader->OFX MPS->linear output->FusionSaver, corresponding sRGB,linear709,gamma2.4 inputs
- `dist/evidence/native-0.9.6-colour-invalidation.json` — Passed. Native Temporal12 same captured pixels, only Input Encoding changed sRGB->Linear; must not reuse prior output
- `dist/evidence/native-0.9.6-conflicting-env-offline.json` — Passed. Actual installed private interpreter and production engine entrypoint under conflicting PYTHONHOME/PYTHONPATH/Conda, hostile torch.py, requested fallback1 and offline flags0; OS denies outbound IP. Isolated QA process, not native supervisor or clean-account installation.
- `dist/evidence/native-0.9.6-crash-recovery.json` — Passed. Actual installed native Resolve render workerSIGKILL duringprocessing; Resolve remained responsive, failed attempt saved no fallback file; normalrenderretry automatically started one matching nonroot worker and completed real temporal inference
- `dist/evidence/native-0.9.6-cut-reference/comparison.json` — Passed. Fresh CPU pinned-upstream4/2 reference for the second blue shot after a hard cut from green; actual installed MPS6frame640x360 result, no recurrent state inherited across shots
- `dist/evidence/native-0.9.6-duplicate-ownership.json` — Passed. Actual native copied OFX settings produce two independent nodes and Saver branches, shared automatic startup. Different post parameters produce correct independent output. Clearing original node through native clearCache action preserves duplicate shared model results: no new neural frame and cache hits increase. Native copy auto-insertion explicitly corrected in test graph.
- `dist/evidence/native-0.9.6-first-temporal.json` — Passed. Exact installed0.9.6 Full1080 temporal first random frame30 after real60-frame MPS analysis
- `dist/evidence/native-0.9.6-fractional-time-deliver.json` — Passed. Actual29.97 timeline and nonzero sourceEXR1001..1012, nonzero timeline109001..109012, two six-frame temporal shots at hard green/blue cut. Source binary stamps confirm exact frame order; all12DeliverfloatRGBA outputs match nativeSaver exactly; actualProRes4444alpha movie confirms30000/1001 and12frames.
- `dist/evidence/native-0.9.6-geometry-units.json` — Passed. Native arm64 production pixel packing/writing code tests run on this Mac; includes negative stride, origins, flip, alpha, padding, window and invalid input. Combined with actual odd385x217 nativeMPS/Fusion and preview/final tests; no claim that Resolve emitted every synthetic stride/origin.
- `dist/evidence/native-0.9.6-gpu-trace.json` — Passed. Native2second stack sampling of automatically launched installed worker50227 during real1080 temporal analysis, plus completed real network counters and MPS float32/fallback diagnostics
- `dist/evidence/native-0.9.6-hdr.json` — Passed. Native Fusion Loader float HDR -> MPS OFX linear straight foreground -> float32 Saver
- `dist/evidence/native-0.9.6-hints.json` — Passed. Actual installed native Fusion MPS12 real-footage-derived odd385x217 frames,8/4 temporal; source alpha/all/reference0/reference4, optional connected alpha/luma matte; CPU reference worker outputs also checked against actual native Saver
- `dist/evidence/native-0.9.6-host-cancel.json` — Passed. Actual Resolve supported Composition.AbortRender during genuine installed MPS temporal inference; native OFX abort path and obsolete-output suppression
- `dist/evidence/native-0.9.6-installed-runtime-audit.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/native-0.9.6-lifecycle.json` — Passed. Native Resolve add/copy/disable/delete/undo/close/reopen lifecycle; per-step observations, not full pass until complete
- `dist/evidence/native-0.9.6-manager-support.json` — Passed. Actual Manager Support File GUI action, archive inspected locally
- `dist/evidence/native-0.9.6-memory-pressure.json` — Passed. Installed production Engine.frame/backend MPS paths in isolated qualification process: tightened allocator ceiling induces real MPS OOM, restores normal profile and retries identical full512x512 float32 request; Resolve remains open. No production worker or source changed.
- `dist/evidence/native-0.9.6-midanalysis-source-edit.json` — Passed. Actual native upstream Gain frame0 changed1.8->1.9 during1080 four-frame temporal model processing, requestedframe2 unchanged
- `dist/evidence/native-0.9.6-preview-final.json` — Passed. Actual native Quarter Internal Resolution preview thenFull1080 Deliver without restarting Resolve; Full result exactly matches earlier independent Full single-frame output, no preview cache poisoning
- `dist/evidence/native-0.9.6-quality-review.json` — Passed. Actual installed Full1080 native renders reviewed for authorized green/blue/glass footage, source/matte/composites. Green clothing and hair retained; blue airplane detail and semi-transparent propeller blur retained; glass/pouring edges and partial alpha retained. Display composites are inspection thumbnails, separate from qualified linear-Merge numeric tests.
- `dist/evidence/native-0.9.6-random.json` — Passed. Actual native Fusion reverse/shuffled frame requests, matching full sequential temporal result
- `dist/evidence/native-0.9.6-range-invalidation.json` — Passed. Native same source/color/profile, only inclusive range end11->10; requested5 source unchanged; new complete context and output generation
- `dist/evidence/native-0.9.6-reanalysis.json` — Passed. Actual native Fusion Analyze Shot control event through host input API, unchanged creative settings and source; saved revision1->2 generates new complete temporal result; unlocked Fusion cache updated and actual Deliver consumes revision2
- `dist/evidence/native-0.9.6-reference-hint-invalidation.json` — Passed. Native12frame8/4 reference0hint propagation unchanged when only nonreference frame11 hint luminance changes to zero; same edit in All Frames changes frame11
- `dist/evidence/native-0.9.6-single-deliver.json` — Passed. Actual exact0.9.6 cached Single Frame Deliver60floatRGBA EXRs vsFusionSaver
- `dist/evidence/native-0.9.6-single60.json` — Passed. Exact0.9.6 actual60SingleFrameFull1080 Fusion outputs after interrupted46-frame first run and35.787s completion run; speed is mixed hits/misses, not fresh-inference timing
- `dist/evidence/native-0.9.6-slog.json` — Passed. Synthetic Sony S-Log3 encoding of Rec709-primaries GS02 frame -> native Fusion Loader Remove Curve SonySLog/SLog3 -> OFX linear input -> linear premult RGBA
- `dist/evidence/native-0.9.6-temporal-deliver.json` — Passed. Actual exact0.9.6 temporal Deliver60floatRGBA EXRs vsFusionSaver
- `dist/evidence/native-0.9.6-temporal-reference/comparison.json` — Passed. Pinned upstream function CPU QA reference vs actual installed0.9.6 MPS 12-frame8/4 shot, two overlapping windows, realGS02-derived odd385x217 input; native Saver/worker mapping verified separately
- `dist/evidence/native-0.9.6-temporal60.json` — Passed. Exact installed0.9.6 actual Fusion60frame temporal Saver output after frame30random request
- `dist/evidence/native-descriptor-overlay.json` — Passed. Qualification-only descriptor overlay installed over full 0.9.3; this is not qualification of the unchanged offline 0.9.3 package
- `dist/evidence/native-overlay-temporal-deliver.json` — Passed. Actual 60-frame temporal Fusion/Deliver through descriptor overlay on installed 0.9.3; unchanged offline 0.9.3 remains unqualified
- `dist/evidence/native-overlay-temporal-frame30.json` — Passed. Actual Fusion temporal result through qualification-only descriptor overlay on 0.9.3; not unchanged-offline-artifact qualification
- `dist/evidence/package-0.9.1-verified.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/package-0.9.2-verified.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/package-0.9.3-verified.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/package-0.9.4-verified.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/package-0.9.5-verified.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/package-0.9.6-verified.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/performance-causal-invalidation.json` — Passed. Actual native temporal OFX Render using performance overlay 2; not final artifact qualification
- `dist/evidence/performance-nodecache-deliver.json` — Passed. Native Fusion Cache to Disk on installed 0.9.4 + performance overlay 2
- `dist/evidence/relocated-engine.json` — Passed. real packaged Python engine IPC in a relocated directory; not installed native supervisor or Resolve
- `dist/evidence/relocated-offline-real.json` — Passed. relocated standalone runtime with OS-denied outbound IP; not a clean-account Installer test
- `dist/evidence/relocated-real.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/temporal-GS02-1080p/temporal.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/temporal-GS02-60-1080p/temporal.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/temporal-cpu-reference/comparison.json` — Passed. See the evidence; not automatically an installed-product acceptance result
- `dist/evidence/user-book-validation.json` — Passed. Static offline-book integrity and accessibility structure, not a browser visual qualification

Direct Single Frame: 60 distinct 1920×1080 frames, median 2.955 s, range 2.793–4.330 s. This excludes model loading and is not Deliver timing.

See `USER_GUIDE.md`, `KNOWN_LIMITATIONS.md`, source references and the original specification. Each evidence file preserves its actual scope.
