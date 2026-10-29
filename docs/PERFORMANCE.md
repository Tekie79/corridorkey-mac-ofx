# Performance work — personal beta

Measurements below were made on the owner's M5 Pro, 20-core GPU, 48 GB RAM,
macOS 26.3.2, Resolve Studio 21.1.1 build 10, using GS02 at a 1920×1080 node
canvas. Neural work remains float32 MPS with CPU model fallback disabled.

## Changes for 0.9.5 / 0.9.6

- Keep verified float images in a bounded 512 MiB RAM LRU.
- Verify immutable cache file contents once per file version. Device/inode,
  size, modification time and change time invalidate verification/RAM entries.
  A requested disk frame is still checksummed when read. The complete temporal
  output set must remain valid before any cached result is returned.
- Cache format 3 checksums the image header and pixels together. A corrupted
  extent cannot pass just because the total pixel count stayed unchanged.
  Older cache files are misses and are regenerated; source media is untouched.
- Reuse owned input content keys when OFX image identifiers, geometry, alpha
  association and applicable hint identifiers match. Check the entire causal
  set before and after temporal processing. Missing identifiers use content
  fingerprints. Missing/corrupt captures are recaptured from the host.
- Batch input-cache lookups, avoid rewriting unchanged captures on playback,
  and let Single Frame requests refer to checked captures without uploading
  their pixels again.
- Limit progress UI updates to 10 per second while preserving abort/generation
  polling, and avoid color transfer round trips for alpha/detail-only controls.
- Reject unsupported internal canvas sizes before uploading the selected shot.

No precision, resolution, temporal-window or algorithm downgrade is automatic.

## Recorded measurements

These are qualification-only overlays on the installed 0.9.4 runtime, not a
claim that an unchanged offline 0.9.5 artifact has passed qualification.

| Measurement | Observed |
| --- | --- |
| Worker temporal cache check/retrieval, 60 outputs, previous implementation | 750.9 ms median |
| Same cache data, new implementation | 12.7 ms median; 59.2× faster for this component |
| Native temporal analysis, 60 frames, default 4/2 context | 247.74 s |
| Native 60-frame float RGBA Deliver after analysis | 54.388 s |
| Prior temporal Deliver workflow | 533.532 s; included an additional analysis, so this is not an isolated cache-only comparison |
| 60-frame temporal output comparison | Exact RGBA equality, maximum error 0 |
| Warm distinct Single Frame, Full | 3.01 s for the recorded representative frame |
| Warm distinct Single Frame, Half | 0.827 s for the recorded representative frame |
| Warm distinct Single Frame, Quarter | 0.333 s for the recorded representative frame |
| Cached Full Single Frame Deliver, six frames | 1.185 s including host acquisition and EXR encoding |
| Fusion viewer, live temporal effect with model results already cached | 1.62 fps over a sampled interval; UI approximately 1.9 fps |
| Fusion viewer, same 60 frames after unlocked native Cache to Disk | 24.42 fps over 4.095 s, 100 frames including looping |
| Float RGBA Deliver from that native node cache, 60 frames | 1.679 s; exact equality to the live temporal output, maximum RGBA error 0 |

The cache microbenchmark excludes OFX acquisition, transport, display and
encoding. It must not be reported as end-to-end playback speed. The preview
profiles do less spatial work and must not be described as equivalent Full
results. Render timing dialogs can exclude work already completed by the
viewer; backend distinct-frame timings and network counters are retained
separately in `.build/evidence/performance-*-health.json`.

The native earlier-frame edit test changed only input frame 0 in a four-frame
shot. The requested frame 2 retained its exact input content identity, but all
temporal output identities changed and frame 2 was recomputed. Its output
changed by up to 0.0677 RGBA, confirming the earlier recurrent dependency was
respected. Cache corruption and replacement tests also exercise warm RAM hits.

## Editing workflow

Use explicit Half/Quarter for interactive adjustments. For the Fusion viewer,
set the render range to the shot, open the keyer node's native **Cache to Disk**
dialog, enable caching, and pre-render to a writable local `DiskCache0000.raw`
path. Leave **Lock Cache**, **Lock Branch** and **Use Network** off. The actual
60-frame test retained all float RGBA values and reached approximately the
25 fps project rate. Refill invalidated cache after editing.

For Edit/Color timeline playback, use Resolve's User
render cache with Fusion Output Cache On for the shot; allow the bar to become
blue before playback. This avoids the cost of calling a whole-shot temporal
effect for every display frame. Resolve's cache is separate from the plugin's
full-precision cache. Final float/HDR/alpha exports should not consume a
lower-precision Resolve cache unless that format has been qualified.

The native cache measurements above use performance overlay 2 on 0.9.4.
Exact final-package binding, native cache invalidation after edits, and the
remaining acceptance gates must be recorded before claiming a qualified release.
