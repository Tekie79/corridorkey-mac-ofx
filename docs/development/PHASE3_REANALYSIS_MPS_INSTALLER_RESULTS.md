# Phase 3: reanalysis confirmation and offline MPS beta

2026-10-30. Branch `feature/mlx-cache-bake`; reviewed base
`aeed8553361947c02066993468c40c96af1c9dea`.
This phase follows the user's MPS-first installer task and [Issue #1](https://github.com/Tekie79/corridorkey-mac-ofx/issues/1).
Earlier evidence is historical and remains unchanged.

**The source is tested. The new installer is an unqualified personal beta,
not an installed or fully qualified release. Production was not replaced and
nothing was merged to main.**

## One click survives independent source confirmation

`AnalysisAttempt` now distinguishes Requested, Capturing, AwaitingConfirmation,
Verifying, Analyzing and Idle. Its per-render scope clears intent on success,
error, abort or cancellation. Only an explicit capture-confirmation handoff
survives a Render action. Pending and confirmation waits expire after 30 seconds;
in-flight work still uses the existing host cancellation and worker timeouts.

Each attempt is bound to the host generation and a serial request token. The
confirmation also binds to the worker's deterministic generation, including the
entire causal input sequence, backend/build, profile, settings, revision and
geometry. A changed generation during confirmation fails that request, then
ordinary navigation reads the prior bake. There is no blind third capture pass
or automatically repeated inference. A newer click cannot be cleared by an older
scope's destructor. Pending intent is transient and is not serialized on save.

The plugin's own `analysisRequest` notification is excluded from source/model
generation changes. Hosts can send that notification synchronously or later;
it must not cancel the click that created it. Force Reanalyze advances the model
revision. Ordinary Analyze / Resume leaves it unchanged and audits completed
outputs before deciding whether input staging is necessary. Complete results
can be resumed without recapturing missing input blobs or loading the model.

Capture confirmation is reported as an informational state and returns no image,
not a successful-looking inference. No OFX image APIs run on background threads,
and no saved host parameters are written by the new Render state machine.

**Host scheduling limitation:** OpenFX has no portable request-render API.
After one Analyze / Resume click, keep upstream settings unchanged and request
another frame within 30 seconds (scrub one frame or render again). The next
eligible host Render continues verification without another Analyze click.
Automatic scheduling of that Render is not promised. Expiry, an actual error
or Cancel restores ordinary baked navigation.

Code: [state machine](../../include/ckmac/analysis_attempt.hpp),
[render integration](../../src/ofx_plugin.cpp),
[explicit output audit](../../worker/ckmac/engine.py).

## Crash-surviving temporal scratch cleanup

An actual QA-worker crash exposed 60 abandoned legacy feature files totaling
**298,643,040 bytes**, separate from captured/result blobs. Their exact task
ownership was known, so that one QA directory was removed manually after the
worker exited. This was not counted as automatic product recovery.

New scratch jobs now have a private registered root, node/generation/build
ownership, a destination nonce and a held job lock. Normal completion and
exceptions remove only their own scratch. Explicit Clear Temporary Analysis
recovers inactive owned jobs after a crash, including after worker restart.
Active jobs, other nodes/generations, symlinks, unknown records and durable bake
roots are preserved. Unmarked legacy scratch is reported and retained for
review, rather than attributed from its filename. Such retention reports
incomplete cleanup instead of claiming an empty cache.

Cleanup reports separate scratch-job counts/bytes, active/other retained jobs
and unknown legacy folders. Capture/result counts and logical bytes remain
separate. Persistent ownership databases/root markers are metadata, not removed
analysis blobs. Recovery also covers the outer scratch scope around the
experimental ordered-backend interface; no MLX neural math or shape metadata
was changed.

Code: [scratch ownership](../../worker/ckmac/temporal_scratch.py),
[transaction protection](../../worker/ckmac/bake_transaction.py),
[cleanup reporting](../../worker/ckmac/generations.py).

## Actual native Resolve checks

Apple M5 Pro, 48 GiB, macOS 26.3.2, Resolve Studio 21.1.2 build 10. Testing used
the separate CacheBakeQA OFX identity and copied projects
`CorridorKey_Phase3_Reanalysis_QA_20261030` and
`CorridorKey_Phase3_Final_QA_20261030`. Original GS02 media is 4096×2160, 25 fps;
source frames 30–89 map to Fusion frames 0–59. An explicit full-frame BetterResize
provides 1920×1080 analysis input. The original media SHA-256 is unchanged:
`756191c3f2c996b97e7552d2ac388dfb5bad8606321476e5aee03c6c66fe5409`.

| Check | Observed result |
|---|---|
| One-click initial analysis | First capture returned no image with zero staging/neural calls. Next host Render completed the 60-frame MPS analysis; request advanced once, model revision stayed 3. |
| Exact upstream-frame edit after RGBA bake/clean | Only source fingerprint **17** changed. One Analyze click, two captures, a new completed generation; model revision stayed 3. Previous Alpha/RGBA hashes remained unchanged. |
| Final candidate, full 60-frame MPS run | Completed in **245.649 s** of recorded analysis scope; all 60 raw outputs exactly matched the preceding FLOAT RGBA reference. Scratch was removed normally. This is not startup or viewer timing. |
| Final forward/reverse/shuffled replay | **300 successful requests**, **60 worker result hits**; remaining requests used Resolve RAM. Zero staging attempts, new analysis or neural calls; blob/JSON sizes, mtime, ctime and inode unchanged. |
| Duplicate resume after worker restart | Native Copy/Paste produced a distinct UUID. After explicitly restoring intended graph connections, one click/two renders reused completed results with the model unloaded, zero staging and zero neural calls. |
| Shared cleanup | Bake & Clean retained all **120 shared entries**. The last owner later removed 61 captures and 89 results; 31 absent identities were not counted as reclaimed bytes. This included partial data from the controlled crash. |
| Changed source during confirmation | First and confirmation renders returned no image; the following normal baked render succeeded. No staging or neural work. |
| Pending cancel | Cancel between capture and confirmation restored baked output, without model loading. |
| Temporal error, simulated OOM/cancel, missing capture | Each attempt failed, then the next normal render used the unchanged bake. OOM/cancel were injected exceptions, not physical GPU exhaustion or a real in-flight UI abort. One QA input really was removed for the missing-capture case. |
| Real owned-scratch crash | SIGKILL after the first real feature file; requested analysis returned no image, subsequent baked render succeeded. Restarted, unloaded worker plus native Clear removed **60 captures / 1,990,659,360 bytes** and **1 scratch job / 4,977,805 bytes**, with zero neural calls. |
| Final Alpha / RGBA media | 60 4096×2160 single-A HALF EXRs and 60 1920×1080 straight RGBA FLOAT EXRs. Every checksum/sample was verified; RGBA also passed the production native reader's full audit. Source dimensions were explicitly verified for the color-only upstream edit. 4K is resampled export, not native 4K inference. |
| Final activation and cleanup | Verified RGBA activated in the copied project, then native Clear removed **60 captures + 60 results / 3,981,318,720 bytes**. Zero remaining capture/result blobs or scratch jobs. Database/root metadata remains. |
| Offline native Saver | All 60 FLOAT RGBA frames exactly matched one premultiplication of the bake; maximum error **0**, Source disconnected, worker absent and cache cleared. |
| 4K alpha composition | Frame 23 output A exactly matched the baked A, and RGB exactly matched original 4096×2160 RGB × A; both errors **0**, worker absent. |
| Final native Deliver | Completed, **60 distinct FLOAT RGBA EXRs**, 1920×1080, 25 fps, maximum error **0**, worker absent/Source disconnected/cache cleared. Individual-clip filenames 30–89 correctly map to Fusion 0–59. Job reported **5.761 s**, an export scope only. |
| Project reopening | Saved during unfinished confirmation in the earlier run, then fresh-session baked output succeeded. Final saved RGBA also reopened with Source disconnected and no worker; frames 0, 43, 59 succeeded. |
| Missing media / Revert / Relink | Controlled relocation of the QA bake returned no image without inference. Restore plus native Relink recovered it; pending Force followed by Revert/Relink preserved baked access. Physical SSD removal was not tested. |

Native Copy/Paste initially rewired the QA source graph. Its new capture matched
the original unedited frame 17, so a genuinely different generation correctly
started analysis. That run was excluded from the reuse pass, interrupted with
an actual QA-worker crash, and its partial cache was measured/cleaned. The graph
was explicitly repaired before the passing duplicate-reuse test.

One Resolve process exited with signal 9 / status 137 during copied-project
setup before the QA worker staged input or loaded a model. Its cause is
unconfirmed; it is not labelled GPU OOM recovery. Subsequent separate project
loads, analysis, exports and reopening passed. Long neural renders exceeded the
connector's 60-second RPC limit; actual completion was verified from the worker,
generation records, native bake and subsequent reads. RPC timeout was never
counted as a successful image result.

**Picker automation limitation:** repeated scripted folder confirmation became
disabled; coordinate activation reported `noWindowsAvailable`, and Dock lookup
timed out. No speculative picker code change was shipped. The final RGBA was
therefore exported via the authenticated QA worker, audited with the production
native reader, activated through supported SDK parameter changes, and cleaned
with the native control. Native Alpha export and earlier RGBA Bake & Clean
callbacks passed. The final interactive picker/one-button route is not claimed
as fully qualified.

## Offline MPS package

Version **0.9.8-beta.1**, build **0.9.8-b1.32baa56c3837**, worker component 9,
protocol 2, adapter math/cache format 3. The manifest explicitly selects MPS.
The package includes the private Python/runtime, all locked model weights,
plugin, Manager, native launcher, maintenance/removal packages and licenses.
Acquisition is build-time only: **35 publisher assets and 39 wheels verified**.
MPS remains the default; MLX graph assets are not required by this package.

Installer SHA-256: `2249be84fb0152d2bbb7608a3492d357bcdde7bd3f91c97458b6570dee4d57cd`;
size **4,050,694,428 bytes**. Candidate/source hashes and test records
are in [candidate-artifact.json](evidence/phase3-20261030/candidate-artifact.json).
Code is ad-hoc signed; the package is unsigned. The artifact and installer UI
remain labelled **unqualified personal beta**. Superseded local candidates were
archived; their qualification is not inherited by the final artifact.

The payload qualifier starts the packaged native launcher and packaged isolated
Python from the expanded installer, with outbound IP denied by macOS and
deliberately invalid PYTHONHOME/PYTHONPATH/Conda settings. It checks actual 1080p
MPS inference, useful alpha, byte-identical cached reads, cache reuse after a
worker restart without loading a model, cleanup, and unchanged payload paths/
hashes. Final first load plus inference was **35.278 s**;
cached read was **0.0362 s**. These are fresh-process
relocated measurements, not installed Resolve/viewer or reboot-cold timings. This is relocated-payload evidence, not installed-supervisor or clean-
account Resolve qualification. Exact final results and timings are in the linked
artifact-bound evidence. The actual preinstall also rejected an unsupported
non-startup target before changing files.

**160 Python tests plus 6 subtests, and 8/8 native CTest checks passed.** New
regressions exercise the two-render handoff, generation mismatch, serial/expiry/
cancel/reopen/concurrent requests, own-token callbacks, full output audit,
60-frame bake/clean/edit/rebake, causal identity, read-only reuse, actual
crash-surviving scratch, node/generation scope, active locks, deletion retry,
symlink/legacy/durable-root refusal and previous-version preservation.

## Remaining release gates

- **Not installed:** the package targets the global production paths and its
  preflight requires the startup volume. Installing, upgrading, repairing or
  uninstalling it here would conflict with the user's explicit production
  preservation requirement. No isolated startup-volume/clean-account native
  installation was qualified. Manager/normal OFX-supervisor first use and all
  installed-artifact gates remain Blocked/Not run; portable transaction tests
  and relocated tests do not replace them.
- End-to-end interactive picker confirmation, true in-flight UI abort, physical
  GPU exhaustion/SSD disconnect, broad HDR/glass/blur/blue-screen coverage,
  complete mode/rate/PAR/origin combinations, a separate Metal kernel trace and
  additional Macs/OS versions remain incomplete for this installer.
- **MLX remains separate and experimental.** Reference commit remains
  `74065491ebd2eddea494ab34c15a6d84d7415353`. The pinned distribution has static
  768×1280 and 1024×1536 t1/t4 profiles, no 1152×1920 native-HD set (or optional
  1152×2048 set), and no reusable fresh-shape exporter. Implementing and validating
  that exporter/operation parity remains unfinished. No graph metadata was
  rewritten, no hidden downscale or earlier-architecture substitution was made,
  and no full-resolution MLX Fusion/Deliver qualification is claimed. This did
  not block construction of the user-requested MPS beta.

Original production plugin/runtime/models and original footage were preserved.
Only copied QA projects were edited. The pre-existing `.DS_Store` modification
is excluded from the implementation commit.
