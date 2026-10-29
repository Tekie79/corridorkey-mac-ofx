# Validation record — 0.1.0-alpha.1

Date: October 27, 2026.

## Result

**Portable integration verification passed. Native macOS and real Apple GPU inference remain unverified.** This archive is source, not a tested Mac plugin release.

The available execution environment was Linux x86_64 with Python 3.12 and GNU C++. It had no macOS SDK, Apple GPU, or running DaVinci Resolve. Model weights were not downloaded here. The worker tests explicitly use fake inference only where necessary to isolate transport; they do not demonstrate real matting.

## Checks performed

| Check | Evidence | Result |
| --- | --- | --- |
| Upstream source inspection | CorridorKey commit `485f5e9ab759ead6138cc990776184b59d6ea971`; model, runtime, color, attention, foundations and RVM code reviewed | Passed source audit; hardware behavior not proven |
| Foundation compatibility inspection | Pinned NVIDIA C-RADIO Python/config source inspected without weights; device buffers and float32 configuration checked | No definite hardcoded CUDA blocker found on selected forward path |
| Native interface compile | Release C++ compilation against OpenFX `c3f1c2dcf4f51762b794c4fc21181b4a501be1bf` | Passed on Linux |
| Required exported entry points | `OfxGetNumberOfPlugins`, `OfxGetPlugin` present in compiled portable module | Passed on Linux |
| CTest | 3/3 suites: pixels, protocol, OFX host | Passed |
| Python tests | 92 tests and 6 subtests, including actual C++/Python transport round trips | Passed |
| Source syntax | All Python parsed; all shell launchers passed `bash -n` | Passed |
| Bundle metadata | Info.plist template parsed and expected executable verified | Passed template check; not a signed Mac bundle |

The temporary Linux `.ofx` module is **not included in the source archive** and must never be installed in Resolve for Mac.

## What the tests establish

### Color and backend contracts

The CPU-verifiable tests cover sRGB reference points, the distinction between gamma 2.4 and the Rec.709 camera curve, signed/HDR linear-to-asinh round trips, exact centered padding and crop, no-hint quality `-1`, explicit source-alpha hint behavior, direct alpha clamp without sigmoid, and invalid-input rejection. The backend refuses non-Apple systems and enabled automatic CPU model fallback.

These do not establish numerical agreement between full CUDA and MPS inference. Float32 MPS and upstream CUDA autocast need not produce bit-identical results.

### Native OFX code

An independent minimal test host invokes the actual exported plugin entry points. Tests exercise describe/create/clip preferences/full-frame regions, a keyed render with a mock worker, supported float components, explicit Original inspection, missing-worker failure, render cancellation, and image handle release. Pixel tests cover bottom-up host coordinates versus top-down model images, nonzero origins, negative/padded row strides, partial render windows, and unpremultiply/premultiply behavior.

This is stronger than merely compiling the headers, but it is still a mock host rather than DaVinci Resolve.

### Worker and wire protocol

Tests use actual local Unix sockets with an explicitly fake neural backend. They cover fragmented I/O, truncated requests, exact binary layout, bounds and flags, NaN/Inf rejection, model exceptions, malformed returned images, cache keys and byte limits, serialization, health availability, canceled partial requests, private directory checks, live/stale sockets and lock ownership.

The cross-language test invokes the compiled C++ `Client` against the actual Python `LocalServer`. It verifies pixel order, input encoding and hint/despill settings, values above 1, response data, and a propagated backend failure. The fake operation is deliberately simple (RGB multiplied by two, alpha 0.25) so it cannot be mistaken for real keying.

## Remaining native gates

| Gate | Status |
| --- | --- |
| Complete dependency installation on the user's Apple Silicon Mac | Not run |
| Publisher weights load into the real model on MPS | Not run |
| A real frame completes full model inference on MPS | Not run |
| Measured unified-memory budget and actual inference time | Not measured |
| Native arm64 Mach-O plugin build and ad-hoc signature | Not run |
| Resolve discovers and loads the bundle | Not run |
| Resolve Fusion rendering, random-access scrub and Deliver export | Not run |
| Fine detail, hair, motion blur, transparency, green/blue spill and color QA | Not run |
| Temporal inference | Not implemented |
| Developer ID signing, notarization and distribution installer | Not implemented |

Follow `MAC_HANDOFF.md` in this directory to complete those gates. A ready health status means the model loaded; use `full_model_inference_succeeded` and actual frame output to distinguish that from full model execution.

## Portable reproduction

With CMake, a compiler, NumPy, pytest and the audited OpenFX checkout installed:

```bash
cmake -S . -B build \
  -DOPENFX_SDK_ROOT=/absolute/path/to/openfx \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build --parallel
ctest --test-dir build --output-on-failure
PYTHONPATH=worker python3 -m pytest tests -q
```

The cross-language tests automatically locate `build/bridge_probe`. If using a different build directory, set `CKMAC_BRIDGE_PROBE=/absolute/path/to/bridge_probe`. They are explicitly skipped if that binary has not been built. Local socket access is required for the transport/host tests.
