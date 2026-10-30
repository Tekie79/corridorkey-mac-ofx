# Codex handoff: MLX, cache correctness, and durable bake reliability

**Target repository:** https://github.com/Tekie79/corridorkey-mac-ofx  
**Working branch:** feature/mlx-cache-bake  
**Reviewed baseline:** 05a5fe01544c5a89cc6249f15b465ded79e97966 (2026-10-30)  
**Status:** Implementation instructions, not a claim that bugs have been fixed or a new package qualified.

## Mission and boundaries

Complete the correctness repairs identified in the review of commit 05a5fe0, preserve the existing MPS implementation, advance the experimental CorridorKey 2.0 MLX adapter through real native-resolution qualification, and build a new personal-use offline Mac OFX installer only after actual Mac/Resolve acceptance tests. Maintain the user-approved workflow: analyze once, render a **durable verified alpha or RGBA EXR sequence**, activate the baked result, and clean disposable analysis data; reanalyze only when explicitly requested.

- Do all work on feature/mlx-cache-bake. Do **not** merge or push changes to main. Do not modify the user's installed production OFX bundle, runtime, models, or saved projects without an explicit separate authorization.
- Existing committed evidence is historical evidence tied to particular source/artifact hashes. Rerun checks for every new candidate. Never convert mock tests or standalone worker tests into an installed-Resolve qualification claim.
- Do not weaken source-change detection or fake an O(1) live-temporal cache validity guarantee when upstream OFX image identity is unavailable. Baked playback is the reliable no-neural-inference path.
- Preserve stable OFX identifiers, serialized parameter IDs/enums, current color/alpha handling, model licensing notices, and clean offline/personal-use installation requirements.

## Required external source references

**The actual CorridorKey v2 MLX source (use this, not the older v1 MLX project):**

- Repository: https://github.com/peterteravskis/corridorkey-v2-mlx
- Pinned source commit: https://github.com/peterteravskis/corridorkey-v2-mlx/tree/74065491ebd2eddea494ab34c15a6d84d7415353
- Core MLX graph implementation: https://github.com/peterteravskis/corridorkey-v2-mlx/blob/74065491ebd2eddea494ab34c15a6d84d7415353/corridorkey_mlx/mlx_graph.py
- Foundation/RVM/stage adapters: https://github.com/peterteravskis/corridorkey-v2-mlx/blob/74065491ebd2eddea494ab34c15a6d84d7415353/corridorkey_mlx/mlx_backend.py
- Independent temporal scheduling and IO: https://github.com/peterteravskis/corridorkey-v2-mlx/blob/74065491ebd2eddea494ab34c15a6d84d7415353/corridorkey_mlx/pipeline.py
- Model graph/profile requirements: https://github.com/peterteravskis/corridorkey-v2-mlx/blob/74065491ebd2eddea494ab34c15a6d84d7415353/docs/MODELS.md
- Validation and methodology: https://github.com/peterteravskis/corridorkey-v2-mlx/blob/74065491ebd2eddea494ab34c15a6d84d7415353/docs/VALIDATION.md
- Measured comparisons: https://github.com/peterteravskis/corridorkey-v2-mlx/blob/74065491ebd2eddea494ab34c15a6d84d7415353/docs/BENCHMARKS.md
- Available companion model collection: https://huggingface.co/collections/cdelta/corridorkey-v2-mlx-6ad84231314d2593c3799e34
- Current integration's pinned FP32 model revision: 7bb9a4443d5f1b4b696bcc0547d49ae0ac5e5f7e; revalidate the SHA/asset manifest in scripts/release/mlx-v2-lock.json before reusing.
- Original CorridorKey **2.0** source of truth: https://github.com/nikopueringer/CorridorKey2.0

**Do not substitute** https://github.com/nikopueringer/corridorkey-mlx. That is a different/earlier CorridorKey architecture. Respect the community adapter's Apache-licensed source and the separate CorridorKey/foundation-model asset licenses.

Inspect the already implemented worker/ckmac/backends/mlx_v2_backend.py. The MLX v2 adapter exists: continue it; do not replace the working engine with an unrelated CLI, PNG encoder, generic MLX-LM model, or reimplementation of the old model.

## Priority P1: preserve the last verified bake when reanalysis fails

**Current issue:** src/ofx_plugin.cpp sets Instance.resumeAnalysis to true on Analyze/Resume/Force Reanalyze. The baked fast path is disabled while true, but the flag is cleared only after successful temporal processing (the successful section near lines 700–702 at the reviewed baseline). Failure, GPU OOM, host abort, missing media, stale snapshot, or invalid profile can leave the old bake unavailable to ordinary subsequent requests.

Implement a bounded, explicit analysis-attempt lifecycle:
- The verified bakedManifest, previousBake, and Use Baked Result remain unchanged until successful new bake activation. A newly analyzed generation must never automatically overwrite an older EXR bake.
- An analysis attempt can bypass the baked path while it is executing; on **every** failed, canceled, timed-out, or rejected Render attempt clear the pending attempt flag and restore ordinary baked playback on the next frame. Avoid host-suite calls from background worker threads.
- A failed reanalysis should report an actionable error during that attempt, **not silently claim a successful model inference by returning the original clip**.
- Explicit Analyze/Resume should not bump the actual model revision unless Force Reanalyze is selected. The analysis request should still invalidate host output caching through a verified supported action.
- Revert Bake / Relink Bake should clear pending analysis state and not start inference. Manage optional Source correctly: an Alpha bake still needs Source RGB; an RGBA bake can render with Source disconnected.
- Handle a failed startup and a host action that never reaches Render; ensure no indefinite stuck analyzing state and avoid unsafe render-thread races. Prefer an RAII/scope guard or equivalent with tests, but verify host callback order before finalizing.

Tests: simulated temporal exception, cancellation/AbortRender, worker crash, OOM, missing captures, render before/after error, saved project reopen, revert/relink; assert previous manifest and EXR hashes unchanged, no neural call during subsequent baked navigation.

## Priority P1: correct Resolve original-source geometry lookup

**Current issue:** worker/ckmac/resolve_geometry.py creates a module with importlib.util.module_from_spec and calls spec.loader.exec_module(sdk), but then accesses sys.modules['DaVinciResolveScript']. exec_module does not guarantee the module has been inserted into sys.modules; this is a reproducible Python import-path defect.

- Safely load the verified installed Resolve scripting module and call sdk.scriptapp('Resolve') on that loaded object (or explicitly and safely register the module, if truly necessary).
- Add a unit test that loads a real temporary mock SDK via spec_from_file_location without prepopulating sys.modules. Exercise query() rather than patching source_size() to return a hardcoded dimension.
- Independently test real Resolve Studio 21.1.x SDK connectivity and Fusion current-comp/tool lookup on the Mac. Ensure shotUUID matches the intended node, and avoid a different open composition or stale MediaIn chain.
- Preserve async/deferred metadata lookup; do not recursively call Resolve scripting API while OFX Render blocks the host.
- Do not confuse 1920x1080 Resolve working canvas with original 4096x2160 source footage. Match Source may require a retry after the deferred lookup; explicit dimension overrides remain supported. For complex crops, transforms, retimes and PAR, fail with an actionable alignment message rather than guessing.
- Validate persisted generation-scoped geometry after restart, reopening the project, duplicate nodes and disconnected external media.

## Priority P2: transactional EXR staging cleanup and recovery

**Current issue:** worker/ckmac/bake.py write_sequence creates a .staging-{id} folder and promotes after verifying all frames, but an exception during individual writes/readback can leave abandoned staging files.

- Wrap staging operations in try/finally (or equivalent transaction object). Remove only the staging directory belonging to the failing, unactivated transaction. Never delete any previously activated bake/version.
- Preserve atomic final-directory promotion and directory fsync. Apply appropriate protections for unexpected process termination, symlinks, same-volume atomic rename, concurrent bakes and external-disk removal.
- Add safe maintenance recovery of abandoned .staging-* directories with explicit ownership/scope, age and active-job checks. Do not broadly delete folders by name outside the product's bake destination.
- If export succeeds and cleanup afterward fails, report 'Bake verified and active; temporary cleanup incomplete' rather than 'Bake failed'. Never roll back the new verified output solely because temporary deletion failed.
- Test simulated disk full, write failure, readback checksum failure, crash-surviving staging folder, two concurrent bakes, missing volume, and retry after failed transaction.

## Priority P2: precise cache cleanup and ownership reporting

- On Bake & Clean and Clear Temporary Analysis, read and display the actual response from worker/ckmac/generations.py and the worker; distinguish removed captures/results, preserved shared entries, retained completed bakes, and cleanup failures. Do not display a success message when deletion fails.
- Preserve model weights, source footage, Resolve project/media, previous durable bakes and other users' caches.
- Current SQLite generation ownership and leases survive worker restart; test duplicated nodes, shared inputs, source change, owner deletion, restart, and explicit cleanup with no other owner.
- The standard playback path must never write cache blobs, update blob mtime/ctime, spawn new analysis, or invoke neural networks for an already completed and unmodified generation. It is acceptable to inspect required causal Source frames where host cache identity is uncertain.
- Detect and report actual causes of misses: missing input, changed source identity/content, changed backend/profile/settings/revision, corrupted file, eviction, or changed cache volume. Do not conflate read, stage attempt, stage write, and neural invocation counters.
- Test disk-cache limit/eviction with shared leases and explain any remaining temporary space after cleanup. Prefer output-targeted validity checks for already completed generations; explicit resume repairs missing results.

## MLX v2 work: maintain MPS, prove complete profiles before default switch

- Retain existing installed MPS implementation as the known-working path and default. MLX remains opt-in experimental until it passes the **actual 1080p** Single Frame AND Temporal requirements inside Resolve.
- Verify the community FP32 graph files and weights at the pinned revisions with SHA-256. Published profiles at this snapshot include padded 768x1280 and 1024x1536 shapes with t1/t4 stages. The current adapter does **not** have a qualified shape for a full 1920x1080 input.
- Derive the exact padded target from the current input conversion and documented model constraints. Current adapter reports 1152x1920 for native 1920x1080; the earlier specification suggested an optional 1152x2048 canvas. Do not assume either graph exists. If a newly generated shape-specific graph is needed, use a verifiable exporter from pinned original model weights, with tensor-shape/operation parity and independent checksums. **Do not simply edit graph JSON shape metadata or secretly downscale 1080p to 720p.**
- Preserve signed/HDR float32 RGB, model color encoding, alpha normalization, actual RVM recurrence, C-RADIO/MoGe foundations, Hann overlap, stage1/stage2 and hint propagation. MLX inference needs native Metal GPU evidence. CPU PyTorch may handle documented preparation, but learned-network work must not silently fall back to MPS or CPU.
- Compare MLX against MPS on real green and blue screen moving footage, fine hair, semi-transparency, glass, motion blur, signed/HDR edges, 24/25/30000/1001 timing, random/reverse requests and full Fusion/Deliver exports. Declare numerical thresholds before reviewing results and publish failures.
- Benchmark independently: model startup, lazy compilation, first frame, warm **distinct** frames, 60-frame temporal analysis, cached read, peak process physical memory, worker/host interaction and native export. The candidate's 720p tests showed warm Single Frame ~0.66s MLX versus ~0.99s MPS, but temporal 6 frames ~8.21s MLX versus ~7.38s MPS. **Do not promise MLX is universally faster** or change the default based on a small benchmark.
- Build-time acquisition only. If MLX becomes qualified, the offline package must contain locked sources, compatible wheelhouse, model graph profiles, complete licenses and integrity manifests; production first use must not download graphs/models. Update installer release/build scripts and versioned backend/cache identities with all required files.

## Durable bake acceptance and UI

- Bake Alpha writes single-A OpenEXR half float by default; Bake RGBA writes straight recovered foreground RGB+A. Full float is available for HDR range. Validate frame count, origin, pixels, frame numbers, fps, channel type, dimensions and SHA-256 before activation.
- Bake & Clean verifies then activates saved bakedManifest/previousBake and only then deletes temporary, unshared analysis data. Previous baked versions are immutable. Cleaned outputs play without a neural runtime. Alpha uses current Source RGB and must warn that recovered foreground RGB is not preserved; RGBA must work without Source and without worker.
- Match Source should export a full-sized 4096x2160 EXR if the original 4K source is known, even after 1920x1080 analysis; that is **resampled export**, not native 4K MLX inference. The manifest must disclose both analysis and export sizes. Validate correct PAR/origin/full canvas with Resolve Saver. Do not silently crop or stretch transformed geometry.
- Support reversible reanalysis and relinking an external SSD. Missing/corrupt active bake must raise NeedsRelink and must not start fresh inference.
- Target simple controls: Analyze / Resume, Force Reanalyze, Bake Alpha, Bake RGBA, Bake & Clean, Revert, Relink, Use Baked Result, Auto-clean Temporary Cache, Match Source / Explicit output resolution. Surface counters and exact storage reclaimed.

## Mandatory native Resolve regression sequence

On the primary Apple Silicon Mac with the **exact candidate** OFX build:
1. Open a copy of representative 1080p shot in Resolve Fusion. Confirm source and output interpretation. Analyze 60 frames.
2. Play forward, reverse, shuffle, and repeat frames. Assert no new .ckf files/mtime changes, zero analysis starts, zero neural calls, stable alpha. Distinguish host RAM-cache hits from worker hits.
3. Bake Alpha and RGBA as separate immutable versions. Verify EXRs independently and use them after stopping/killing the worker and clearing temporary analysis.
4. Close/reopen Resolve and its project. Confirm baked output, frame timing and alpha; repeat with disconnected Source for RGBA.
5. Trigger reanalysis exceptions, cancellation, failed source lookup, GPU OOM and source edits. After each failure, verify the previously active baked output remains accessible, with unchanged hashes.
6. Run full 4096x2160 Match Source alpha export from analyzed HD data, validate every image size and edges, distinguish resampled resolution from neural resolution. Include an upstream resized/cropped/PAR case and a failed geometry SDK lookup.
7. Test full temp-cache cleanup after a worker restart; shared-node inputs retained, unshared cleared. Test a stopped engine and a switched/unplugged external SSD with controlled relink.
8. Repeat all applicable cases after building/installing the **real offline .pkg** under a clean test account with network disabled, without a source checkout. Verify the installed artifact identity, installer, repair and uninstall. If the test cannot be performed, mark Blocked/Not run, not Passed.

Produce append-only evidence in docs/development/evidence (logs may instead remain uncommitted when large or sensitive), updated functional tests, a new artifact manifest and exact SHA-256. Keep original older evidence separate.

## Execution contract for Codex

1. Confirm branch and newest SHA; work from the latest branch head, not blindly from 05a5fe0 if it advanced.
2. Fix P1/P2 regressions with small, independently testable changes and add unit/host regression tests.
3. Verify repeated cache playback, bake + cleanup, reanalysis failure/revert/relink, and real geometry under Resolve.
4. Integrate/qualify full-resolution MLX only with exact verified compatible graph profiles and model assets. Otherwise retain experimental option and MPS default, and document the precise blocker.
5. Build and qualify a new Mac installer only when its target host and model tests pass; report blocked native work truthfully.
6. Commit reviewed, tested source and documentation to feature/mlx-cache-bake only. Do not merge main or alter the user's installed production app without permission.

**Done means:** persistent baked playback survives canceled/failed reanalysis; geometry probe works; failed bake staging is cleaned safely; cleanup reports truthful results; no unnecessary cache writes on normal navigation; MPS remains usable; MLX capability claims match actual tested graph profiles; and a new package is called qualified **only if installed Resolve tests prove it**.
