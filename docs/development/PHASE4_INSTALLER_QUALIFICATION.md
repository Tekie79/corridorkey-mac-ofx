# CorridorKey Mac installer qualification

**Release decision: unqualified personal beta.** The current isolated candidate is
`dist/0.9.8-qa.4/CorridorKeyMac-0.9.8-qa.4-arm64-Offline.pkg`, build
`0.9.8-qa4.f1f98dd88eee`, bundle 9085, SHA-256
`49dc3c677eedf487003ebd5c0b1698b927cbbc048a982bb851ad4d54440143a7`.
It is 4,050,850,088 bytes. Mandatory broader release gates remain incomplete;
QA results do not qualify the production-path package.

Testing used Mac17,8 / Apple M5 Pro / 48 GiB, macOS 26.3.2 (25D2150), Resolve
Studio 21.1.2 build 10. The user selected side-by-side QA on this Mac. Only
`CorridorKey_Phase4_Installed_QA_20261030` and disposable media/storage were edited.
The starting feature commit was `df25f4a21e7dbb240b20817d0c0c76b5cea72c4e`.
The installation/discovery corrections are committed in
`c0bf9ea3320c697ea45940462ba0b7c2ea963a31`; picker corrections are committed in
`58e6c19`. Artifact-bound evidence is retained with the final feature-branch
commit. No main merge is authorized.

## Artifact boundaries

| Candidate | Build | SHA-256 | Observed result |
|---|---|---|---|
| Original beta.1 | `0.9.8-b1.32baa56c3837` | `2249be84fb0152d2bbb7608a3492d357bcdde7bd3f91c97458b6570dee4d57cd` | Archive passed; exact installation blocked. |
| QA.1 | `0.9.8-qa1.9a72e0ba5e4b` | `92d8fd04ea9b1ec9c6989bc7fe22306909d806e088bbc0893b7cadbe1353d74c` | GUI install passed; Resolve discovery failed. |
| QA.2 | `0.9.8-qa2.bc3c1fd474fa` | `d530d3a14c8852f9a56d9e70c852ac37dfd985670b3f43975308dea1025b5c66` | Working installed upgrade baseline. |
| QA.3 | `0.9.8-qa3.efc225cfab3d` | `14cf95a53187e8eff815b13c5a0e5441b7e21295f900633f80e361c536ad39f6` | Full-shot native results; repeated host picker failure. Superseded. |
| QA.4 | `0.9.8-qa4.f1f98dd88eee` | `49dc3c677eedf487003ebd5c0b1698b927cbbc048a982bb851ad4d54440143a7` | Final tested QA candidate; results below. |

The original beta.1 remains byte-for-byte immutable. Its actual Manager payload
reports 0.9.4 / 9041 despite the 0.9.8 package version; new builds correct those
Info.plist fields. Archive audits verified 27,154 records in beta.1 and 27,155 in
each completed QA package, including executable policy and both code signatures.
QA.4 installed inventory verified all 27,151 root-owned/protected records.
All packages use ad-hoc contained-code signatures and unsigned installer packages.
Normal Installer succeeded; no security protection was disabled. The user supplied
normal macOS authorization for QA.3; the initial QA.3-to-QA.4 upgrade did not
display another authorization prompt. Subsequent maintenance/reinstall operations
required normal macOS authorization. The initial QA.4 upgrade's first observed
completion was 77.7 s after Install,
which includes the observation interval rather than an exact installer benchmark.

## Actual fixes and regression tests

The same C++/Objective-C++ and Python implementation selects a fixed production or
QA namespace. Installed Python derives its identity from its protected runtime
location, not user environment variables. QA has independent bundle/app IDs,
root, receipts, activation manifests, sockets/tokens, preferences, cache ownership,
logs and maintenance. A QA stage containing production paths is refused.

| Destination | Production | QA |
|---|---|---|
| Support root | `/Library/Application Support/HarvestPictures/CorridorKeyMac` | `/Library/Application Support/HarvestPictures/CorridorKeyMacQA` |
| OFX bundle | `CorridorKeyMac.ofx.bundle` | `CorridorKeyMacQA.ofx.bundle` |
| Manager | `/Applications/CorridorKey Mac Manager.app` | `/Applications/CorridorKey Mac QA Manager.app` |
| Domain | `org.harvestpictures.CorridorKeyMac` | `org.harvestpictures.CorridorKeyMac.QA` |
| Socket prefix | `/private/tmp/ckmac-<uid>` | `/private/tmp/ckmac-qa-<uid>` |
| External cache child | `CorridorKey-hp-Cache-<uid>` | `CorridorKey-QA-Cache-<uid>` |
| Maintenance scheme | `ckmachp` | `ckmachpqa` |

QA.1 exposed an actual discovery defect: its bundle was named CorridorKeyMacQA,
but its executable/Info.plist still named CorridorKeyMac.ofx. QA.2 fixes the
basename agreement and clears stale generated bundle contents before rebuilding.
Resolve retained the failed QA scan as disabled; only the QA checkbox was
re-enabled through normal Preferences > System > Video Plugins, then Resolve
restarted. Host scan XML and other plugin flags were not edited.

QA.3 later exposed disabled Choose/New Folder controls in repeated native host
pickers, including a local destination and after restarting Resolve. Earlier
successful picker observations remain valid narrower evidence. The same panel
outside Resolve allowed selection. QA.4 delegates bake/relink panels to a short-lived
mode of the fixed installed Manager executable, which owns its Cocoa event loop.
The caller validates a bounded version/profile/absolute UTF-8 path response or
explicit cancellation. No shell command or background host-suite callback is used.
Normal Manager now also has a working Quit menu/Cmd-Q. The installer guide uses
only its own profile's maintenance links; the obsolete literal-rewrite QA builder
refuses the new macro-based source rather than emitting an ambiguous plugin.

Build validation now requires all 35 locked model assets and all 39 locked wheels,
rejecting missing, changed, duplicate or extra assets. Source checks passed
**171 Python tests plus 6 subtests**, and **10/10 native CTest checks in each
profile**. New native picker regressions exercise selected/canceled paths, Unicode
and spaces, malformed/oversized responses, relative/NUL paths, and cross-profile
replies. These source/harness tests do not qualify an installed artifact.

## QA.4 native results

The representative original shot is 4096x2160 at 25 fps; source frames 30–89 map
to Fusion 0–59. A deliberate full-frame Resize supplies 1920x1080 neural input.
The original media SHA-256 is
`756191c3f2c996b97e7552d2ac388dfb5bad8606321476e5aee03c6c66fe5409`.
Storage tests use its byte-identical disposable copy.

- Normal QA.3-to-QA.4 GUI upgrade retained UUIDs, saved revision/generation,
  controls and baked paths. Normal Resolve scanning and baked reads started no
  worker. Source disconnection was explicitly checked with the native SDK's
  `ConnectInput`/`GetConnectedOutput`; ordinary `Source = None` assignment is not
  accepted as proof of disconnection in this harness.
- Genuine MPS float32 temporal analysis completed all 60 frames in **245.400 s**.
  All learned networks ran on MPS; CPU neural fallback was disabled. This is the
  continuous-RVM / Hann 4/2 / stage2 profile, not independent matte averaging.
- With baked playback disabled, **300 actual live requests** (forward, reverse,
  three shuffled passes) succeeded in **26.472 s**. Neural calls, analysis starts,
  stage writes, blob puts and bytes written all stayed at zero. All 121 blob/JSON
  records (3,981,327,814 bytes) retained inode, size, mtime and ctime. 59 requests
  reached the worker; 241 were host-cache hits. SQLite leases are separate.
- A deliberately flipped bit in temporary result 43 produced a failed native
  image and no model load/inference. The old bake still rendered; restoring exact
  bytes restored live cached rendering. No source/model/durable file was changed.
- Native Bake RGBA wrote 60 float RGBA EXRs, every decoded sample identical to
  completed analysis hashes. Finite foreground RGB ranged from **-0.0847671 to
  1.2587984**. Low-space destination refusal preserved the old bake and left no
  staging folder; native retry and New Folder succeeded.
- Native Bake Alpha with **Match Source**, Auto dimensions and half precision
  wrote all 60 **4096x2160 single-A EXRs**. Resolve SDK supplied original geometry;
  all samples exactly matched full-frame bilinear pixel-center resampling plus
  half conversion. This is **resampled 4K export, not 4K neural inference**.
- A native duplicate received a distinct saved UUID and reused the same generation
  without inference. First-owner auto-clean retained all 120 shared entries.
  Last-owner native Bake & Clean removed **60 captures + 60 results,
  3,981,318,720 bytes**. No frame blobs or active scratch remained. Durable versions
  remained intact. A fixture correction identifies pasted tools by stable names/IDs,
  since numeric SDK list indices reorder; it caused no inference or staged writes.
- With analysis cleared and worker released, native Fusion Saver exported 60 float
  RGBA frames with Source disconnected (reported 2.95 s). Deliver exported 60 float
  RGBA frames numbered 30–89, corresponding to Fusion 0–59 (reported 698 ms hot
  export, not a neural timing). All samples matched one premultiplication exactly.
- A native **4096x2160 alpha composite** at frame 23 exactly matched current
  original Source RGB multiplied once by the baked alpha. Both alpha and RGB
  maximum error were zero. It occupied the full source canvas; viewer zoom is
  separate from exported image extent.
- Fresh-session RGBA remained usable with Source disconnected and its disposable
  source volume detached. With the bake volume detached, both Alpha and RGBA failed
  without worker startup and kept their paths. Remount and media relink restored
  images. Native Relink canceled/retried successfully, and rejected an incomplete
  two-frame EXR candidate before activation; the prior bake remained usable.
- Native Use Baked Result off/on behaved correctly with Source disconnected.
  Actual Analyze with Source disconnected reported the source-fetch failure;
  the next baked request succeeded with no worker. Actual in-flight Cancel during
  learned-network work returned in **604 ms**, with no incomplete generation
  activated and the other node still usable. Ordinary retry retained revision 3.

The installed worker also passed kernel-enforced outbound-IP and checkout-read
denial with conflicting Python/Conda settings: cold load/inference **13.609 s**,
cache read **0.0344 s**, byte-identical cached results after restart with no model
loaded. Protected inventory/file set remained unchanged. The first harness attempt
inherited the denied checkout as CWD, so PyTorch's `os.getcwd()` import failed;
retry from a valid owned temporary CWD passed while explicit checkout reads still
failed. No installed-code workaround or network allowance was added. This test
starts the packaged launcher manually; it does not qualify Resolve automatic first
use, a clean account, reboot or globally offline operation.

## Recovery and maintenance completion

Edited-source completion, native worker-crash recovery and GUI repair passed on
QA.4. Both normal GUI uninstall modes and subsequent reinstall recovery checks
also passed, with artifact-specific records in the acceptance matrix.
QA.4 reanalysis kept revision 3, changed only source input 17, and recomputed
outputs 14–59 through temporal context. The new 60-frame float bake matched every
completed result hash; the prior bake remained unchanged. Native Saver frame 43
matched the new result exactly and differed from the old by a maximum 0.0200246.
Media relink reset this host's composition canvas to 4096x2160; the harness
explicitly restored HD before its HD pixel comparison. The source-sized alpha
comparison separately used the full original canvas.

Actual native Force Reanalyze advanced revision to 4. A controlled SIGKILL of only
the authenticated same-user QA worker left Resolve and both bakes usable. Native
Clear Temporary Analysis restarted a cache-only worker without model calls,
removed 60 captures (1,990,659,360 bytes), reported 60 absent results, and recovered
one abandoned 129,412,410-byte scratch job. No frame blobs or scratch remained.

QA.3 historical crash recovery removed 60 captures, 77 results and one abandoned
298,643,466-byte scratch job, with the previous bake surviving. It does not pass
QA.4's equivalent gate.

For the repair test, a normal root-authorized QA-only fixture moved the exact
C-RADIO configuration into a reversible QA transaction backup. Manager Verify
reported the missing asset. Native analysis failed with `CK-ASSET-INTEGRITY`,
zero neural calls and no model loaded; the previous RGBA bake remained usable.
Manager's actual Repair picker validated a relocated, byte-identical QA.4 package
before opening normal Installer. Repair restored the expected configuration hash,
verified all 27,151 protected records, and drained the failed worker. A subsequent
uncached native Single Frame render completed real MPS inference, followed by
successful Source-disconnected baked playback. No production component was moved.

The exact archive's preinstall hook also refused a running Resolve before
mutation with “Close DaVinci Resolve and Fusion, then retry. No host was stopped.”
A later actual GUI Remove All attempt also safely refused while Resolve was still
running, leaving the QA payload intact. The SDK had returned `Quit = True` without
the process exiting; normal Cmd-Q closed it. Final cleanup was retried only after
checking that the host process was gone.

Keep Models removed QA software and drained the loaded MPS worker/socket while
retaining all 35 verified model records. Reinstalling the exact QA.4 package
verified all 27,151 protected records and rendered the saved RGBA bake with Source
explicitly disconnected and no worker. Remove All then removed QA software and
models; reinstall again verified all records and the same saved bake, UUID and
revision 5. Manager Cmd-Q worked. Standard macOS package receipts and the empty
QA maintenance lock are normal remaining bookkeeping. Durable bake versions
remained verified until the user-authorized disposal after testing.

## Remaining release blockers and support limits

The unchanged production-path beta.1 installer cannot be installed here without
replacing production. Its installation, lifecycle, repair and uninstall remain
**Blocked** until an independent suitable Apple Silicon macOS/Resolve environment
is supplied. QA.1 failed discovery and QA.3 failed repeated picker selection;
neither is QA-qualified. QA.4 is not declared fully QA-qualified while mandatory
cases or broader universal release gates remain incomplete.

Clean-account/whole-Mac offline/reboot, actual interrupted privileged activation,
second Mac, full color/hint/time-mapping/cut/preview/final/geometry/memory/quality
fixture matrices and fresh Metal/physical-memory profiling remain incomplete.
Every broad gate is listed honestly in `evidence/phase4-20261030/qualification.json`;
narrow functional passes do not waive those gates or inherit earlier results.

When original source media was unavailable, Resolve still returned an image for
Alpha playback. Its contents were not accepted as verified original RGB. Missing
source-media detection for Alpha is therefore **unqualified**; it may receive a
host-cached/offline image. RGBA independence from missing source was verified.

Native internal canvases above 2048x1152 remain refused after earlier native-4K
quality failure. Half/Quarter are explicit smaller-key quality choices. Match
Source defaults to the original dimensions when verified; transformed/cropped/PAR
chains must provide verified alignment/dimensions rather than guessed geometry.
The experimental CorridorKey v2 MLX port remains pinned to
`74065491ebd2eddea494ab34c15a6d84d7415353`. Native 1080p/4K shape graphs/exporter
and full GPU/Fusion/Deliver quality/performance qualification remain separate.
MPS is still the default and no MLX assets were added to this package.

## Preservation and requested cleanup

Production's 27,113 protected records verified unchanged after QA installs/native
work. Final preservation checks and scoped removal are recorded in
`evidence/phase4-20261030/cleanup.json` and `production-final.json`. The user
requested removal of disposable test files/footage after testing. This round's
copied Resolve project was deleted; the 13 other project names were unchanged.
Both disposable volumes were unmounted. Copied media, all 542 test EXRs in ten
bake versions, native renders, sparse images, QA caches/preferences, expanded
payloads, QA build staging and superseded QA.1/2/3 offline packages were removed
after retaining small evidence. The original beta.1 and final QA.4 installers
remain available. Shared build dependencies, original footage, production
projects/installation and pre-existing durable bakes were preserved. Final QA
system removal is recorded separately; its authorization retry was still pending
when file cleanup finished.
