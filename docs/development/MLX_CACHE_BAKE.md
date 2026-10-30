# MLX/cache/bake candidate — unqualified development branch

2026-10-30, branch `feature/mlx-cache-bake`, based on
`deb84c2d619983663ef31e5a9d5ef40191b6cca4`. This is a source candidate with
native evidence, **not an installed upgrade or qualified offline release**.
The original production plugin, runtime and models were preserved. No package,
merge, push or production installation was performed. The existing `.DS_Store`
modification was left alone.

## Export size and the small-image defect

`Bake / Export Size` defaults to **Match Source**. Other saved options are
Analyzed / Baked Size (no resize), UHD 3840×2160, DCI 4096×2160 and Custom.
Half float is the default; full float preserves RGB beyond the half-float range.
Export size is independent of neural analysis resolution. Resampling maps the
complete frame with bilinear pixel-center interpolation and no crop; RGB is
resampled in linear light and alpha is clamped to [0,1]. The manifest records
analysis size, source size, output size, resampling method, fps and frame range.
Selecting 4K export does not create a native 4K neural graph.

The original test footage is **4096×2160 at 25 fps**. The test analysis used an
explicit full-frame resize to 1920×1080. A 4096×2160 Fusion canvas initially
placed the smaller baked image into a corner. Baked playback now fits the whole
image to the output canvas. Matching the analysis canvas and enabling Resolve's
Use plugin RoD for output size also produced exact 1920×1080 native Saver files.

Resolve can report its normalized working canvas as OFX Source dimensions.
The worker therefore probes original upstream media dimensions using the
installed official Resolve scripting SDK. It follows the matching saved node
UUID's primary input to MediaIn/Loader clip metadata, without evaluating images.
Resolve serializes that SDK access during OFX callbacks, so the probe is deferred
until Render returns and retained by node plus analysis generation. It survives
worker restarts and pixel-cache cleanup. Explicit Original Source width/height
overrides remain available for complex graphs and legacy projects. If automatic
dimensions are unavailable, Match Source preserves the previous bake and asks
for a retry or explicit dimensions; it does not silently use normalized HD.
A legacy bake without prefetched geometry needed one retry in the native test.

Native Bake Alpha with Match Source=0 and both dimension overrides=0 produced
**60 distinct 4096×2160 single-A HALF EXRs**, frames 0–59 at 25 fps, from the
1920×1080 analysis. Every checksum, dimension, channel type and alpha range was
verified. This re-export ran after all temporary analysis had been removed:
worker model_loaded=false, fixture_passed=false, zero model calls, zero cache
puts. Native Saver composition at frames 0 and 59, with the worker stopped,
matched the baked A exactly and original 4K RGB × A exactly. The host may cache
frames; these are output-correctness checks, not uncached playback benchmarks.

Evidence: [4K alpha](evidence/native-4k-alpha.json),
[4K composition](evidence/native-4k-composite.json),
[1080 RGBA native Saver](evidence/native-1080-rgba-saver.json).

Matching dimensions assumes the analyzed image covers the same complete frame.
Resampling cannot undo upstream crops, transforms, retiming or different pixel
aspect mapping. Those cases require explicit alignment and further qualification.

## What the cache evidence establishes

The installed DiskCache was reproduced in an isolated synthetic cache on the
actual Mac: same filename and bytes, changed mtime/ctime on an aged read, no
neural execution. This proves a timestamp-touch path, not that every observation
in the user's original project came from that path. Existing stage requests
already deduplicate input content; they were never unconditional writes.

The candidate removes read-time utime, makes writes immutable/idempotent under
thread/process locks and atomically promotes flushed files. In-memory LRU avoids
touching blobs. SQLite stores capture/result ownership, generation records and
shared leases across worker restarts. Clear Temporary Analysis removes matching
unshared captures, results and completion markers. Model weights and durable
media are outside that cleanup domain.

`analyze_status` and `result_get` identify a complete generation and validate only
the requested result. Losing another frame does not force whole-shot inference.
A missing requested result is an explicit stale error; Analyze / Resume repairs
it, while Force Reanalyze creates a new revision. Source snapshot identities
include the complete causal keys, profile, hints, color settings, backend,
precision and pinned model identity. Cache-only worker startup does not load a
model or run a GPU fixture.

Actual Resolve Fusion analysis of 60 frames at **1920×1080**, MPS FP32, window 4,
completed in **249.508 s** for the neural analysis scope; the first complete host
request took about 266.38 s including capture/startup. Initial storage was 60
captures, 60 results and one analysis marker. Then 60 forward, 60 reverse and
three seeded shuffled passes of 60 requests produced:

| Observation | Measured delta |
|---|---:|
| New/removed blobs or completion markers | 0 / 0 |
| Blob mtime/ctime/inode changes | 0 |
| Byte growth | 0 |
| New input staging / staging attempts | 0 / 0 |
| Analysis starts/completions | 0 / 0 |
| Neural network invocations | 0 |
| Worker result hits | 59 |

Resolve's RAM cache satisfied other requests. The 59 worker hits are distinguished
from the 300 host requests; no 300-worker-read claim is made. The native cache
navigation evidence predates the later export-size metadata addition; that
addition separately writes a small source-geometry record once per generation,
without rewriting `.ckf` or analysis markers.

Evidence: [installed timestamp reproduction](evidence/installed-cache-repro.json),
[native navigation](evidence/native-cache-replay.json).

## Durable bake behavior

Bake Alpha, Bake RGBA and Bake & Clean operate on legally captured complete
generation buffers, or on verified durable media when re-exporting after cleanup.
Files are written in a versioned staging directory, read back, checksum-verified
and atomically promoted. The native reader independently verifies the entire
sequence before the saved manifest parameter is activated. The previous manifest
is retained; cleanup runs only after that activation and only if this node still
owns the matching temporary generation. Failed exports never clean the cache.
The destination cannot be inside any part of the temporary cache root.

Alpha files contain a dedicated A channel and use current original Source RGB
for composition; recovered foreground is not baked into them. RGBA files contain
straight recovered RGB plus A, and native output premultiplies once. Baked RGBA
renders with Source disconnected. Both modes bypass the inference worker and
whole-shot acquisition. Missing/corrupt files give a relink error, with no neural
fallback. Revert and Relink verify manifests before activation.

Native Bake & Clean created 60 verified alpha files, preserved all 60 previous
RGBA files byte-for-byte, then removed **120 temporary blobs and the completion
marker** after a worker restart. A subsequent 60-frame 1920×1080 native Saver
render with Source disconnected matched RGBA bake pixels exactly. A saved QA
project was reopened under a fresh Resolve session with the worker absent;
baked playback remained available. The current 4K alpha QA project is saved.
External-volume physical unplug/replug and a production plugin upgrade were
not performed.

Evidence: [native cleanup](evidence/native-bake-clean.json).

## Native MLX scope and measurements

Thresholds declared before native comparison: FP32 alpha MAE <= 0.001,
p99 absolute error <= 0.01, maximum <= 0.05; decoded foreground MAE <= 0.01,
p99 <= 0.05 in declared linear Rec.709. All output samples must be finite,
alpha must remain [0,1], and signed/HDR RGB must survive. These thresholds are
necessary, not sufficient: hair/translucency/motion and temporal seams require
visual review. No reduced precision equivalence is claimed.

The installed 0.9.7 MPS backend is preserved. Native 1080p MLX is blocked:
pinned community source `74065491ebd2eddea494ab34c15a6d84d7415353` publishes
768x1280 and 1024x1536 t1/t4 graphs, with no fresh-shape exporter. Precision
conversion scripts cannot create the required 1152x2048 graphs. MPS remains
the default; mlx_v2 is an explicit experimental manifest option only.

Host safety constraint: no trustworthy non-render, shot-wide upstream generation
signal was found in the inspected OFX/Resolve API. Live temporal renders still
inspect the causal Source set in permitted Render actions; cached reads skip
capture uploads, model execution, whole-output-set validation and the second
post-analysis scan. They cannot safely skip the initial causal inspection.
Baked RGBA is the worker-free, source-free fast path. No unsafe O(1) live
playback across arbitrary upstream edits is claimed.

The existing signed-asinh adapter pads to multiples of 128: a native 1080p
request currently becomes 1152x1920. Neither that canvas nor the specification's
1152x2048 target has a published pinned graph. Extra reflection to 2048 would
also need explicit numerical verification. No graph dimensions are rewritten.

The adapter calls the raw community v2 MLXGraph components in memory, not its
PNG renderer or CLI. All learned RVM, foundations (C-RADIO/MoGe), stage1 and
stage2 calls use MLX GPU with evaluation/synchronization at measured boundaries.
CPU PyTorch interpolation remains; this runtime is not torch-free. A global
torch Module forward hook observed zero forward calls in the matched temporal
MLX test. A separate Metal trace has not been captured.

Source is pinned to [74065491](https://github.com/peterteravskis/corridorkey-v2-mlx/tree/74065491ebd2eddea494ab34c15a6d84d7415353).
FP32 model assets are pinned to [7bb9a444](https://huggingface.co/cdelta/CorridorKey-v2-MLX-fp32/tree/7bb9a4443d5f1b4b696bcc0547d49ae0ac5e5f7e).
Actual source/model SHA-256 entries and separate licenses are in
[`mlx-v2-lock.json`](../../scripts/release/mlx-v2-lock.json) and `licenses/`.
All downloaded 768×1280 t1/t4 asset bytes were verified. 1024×1536 is locked but
has not been downloaded/native-tested in this task. Unsupported canvas/window
combinations fail explicitly. There is no automatic MPS or single-frame fallback.
No installed-runtime network acquisition was added.

Actual hardware: **Apple M5 Pro, 48 GiB**, macOS **26.3.2**, Resolve **21.1.2**.
Matched comparisons used the same six source frames 30–35, explicitly resized
to **1280×720**, linear input, FP32; model padding was 1280×768. These are native
standalone worker measurements, not Resolve plugin MLX or Deliver benchmarks.
Resolve remained open during the matched temporal pair.

| Scope | MPS | MLX v2 |
|---|---:|---:|
| Single-process load | 9.818 s | 1.985 s |
| First inference, after load | 2.010 s | 7.141 s |
| Steady distinct frame, approximate | 0.99 s | 0.66 s |
| Six-frame temporal compute, Resolve open | 7.381 s | 8.206 s |
| 18 requested cached reads, same temporal run | 0.0123 s | 0.0111 s |
| Sampled peak process physical footprint | 10.85 GiB | 7.78 GiB |

MLX lazy graph/weight work appears in its first inference; load time alone is
not an equivalent cold-start comparison. Physical footprint was sampled every
50 ms and excludes Resolve. Steady single-frame inference improved on this
sample; temporal inference did not. Cached reads created no new files, changed
no blob timestamps and executed no networks in either backend.

| Quality versus MPS | Single frame | Temporal |
|---|---:|---:|
| Alpha MAE | 0.000111083 | 0.0000973544 |
| Alpha p99 absolute error | 0.00128800 | 0.00128049 |
| Alpha maximum absolute error | 0.0215510 | 0.00581580 |
| Linear foreground MAE | 0.0000143853 | 0.0000120774 |
| Linear foreground p99 | 0.000184815 | 0.000166133 |

The sample passes the predeclared thresholds above. Signed foreground values
survived, and alpha remained finite in [0,1]. This is not broad HDR, hair/gauze,
glass, motion-blur or full-resolution parity qualification. Reduced precision
FP16/Q8 is not offered by this adapter.

Evidence: [quality](evidence/quality-comparison.json),
[MPS single](evidence/mps-single.json), [MLX single](evidence/mlx-single.json),
[MPS temporal](evidence/mps-temporal-with-resolve-open.json),
[MLX temporal](evidence/mlx-temporal-with-resolve-open.json),
[source identification](evidence/source.json).

## Validation and remaining release gates

Final source checks: **138 Python tests, 6 subtests**, and **7/7 native CTest
checks**. Python transport and native socket checks ran with local socket access;
an initial sandbox-only CTest attempt failed to bind sockets, then passed under
the authorized native check environment. Tests cover concurrent single producing
jobs, eviction/corruption, causal snapshots, restart ownership, explicit repair,
independent EXR decoding, signed/HDR values, native file readback, resized canvas,
saved bake activation/revert/relink and deferred metadata. These tests do not
substitute for missing host acceptance evidence.

| Gate / acceptance IDs | Current evidence and unresolved work |
|---|---|
| G0, CACHE-01/02/08 | Installed timestamp path reproduced; candidate native 60-frame navigation passed. Original live production project was not destructively instrumented. |
| G1, CACHE-03/04/05/06/07 | Source/transport/native harness checks pass; native restart cleanup passed. Full new-version Resolve edit/corruption/eviction/cancel and cross-node matrix remains. |
| G2, MLX-01/02/04 | Real 768×1280 t1/t4 GPU execution and sample parity passed; 1024×1536, Metal trace and broad edge/HDR suite remain. |
| G3, MLX-03 | Native 1080p MLX blocked by unavailable fresh-shape exporter/graphs. No hidden downscale. Native 4K neural inference is unqualified. |
| MLX-05 | Matched standalone startup/frame/temporal/cache/memory measured. Full-length same-profile Resolve MLX, uncached/captured source comparison and Deliver timing remain. |
| G4, BAKE-01/02/03/06 | Native EXR/Saver, cache cleanup, restart and worker-absent checks above. Original 4K size export/composition passed. Full real-edit reanalysis continuity (BAKE-04), physical external-volume relink (BAKE-05), nonzero origins/PAR/retime host matrix remain. |
| G5, HOST-01 | No new package built or installed. Clean-account offline install, upgrade, repair/uninstall, signing, old macOS support, full Fusion/Deliver and installed-artifact acceptance remain. |

The experimental MLX implementation is available in source through an explicit
manifest (`backend=mlx_v2`, reviewed `mlx_source_root`, `mlx_model_root`,
`mlx_lock`); it is not a qualified shipped installer beta. MPS is still the
production/default backend. The temporary MLX 0.32.4/Metal wheels used here
require macOS 26; support for older macOS versions is unqualified.

Installed production build: `0.9.7-b1.027347b5a7e5`, plugin SHA-256
`e6304a001859f5026735b5d4e12156573c30109a7fae250dfe4ee647cb09fae2`
(unchanged). The QA alias used a separate OFX identity and same-user QA manifest
under `.build`; production root-owned-manifest enforcement was not relaxed.
Candidate, QA alias and installed hashes are recorded in
[artifact evidence](evidence/final-artifacts.json); worker source hashes are
[recorded separately](evidence/worker-source-inventory.json).

## Reproducing diagnostics

Use the candidate Manager's Details health data for model/cache/node-generation
counters. Support File now adds `engine-counters.json` from an already-running
authenticated local worker, without starting a worker or including its token.
Source/bake counters are local to the OFX instance until Details is requested;
baked Details does not launch the worker. Counts reset with process/instance
lifetimes; compare snapshots within the same lifetime.

For development, `scripts/cache_audit.py snapshot --cache-root ... --output ...`
records `.ckf`/completion filenames, bytes and timestamps. Optional `--socket`
and `--build` add authenticated worker health; the token is read locally and
never included in the report. Take before/after snapshots around forward,
reverse and repeated random navigation, then use `compare before.json after.json`.
Inspect new names separately from timestamp changes and network counter deltas.
Resolve's own playback cache must be measured in its separate configured folder.

`scripts/release/compare_backends.py` writes matched native worker evidence;
`acquire_mlx.py` only acquires hash-locked build-time assets into an explicit
destination. `build_cache_bake_qa.py` creates an isolated QA alias requiring an
already-running matching worker; it never installs or replaces production.
Raw EXR/NPY outputs and large temporary models stay ignored under `.build` or
`/private/tmp`. Compact JSON evidence is checked alongside this report.
