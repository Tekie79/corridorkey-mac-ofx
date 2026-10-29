# Codex execution prompt

Open this project in Codex on the Mac. Use the following prompt. The complete execution contract is in `docs/PERSONAL_INSTALLER_SPEC.md`.

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
