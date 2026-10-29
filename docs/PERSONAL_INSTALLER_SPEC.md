# CorridorKey Mac personal installer specification

**Specification version:** 1.0  
**Date:** October 27, 2026  
**Owner:** Tekie  
**Implementation agent:** Codex running on an Apple Silicon Mac with DaVinci Resolve available  
**Starting project:** CorridorKey Mac OFX `0.1.0-alpha.1`  
**Intended use:** private, personal filmmaking and editing on the owner's Macs

## 1. Product objective and completion contract

Build a complete, offline macOS installer for a real CorridorKey 2.0 OpenFX plugin in DaVinci Resolve. The installed product must run the actual model on the Apple Silicon GPU and manage its own runtime, models, worker process, cache and diagnostics. The user should install the package, reopen Resolve, add the effect and begin keying. Creative decisions such as input color interpretation, subject hints and temporal processing are acceptable; Python installation and process management are not part of the editing workflow.

This specification changes the previous development-only delivery into an installed application. The user has explicitly stated that this is for personal use, not commercial distribution. Build the complete private installer with its required assets. Retain attribution and dependency notices; do not add accounts, activation, subscription logic, a payment interface or a public distribution service.

For the requested installed product, this specification supersedes the alpha README's manual end-user setup and worker-launch workflow. The original source, README and validation record remain useful baseline evidence; their instructions are not the final user experience.

**The requested final deliverable is a verified `.pkg`, not only source code, a `.venv`, an unsigned bundle in a build directory, a shell launcher or a set of instructions.** This document describes work Codex must perform on the Mac; it does not claim the installer already exists.

### 1.1 Mandatory completion conditions

| ID | Requirement |
| --- | --- |
| DONE-01 | Produce `CorridorKeyMac-<version>-arm64-Offline.pkg`, containing every runtime and model asset needed for offline installation and first inference. |
| DONE-02 | Install and run under a clean nondeveloper user account, without user-installed Python, pip, Git, Homebrew, Xcode, an upstream checkout or an existing Hugging Face cache. |
| DONE-03 | Run the complete real model on MPS with automatic CPU model fallback disabled; retain native hardware evidence. |
| DONE-04 | Resolve discovers the plugin, processes real footage, composites correct alpha and exports a tested sequence. |
| DONE-05 | Worker startup, endpoint selection, recovery and shutdown are automatic. No Terminal window or service registration is required for normal use. |
| DONE-06 | Single-frame and actual temporal shot processing work, with deterministic cached results under reverse/random frame requests. |
| DONE-07 | Installation, first use, keying, analysis and export work with network access disabled. |
| DONE-08 | The installed product remains usable after the build checkout is moved away, unrelated Python settings are changed, and the Mac is restarted. |
| DONE-09 | Upgrade, repair, rollback and uninstall have tested, narrowly scoped behavior and preserve unrelated Resolve work. |
| DONE-10 | Deliver the installer, source, manifests, test results, measured hardware support, a short user guide and an uninstall method. Explicitly identify any unmet gate. |

MUST means required for the finished personal release. SHOULD means the specified default may change only with a documented technical reason and equivalent user outcome. MAY marks optional work. The user does not need to approve routine implementation decisions already covered by this specification.

### 1.2 Scope and release milestones

The first engineering milestone is a fully installed, automatically started **Single Frame** build. Label it `0.9.x-beta` until the required temporal and final delivery gates pass. Do not stop there and represent it as the complete 1.0 specification.

The final 1.0 feature set includes real single-frame inference, actual upstream-style temporal shot analysis, per-frame hints, alpha/foreground output, native-resolution rendering, automatic local runtime management, the offline installer and graphical maintenance. A first-frame hint with propagation is included once the temporal path is working. Long-window presets beyond the hardware-validated limits are not required.

Direct OFX Metal-buffer exchange, a Core ML/MLX rewrite, Intel Mac support, Windows support, a cloud service, a public update server, an asset marketplace and a commercial licensing system are outside this release. GPU inference through the separate MPS worker satisfies the GPU requirement; zero-copy host integration is a later optimization.

## 2. Starting point and verified facts

Use the existing project rather than generating a replacement scaffold. Read its `README.md`, `docs/VALIDATION.md`, backend and C++ render/protocol code before modifying it.

### 2.1 Baseline status

The source alpha has compiled on Linux against the official OpenFX headers. Its recorded verification is three C++ suites, 92 Python tests and six subtests, including a real C++ client talking to the Python server with a deliberately fake inference backend. The alpha has not completed actual Mac model inference, native plugin compilation, Resolve loading or visual matte validation. These are starting facts, not release evidence.

The alpha already implements float RGBA transport, image orientation and stride handling, correct model encoding/decoding, explicit MPS placement, source-alpha hints, basic RAM caching and explicit inference errors. It still depends on a project-local virtual environment, manually downloaded models, a manually started worker and a visible socket-path setting. It performs independent T=1 inference only.

### 2.2 Preserve these audited revisions initially

| Component | Revision or version |
| --- | --- |
| CorridorKey source | `485f5e9ab759ead6138cc990776184b59d6ea971` |
| CorridorKey weights snapshot | `cf44a8db3f024bb49fd59daa408848ccf05f7477` |
| OpenFX SDK | `c3f1c2dcf4f51762b794c4fc21181b4a501be1bf` |
| NVIDIA C-RADIO snapshot | `c0457f5dc26ca145f954cd4fc5bb6114e5705ad8` |
| MoGe snapshot | `ca5f0e07ff01d3e5a364c1d954ed12ee1814b368` |
| utils3d source | `83bfa5bda008803f6521ce9547f94023b8afeddd` |
| RVM asset | `pretrain_rvm_small16_256_204031069.npz` |
| PyTorch and torchvision | `2.9.1` and `0.24.1` |
| NumPy and OpenCV | `1.26.4` and `4.11.0.86` |

Select one native CPython 3.12 patch/build during the first qualification milestone, then lock its archive name and SHA-256. Lock all transitive dependencies and their wheel hashes. There are no invented hashes in this document: generate hashes from the verified artifacts and commit the resulting manifests. Replacing a pin requires a recorded compatibility reason and rerunning the affected native gates. [S1, S2]

## 3. Target machines and host support

The owner's known machines are an M2-family Mac Studio and an M5 MacBook Pro with 48 GB unified memory. Inspect the actual chip, GPU configuration, memory, macOS and Resolve edition/version on each accessible machine. The Mac Studio's memory is not assumed. Prior conversation context is not a substitute for inspecting the current installation.

| Area | Target and rule |
| --- | --- |
| Architecture | Native Apple Silicon arm64 for plugin, helper, Python and native dependencies. No Rosetta requirement. |
| macOS | Initial deployment target 14.0, subject to all locked binaries supporting it. Only tested versions may be listed as qualified. Do not silently raise the deployment target to the developer Mac's OS. |
| Resolve | The owner's installed DaVinci Resolve Studio is the primary host. Record its exact version; do not infer support for other releases from a major-version number. |
| Primary workspace | Fusion page, including Merge compositing and Deliver export from a timeline containing the composition. |
| Secondary surfaces | Color/Edit and free Resolve may be qualified separately. Do not claim their support solely because Fusion Studio/Resolve Studio works. |
| Image format | Progressive float RGBA processing. UHD 3840×2160 is a target; 1920×1080 is the minimum full workflow qualification. |
| Frame rates | At least one integer rate and 30000/1001, with frame identity preserved. Test other rates if used by the owner's footage. |
| Storage and memory | Measured requirements derived from package size, model profile, frame size and temporal range. No NVIDIA-VRAM-to-Mac-RAM conversion. |

The required release baseline is the available primary Apple Silicon Mac, its installed Resolve Studio/Fusion workflow, and a qualified native 1920×1080 profile with both required processing modes. Final 1.0 requires all universal product gates and the gates for every explicitly claimed support combination. Required features, including actual temporal processing, cannot be waived by narrowing the hardware matrix.

Attempt native UHD and the second Mac when physically available. If a device cannot support a particular temporal/native-resolution combination, record the exact boundary and offer an explicit lower profile. UHD, a second Mac, other macOS/Resolve versions and secondary host surfaces are conditional support claims. A failed or unavailable test excludes that combination from qualified support; it never counts as Passed. It does not block release for the fully qualified primary combination. The installer description and report must state the qualified combinations prominently.

## 4. Expected user experience

### 4.1 Installation

1. The user double-clicks the complete offline `.pkg`.
2. Installer identifies the product, supported architecture/OS and required storage. The normal macOS authorization is the only administrative setup step.
3. If Resolve or Fusion is open, the installer gives a clear instruction to close it and retry. It never kills the host or discards unsaved work.
4. The installer places the plugin, private runtime, model set and Manager application in their standard locations, verifies the payload and activates a compatible complete version.
5. The completion screen says: **Installation complete. Open DaVinci Resolve and add CorridorKey Mac. Its GPU engine starts automatically.**

No model download, Python setup, shell profile edit, PATH change, service registration or mandatory Manager launch occurs after installation. A normal macOS trust approval may still be necessary for a private, locally signed build; section 16 defines that behavior accurately.

### 4.2 First use

The user adds **CorridorKey Mac** to a Fusion composition. The effect starts its worker on demand, verifies the installed runtime/model identity, loads the models and performs a small real-model check for the current hardware/software combination. It then keys the actual frame. Status distinguishes preparing, loading, checking GPU, processing and ready. It never displays a successful GPU-verification badge merely because a device enumeration or matrix multiplication worked.

Default Single Frame mode gives a real initial key. The user can select Temporal and analyze the shot for temporal processing. This is a creative processing action, not an installation/configuration step.

### 4.3 Everyday use

Opening a saved project, duplicating a keyer, moving between shots and exporting do not require managing the helper. Multiple nodes share a compatible worker. Results cache automatically. The Manager is available for Verify, Repair, storage details and diagnostics, but ordinary editing works without it.

Input color interpretation remains explicit when the host cannot establish it reliably. The product must not hide an unknown gamma assumption in order to claim zero configuration.

## 5. Architecture and installation layout

### 5.1 Components

| Component | Responsibility |
| --- | --- |
| `CorridorKeyMac.ofx.bundle` | Native C++ OFX effect, creative controls, valid host image acquisition, parameter snapshots, render completion and host errors. |
| Native worker launcher/manager | Locate protected installation metadata, coordinate one compatible per-user worker, spawn it with explicit arguments/environment, negotiate readiness, track lifecycle. |
| Private arm64 Python runtime | Complete interpreter, standard library, locked packages, upstream model code and adapter, isolated from user Python installations. |
| MPS inference worker | Actual model loading/inference, shot analysis, scheduling, caches and structured status/errors. It runs as the Resolve user. |
| Immutable model store | Exact verified model assets and executable foundation-model snapshot code, referenced by manifests. |
| `CorridorKey Mac Manager.app` | Native GUI for verification, maintenance, local diagnostics and opening the uninstaller. It is optional during normal operation. |
| Offline installer and uninstaller | Authorized changes to product-owned system locations, version activation, rollback and scoped removal. |

Keep Python outside the Resolve process. Use the existing CPU OFX image bridge and MPS worker initially. Do not move Python into the OFX binary merely to avoid managing a helper process.

### 5.2 Required path policy

| Data | Default location | Access policy |
| --- | --- | --- |
| OFX bundle | `/Library/OFX/Plugins/CorridorKeyMac.ofx.bundle` | System-installed, root-owned, readable/executable by normal users. |
| Versioned runtime | `/Library/Application Support/HarvestPictures/CorridorKeyMac/Runtime/<build-id>/` | Immutable, root-owned; all runtime dependencies resolve here. |
| Versioned models | `/Library/Application Support/HarvestPictures/CorridorKeyMac/Models/<model-set-id>/` | Shared read-only files, one copy per retained model set. |
| Active installation manifest/journal | Product system Application Support directory | Root-owned, updated only by installation/maintenance operations. |
| Manager | `/Applications/CorridorKey Mac Manager.app` | Runs as the logged-in user. |
| Installed uninstaller | Product system Application Support directory, `Maintenance/CorridorKeyMac-Uninstall-<version>.pkg`, or equivalent installed GUI removal implementation | Root-owned, integrity recorded; remains available if the original downloaded installer is deleted. |
| User preferences and validation records | User Application Support directory for `org.harvestpictures.CorridorKeyMac` | Private, user-owned. |
| Reconstructable cache | User Caches directory for the product | Private, bounded, safe to rebuild. |
| Logs | User Logs directory for the product | Rotating; no frame data by default. |
| Socket and startup lock | Automatically selected private user runtime directory | Mode 0700 directory and 0600 files/socket; validate platform path length. |

Use Foundation/platform APIs to locate user directories. Do not assume a literal `/Users/<name>` string. The OFX packaging specification defines the Mac bundle layout and standard system search location; use `Contents/MacOS/CorridorKeyMac.ofx`, not a fabricated `Contents/arm64` directory. [S3]

Backups of old OFX bundles must live **outside the scanned OFX tree** so Resolve cannot discover duplicate identifiers. Do not leave timestamped copies beneath `/Library/OFX/Plugins` and assume every host ignores them.

### 5.3 Version identity

Preserve the existing OFX identifier `org.harvestpictures.CorridorKeyMac`. Give the package, native worker, Manager, wire protocol, adapter math, model set and cache format explicit independent version fields. Bundle version alone is not a compatibility test.

Keep saved parameter identifiers stable. Append enum choices rather than reordering existing values. Hide/deprecate legacy socket configuration without letting an old saved socket override the protected installed-runtime discovery path. Provide migration tests for projects saved with the alpha and later releases.

## 6. Private runtime and reproducible build

### 6.1 Packaging strategy

Begin with an audited Python Build Standalone `aarch64-apple-darwin` `install_only` distribution. Pin its exact build and archive hash after native qualification. If a different embedded CPython build is required, document why and prove the same relocation/isolation properties. Python virtual environments generally contain references to their original interpreter and are not a reliable relocatable product runtime; the existing `.venv` remains a developer convenience only. [S4, S5]

The build pipeline MUST:

- Assemble a private interpreter containing the standard library, required native modules, package metadata, PyTorch libraries and all actual import dependencies.
- Install `ckmac` and pinned upstream code into the private import tree so the worker can launch in isolated mode, without a user `PYTHONPATH`.
- Lock all dependencies, including transitive dependencies and the built `utils3d` wheel. Produce a build-time wheelhouse and hash-checked lockfile.
- Audit native libraries with `file`, `lipo`, `otool` and native load tests. Reject absolute dependencies on the checkout, temporary directories, `/opt/homebrew`, `/usr/local` packages or a developer home directory. Approved Apple system libraries may remain external.
- Verify deployment targets and arm64 availability for every binary extension, not just the main interpreter.
- Resolve any required library paths before signing. Re-run dependency and relocation tests after signing.
- Move a staged runtime to a different path containing spaces and a non-ASCII segment, then run the full-model fixture from that relocated location.
- Disable writes into installed source/bundles or redirect generated bytecode, Hugging Face module caches and runtime compilation caches to private user cache directories. A signed bundle must remain unchanged during use. [S6]

Runtime execution MUST NOT call `pip`, Git, Homebrew, a shell activation script or a Python executable discovered from `PATH`. Remove installer/runtime dependence on the source checkout and `.deps`. `RuntimePaths` must be constructed from the installed manifest's separate code and model roots.

If upstream modules import video helpers, distinguish import requirements from actually executed paths. Resolve already supplies image pixels. Do not introduce an unbundled `ffmpeg`/`ffprobe` runtime requirement; if any such executable is genuinely needed, package and qualify its exact native build.

### 6.2 Model and source acquisition at build time

The final package includes all assets required for the selected model. The build fetches them from the original pinned publishers, supports safe resume, verifies complete contents and stages a content-addressed cache. No network acquisition occurs during the installed runtime's startup or inference.

Every asset record MUST contain its logical role, immutable source revision/URL, relative installed path, exact byte size, SHA-256 and license/notice reference. The release must add SHA-256 verification for RVM even though the upstream downloader uses MD5. Audit and pin executable C-RADIO snapshot code as code, not merely as generic model data.

Partial downloads are not eligible for packaging. Resume only when the remote artifact identity and range response match; otherwise start a new staging file. Verify hashes before atomic promotion. Never package credentials, Hugging Face access tokens, development caches or `.git` directories.

### 6.3 Required manifests

Produce these machine-readable build outputs:

| Manifest | Required content |
| --- | --- |
| `runtime-lock.json` | Python distribution identity/hash, exact wheels/hashes, native dependency inventory, deployment target, adapter/upstream revisions. |
| `model-manifest.json` | Model-set ID and all required tensor/config/code files with size/hash/source/license. |
| `install-manifest.json` | Product/build IDs, component versions, protected installation paths, protocol range, compatible model set, payload inventory. |
| `qualification.json` | Machine/OS/Resolve versions, test outcomes, fixture identities, device evidence, memory/timing measurements and untested combinations. |
| `release-checksums.txt` | SHA-256 values for the final installer and other delivered release artifacts. |

These are generated from actual build artifacts. Placeholder hashes, `latest`, unresolved wheel versions and fabricated test results fail release validation. The activation record must name a compatible complete set rather than independently selecting the newest plugin/runtime/model directories.

## 7. Offline installer, upgrades and maintenance

### 7.1 Installer implementation

Use Apple's package tooling (`pkgbuild`/`productbuild`) with a native Installer workflow. The build machine may use developer tools; the target editing account must not need them. Package size is measured from the actual staged payload. Display installed size and temporary upgrade space rather than a guessed fixed download size. [S7]

Preflight checks architecture, OS requirements, available storage, payload destination safety, existing version and open supported hosts. Reject Intel/Rosetta-host mismatch with a clear explanation. Never force-quit Resolve. Root-run package hooks perform filesystem/transaction operations only; they do not start a GUI, download assets, load Torch or run inference.

Configure the distribution for the supported local-system/startup-volume destination. Disable unsupported current-user and alternate-volume targets, and validate Installer's target-root argument before mutation. A hook must not write to the boot volume while Installer reports installation to a different volume. Reject an unsupported target without partial changes.

Install shared runtime/models root-owned with ordinary read/execute access. The installer must not use its own `$HOME` to create the eventual editor's configuration. Runtime caches are created later by the unprivileged worker. Complete first-run verification is triggered by actual user activity.

### 7.2 Transaction and rollback

A multi-component `.pkg` must not be assumed universally atomic. Implement an explicit journal and staged version activation:

1. Verify enough storage for the new version and retained rollback set.
2. Stage every new component, including the OFX bundle, Manager, maintenance payloads and immutable runtime/model set, outside its live activation destination. Do not let the package payload overwrite live bundles before rollback copies exist. If using direct package destinations instead, a verified preinstall backup must precede every replacement.
3. Verify inventory, hashes, ownership and compatible metadata for all staged components.
4. With supported hosts closed and affected workers quiescent, preserve the previous plugin/Manager, maintenance payloads and active manifest outside host discovery paths.
5. Replace activation artifacts using same-volume atomic replacement where possible. Journal each boundary.
6. On interruption or failed activation, restore the previous consistent set or leave a clear repair-required record. Never point the new plugin to a partial runtime.
7. Retain at least the previous complete working set until native verification succeeds. Garbage-collect only unreferenced versions through explicit maintenance.

A running worker must never be redirected halfway through a job by changing a symlink. Each worker resolves one immutable runtime/model identity at launch. Deleting an old version requires proving no retained activation or live worker still uses it.

Host exit alone does not prove worker exit. Before rollback, uninstall, or deletion/replacement of a runtime/model generation, use scoped product IPC to drain and stop its affected workers, then verify they have exited. Do not start root inference, use broad process-name termination or remove files from a running generation. If work is active or a worker cannot be stopped safely, report a maintenance-blocked result and leave the consistent installed set intact.

### 7.3 Repair and uninstall

The Manager's Verify checks the protected install inventory and optionally runs the real GPU fixture as the normal user. Repair opens the exact offline installer or repair package for authorization; it does not attempt an in-place `pip install` or silently upgrade models. The default repair policy does not retain a duplicate multi-gigabyte installer. If a previously selected package is unavailable, use a native file picker to locate the matching original `.pkg`, verify its build identity and complete payload against the protected installed manifests, then open Installer. Also verify the whole-package SHA-256 when the validated post-build release manifest is available. Never assume the package remains in Downloads or require a network connection. Do not create a circular requirement to embed a package's final hash inside that same package; release checksums are external build outputs. A verified retained repair package is an allowed alternative if its storage cost is explicit.

When a trusted whole-package hash is unavailable, verification must also cover preinstall/postinstall scripts, executable Distribution logic and nested component definitions against protected build-time digests. Generate these digests before package construction. Matching only the installed-file payload is insufficient to authorize execution of a selected package. Open Installer only after the complete selected package passes this validation.

Supply a graphical uninstall path through a narrow uninstall package or equivalent supported authorization flow, installed with the product so deleting the original installer does not remove this ability. Quiesce affected workers first. It removes only allowlisted product-owned plugin/runtime/Manager locations and receipts. Offer Keep Models and Remove Models choices, with the size shown. Current-user cache removal is separate; never sweep other users' home directories or delete the common OFX root. Do not remove the official CorridorKey plugin or other plugins.

## 8. Automatic worker lifecycle

### 8.1 Native supervisor

Add a native `WorkerManager` abstraction shared by the plugin and Manager. It locates the installed manifest, verifies ownership/compatibility, connects to the current user's worker and starts the exact packaged executable when necessary. Prefer an on-demand same-user child launched with `posix_spawn` and an argument array. No default LaunchAgent, LoginItem or root daemon is required.

Use a startup lock so concurrent first use across nodes or host processes creates only one compatible model process. One worker serves a user/runtime generation, not one worker per effect instance. A different installed generation gets a separate negotiated endpoint until the old generation has no clients.

Launch with controlled imports and environment. In particular, user `PYTHONPATH`, `PYTHONHOME`, Conda/virtualenv settings or dynamic-library search overrides must not redirect execution. Run the bundled interpreter in isolated mode and explicitly configure the product's writable cache paths. Keep automatic MPS CPU fallback disabled.

The supervisor MUST NOT spawn anything during OFX enumeration, Load, Describe or DescribeInContext. Host scanning may occur in helper processes with no editing session. Start on first actual processing demand or an explicit user preparation action. A render callback must not open modal GUI windows.

### 8.2 States and status

| State | Meaning and allowed action |
| --- | --- |
| Not running | No worker is needed yet. First real request may start it. |
| Checking installation | Validate manifest compatibility and essential file integrity. |
| Starting | Launch/handshake is in progress; wait with bounded polling and cancellation. |
| Loading model | Actual publisher models are being loaded; report elapsed stage information. |
| Checking GPU | A small full-model fixture is running on MPS for this installation/hardware identity. |
| Ready | Required self-check has passed; the worker can process requests. |
| Processing | A frame/analysis job is active; stable device/version facts remain available. |
| Cancelling | Queued work is removed; executing GPU work is being allowed to finish or safely stop. |
| Recovering | One bounded restart/retry is in progress for a recoverable failure. |
| Error | A stable actionable error is available; repeated blind relaunches stop. |
| Idle | No active work; memory retention/exit policy is counting down. |

Keep model-loaded, fixture-passed and real-user-frame-completed facts separate in diagnostics. A cached self-check is invalidated by a change of runtime, model set, adapter, relevant OS/driver identity or hardware. Do not rerun a long benchmark every time the effect is added.

### 8.3 Lifecycle and recovery defaults

- Track client session IDs and leases, not just PIDs. A deleted node does not own the shared worker.
- Use separate connection, startup and job timeouts. Begin with a short connection timeout and a conservative bounded model-load timeout; calibrate them from real cold-start measurements. Show progress while waiting.
- Poll host abort at short intervals while waiting. Target return from a canceled host wait within one second, independent of an uninterruptible GPU kernel continuing in the worker.
- Permit at most two automatic restart attempts with backoff for worker crashes. Missing/corrupt assets or unsupported operators are configuration failures, not reasons for an endless restart loop.
- Remove queued obsolete requests immediately. Discard results for canceled or superseded generations. Do not kill a worker that still serves other clients.
- Release GPU resources after all clients disappear, including after a host crash. As a starting policy, unload after ten minutes of inactivity and exit after a further bounded idle period; verify this does not disrupt active analysis and adjust from measured use.
- Reap child processes owned by the launcher and handle plugin unload safely. No background task may retain a destroyed OFX instance or execute unloaded plugin code.

Idle timings are product defaults, not user setup fields. The Manager may offer a simple Release GPU Memory action when no active job would be lost.

## 9. IPC, scheduling and cancellation

The original version-1 frame protocol can remain for development compatibility, but final lifecycle/analysis features require a versioned control protocol. Keep local-only IPC and float binary image transfer; do not expose a TCP service or send footage off the Mac.

### 9.1 Protocol requirements

Negotiate protocol version, build ID, model-set ID, adapter/cache format and capabilities before sending image data. Requests include a session ID, request ID, effect generation, job kind, exact frame/time identity, input geometry, color interpretation, hint settings, processing profile and bounded payload descriptors. Responses include state, structured error code, dimensions, dtype, alpha association and immutable result identity.

Control messages cover health, frame requests, analysis creation/progress/cancel, result retrieval, cache operations and safe idle release. Image payloads remain explicit little-endian float32 unless a separately qualified transport version is introduced. Reject invalid lengths, integer overflow, unsupported types, non-finite images and unexpected response geometry before touching host memory.

Use a private endpoint with owner/peer checks and an unguessable session/generation handshake. Automatically keep socket paths within macOS limits, including long user names. Do not expose socket names as ordinary OFX parameters. No request may supply arbitrary executable/module paths or unrestricted filesystem destinations.

### 9.2 Queue behavior

Serialize expensive model execution initially, with bounded queued metadata and bounded frame staging. A scrub burst should coalesce obsolete previews. Export/analysis jobs get fair progress; an endless preview stream must not starve them. Release the inference lock before transmitting a completed immutable result to a slow client.

An executing GPU kernel may not be safely preemptible. Cancellation means the host stops waiting promptly, queued work is removed, and late results cannot overwrite newer output. Cancellation must not mean forcibly terminating every shared client. A watchdog may terminate a genuinely hung worker only through bounded recovery with all affected jobs explicitly failed.

## 10. OpenFX behavior and host integration

### 10.1 Preserve the image contract

Keep the plugin native C++ and support filter/general contexts appropriate to the tested host. Negotiate float RGBA for both input and output. Declare CPU OFX buffer handling; reject actual Metal/CUDA/OpenCL resource handles unless a separate native GPU-buffer implementation has been completed.

Handle full-frame source requirements, RoD/ROI, proxy render scale, nonzero bounds, padded and negative row strides, pixel aspect ratio and progressive frames. Do not equate host UI origin hints with pixel memory layout. Test frames whose dimensions are not multiples of 128 and images with nontrivial bounds. A host may provide a larger image region than requested; use the correct requested/source extent rather than rejecting every padded allocation as a partial frame.

Every image acquired from the host must be released within its permitted action. Copy needed data to owned storage before handing it to a worker or retaining it. OFX permits image acquisition in render actions and certain user-edited change actions, with temporal access dependent on host/plugin capabilities. Validate the actual Resolve behavior before building shot analysis around it. [S8]

### 10.2 Threading and instance lifetime

Snapshot render-affecting parameters and source generation at request creation. Main/UI actions can overlap rendering; a render mutex alone does not protect all instance state. Separate UI state, immutable render settings and asynchronous job ownership. Do not call parameter setters or arbitrary OFX suites from worker/background threads. Status changes must be exposed through supported host actions or the separate Manager. [S9]

Qualify the exact Resolve mechanism used for progress and status refresh. During a supported synchronous analysis action, use the tested host progress/cancel interface; this does not imply unrestricted concurrent editing. For asynchronous work, update OFX parameters only through demonstrated permitted callbacks/actions. Standard OFX must not be assumed to supply a universal dispatch-to-main-thread callback. If live panel refresh cannot be supported, show stable truthful status and use the supported progress surface or Details view. Do not call host suites from a timer merely to satisfy a visual requirement.

Prevent stale completion writes after parameter changes, instance destruction, undo/delete, composition close and plugin unload. Do not leave an open socket read on the main UI thread. The current raw JSON health button and visible Worker Socket control must be replaced with human-readable status and a Details/Open Manager action.

Handle Begin/EndSequenceRender, cache purge, instance changes, clip changes and private-data synchronization where required. Project save/copy must preserve settings and enough analysis identity to resolve data correctly; it must not serialize opaque live socket handles or a GPU pointer.

### 10.3 Output and host errors

Keyed RGBA contains premultiplied foreground and alpha. Matte and Straight Foreground are clearly labeled inspection views; preserve the alpha policy documented for them. Original is an explicit user-selected bypass/preview, never a fallback for inference failure.

Final processing failure returns an OFX error with a useful message. The plugin must not report a successful render containing the original frame, a conventional key, an empty matte or a lower-quality substitute. Missing workers should normally trigger automatic startup; repeated startup failure should direct the user to Manager → Verify/Repair.

## 11. Color, alpha and hint correctness

### 11.1 Color contract

Preserve the alpha's correct conversion path: selected input transfer to scene-linear RGB; signed-asinh encoding for the keying model; a separate clamped SDR proxy for foundation networks; decode predicted foreground; return foreground in the declared output transfer. Keep unclipped finite RGB values for negative/HDR data. Do not accidentally replace the model's actual input with its clamped foundation proxy.

Input primaries and transfer function are different concepts. The baseline modes are sRGB, linear Rec.709/sRGB primaries and Rec.709 gamma 2.4. Gamma 2.4 must not be mislabeled as the Rec.709 camera OETF. Default sRGB preserves the current saved parameter behavior; provide a clear Linear Rec.709 workflow preset. An Automatic option is allowed only if the tested host supplies reliable image color metadata and the result is verified.

For the owner's S-Log3/S-Gamut footage, validate a transform into the supported working representation before keying and an appropriate transform after compositing if needed. Do not infer the node's encoding from the camera name, project label or display LUT. Do not apply a second log decode to already transformed footage.

### 11.2 Alpha and foreground

Preserve actual straight foreground from the model. Raw model alpha is clamped to the valid range, not passed through a sigmoid. Unpremultiply incoming associated color safely; handle zero alpha explicitly; premultiply keyed output exactly once. Test transparent edges over black, white and saturated backgrounds in linear light.

Keep model foreground/matte separate from display views so changing Matte/Foreground/Keyed Output does not rerun inference. Additional green despill remains explicitly green-only and off by default. The model's learned unmixing is distinct from that optional correction. Do not add an Auto Blue/Green control without a real implemented algorithm and tests.

### 11.3 Hints

Support None, a real optional matte input where the tested Fusion OFX context provides it, and legacy Source Alpha. An opaque source alpha of one everywhere must not silently become a useful-subject assumption. Hint confidence controls trust in the hint, not model quality.

Validate separate hint dimensions, sample times and alignment. Define whether an RGBA hint uses its alpha or luminance; prefer explicit Alpha and Luminance choices in Advanced rather than guessing. Full-sequence hints must track the actual processed frame. First-frame hint propagation belongs to temporal analysis and must never appear as supported in an independent-frame-only build.

When no explicit hint is present, retain the upstream `-1` no-hint quality semantics. A zero quality inside a hinted temporal sequence is a different state. Crop, pad and resize hints consistently with the actual image without shifting the subject. [S1]

## 12. Temporal shot processing

Temporal processing is a required final milestone because the current T=1 adapter omits the model's video-context pipeline. It must use the actual neural temporal algorithm, not post-process independently generated mattes with a blur or average and call that CorridorKey temporal processing.

### 12.1 Resolve frame-acquisition feasibility gate

Before implementing the final Analyze Shot UI, prove a small end-to-end acquisition prototype in the actual Resolve version:

1. Inspect the host's temporal-access capability and the source/hint ranges.
2. Declare temporal access on the effect and the clips that require it; implement `GetFramesNeeded` for the dependencies actually used.
3. Demonstrate legal acquisition of a short ordered range from the **image arriving at the node**, including upstream transforms/effects.
4. Copy/release every acquired image within the permitted action. Demonstrate progress and cancellation without a frozen Resolve session. Record the exact progress suite/callback path and whether analysis is synchronous or asynchronous.
5. Process owned frames in the worker and render the requested result back through OFX.

Preferred analysis entry is a user-edited Analyze Shot action with valid host image access and the host's progress/abort mechanism, if Resolve implements it correctly. A supported render-driven acquisition path is acceptable when it declares the complete required frame dependencies and keeps memory bounded. Arbitrary image fetches from a free-running Python/background thread are not acceptable.

Do not assume that an Analyze button can start a background thread which continues to call `clipGetImage` after its host action has returned. Do not reopen the underlying movie path in Python as a substitute: that would miss upstream grades, transforms, retiming and masks. If neither supported host acquisition path can be demonstrated, record the precise host limitation, preserve the working Single Frame beta and do not label temporal 1.0 complete. [S8, S10]

### 12.2 Analysis identity and range

Create an explicit analysis record with a persistent effect/analysis UUID, range, frame-rate/time mapping, source and hint fingerprints, processing resolution, color transform, model/adapter versions and all inference settings. A filesystem path plus frame number is insufficient.

Separate immutable reusable analysis identity from live node/session/job ownership. Resolve may copy a saved UUID when duplicating a node. Matching duplicates may reuse an immutable completed analysis, but their live request generations, mutable jobs and cancellation ownership must be independent. Editing, canceling or deleting one duplicate must not mutate the other's valid analysis or cancel its jobs.

A shot analysis is a transaction over one source/hint generation and one immutable parameter snapshot. If the host reports a contributing source, topology, hint, time-mapping or parameter change during acquisition/analysis, cancel that generation and do not promote its partial results. Where no trustworthy source revision exists, implement and document a revalidation strategy before activation. Never publish a completed shot assembled from inconsistent upstream generations.

Default the displayed range from reliable clip/composition metadata, clipped to the actual available source. Show the resolved start/end before a long analysis; allow a concise range override in Advanced. Do not treat an entire media file or a whole timeline as the user's shot without evidence.

Use frame-accurate host times. Preserve 30000/1001 rates, nonzero clip starts and exact requested positions; do not index results by rounded milliseconds. Define handling of fractional times, reverse/variable retiming and unavailable frames. If a path cannot preserve temporal semantics, give a clear instruction to bake that operation before the keyer rather than silently rounding.

Analyze each shot/segment independently. Never carry subject state through a cut. At minimum, a Fusion shot or explicitly selected range is a reset boundary. If multiple cuts occur inside the selected range, accept explicit segment boundaries; automatic cut detection may assist, but must not be the sole correctness mechanism.

### 12.3 Actual model stages

Port the relevant upstream orchestration to a device-independent implementation while preserving algorithm order:

- Prepare declared-color frames and correctly aligned hints.
- Compute recurrent foundation context in ordered frame sequence with the required reset and carry behavior.
- Run stage one on validated overlapping temporal windows.
- Combine the appropriate intermediate features using the upstream taper/overlap rules.
- Run full-resolution stage-two refinement from those features.
- Decode and persist straight foreground plus alpha, then apply the host output association once.

Do not average final mattes as a replacement for blending the required intermediate representation. Do not retain last-rendered-frame recurrent state on an OFX instance and assume Resolve requests chronological frames. Align window starts to the declared analysis range, not whichever preview frame was requested first.

Begin with a short measured temporal profile, such as a 4-frame window with 2-frame stride, and qualify an 8/4 profile when memory permits. These are implementation starting values, not validated support promises. If the published upstream runtime uses additional continuous context beyond that window, implement it or explicitly name the bounded variant and compare it to its exact documented reference. Full upstream temporal equivalence cannot be claimed after silently omitting context.

### 12.4 Preview and final consistency

Use explicit saved processing modes: Single Frame and Temporal. A selected mode must produce the same algorithm for the same inputs regardless of arbitrary host request order. Do not secretly switch algorithms solely because a private interactive/export flag changes; the host might otherwise reuse a preview cache during final output.

Temporal output requires matching completed analysis or a supported deterministic analysis-on-demand path. During setup/analysis, provide progress and cancellation; never pass through the source as a successful temporal result. A visible Single Frame preview can be selected explicitly while developing a key, but final Temporal output must use the analyzed result.

After an analysis-affecting edit, increment the analysis generation and mark dependent results stale. A pending old job cannot overwrite a newer generation. View-only output changes reuse the same foreground/matte. Any automatic switch of a saved mode must occur through allowed host actions and invalidate the host cache.

Every newly activated or replaced analysis revision must also invalidate Resolve's own output cache, even if all visible controls remain unchanged. Prefer a hidden serialized render-affecting analysis-revision parameter changed only within a permitted host action, or another demonstrated supported mechanism. Changing a worker generation or disk file alone does not invalidate the host cache. Background completion must never invoke parameter setters directly; activation waits for the qualified host action/callback path. Test reanalysis of the same node with unchanged visible settings and verify both the viewer and export use the new revision.

### 12.5 Resume and cache validity

Checkpoint only at valid algorithm boundaries with the full necessary recurrent/intermediate state and version identity. A half-written chunk is not resumable. If a checkpoint is incompatible or unverified, recompute from the nearest safe boundary.

Source edits must invalidate all dependent temporal outputs, including later frames influenced by recurrent context. Use verified host generation/unique-image identifiers when available, plus content fingerprints. If the host cannot prove the upstream generation is unchanged, revalidate the relevant frame content before trusting a persistent analysis on reopen/export. File modification time or an unchanged clip name alone is insufficient.

Here, relevant content means the complete causal dependency set: contributing temporal-window frames, hint frames and every earlier source/state dependency represented by a recurrent checkpoint. Checking only the requested frame is insufficient. Trust a checkpoint only if its complete source/hint provenance is unchanged; otherwise recompute from the nearest independently verified reset boundary. A required test changes an earlier frame while leaving a later requested frame's pixels unchanged and proves that the later temporal result is invalidated.

Test the same shot processed forward, backward, shuffled and after reopening the project. Under identical settings, the same output frames must agree within the declared numerical tolerance, and chunk boundaries must not produce seams.

## 13. MPS execution, performance and memory

### 13.1 Real GPU requirements

Use PyTorch MPS as the initial neural backend. MPS maps tensor operations to Apple's GPU infrastructure, but the exact model and shapes still require hardware qualification. [S11]

Keep model construction/loading on CPU where needed for initialization, then move the actual model and registered buffers to MPS. Freeze parameters and use evaluation/inference mode. CPU loading and explicit color/resize preprocessing do not constitute CPU neural inference. Maintain a written list of intentional CPU work and any scoped compatibility adapters.

Release verification MUST include a complete real-model fixture with all foundation weights, automatic CPU fallback disabled, device/dtype checks, finite output, alpha validation and a Metal/MPS trace of actual neural work. Parameter placement, `is_available()`, Activity Monitor alone or a matrix multiplication are not sufficient. Store model-load and model-inference outcomes separately.

If an operation fails, identify the exact operator, shape and dtype. Fix a narrowly defined compatible path and test its math. Do not globally monkeypatch Torch, replace the model, enable blanket CPU fallback or suppress the exception to make the workflow appear successful.

### 13.2 Precision and profile policy

Float32 is the initial reference path. A float16/bfloat16 or fused-kernel optimization must have separate finite-output, matte/foreground accuracy, memory and throughput qualification. Runtime choice is determined by a validated profile, not an untested guess based on chip branding.

Separate these dimensions in implementation even if the UI is simple:

| Dimension | Rule |
| --- | --- |
| Processing mode | Single Frame or actual Temporal. |
| Spatial resolution | Requested native resolution by default; explicit preview/proxy mode when chosen. |
| Precision | Locked validated profile, generally hidden from normal UI. |
| Temporal context | Hardware-qualified window/carry profile, with clear creative tradeoff. |
| Internal chunking | May change automatically if it preserves the algorithm and numerical contract. |

Automatic memory adaptation may reduce equivalent execution-batch/chunk sizes. It may not silently turn Temporal into Single Frame, halve final spatial resolution, change precision or substitute the original frame. A lower-quality retry must never return success for an unchanged native-resolution/quality OFX request. It is allowed only when the host requested that proxy scale, or a saved render-affecting preview setting changes through a permitted host action and invalidates the host cache. A label or worker-only cache key is insufficient. If neither condition is available, fail the request and offer the explicit validated lower profile. A final native render that cannot fit must fail with an actionable message.

Do not use arbitrary spatial tiling as a generic OOM fix: the model's global/contextual operations make that a different inference problem. Tiled execution requires its own algorithm and quality work and is not the default path.

### 13.3 Memory accounting

Measure model tensors, driver allocations, CPU frame copies, intermediate features, host-held images and persistent cache separately. Use MPS allocation/driver/recommended-working-set statistics and macOS memory-pressure information; neither physical RAM nor a recommended GPU working set guarantees what is free while Resolve is running. Keep allocator safety limits enabled. [S12]

Bound work queues and CPU/GPU staging. Release temporary tensors after each job/chunk. Avoid keeping full-resolution image copies in the C++ client, Python request, model preparation and output cache longer than required. Do not run a large number of parallel model instances to pursue throughput on unified memory.

On OOM, release the failed job, clear only unoccupied allocations when useful, and perform at most one approved same-quality retry. If it fails, report which resolution/mode exceeded the qualified profile. Verify a subsequent smaller request can succeed without relaunching Resolve.

### 13.4 Measurements and usability budgets

Record cold worker startup, model loading, first actual inference, subsequent **distinct-frame** inference, temporal analysis per frame, cached rendering and peak memory with Resolve open. Report dimensions, precision and temporal context with every timing. A cache hit must never be reported as model inference speed.

Set engineering responsiveness targets: bounded scan/descriptor work with no model load; prompt cancellation of a waiting host render; responsive health reporting while inference runs; no indefinite UI waits. Calibrate exact startup/inference timeouts from real measurements, then lock defaults. Do not promise real-time playback or a particular fps before measuring it.

## 14. Cache and disk behavior

Use a per-user RAM cache and bounded on-disk analysis/result cache. Cache **straight foreground plus alpha**, with explicit color/precision metadata, before inexpensive view/association operations. Preserve float32/HDR values by default; lossy cache quantization needs separate qualification.

### 14.1 Cache keys

Every persistent key includes the model and foundation asset fingerprints, adapter/math version, precision/profile, color transform, actual input pixels or proven content identity, relevant hints and their timing/quality, geometry/proxy scale, processing settings and temporal dependency/checkpoint identity. Separate host timeline coordinates from content identity so retimes do not accidentally reuse the wrong frame.

Use a versioned binary payload plus checked metadata, dimensions, byte count and checksum. Write through temporary files and atomically promote completed entries. Treat truncation, checksum mismatch and unknown formats as cache misses. Cache files are data; never deserialize executable Python objects from user-writable cache storage.

### 14.2 Capacity and cleanup

Estimate required temporary and final storage before shot analysis using measured data sizes; do not assume green-screen data compresses by a fixed ratio. Give a useful insufficient-space message before consuming the volume. Choose a conservative automatic cache budget and reserve free space for Resolve and macOS. A starting default of up to 50 GiB, constrained by actual free space, may be tuned in qualification rather than hardcoded as a guarantee.

The normal user does not need to choose a directory. Advanced Manager settings may select another volume and cache limit for long shots. A disconnected selected volume must produce a clear recovery choice, not silently write into a different mount-point directory on the internal drive.

Evict least-recently-used completed unpinned entries. Active analysis/result readers hold leases so cleanup cannot remove in-use data. Preserve a completed shot only within the configured budget or explicit user pin. Cleaning the cache must not delete model assets, source footage, Resolve project files or unrelated caches. A full disk during a write leaves existing valid cache entries usable.

## 15. User interface specification

Use Resolve's native OFX controls. Keep normal controls concise and use familiar filmmaking language. Technical process paths, raw JSON, dependency versions and GPU allocator knobs belong in Details/Manager.

### 15.1 Default effect panel

| Group | Control | Default and behavior |
| --- | --- | --- |
| Status | One human-readable status line | Preparing engine, Keying, Ready on Apple GPU, or an actionable failure. Live counts such as Analyzing 24/120 appear only through the verified supported refresh/progress mechanism. |
| Key | Output | Keyed RGBA; options Matte, Straight Foreground and Original preserve existing enum IDs. |
| Key | Processing | Single Frame initially; Temporal activates the real analysis path. No fake/offline-disabled promise. |
| Key | Analyze Shot / Cancel | Available when supported, with clear range/progress. Reuses valid analysis; does not ask technical setup questions. |
| Refine | Hint source | None; optional connected matte or legacy Source Alpha. |
| Refine | Hint confidence | Enabled only when a hint is used. Default 0.75 for a rough matte may be introduced through explicit versioned defaults; preserve existing saved 0.95 values. |
| Refine | Extra Green Despill | 0.0; explicitly additional green-only correction. |
| Advanced | Input encoding | sRGB, Linear Rec.709, Rec.709 Gamma 2.4; explanatory tooltips and tested presets. |
| Advanced | Analysis range/profile | Safe defaults from the shot and measured machine profile; avoid exposing unsupported windows. |
| Advanced | Details / Open Manager | Opens native maintenance UI through a permitted user action. |

Do not add a redundant screen-color selector when the model does not consume it. Do not name a hint-confidence slider Quality. Optional future matte black/white, shrink/grow and softness controls must be neutral by default and must preserve straight foreground when changing alpha; they are not mandatory for the first installer.

### 15.2 Preview behavior

The viewer must clearly distinguish Single Frame and Temporal processing. Proxy/preview resolution is explicitly identified; cached low-resolution previews cannot satisfy native final-render requests. Keep UI layout stable while statuses change, with long technical details moved into a details view.

Do not automatically modify the user's timeline, source clip, Resolve project color management or export settings. Provide a tested Fusion example and clear placement guidance instead. Opening an existing project must not trigger destructive migration or a surprise full-shot reanalysis until needed/authorized by its processing mode.

### 15.3 Optional Manager application

Use a native macOS application with simple sections:

- **Overview:** installed version, Apple GPU, model integrity, real inference check and supported host/machine profile.
- **Verify:** run manifest checks and a small real-model test; show per-step results and observed duration.
- **Storage:** runtime/models/cache sizes, cache location/limit, Clear Cache and Release GPU Memory when safe.
- **Diagnostics:** concise error description and Export Diagnostics; exported logs remain local and redact unnecessary personal paths.
- **Maintenance:** Repair, installed/previous version information, rollback entry and Uninstall.
- **About:** attribution and bundled dependency notices.

The Manager must not be a requirement for every Resolve session. No login screen, online activation, account selection or mandatory network check. Do not embed a browser-based dashboard merely to manage a local worker.

### 15.4 Error messages

| Code | User-facing meaning and next action |
| --- | --- |
| CK-INSTALL-MISSING | Installation is incomplete. Open Manager → Repair using the offline installer. |
| CK-ASSET-INTEGRITY | A required model file failed verification. Repair the installed model set. |
| CK-ARCH | This build requires Resolve and the runtime to run natively on Apple Silicon. |
| CK-GPU-UNAVAILABLE | The installed runtime cannot use the Apple GPU; show the observed OS/runtime details in Details. |
| CK-GPU-OP | A specific GPU operation failed. Save diagnostics; do not silently use CPU. |
| CK-MEMORY | The requested native-resolution/profile cannot fit the measured available memory; offer a named explicit alternative. |
| CK-CACHE-SPACE | There is not enough space for the selected analysis range; show estimated need and available space. |
| CK-ANALYSIS-STALE | Source, hints or settings changed; the temporal result needs reanalysis. |
| CK-HOST-TEMPORAL | This host/context cannot provide the required temporal frames through the supported path. |
| CK-WORKER-FAILED | The engine stopped and bounded recovery did not succeed; Manager can verify/restart it. |
| CK-CANCELLED | Processing was canceled. No late result was used. |

Include the error code in diagnostics, not a wall of implementation detail in the viewer. Distinguish user cancellation from a failed model so it does not produce repeated alarming dialogs.

## 16. Signing and personal-use trust

Support a **Personal Local** build profile without requiring a paid Apple Developer account. Apply appropriate ad-hoc signatures to the native executable code and verify them. The package itself may be unsigned; do not describe it as ad-hoc-signed because its contained binaries have local signatures.

A separate **Developer ID** build profile MAY use existing authorized credentials to sign code with Developer ID Application, sign the package with Developer ID Installer, submit for notarization and staple the accepted ticket. Do not create an account, buy a membership or upload artifacts for notarization without the applicable authorization. Ad-hoc signing is not notarization and does not remove Gatekeeper's provenance-dependent checks. [S13]

Sign nested code in the correct dependency order, inside out, after staging/path fixes. Do not use `codesign --deep` as a blanket signing strategy. Apply only required entitlements to the appropriate executables; library code does not gain independent process permissions. Audit the Python/native extension layout intentionally. [S14]

Test the actual local package installation/load route on the primary Mac and record any normal macOS trust approval required. When transfer to the second Mac is available or claimed, separately test that actual transfer route; local success does not prove downloaded/transferred-artifact behavior. The second-Mac test is conditional as defined in section 3. Use the standard system approval flow when available; never disable Gatekeeper, alter Resolve's signature/entitlements or automatically strip quarantine recursively. The specification promises minimal application setup, not a way around operating-system approval.

Keep inference in the separate worker so Python/JIT/native-extension requirements do not require modifying Resolve's process permissions. If a signing/host-loading limitation remains, report it with the exact artifact and error rather than pretending the installer has passed.

## 17. Build automation and required deliverables

### 17.1 Build entry points

Codex must create a single documented developer entry point, for example:

```bash
bash scripts/release/build_personal_installer.sh --profile personal --verify
```

This is a command Codex must implement, not an existing command in the alpha. It should orchestrate source/asset verification, runtime assembly, native build, portable/native tests, staging, signing, package construction and artifact verification. It may use normal developer tools on the build Mac; it must not shift those requirements to the installed product.

Support resumable build stages and a verified build cache so a packaging retry does not redownload all models. If required publisher access is temporarily unavailable, report the exact artifact and retain completed verified work. Do not quietly substitute an unpinned asset.

### 17.2 Build stages

| Stage | Required output/gate |
| --- | --- |
| Inspect | Actual hardware/OS/Resolve inventory; baseline source/test status. |
| Resolve assets | Complete pinned sources, wheelhouse, Python distribution and verified model manifest. |
| Prove model | Actual model fixture succeeds on the target Mac GPU before a release package is called verified. |
| Assemble runtime | Isolated relocated runtime passes imports, native dependency audit and full model inference. |
| Build native | arm64 OFX, supervisor and Manager; valid bundle metadata and exports. |
| Verify behavior | Worker/OFX/color/temporal/cache tests plus actual host workflows. |
| Stage package | Correct ownership, permissions, immutable model/runtime directories and upgrade journal. |
| Sign/package | Personal or explicitly selected Developer ID profile; signature checks record actual identity/state. |
| Install and qualify | Offline clean-account install, first use, export, recovery and lifecycle tests using the package. |
| Finalize | Exact artifact checksums, qualification report, limitations and short user guide. |

Portable tests may run before every package, but a source-only test result cannot replace native/host qualification. A development package can be produced before every gate passes only with an unmistakable beta/unverified label and an accurate report. The final release flag must fail if a universal gate or a gate for an explicitly claimed support combination is missing. An unavailable or failed investigation target does not block the qualified baseline, but must remain excluded from support claims and documented with its actual result.

### 17.3 Delivered artifacts

| File/artifact | Purpose |
| --- | --- |
| `CorridorKeyMac-<version>-arm64-Offline.pkg` | Complete private installer, with runtime and models. |
| `CorridorKeyMac-Uninstall-<version>.pkg` or equivalent tested GUI workflow | Scoped authorized removal, with clear model-retention behavior. |
| Source tree and build scripts | Reproducible personal maintenance. |
| Runtime/model/install manifests and dependency notices | Exact contents and compatibility identity. |
| `qualification.json` and readable native test report | What actually passed on each machine and host version. |
| `release-checksums.txt` | Integrity checks for delivered artifacts. |
| `USER_GUIDE.md` | Install, apply, interpret input color, analyze a shot, export, repair and uninstall in concise nondeveloper terms. |
| `KNOWN_LIMITATIONS.md` | Only actual remaining constraints, qualified combinations and unsupported cases. |

The final user-facing answer must lead with the real installer path and actual test status. Do not deliver only a long explanation saying the user can compile it later.

## 18. Implementation map from the alpha

The following names are suggested module boundaries. Codex may refine them while preserving behavior and compatibility.

| Existing file | Required work |
| --- | --- |
| `CMakeLists.txt`, `cmake/Info.plist.in` | Add supervisor/native shared utility targets and package metadata; preserve arm64 bundle layout and exported entry points; include tests in release builds. |
| `src/ofx_plugin.cpp` | Automatic worker connection, safe parameter snapshot/generation handling, clean controls, actual status, optional hint clip, temporal declarations/actions, lifecycle and source-change handling. |
| `src/protocol.cpp`, `include/ckmac/protocol.hpp` | Versioned handshake/jobs/status/cancel; protected runtime discovery; separate transport from worker startup; bounded waits and structured errors. |
| `src/pixels.cpp`, `include/ckmac/pixels.hpp` | Retain orientation/stride/alpha correctness; expand proxy/full-RoD and host negotiation coverage. |
| New `src/worker_manager.*` | Installed-path discovery, same-user spawn, locks, leases, process recovery and shutdown. |
| New native Manager project | GUI maintenance and diagnostics, no mandatory editing-session dependency. |
| `worker/ckmac/backend.py` | Installed asset roots, qualified MPS compatibility, exact color contract, real fixture checks and measured profiles. |
| New `worker/ckmac/temporal.py` | Ordered recurrent context, windows/overlap/refinement, checkpoints and deterministic analysis. |
| `worker/ckmac/server.py` | Job scheduler, stable status, cancellation/generations, result leases, memory and idle policy; release compute locks before slow output transfer. |
| New `worker/ckmac/cache.py` | Persistent versioned cache, manifest/checksums, capacity, atomic promotion and corruption recovery. |
| `worker/ckmac/protocol.py` | Control schema/capabilities and binary payload bounds matching the C++ implementation. |
| `scripts/setup_macos.sh` and launch scripts | Retain as developer helpers if useful; remove them from the required end-user workflow. |
| New `scripts/release/` | Lock/download/stage/audit/sign/pkg/repair/uninstall pipeline. |
| `tests/` | Preserve existing tests; add real packaged-runtime, host and temporal correctness coverage. |

Do not blindly rewrite the working conversion/protocol code or delete the existing tests to achieve a new layout. Add focused tests for new risks. Record architecture decisions affecting signatures, host calls, model math or saved projects.

## 19. Ordered milestones for Codex

### M0 — Inspect and prove the hardware path

Record actual Mac/Resolve versions, inspect the baseline, fetch the pinned required assets and run a small real-model MPS inference. Establish reference images and output checks. Demonstrate the host frame-acquisition path needed for temporal analysis. Exit with genuine evidence or a precise reproducible blocker; do all unrelated build/packaging preparation that remains possible.

### M1 — Build a self-contained installed Single Frame beta

Assemble the private relocatable runtime, native OFX and automatic supervisor. Build an offline beta package. Install in a clean account, disable networking, move the checkout away and render a real image in Resolve. A manual worker or system Python dependency fails this milestone.

### M2 — Harden lifecycle and compositing

Complete automatic startup, multi-node sharing, bounded recovery, cancellation, geometry, colors, alpha, native-resolution results and dependency isolation. Confirm actual Deliver export and project reopen. Lock the compatible runtime/profile after testing.

### M3 — Implement real temporal analysis

Use the verified host acquisition path, actual upstream model stages and persistent generation-aware cache. Add full-sequence and first-frame hints with valid propagation. Compare sequential/reverse/random requests and restart/resume behavior. Test chunk boundaries, range boundaries, source edits and cuts. A temporal-looking UI with T=1 output does not satisfy M3.

### M4 — Complete maintenance and installation transactions

Finish native Manager, storage handling, verify/repair, upgrade journal, rollback and uninstall. Test corrupt/missing assets and interrupted writes. Verify no root inference process or permanent service is introduced.

### M5 — Qualify the actual package and release

Run the universal acceptance matrix on the available primary Mac, including clean offline installation and real Resolve rendering, and qualify additional hardware/resolution combinations when available. Measure performance/memory and the actual private signing behavior. Build/check the final artifact, record checksums and deliver the complete installer with an honest support report. A qualified primary release need not wait for an unavailable second Mac; required temporal behavior still must pass.

Do not end the task at M1 unless a documented external blocker prevents further required work. If a user-only action is needed for a mandatory gate (for example, an operating-system authorization on the primary Mac), complete all other work first and ask only for the concrete remaining action. Record optional unavailable hardware as unqualified rather than creating an unnecessary release blocker.

## 20. Acceptance matrix

All rows need a recorded applicability and result, with evidence for executed tests. **U** marks a universal release gate on the qualified primary combination; **C** marks a gate required for each corresponding support claim. **I** may be assigned to an unclaimed investigation target such as unavailable second hardware. A result can be Passed, Failed, Blocked or Not run; missing data is never implicitly Passed. A conditional row that remains unclaimed must record its limitation and actual status without failing the qualified baseline release. Required product features cannot be reclassified as investigations to evade completion. Hardware/host rows identify the exact machine and installed artifact hash. Mocks remain useful but cannot satisfy the corresponding real hardware rows.

| ID | Class | Scenario | Required result |
| --- | --- | --- | --- |
| QA-01 | U | Offline package inventory | All runtime/model assets present with verified size/hash; no first-run downloads. |
| QA-02 | U | Clean-account installation | Normal Installer flow succeeds without user Python/Homebrew/Git/Xcode. |
| QA-03 | U | First use offline | Applying the effect starts the worker and returns a genuine keyed frame without opening Manager. |
| QA-04 | U | Relocated/deleted checkout | Installed product still works; no developer-path dependency. |
| QA-05 | U | Conflicting Python environment | User Conda/PYTHONPATH/global packages do not alter the private runtime. |
| QA-06 | U | Native architecture | Plugin, Python and all native extensions load arm64; no Rosetta path is required. |
| QA-07 | U | Plugin discovery | Resolve scans and loads the actual installed bundle without starting the model during scanning. |
| QA-08 | U | Real MPS inference | All real models execute, fallback disabled, trace retained, finite meaningful outputs. |
| QA-09 | U | Readiness truth | Loaded-only state never appears as completed inference; cached self-check identity is correct. |
| QA-10 | U | Multiple nodes | Concurrent first use produces one compatible model worker and independent job/cancel ownership, including duplicated nodes with copied saved UUIDs. |
| QA-11 | U | Worker crash | Resolve survives; bounded restart or actionable failure; no silent source fallback. |
| QA-12 | U | Host crash/quit | Worker leases expire and GPU memory is released; no orphan forever. |
| QA-13 | U | Cancellation | Host wait cancels promptly; obsolete jobs/results are suppressed; another node remains usable. |
| QA-14 | U | Lifecycle | Add, duplicate, disable, delete, undo, close and reopen without stale pointers, leaks or hung tasks; editing/deleting one duplicate does not corrupt the other. |
| QA-15 | U | Geometry | Odd sizes, nonzero origins, proxy scales and stride variants preserve orientation and exact extent. |
| QA-16 | U | Color inputs | sRGB, linear Rec.709 and gamma 2.4 match the declared reference transformations. |
| QA-17 | U | S-Log3 workflow | Tested transform chain produces correct model input and preserves intended output interpretation. |
| QA-18 | U | Alpha association | Fine transparent edges composite correctly over black, white and saturated backgrounds; no double premultiplication. |
| QA-19 | U | HDR and negatives | Finite out-of-range RGB survives supported float paths; foundation clipping does not clip the main signal. |
| QA-20 | U | Hints | None, source alpha, full-sequence and first-frame temporal hints follow their semantics; qualify a separate matte clip where that host/context provides it. |
| QA-21 | U | True temporal algorithm | Ordered context, window blending and refinement agree with the declared reference; no matte-average substitute. |
| QA-22 | U | Random access | Sequential, reverse and shuffled requests return matching analyzed results. |
| QA-23 | U | Temporal boundaries | Window ends, first/last frames and cuts produce no state leakage or unintended seams. |
| QA-24 | U | Time mapping | Integer and 30000/1001 rates and nonzero starts have no off-by-one frame errors. |
| QA-25 | U | Source invalidation | Pixel/color/hint/range/model changes invalidate all affected outputs, including a later unchanged frame whose earlier recurrent dependency changed. |
| QA-26 | U | Preview/final cache | Render a lower-resolution/different-mode preview, then export without restarting Resolve; native final output uses its correct algorithm and resolution. |
| QA-27 | U | Cache corruption/full disk | Invalid/incomplete entries are ignored; existing valid data and source footage remain intact. |
| QA-28 | U | Memory pressure | OOM is bounded and recoverable; no disabled safety limits or silent final-quality reduction. |
| QA-29 | U | 1080p sequence | At least 60 representative consecutive frames key and export in both required modes with stable quality and bounded resource use. |
| QA-30 | C | UHD target | At least 24 consecutive UHD frames complete at every claimed native/profile combination; otherwise record the actual failure/unavailability and exclude that combination. |
| QA-31 | U | Final export | A real Resolve Deliver sequence preserves alignment, intended color and useful alpha in an appropriate supported output. |
| QA-32 | U | Frame-quality review | Hair, fine detail, motion blur, transparency, green/blue screens and imperfect lighting have inspected foreground/matte outputs. |
| QA-33 | U | Performance report | Cold/warm/distinct-frame/cache/temporal times and peak memory measured with Resolve open. |
| QA-34 | U | Read-only payload | Signed/runtime/model files are unchanged after inference and analysis; generated caches are user-local. |
| QA-35 | U | Upgrade | Previous saved project opens with stable parameter meanings and compatible worker/model set. |
| QA-36 | U | Interrupted activation | Backups precede replacement of every live component; journal/rollback produces a complete previous or new set, never a mixed partial installation. |
| QA-37 | U | Repair | Offline repair restores a deliberately corrupt/missing file; moved original installer is found through a GUI picker and verified; no Terminal package management. |
| QA-38 | U | Uninstall | Installed removal path works after original installer deletion; only product paths removed; model retention honored; other plugins/projects remain. |
| QA-39 | U | Signing/provenance | Primary local install/load route verified for the selected personal profile; transferred-package support is a separate conditional claim. |
| QA-40 | C | Second Mac | Equivalent package tests and actual transfer/install/load route recorded on the second Mac before claiming support; unavailable hardware is explicitly unqualified. |
| QA-41 | U | Host analysis cache | Reanalysis with unchanged visible settings advances the supported render revision; viewer and export consume the newly activated result. |
| QA-42 | U | Source changes during analysis | Upstream change during frame acquisition cancels the inconsistent generation; mixed-source results never activate. |
| QA-43 | U | Maintenance and workers | Idle/live workers are drained and stopped before affected files are removed; unsafe maintenance is blocked without broad process kills or partial deletion. |
| QA-44 | U | Installer destination | Unsupported user/alternate-volume targets are unavailable or rejected before changes; hooks cannot silently target the wrong volume. |
| QA-45 | U | Progress and host calls | Actual Resolve progress/cancel/refresh path is recorded and responsive; no background/timer suite calls or unsafe parameter changes. |

Use representative real footage with permission. If no such fixture is available, finish infrastructure work and request a short source clip/frame needed for the remaining visual/host gate. Generated checkerboards or fake backends alone cannot establish key quality. A same-version CPU or trusted upstream GPU reference on small fixtures may be used for QA; that does not authorize a CPU production fallback.

Define numerical tolerances before reviewing the comparison results, based on precision/reference choice. Report alpha/foreground errors and edge/crop comparisons where useful. Do not loosen thresholds merely to make a failed optimization pass, and do not promise a perfect matte on arbitrary footage.

## 21. Release evidence and completion report

The final report must contain:

1. Exact installer filename, byte size and SHA-256.
2. Signing profile and actual verification results; whether any standard macOS approval was needed.
3. Tested Mac model/chip/RAM, macOS, Resolve edition/version and artifact identity.
4. Runtime and model versions; measured proof of actual MPS inference.
5. A short description of the real Resolve test and exported output, with image/clip dimensions and frame counts.
6. Single-frame and temporal profile results, including visual inspection and random-access consistency.
7. Cold-start, inference, cached render and memory measurements, without mixing cache hits into model-speed figures.
8. Upgrade/repair/uninstall results and all remaining Failed/Blocked/Not run rows.
9. Concise install/use steps that do not ask the user to configure Python or launch a worker.

Never infer a successful native build from a Linux build, a successful Resolve render from a mock host, or a successful model from a smoke test that exercised only matrix multiplication. No status field, report or final response may imply more than the recorded evidence.

## 22. Codex execution prompt

Copy the following prompt into Codex on the Mac, with this specification and the initial source project available in the same workspace:

```text
Implement the complete personal-use CorridorKey Mac installer described in
docs/PERSONAL_INSTALLER_SPEC.md. Work from this existing CorridorKey Mac OFX
0.1.0-alpha.1 project. Read that specification, README.md and
docs/VALIDATION.md before changing implementation.

The owner's goal is a .pkg that installs and works in DaVinci Resolve with
minimal configuration. This is private personal use. Build a FULL OFFLINE
installer containing the native arm64 OFX plugin, a genuinely relocatable
private Python/PyTorch runtime, the pinned upstream code, all verified models
and a small native Manager for optional maintenance. At runtime the user must
not install Python, pip, Git, Homebrew or Xcode, download models, set paths,
open Terminal, register services or start a worker manually. Do not add
accounts, activation, payment or public distribution features.

Inspect the actual Mac and installed Resolve first. Preserve the audited
source/model/dependency pins unless a demonstrated compatibility issue
requires a documented, retested change. Run the ACTUAL CorridorKey model
and all foundation networks on Apple MPS. Disabled automatic CPU fallback,
successful model placement and a tiny matrix multiplication are not enough:
complete real-model inference, retain GPU evidence and inspect real output.
Do not fake a key, return the original frame on inference failure, or hide a
lower-quality final result.

First produce a clean installed Single Frame beta with automatic same-user
worker startup; then continue through the required temporal, reliability,
maintenance and native qualification milestones. Single Frame alone is an
intermediate build, not completion of the full 1.0 specification. Implement
actual upstream temporal stages with ordered recurrent context, overlap
handling and persistent generation-aware results. Prove the legal Resolve
frame-acquisition/progress/cancel path before building analysis around it.
Do not call OFX image/parameter suites from arbitrary background threads or
retain host image handles after their action returns.

Keep the correct signed-asinh color encoding, separate foundation proxy,
decoded straight foreground, clamped model alpha and exactly-once output
premultiplication. Preserve HDR/negative values and explicit input color
interpretation. Keep protocol/image bounds, source-change invalidation,
random-access correctness and cancellation robust. Avoid full model loads
during plugin scanning or one model process per node.

Package a pinned standalone arm64 interpreter; do not copy the developer
.venv and call it portable. Audit every native dependency and eliminate
checkout/Homebrew/user-Python paths. Fetch and SHA256-verify all model/runtime
assets at build time. Install immutable shared assets and separate private
user caches. Use one automatic compatible worker per user/runtime generation,
with bounded recovery and idle release. No permanent root inference daemon.

Create the offline .pkg using native package tools. Personal/local signatures
are acceptable when tested on the owner's machines; do not require a paid
Apple Developer account. Do not call ad-hoc signatures notarization or bypass
Gatekeeper. Use existing Developer ID credentials only if that optional
profile is selected and authorized. Retain notices. Implement tested scoped
repair, upgrade/rollback and uninstall.

Run the specification's acceptance matrix on the actual installed artifact:
clean-account installation with networking disabled, checkout moved away,
automatic first use, real Resolve Fusion keying/Merge and Deliver export,
temporal/random-access/alpha/color tests, cancellation, multi-node behavior,
worker crash, memory/disk failure, upgrade and uninstall. Measure actual
performance and memory. Preserve existing portable tests, but do not label
them as GPU or Resolve tests.

Qualify the available primary Mac at native 1080p with both required modes
and all universal gates. UHD, an unavailable second Mac and other host/OS
combinations are conditional support claims, not reasons to block an otherwise
qualified primary release. Record them honestly as unqualified when untested.
Do not waive required temporal behavior by narrowing the hardware matrix.

Continue autonomously through ordinary build and debugging work. Do not stop
at a scaffold, a compiling source tree, mock tests or a manual-launch bundle.
If a necessary physical Mac, Resolve session, real footage fixture, OS
authorization or other external resource is unavailable, complete everything
else and report the exact remaining gate without fabricating success. Ask
only for the concrete missing action/resource. Never overwrite production
Resolve projects or publish/upload footage or the private product.

Deliver the actual installable package and its SHA256, reproducible source,
locked manifests, native qualification evidence, short user guide, known
limitations and tested uninstall path. Clearly distinguish Passed, Failed,
Blocked and Not run. Your final answer must identify the real installer and
what genuinely ran on the Mac and in Resolve.
```

## 23. Sources and technical grounding

The product requirements and chosen architecture above are design decisions for this personal project. These references ground platform/model facts; they are not evidence that the future installer has passed its native tests. Consult the pinned code and locally installed SDK behavior when a current document and the actual target version differ.

- **S1 — CorridorKey source and model orchestration:** [Repository](https://github.com/nikopueringer/CorridorKey2.0), audited source revision in section 2; model, foundations, runtime, color and video modules inspected in the initial project work.
- **S2 — Model assets and third-party origins:** [CorridorKey model repository](https://huggingface.co/nikopueringer/CorridorKey2.0), [third-party notices](https://github.com/nikopueringer/CorridorKey2.0/blob/master/THIRD_PARTY_NOTICES.md). Preserve the pinned asset identities and included notices.
- **S3 — OpenFX packaging and Mac discovery:** [Packaging OFX Plug-ins](https://openfx.readthedocs.io/en/main/Reference/ofxPackaging.html).
- **S4 — Python environment portability:** [Python 3.12 venv documentation](https://docs.python.org/3.12/library/venv.html).
- **S5 — Standalone Python targets/layout:** [Python Build Standalone](https://github.com/astral-sh/python-build-standalone), [running distributions](https://gregoryszorc.com/docs/python-build-standalone/main/running.html).
- **S6 — Embedded nonstandard runtimes and read-only bundles:** [Apple bundle guidance](https://developer.apple.com/documentation/xcode/embedding-nonstandard-code-structures-in-a-bundle).
- **S7 — Installer packaging:** [Apple Packaging Mac software for distribution](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution). This project's private-use scope does not add a public-distribution requirement.
- **S8 — OFX image access/lifetime and temporal capabilities:** [Images and Clips](https://openfx.readthedocs.io/en/main/Reference/ofxImageClip.html).
- **S9 — OFX concurrency and safe host calls:** [Thread and Recursion Safety](https://openfx.readthedocs.io/en/main/Reference/ofxThreadSafety.html), [Parameter Suite](https://openfx.readthedocs.io/en/main/Reference/suites/ofxParametersSuiteReference.html).
- **S10 — OFX actions and dependencies:** [Image Effect Actions](https://openfx.readthedocs.io/en/main/Reference/ofxImageEffectActions.html).
- **S11 — Pinned PyTorch MPS backend:** [PyTorch 2.9 MPS](https://docs.pytorch.org/docs/2.9/notes/mps.html).
- **S12 — MPS memory/profiling facilities:** [PyTorch 2.9 torch.mps](https://docs.pytorch.org/docs/2.9/mps.html), [MPS environment variables](https://docs.pytorch.org/docs/2.9/mps_environment_variables.html).
- **S13 — Notarization and plugin trust:** [Apple notarization guidance](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution).
- **S14 — Native code signing order and entitlements:** [Creating distribution-signed code for macOS](https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac/).

The initial source bundle remains an experimental implementation. This specification is the execution contract for producing and proving the installed personal-use product.
