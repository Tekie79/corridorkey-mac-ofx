For the illustrated, bookmarked offline guide, open
[CorridorKey2.0 hp beta — User Book](CorridorKey2.0-hp-beta-User-Book.html).

Documentation update for installed 0.9.7: the real acquisition-edit safety test,
graphical repair and both installed removal workflows passed. The overall beta
still needs clean-account/offline first use and restart evidence. A new or changed
temporal shot requires matching captures in separate render requests; if prompted,
keep inputs stable and request another frame or repeat native pre-render. Do not
click Analyze Shot again merely to acknowledge verification. Safe source-identity
refresh retries can occur even with unchanged visible pixels.

# CorridorKey2.0 hp beta

This build is under native qualification. It is not a completed 1.0 release.
Read `dist/NATIVE_QUALIFICATION.md` before using it for important work.

## Install

Close DaVinci Resolve and Fusion. Double-click
`CorridorKeyMac-0.9.7-beta.1-arm64-Offline.pkg` and use the normal macOS
Installer authorization. Install on the startup volume. The package includes
the private arm64 runtime, publisher models, native plugin and optional Manager.
It does not need a Python installation, model download or manually launched worker.

The package is unsigned; its executable code uses local ad-hoc signatures.
That is not notarization. The actual local trust/load path remains a native
qualification gate. Use normal macOS approval if requested.

## Key a shot

Reopen Resolve and add **CorridorKey2.0 hp beta** in Fusion. The GPU engine starts
on the first keyed render. The first model load and real GPU self-check take
longer than later frames. Errors fail the render and do not replace the key
with the source image.

Choose the encoding arriving at this node: sRGB, scene-linear Rec.709 or
Rec.709 gamma 2.4. Transform S-Log3/wide-gamut footage into the selected
working representation before this node. The plugin does not detect camera
log or primaries automatically.

Connect Premultiplied to a Merge foreground and a background to its background
input. Premultiplied is associated exactly once. Matte and Straight FG
are opaque inspection views. Original is an explicit bypass.

Hints are optional. An ordinary camera clip's opaque alpha is not a useful
subject matte. Choose Source Alpha or the aligned Hint input explicitly, and use
Use Hint for comparisons. New nodes start at 0.75 external hint strength;
previously saved strengths retain their values. Internal Hint independently
controls trust in the neural hint carried between windows.

Internal Resolution offers Full, Two Thirds, Half and Quarter. Lower profiles
compute a smaller key and upscale to the original canvas. They are explicit
quality choices. The current beta rejects internal sizes above 2048×1152 because
native 4K failed numerical qualification. For a 3840×2160 canvas, Half explicitly
requests a 1920×1080 key. No failed Full render is automatically downgraded.

Additional Despill defaults to zero. Auto estimates the backing from source
pixels weighted by the predicted background matte; Green, Blue and Picked override
it. Average, Double Limit and Neutral are separate post operations. Freeze
Color copies the last rendered estimate into Picked. These controls do not alter
the neural model. Keep Solid Detail restores original RGB above raw
alpha 0.95, before despill. Linear Output returns linear RGB. White Point
remaps alpha and leaves straight RGB intact; 1 is neutral.

Single Frame processes each frame independently. For Temporal, set the inclusive
Shot Start and Shot End to one continuous shot, then select Temporal and click
Analyze Shot / Reanalyze. The next render acquires the images arriving at the node,
records a candidate capture. A new source set must be observed identically in a
separate Render action before analysis is submitted. If the message says
“Capture ready”, keep upstream settings unchanged and render again. Only a
verified capture is analyzed and returned as a keyed result. Resolve's progress/cancel surface
is used during the render. A negative Shot End uses the available source range;
explicitly shorten it when the input includes more than one shot or over 240 frames.

Temporal uses continuous RVM context, overlapping windows, blended intermediate
features and full selected-resolution refinement. The default window is four
frames with a two-frame stride. The Window slider requests 1–48 frames;
only tested profiles are qualified. A request that cannot fit fails rather than
reducing its window, precision or spatial resolution. Low GPU Memory reduces
equivalent execution chunks. GPU Memory Limit bounds the allocator against
Metal's recommended working set; Auto uses 80%, which is not a measurement of
currently free memory.
It revalidates every contributing input frame before returning the result.
Changing earlier input pixels invalidates later recurrent-dependent outputs too.
Reanalyze advances a saved render revision so Resolve can refresh its own cache.

With a useful hint, Hint Frames chooses All Frames or Single Frame and Propagate.
Reference Frame may be empty for the shot start, or an integer within the shot.
Set Current Frame as Reference captures the current integer frame. For a later
reference, independent ordered passes propagate outward in both directions;
this variant needs its own qualification. Show Result off explicitly
selects Original output, and on selects Premultiplied.
The optional Hint input can use its Alpha or Luminance and must match Source's
dimensions, origin and timing. None / Legacy Source Alpha preserves older saved
projects; the separate Use Source Alpha toggle remains available for compatibility.

Reuse Captures also reuses verified inputs across explicit reanalysis. Ordinary
playback always reuses unchanged captures. The complete causal source and hint
set is checked using host image identities, with content checks where identities
are absent. Analyze Shot selects Temporal and advances the saved revision. Cancel
stops this node's wait without terminating the shared engine.

## Faster editing and playback

Use **Half** or **Quarter** Internal Resolution while adjusting the key. These
are saved quality choices: switch back to **Full** before a native final render.
Changing the profile invalidates the corresponding output; a preview cannot
satisfy the Full request. Keep the shot range short and limited to one shot.

For smooth **Fusion viewer** playback, set the composition render range to the
shot, right-click the keyer node and choose **Cache to Disk**. Keep **Enable
Cache** checked and **Lock Cache**, **Lock Branch**, and **Use Network** unchecked.
Choose a writable local cache path ending in `DiskCache0000.raw`, then click
**Pre-render**. Let all frames finish before playing. The unlocked cache can be
invalidated by edits; do not lock it while changing the source or key settings.

For smooth **Edit/Color timeline** playback, choose **Playback → Render Cache → User**, then
right-click the timeline clip and set **Render Cache Fusion Output → On**.
Leave Resolve idle while it fills the cache. Play after the cache bar is blue.
Edits invalidate Resolve's affected cache and require it to fill again. The first
analysis still takes time; a cache hit is not new neural inference.

Resolve's playback cache is separate from this plugin's float32 result cache.
For float/HDR/alpha final qualification, leave **Use render cached images** off
in Deliver unless the selected Resolve cache format has itself been qualified
for the required precision and alpha. The plugin can reuse its own full-precision
results during that export.

The 0.9.6 performance work removes whole-shot pixel copies/uploads for unchanged
host image identities, repeated whole-shot checksum reads, and unnecessary
color conversions for alpha/detail-only controls. A bounded 512 MiB RAM LRU
supplements the disk cache. File replacement, truncation, corruption and source
changes still invalidate the affected results. See `docs/PERFORMANCE.md` for
measurements and their exact test-build scope. `PERFORMANCE.md` is installed
beside this guide and included in the release folder.

## Verify and repair

Open **CorridorKey2.0 hp beta Manager** in Applications (installed at
`/Applications/CorridorKey Mac Manager.app`). Verify checks the installed
inventory. GPU Status prepares the real model and reports its actual state;
model-loaded and completed-inference facts are separate. Repair lets you choose
the matching offline `.pkg` and checks its payload and installer logic before
opening Installer. Storage shows measured model/runtime/cache sizes. Choose Cache
selects an existing volume for this user's private cache and safely drains an idle
engine before switching. A disconnected volume causes an explicit error. Support
File creates local product diagnostics without footage or uploads. Keep your
original package for offline repair. Repair and
upgrade require Resolve and Fusion to be closed.

## Uninstall

In Manager, choose **Keep Models** or **Remove All**. These open the installed
scoped removal packages and request normal macOS authorization. Keep Models
retains shared model files; Remove All removes this product's model sets too.
Other OFX plugins, the official CorridorKey plugin, source footage and Resolve
projects are outside the removal paths. Current-user cache cleanup is separate.

Installed removal packages also live under
`/Library/Application Support/HarvestPictures/CorridorKeyMac/Maintenance/`.
They remain available after deleting the original downloaded installer.
Read QA-37 and QA-38 in the accompanying acceptance report for the actual
installed maintenance results.

## Illustrated offline user book

Open `CorridorKey2.0-hp-beta-User-Book.html` beside the installer for the full
step-by-step guide, chapter bookmarks and real Mac/Resolve screenshots.
