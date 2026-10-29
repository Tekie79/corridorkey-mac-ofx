# Native Mac completion and acceptance

The remaining gate is real hardware. Portable source tests cannot replace a native Mach-O build, real MPS model inference, or Resolve host validation.

## Ordered native checks

1. Record Mac model, chip, unified memory, macOS version, native Python version, Resolve edition/version, and display/working color configuration. Ensure Python and the plugin are arm64, not Rosetta.
2. Read the publisher license. Run `bash scripts/setup_macos.sh`. Keep the audited source/model revisions; record the resulting installed dependency list. Do not silently upgrade everything when one operation fails.
3. Run `bash scripts/start_worker.sh`, query `bash scripts/worker_status.sh`, and capture the model-load result. Model placement on MPS is only the loading gate.
4. Export a representative sRGB frame with green/blue screen, fine hair, motion blur, foreground detail and uneven illumination. Run the smoke command from README at width 512. Inspect the actual foreground and alpha; preserve worker errors if any.
5. If an operator fails, identify the exact operation, input shape, dtype and device. Make a narrow device-compatible change or explicit same-math CPU preprocessing step. Document it. Keep the neural network on MPS; do not claim a GPU port by enabling blanket CPU fallback. Do not fabricate a key as a substitute.
6. Repeat at 720p and 1080p. Only then attempt the user's native resolution, such as UHD. Record cold model-load time, first-frame time, later distinct-frame time, cache-hit time, process memory, and MPS allocated/driver memory. A repeated cached frame is not an inference speed measurement.
7. Run `bash scripts/build_macos.sh`; inspect `file` output, exported `OfxGetNumberOfPlugins` and `OfxGetPlugin`, bundle Info.plist, and ad-hoc signature. The script compiles arm64 and runs its portable tests. This is the first actual Mac build gate.
8. Close Resolve, install with `bash scripts/install_macos.sh`, start worker and reopen Resolve. Check discovery and load logs. Create a duplicate Fusion composition and apply the effect. Do not overwrite an existing production composition.
9. Verify source geometry, odd dimensions, full-resolution and proxy renders, source-alpha hint off/on, each color choice, each output view, foreground transparency over multiple backgrounds, and correct absence of double premultiplication.
10. Scrub forwards, backwards and to non-adjacent frames. Render a short sequence twice and compare the same frames. Change source pixels, hints and despill to prove stale cached frames do not persist. Cancel a render, then request a new one. Try multiple effect instances.
11. Stop the worker during a request and test a missing model path. Resolve must report an actionable error and remain usable; a failed key must not quietly render as success. Verify no client or model thread causes an unrecoverable host hang.
12. Render a short final sequence through Deliver and inspect alpha/color in an appropriate high-precision format. Test both free and Studio editions only if support for both is intended; do not infer one from the other.

Record pass/fail evidence in `docs/NATIVE_RESULTS.md`, including exact versions, image dimensions and observed limits. Mark anything not run as unverified. Keep hardware tests representative and stop expanding them once the remaining concrete risk is resolved.

## Temporal follow-on

The current build is explicitly T=1. A full temporal implementation requires clip/frame-range identity, host frame dependency declarations, bidirectional neighboring-frame requests or an explicit analyze/cache job, deterministic chunk boundaries, overlap blending, recurrent reset at cuts, and cache invalidation when source/color/hint settings change. It must remain correct when Resolve requests frames out of order or concurrently.

Do not simply retain the last frame's recurrent state in an OFX render instance: preview scrubbing and final export may visit frames in different orders. The native model and single-frame integration should pass before adding clip analysis.

## Prompt for Codex on the Mac

```text
Open this CorridorKey Mac OFX source project and finish its native Apple Silicon
validation. Read README.md, LICENSE.md and docs/VALIDATION.md before changing code.
The user wants a local DaVinci Resolve OFX plugin that uses the Mac GPU. This is
an experimental source alpha, not a previously verified installable plugin.

Run the ordered checks in docs/MAC_HANDOFF.md. Inspect this Mac and the available
Resolve version. Keep the pinned upstream/model revisions. Use actual CorridorKey
weights and MPS inference. Start at a small real frame, then increase resolution.
If MPS rejects an operation, capture the traceback and fix that exact compatible
path; do not enable blanket CPU fallback, remove validation, or substitute a
conventional keyer. Preserve the model's signed-asinh color contract, correct
alpha, same-user local transport and explicit failure behavior.

Build the arm64 OFX bundle and verify its exports, Info.plist and local signature.
After Resolve is closed, install only this custom bundle; retain any previous
custom version. Validate inside a duplicate Fusion composition, including actual
renders, cancellation, random-access frames, alpha and color. Record real model
and host outcomes, timing and memory in docs/NATIVE_RESULTS.md. Report precisely
what passed and what remains unverified. Do not label mocked tests as Mac GPU
tests. Do not change production projects, publish, upload footage, or distribute
a competing bundled product. Temporal processing remains a separate phase;
do not expose a control that promises it until it has been implemented and tested.
```
