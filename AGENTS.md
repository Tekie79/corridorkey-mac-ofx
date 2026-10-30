# Codex repository instructions — CorridorKey Mac OFX

This is a **personal-use Apple Silicon DaVinci Resolve OpenFX plugin** project. Preserve the user's original media, saved Resolve projects, prior durable bakes, installed production plugins, and the existing functional PyTorch/MPS implementation.

## Active implementation handoff

**Start with [docs/development/CODEX_NEXT_PHASE_MLX_CACHE_BAKE.md](docs/development/CODEX_NEXT_PHASE_MLX_CACHE_BAKE.md)** for the current P1/P2 regression fixes, cache/alpha bake workflow, MLX integration reference, and explicit Mac/Resolve release gates.

The correct **CorridorKey 2.0 MLX** implementation is https://github.com/peterteravskis/corridorkey-v2-mlx at pinned commit https://github.com/peterteravskis/corridorkey-v2-mlx/tree/74065491ebd2eddea494ab34c15a6d84d7415353. Its shape-specific graph/models, temporal behavior, licensing and benchmarks must be inspected and verified. Do not substitute https://github.com/nikopueringer/corridorkey-mlx, which targets the earlier CorridorKey architecture. Original model reference: https://github.com/nikopueringer/CorridorKey2.0.

## Working rules

- Continue the current **feature/mlx-cache-bake** branch unless explicitly instructed otherwise. **Never merge to main without approval.**
- Implement actual code and tests; do not stop after writing another plan. Report precisely what was changed versus what remains blocked.
- Never deploy/overwrite an installed plugin, delete footage, clean somebody else's cache, or discard existing baked EXRs without explicit authorization. Use isolated QA bundles and a copied Resolve project.
- Maintain backward compatibility of OFX plugin identifier and saved parameter IDs. Fix repeated cache invalidation without weakening upstream edit detection.
- Default to durable verified Alpha/RGBA EXR bake, then safe temporary-cache cleanup. A failed/canceled reanalysis must not strand the previous bake.
- Keep **MPS as default** until full-resolution MLX achieves recorded real Mac GPU, Fusion and Deliver qualification. No silent resize, CPU neural fallback, or fabricated speedup claims.
- Model/source retrieval belongs at **build time**, not the installed offline workflow. Honor the source and model licenses.
- Run Python tests and platform-appropriate native tests after changes. Qualify actual Resolve behavior and installed offline .pkg separately. Mark tests that cannot be run as **Blocked/Not run**, never as Passed.
- Include exact commit hashes, artifact SHA-256, observed GPU timings/quality, log evidence and outstanding limitations in the handoff.
