# Start here: CorridorKey Mac installer handoff

This handoff contains the original experimental OFX source project and the detailed specification for Codex to build a complete personal-use Mac installer. **It is not an installer or a claim that native Mac/Resolve validation has already passed.**

## Use with Codex on the Mac

1. Extract this archive and open the `corridorkey-mac-ofx` directory as the Codex workspace.
2. Read `docs/PERSONAL_INSTALLER_SPEC.md` for the complete requirements and acceptance matrix.
3. Give Codex the prompt in `CODEX_PROMPT.md`. It directs Codex to inspect the actual Mac, implement the product, build the offline `.pkg`, and validate it in the installed Resolve version.

The expected result is `CorridorKeyMac-<version>-arm64-Offline.pkg`, containing the native OFX plugin, isolated arm64 runtime, real models and optional maintenance Manager. Ordinary use must not require Python setup, manual model downloads, a terminal worker or a socket path.

## Which instructions govern implementation?

`docs/PERSONAL_INSTALLER_SPEC.md` is the execution contract for this requested product. It supersedes the alpha README's manual end-user setup and worker-launch workflow. The existing README and validation record describe the starting alpha and remain useful engineering references.

A clean installed Single Frame beta is the first milestone. The final 1.0 requires actual temporal processing, real MPS inference, and real Resolve/Fusion/Deliver qualification. A qualified primary Mac at native 1080p is the required baseline. UHD, a second Mac and other host versions are supported only after their corresponding tests pass.

## Exact baseline and contents

The source files in the original `0.1.0-alpha.1` archive are unchanged in this handoff. This archive adds only the specification, this guide, the Codex prompt and a handoff integrity manifest.

Original archive: `CorridorKeyMac_OFX_0.1.0-alpha.1_source.zip`  
SHA-256: `b94ed0823aebb4aee207ead544288d6854760be4c7c827b777f2339c56def9e6`

The original `SOURCE_SHA256.json` describes the historical alpha. `HANDOFF_SHA256.json` records every file in this handoff except that manifest itself. Upstream model weights, private runtime binaries and a compiled Mac installer are not included; Codex must fetch pinned assets at build time and include them in the final offline installer.

Keep the original notices. This is for the owner's private personal use; accounts, payment, activation and a public distribution service are outside scope.
