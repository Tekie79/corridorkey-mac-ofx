# Phase 2: bake recovery, cache ownership and MLX validation

2026-10-30. Implements the P1/P2 work from [Issue #1](https://github.com/Tekie79/corridorkey-mac-ofx/issues/1)
and [the handoff](CODEX_NEXT_PHASE_MLX_CACHE_BAKE.md) on `feature/mlx-cache-bake`.
The exact base commit, candidate binaries and source SHA-256 inventory are in
[final-artifacts.json](evidence/phase2-20261030/final-artifacts.json).
Earlier evidence remains separate and unchanged.

**This is a tested source candidate and isolated QA bundle. No new installer was
built, no production installation was replaced, and nothing was merged to main.**

## Implemented fixes

### P1: failed reanalysis no longer strands the previous bake

`AnalysisAttempt` replaces the persistent resume boolean. A button arms one
render; Render consumes that request before locks, image access, startup or other
fallible work. Its local attempt state disappears on every return or exception.
A request that never reaches Render expires after 30 seconds without a timer
calling host suites. Cancel, Revert and Relink cancel pending attempts.

Analyze / Resume changes the saved host invalidation token without changing the
model revision. Force Reanalyze changes the revision. Failed attempts report an
error for that request; ordinary subsequent requests read the prior verified
bake. A successful analysis updates its transient generation without activating
a new EXR version. Existing manifest paths and EXRs remain intact until a new
verified bake is activated.

The final candidate also refuses implicit recomputation if the host remembers a
completed generation but the worker has lost that same generation's metadata.
It requests explicit Analyze / Resume. A genuinely changed causal identity is
still distinguished from missing storage. Live mode continues to inspect the
causal Source set; no unsafe O(1) edit-detection guarantee was added.

Code: [attempt lifecycle](../../include/ckmac/analysis_attempt.hpp),
[OFX actions](../../src/ofx_plugin.cpp).

### P1: SDK loading and original-source geometry

The SDK loader executes the installed vendor shim under a private registered
module name, obtains the loaded object (including the vendor shim's replacement
with `fusionscript`), and restores the previous private module entry. It neither
assumes `exec_module` registered the public name nor clobbers an existing public
SDK module. Tests execute real temporary SDK files with both ordinary and
self-replacing import behavior.

The deferred lookup matches exactly one saved shot UUID in the current Fusion
composition. Duplicate UUIDs, missing media, cycles, unknown transforms, Crop,
non-square clip metadata, and ambiguous fit/letterbox Resize mappings are
rejected. Full-frame BetterResize with KeepAspect=0 and transparent PipeRouter
links are supported. Original dimensions are revalidated after worker restart;
unchanged revalidation does not rewrite the metadata file.

Source dimensions carry their basis into new manifests: `resolve_sdk`,
`user_explicit` or `captured_source`. A verified durable bake with known original
dimensions can be re-exported after cleanup or with disconnected Source. An
unverified original-size lookup requests a retry or explicit aligned dimensions.
It does not silently substitute the normalized working canvas.

Native testing found an additional deadlock: Resolve evaluated upstream data
inside `clipGetRegionOfDefinition` during the Bake parameter callback. A stack
sample identified that call. It was removed; Bake uses captured provenance and
the deferred SDK probe. No host image evaluation is performed by that callback.
The stalled copied QA process was restarted; no bake request had reached its
worker and no production project or plugin was changed.

Code: [geometry](../../worker/ckmac/resolve_geometry.py),
[bake dispatch](../../worker/ckmac/engine.py).

### P2: transactional staging and recovery

Each export owns a private staging directory, a same-user transaction record
bound to a registered destination nonce, and a held job lock. Exception cleanup
removes only that transaction's unpromoted staging directory. Final `bake-*`
versions are never cleanup targets. Atomic same-volume rename and directory
fsync remain in the promotion path.

Explicit abandoned-export recovery checks destination registration, UID,
transaction identity, age, symlinks and the nonblocking job lock. The default
minimum age is 24 hours. Active, recent, unmarked or mismatched folders are
skipped/refused; completed versions remain untouched. An unavailable volume
leaves an actionable cleanup note instead of masking the original export error.
A crash before the ownership marker is durable can leave an unmarked folder;
automatic recovery intentionally refuses that folder for manual review.

Developer/maintenance invocation, using the product Python environment:

```sh
PYTHONPATH=worker python3 -m ckmac.bake_transaction \
  --destination /absolute/registered/bake-folder --older-than-hours 24
```

Code: [transactions](../../worker/ckmac/bake_transaction.py),
[EXR writer](../../worker/ckmac/bake.py).

### P2: truthful cleanup and cache-miss reporting

Cleanup returns actual removed capture/result counts, logical file bytes,
already-absent keys, shared/other-generation retention, completion-record counts
and failures. Partial deletion preserves retryable ownership and completion
metadata for failed entries. Retrying after restart removes the remainder.

The native controls display those results. If cleanup fails after activation,
the verified bake stays active and the UI reports **temporary cleanup incomplete**.
It does not label the verified export as failed or roll it back. Cache cleanup
never removes durable EXRs, model weights, original footage or project files.

Diagnostics distinguish source/profile/settings/revision/backend identity
changes, corrupt blobs, known budget eviction, explicit cleanup and unavailable
or changed cache volumes. A missing file with no surviving cause history is
reported as unknown; eviction is not invented after restart. Bake jobs also
report their active state, preventing idle shutdown while writing.

Code: [ownership](../../worker/ckmac/generations.py),
[cache](../../worker/ckmac/cache.py),
[native cleanup summary](../../src/worker_manager.mm).

## Native Resolve evidence

Apple M5 Pro, 48 GiB, macOS 26.3.2, Resolve Studio 21.1.2. Testing used a separate
OFX identity and a new copy named `CorridorKey_Phase2_QA_20261030`. The installed
production bundle and its root-owned-manifest enforcement were preserved.

| Check | Observed result |
|---|---|
| Final candidate, 60-frame 1920×1080 MPS temporal analysis, window 4 | Completed; neural analysis scope **241.877 s**. |
| 60 forward, 60 reverse, three seeded shuffled passes of 60, live cached mode | **300 requests**, **59 worker hits**; other requests used Resolve RAM. No new/removed blobs or markers, no mtime/ctime/inode changes, zero byte growth, zero staging attempts, analysis starts or neural calls. |
| Native Single Frame at 1920×1080 | One genuine user inference; three host-invalidating request tokens produced **three worker cache hits**, with zero additional neural calls or puts. |
| Lost metadata for an already completed generation | Returned no image/error; model remained unloaded and staging/analysis/network counters stayed zero until explicit resume. |
| Reanalysis exceptions, cancel and OOM error injection | Failed request returned no image; next baked request succeeded with unchanged manifest and no new neural/staging work. OOM/cancel were simulated errors, not physical memory exhaustion or a real user in-flight abort. |
| Missing capture | A disposable QA capture was removed; analysis failed and subsequent baked navigation succeeded. |
| Worker crash | QA worker actually exited with code **87**; the next baked request succeeded. |
| Failed QA runtime startup | An isolated duplicate returned no image for its attempt, then recovered baked output without a running worker. This tests unavailable QA startup, not a production-install failure. |
| Pending attempt followed by Revert / Relink | Baked output recovered; RGBA also worked with Source disconnected. |
| RGBA bake | 60 immutable 1920×1080 HALF RGBA files; every checksum verified; zero sample difference from the earlier MPS RGBA bake. |
| Match Source alpha | 60 4096×2160 single-A HALF files from HD analysis; source basis `resolve_sdk`; all checksums, types, dimensions, frame numbers, range and finite alpha verified. Resampled export, not native 4K neural inference. |
| 4K alpha composition, worker stopped/cache cleaned | Native Saver A exactly matched the baked A; output RGB exactly matched original 4K RGB × A. |
| Duplicate node and restart ownership | Native Copy/Paste produced a distinct saved UUID and two leases on the same generation. Bake & Clean retained all **120 shared entries**. |
| Cleanup failure after activation | New alpha remained active; UI reported verified/active plus temporary cleanup incomplete. Previous RGBA stayed unchanged. |
| Clear after restart | Other owner removed 60 results and retained 60 shared captures; remaining owner removed 60 captures. Sixty output identities from failed attempts were reported already absent, not reclaimed bytes. All blobs, markers, ownership rows and leases ended at zero. |
| Final 1080p cleanup | Removed 60 captures and 60 results: **3,981,318,720 logical file bytes**. Durable media remained. |
| Native Saver, worker absent/Source disconnected/cache empty | All 60 RGBA frames matched the bake with exactly one premultiplication; maximum error **0**. |
| Saved project, fresh Resolve session | Baked RGBA at frame 43 succeeded with Source disconnected, no worker and no temporary blobs. |
| Original geometry SDK | Both duplicate UUIDs resolved to 4096×2160; wrong owner returned no dimensions; Crop and ambiguous fit returned no dimensions. |
| Offline/relink | Moving the QA bake directory made the read fail without inference. Restoring it and using the native Relink picker recovered output. Physical external-SSD removal was not performed. |
| Native Deliver | Complete: **60 distinct 1920×1080 FLOAT RGBA EXRs**, 25 fps, premultiplied AlphaMode=0; worker stopped, Source disconnected, cache cleaned. Every alpha/RGBA sample matched, maximum error **0**. Job reported **3.080 s**, an export scope, not live-viewer performance. |

The geometry edge-case test temporarily changed Resize1 to 1920×1013. All
60 source identities correctly changed and produced a different generation,
while the old bake stayed active. That run was separated from the cache-loss
test. Exact 1920×1080 was then restored and the final analysis/replay rerun.
Long synchronous SDK requests exceeded the connector's 60-second RPC limit;
actual analysis completion was verified through worker counters, saved generation
and subsequent native reads. No timeout was counted as a completed render.

Evidence: [replay](evidence/phase2-20261030/final-native-cache-replay.json),
[Single Frame](evidence/phase2-20261030/native-single-frame-replay.json),
[bakes/recovery](evidence/phase2-20261030/native-bake-recovery-verification.json),
[cleanup](evidence/phase2-20261030/native-cleanup-and-startup.json),
[4K composition](evidence/phase2-20261030/native-4k-alpha-composite.json),
[Saver](evidence/phase2-20261030/native-rgba-saver-verification.json),
[reopen](evidence/phase2-20261030/native-project-reopen.json),
[Deliver](evidence/phase2-20261030/native-deliver-verification.json).

## CorridorKey 2.0 MLX work

The reviewed community v2 source remains pinned to
`74065491ebd2eddea494ab34c15a6d84d7415353`; the FP32 model revision remains
`7bb9a4443d5f1b4b696bcc0547d49ae0ac5e5f7e`. Both published 768×1280 and
1024×1536 t1/t4 assets were acquired/verified against the lock. Identical locked
temporary files were reused; differing shape-specific weights were downloaded
and hashed, never produced by editing graph metadata.

The pinned upstream parent verifier independently passed **1,476 exact tensor
comparisons** against the installed official v2 checkpoint, SHA-256
`c43596de98cc8866d577c8a9f9ea239acdf3f7a130ff24e25db4375a50590436`.
The source is the actual RVM/C-RADIO/MoGe/stage1/stage2 v2 architecture; the earlier
Hiera port was not substituted. Separate model/source license notices remain.

New native standalone comparisons use the pinned public 1536×1024 blue-screen
redhead/gauze still, decoded to linear RGB with **no resizing**, repeated six
times to exercise t4 recurrence and overlap. All learned MLX components executed
on MLX GPU; the PyTorch Module forward hook recorded **0** calls. CPU transfer,
interpolation and scheduling remain documented dependencies. These runs were
separate processes, serialized with no other neural QA worker running and
Resolve open. They do not establish real-motion quality or Resolve MLX playback.

| Scope | MPS | MLX v2 |
|---|---:|---:|
| Single-process load | 6.911 s | 1.119 s |
| First inference after load | 1.987 s | 4.220 s |
| Warm repeated-still median | 1.726 s | 1.104 s |
| Six-frame temporal compute | 12.673 s | 10.711 s |
| 18 cached reads | 0.0136 s | 0.0142 s |
| Temporal peak sampled process physical footprint | 14.54 GiB | 8.35 GiB |

Physical footprint sampling was 50 ms and excludes Resolve. MLX defers profile
verification, graph/weight work and compilation into first inference; load alone
is not a comparable cold-start endpoint. These are fresh-process measurements on
an already-running Mac, not reboot-cold timings or distinct moving-frame results.
The earlier 720p sample had slower MLX temporal processing; speed is profile and
workload dependent.

| Error versus MPS | Single | Temporal |
|---|---:|---:|
| Alpha MAE | 0.000757352 | 0.000548065 |
| Alpha p99 | 0.00461781 | 0.00245363 |
| Alpha maximum | 0.0183100 | 0.00395459 |
| Linear foreground MAE | 0.000364476 | 0.000162566 |
| Linear foreground p99 | 0.00351092 | 0.00139624 |
| Linear foreground maximum | 0.217847 | 0.0496740 |

Both pass the **existing predeclared** MAE/p99/alpha-maximum thresholds. Foreground
maximum was not a declared threshold: the single-frame maximum occurs around
alpha 0.037. Premultiplied linear RGB maximum differences were 0.01734 single and
0.007514 temporal. These differences are reported, not described as equality.
Signed and >1 foreground values survived (MPS maximum 6.92 in this fixture).
Side-by-side preview review showed comparable hair/gauze structure and residual
blue spill in both; there is no perceptual pass score or broad HDR qualification.

Evidence: [parent bytes](evidence/phase2-20261030/mlx-parent-bytecheck.json),
[timings](evidence/phase2-20261030/larger-profile-summary.json),
[quality](evidence/phase2-20261030/larger-profile-quality.json),
[fixture](evidence/phase2-20261030/larger-profile-source.json).

## Checks and remaining blockers

**150 Python tests plus 6 subtests; 8/8 native CTest checks passed.** Added
regressions cover attempt expiry/cancel/abort/concurrent consumption, recovery
after rejected native renders, real SDK import behavior, geometry rejection and
restart revalidation, staging write/readback/promotion failure, crash-surviving
staging recovery, active/concurrent export protection, shared eviction, partial
cleanup retry, miss classification, trusted-size re-export and active-bake drain
protection. Mock/harness checks are not labelled installed-Resolve qualification.

`scripts/release/run_fault_qa.py` is a developer-only native fault runner. It
requires an isolated same-user QA manifest and a cache/fault file under that
manifest's directory. Installed launchers never invoke it. Raw media, large
outputs, stack samples and models remain outside tracked evidence.

The installed plugin is unchanged at SHA-256
`e6304a001859f5026735b5d4e12156573c30109a7fae250dfe4ee647cb09fae2`.
Candidate product SHA-256:
`3d8c09120394ec37b4207cf3f3c713228597102645c2e3a3b4b5dca96595dcaa`.
Final QA alias SHA-256:
`0b5aa24e7e4986f17066a31bb497d7d2f745aa0e51f7c1c5b21e8999df05225e`.

Release gates still **Blocked / Not run**:

- **Native 1920×1080 MLX:** current conversion pads it to **1152×1920**. Neither
  that graph set nor the optional 1152×2048 set exists in the pinned distribution.
  The pinned source supplies precision converters, not a fresh-shape exporter.
  No graph JSON dimensions were rewritten and no hidden downscale was added.
- Full-resolution MLX Single/Temporal Fusion and Deliver, broad moving green/blue
  footage, hair/glass/blur/HDR, long sequences, nonzero-origin/PAR and 24/29.97 fps
  host qualification, and a separate Metal kernel trace remain incomplete.
- True in-flight Resolve user-abort and physical GPU exhaustion are not claimed
  from error injection. Physical SSD disconnect/remount and real non-square-PAR
  media were not tested; controlled missing-path and unit rejection were tested.
- **Offline installer:** no new package was built. Clean-account offline install,
  installed-artifact upgrade, repair/uninstall and installed Fusion/Deliver gates
  have not been run. Production replacement requires the user's separate approval.
- MLX 0.32.4 used here requires macOS 26; older macOS MLX support remains
  unqualified. MPS stays the default and the MLX adapter stays opt-in experimental.

The QA project is saved. Temporary analysis was cleaned, previous bakes and
original footage were retained, and the pre-existing `.DS_Store` change was left
out of the implementation commit.
