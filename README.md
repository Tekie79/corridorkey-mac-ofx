> **Current installed-product work:** Read [USER_GUIDE.md](USER_GUIDE.md), the
> [illustrated offline user book](dist/CorridorKey2.0-hp-beta-User-Book.html), and
> [the exact-artifact acceptance report](dist/NATIVE_QUALIFICATION.md). The alpha
> manual setup instructions below are a historical baseline, not the installer
> workflow. The current personal beta remains unqualified while required gates
> are incomplete.

# CorridorKey Mac OFX — experimental source project

**Version 0.1.0-alpha.1 · Apple Silicon target · source delivery, not an installable Mac binary**

This project connects a native OpenFX effect to the real CorridorKey 2.0 model through a local PyTorch MPS worker. The intended host is DaVinci Resolve on an M-series Mac. Model inference targets the Apple GPU through Metal Performance Shaders; image transport and explicit color conversions use the CPU.

The portable C++ code and Python contracts are tested on Linux. **Actual CorridorKey model inference on MPS, a macOS bundle build, loading in Resolve, and visual matte quality have not been tested in this environment.** Do not treat this source alpha as production certified or equivalent to the official plugin.

## An official Mac plugin already exists

As checked on October 27, 2026, Corridor's [manual](https://help.corridorkey.com/docs/manual/) lists Apple Silicon, macOS 14+, and Resolve via OpenFX. Its [troubleshooting page](https://help.corridorkey.com/docs/troubleshooting/) explicitly says the Mac implementation runs on the Apple Silicon GPU. The [store](https://corridorkey.com/) provides the official product. Use that route for the vendor-supported implementation; this project is for a custom development workflow.

The GitHub repository's NVIDIA/CUDA instructions describe the supplied Python runtime. They do not establish that Apple's GPU cannot execute the model. Conversely, the official Mac product's existence does not prove that this independent MPS adapter has passed its required tests.

## What is implemented

| Component | Behavior |
| --- | --- |
| Native OFX front end | Float RGBA Source/Output, filter/general contexts, full-frame request, image bounds and row-stride handling, clear host errors |
| Actual model adapter | Loads upstream CorridorKey and its three foundation models from separately downloaded publisher files; moves model parameters and buffers to MPS |
| Color handling | Explicit sRGB, scene-linear Rec.709, or Rec.709 gamma 2.4 input; correct signed-asinh model encoding and foreground decoding; negative and HDR RGB are retained |
| Alpha | Predicted alpha is clamped, not sigmoid transformed; final keyed output is premultiplied once |
| Controls | Input encoding, source-alpha hint, hint quality, extra green despill, keyed RGBA/matte/foreground/original display, worker socket |
| Local worker | Persistent model, private Unix socket, serialized inference, bounded RAM cache, live health query, no image uploads |
| Failure behavior | Unavailable GPU, unsupported operations, missing weights, malformed images, and model errors fail explicitly; no substitute chroma key or automatic CPU model fallback |
| Build/setup | Pinned upstream/model/SDK revisions, Apple Silicon setup, arm64 CMake bundle, ad-hoc local signing, backed-up installation of this custom plugin |

## Current boundaries

- **One-frame inference only (T=1).** No overlapping Hann windows, clip-wide temporal analysis, recurrent carry across render calls, or first-frame hint propagation. Random-access renders cannot contaminate one another through hidden state, but temporal stability can be lower than CorridorKey's full video mode.
- **The Mac GPU path is implemented but unverified with the full model.** Unsupported MPS operators must be fixed and measured on a Mac; the integration does not silently route the neural network to CPU.
- **The OFX image buffers are CPU buffers.** This build deliberately does not advertise direct OFX Metal-buffer rendering. GPU inference happens in the separate worker. It is not zero-copy or GPU-only end to end.
- **Float32 inference is the initial target.** It can use substantially more unified memory than half-precision CUDA inference. NVIDIA VRAM tables do not establish memory use or speed on Apple Silicon.
- **No real-time or 4K performance claim.** Start with a small real source frame and increase resolution after successful inference and visual inspection. Protocol limits (8192 per dimension, 33,554,432 pixels) are safety limits, not validated inference capacities.
- **No automatic Resolve color-space detection.** The plugin expects Rec.709/sRGB primaries and the selected transfer function. Log, DaVinci Wide Gamut, ACES, PQ and HLG need deliberate transforms around it.
- **Extra Green Despill is green-only.** The learned foreground prediction also performs its own unmixing. The optional extra correction is not an automatic green/blue selector.
- The worker starts manually in this alpha. A canceled host request stops waiting; a model operation already executing can finish in the worker. Restart the worker after a model-load failure or dependency change.
- No Developer ID signature, notarization, universal Intel binary, installer package, or automatic updater is supplied.

## Build and try on a Mac

Use native Apple Silicon Python 3.11 or 3.12, macOS 14 or newer, Git, and Apple's command-line developer tools. PyTorch 2.9.1 / torchvision 0.24.1 match the upstream tested pair; MPS compatibility still needs the real-model check below. Keep this extracted directory at a stable path because the worker uses its `.venv` and `.deps` folders.

### 1. Set up dependencies and publisher models

Read `LICENSE.md` and the upstream notices first. Setup downloads dependencies and about 5 GB of model assets. Files come from the publishers; the source archive does not contain their model weights or a repackaged CorridorKey distribution.

```bash
cd /path/to/corridorkey-mac-ofx
bash scripts/setup_macos.sh
```

If command-line tools are missing, run `xcode-select --install`, complete Apple's installer, and rerun setup. Install Python 3.11/3.12 through your usual trusted method if needed. You can select a native interpreter with `CKMAC_PYTHON=/absolute/path/to/python3.12 bash scripts/setup_macos.sh`.

### 2. Start the GPU worker and inspect it

In one Terminal window:

```bash
bash scripts/start_worker.sh
```

Keep that window open. In another:

```bash
cd /path/to/corridorkey-mac-ofx
bash scripts/worker_status.sh
```

Wait for `state: ready`, `backend.loaded: true`, and `backend.device: mps`. These mean the model loaded on MPS. **They do not mean an actual frame has passed inference.** If loading fails, read the worker error; fix it before trying Resolve. Ctrl-C stops the worker.

### 3. Run a real-image smoke test before opening Resolve

Use an 8-bit RGB or RGBA sRGB PNG/JPEG exported from representative footage. The command resizes to width 512 by default for the first hardware test and refuses to overwrite an output directory.

```bash
PYTHONPATH=worker .venv/bin/python -m ckmac.client smoke \
  /absolute/path/to/greenscreen-frame.png \
  --output /absolute/path/to/new-smoke-output
```

The result contains a straight floating-point RGBA `.npy`, a cutout PNG preview, a matte PNG preview, and timing metadata. The PNGs are clipped 8-bit previews, not HDR masters. Inspect hair, fine detail, motion blur and spill. Check worker status again: `successful_frames` must increase. A small-frame success does not establish full-resolution capacity. Use `--max-width 0` for native dimensions only after smaller tests work.

### 4. Build and install the native OFX bundle

```bash
bash scripts/build_macos.sh
bash scripts/install_macos.sh
```

Build runs C++ and Python tests, creates `build/CorridorKeyMac.ofx.bundle`, and signs it ad hoc for local development. Installation uses `sudo` to copy that bundle to `/Library/OFX/Plugins`. Quit Resolve first. An existing custom bundle at that exact path is retained with a timestamped backup; the official CorridorKey plugin is not targeted.

Ad-hoc signing is not notarization and does not establish host compatibility. If macOS refuses a locally built bundle, inspect the signature and host log through the normal development workflow. The scripts do not disable Gatekeeper or strip quarantine recursively.

### 5. Validate inside Resolve

Start the worker, reopen Resolve, and search for **CorridorKey Mac (Experimental)** in the Fusion page's OpenFX tools. First test a duplicate short composition with a known image and simple merge over a contrasting background. Place the keyer after the required input color transform, connect its output to the Merge foreground, and send the composite to MediaOut.

If Resolve does not discover the plugin, inspect the host's OFX loading log and the built architecture before changing plugin logic. Use `docs/MAC_HANDOFF.md` for the required native checks.

## Color and compositing

Select the encoding of the image arriving at this node, not the camera's original recording label. The scene-linear option means linear gamma with Rec.709/sRGB primaries. Gamma 2.4 is a display power function, not the Rec.709 camera OETF. Transform Sony S-Log3/S-Gamut3.Cine or another log/wide-gamut input before this node unless Resolve has already performed the required conversion.

The worker converts the declared transfer function to linear RGB, then to the model's signed-asinh representation. Foundation networks receive a separate SDR proxy. The predicted foreground is decoded back to linear and then to the chosen input encoding. For compositing in linear light, feed scene-linear Rec.709 and retain linear values through the Merge.

Keyed RGBA is premultiplied. Matte, Straight Foreground, and Original are opaque inspection outputs (alpha 1 inside the source image). Original is an explicit preview mode that can operate without a worker; it is not a fallback for failed inference. Preserve straight foreground data when changing alpha downstream, and avoid double premultiplication.

Source Alpha Hint is opt-in. An opaque camera clip generally has alpha 1 everywhere, which is not a useful subject mask. A useful hint must line up with the actual frame. If an upstream operation has already discarded RGB under zero alpha, the plugin cannot reconstruct those missing source pixels merely by unpremultiplying.

## Source layout

| Path | Responsibility |
| --- | --- |
| `src/ofx_plugin.cpp` | OFX descriptors, parameters, lifecycle and render actions |
| `src/protocol.cpp`, `include/ckmac/protocol.hpp` | Native socket client and bounded wire format |
| `src/pixels.cpp`, `include/ckmac/pixels.hpp` | Buffer/orientation/alpha conversions |
| `worker/ckmac/backend.py` | Real upstream model loading, MPS placement and inference |
| `worker/ckmac/server.py` | Persistent private worker, cache, serialization, health |
| `worker/ckmac/client.py` | Status and real-image smoke test |
| `scripts/` | Setup, build, local install, diagnostics and worker launch |
| `tests/` | Portable contracts, local transport and mock-host verification |
| `docs/VALIDATION.md` | Exact verified/unverified status |
| `docs/MAC_HANDOFF.md` | Native completion steps and Codex prompt |

## Reproducibility

| Source | Pinned revision |
| --- | --- |
| [CorridorKey 2.0 code](https://github.com/nikopueringer/CorridorKey2.0) | `485f5e9ab759ead6138cc990776184b59d6ea971` |
| [CorridorKey model](https://huggingface.co/nikopueringer/CorridorKey2.0) | `cf44a8db3f024bb49fd59daa408848ccf05f7477` |
| [ASF OpenFX](https://github.com/AcademySoftwareFoundation/openfx) | `c3f1c2dcf4f51762b794c4fc21181b4a501be1bf` |

The upstream downloader pins its three foundation model sources. Critical Python packages are pinned in setup; remaining dependencies follow upstream constraints and are recorded in `installed-requirements.txt` after installation. This is not a fully hashed cross-platform dependency lockfile.

## Relevant primary references

- [CorridorKey code and README](https://github.com/nikopueringer/CorridorKey2.0)
- [CorridorKey custom license](https://github.com/nikopueringer/CorridorKey2.0/blob/master/LICENSE)
- [Third-party notices](https://github.com/nikopueringer/CorridorKey2.0/blob/master/THIRD_PARTY_NOTICES.md)
- [Official Mac/OFX manual](https://help.corridorkey.com/docs/manual/)
- [Official Mac GPU statement](https://help.corridorkey.com/docs/troubleshooting/)
- [Official measured support matrix](https://help.corridorkey.com/docs/support-matrix/)
- [PyTorch MPS backend](https://docs.pytorch.org/docs/stable/notes/mps.html)
- [OpenFX rendering and Metal buffer contract](https://openfx.readthedocs.io/en/main/Reference/ofxRendering.html)
