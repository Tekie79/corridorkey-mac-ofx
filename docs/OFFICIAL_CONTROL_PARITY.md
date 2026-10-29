# CorridorKey2.0 hp beta — control audit

The requested production-facing effect label is **CorridorKey2.0 hp beta**.
The existing OFX identifier and bundle path stay stable so saved personal projects
remain connected. The official `com.corridordigital.corridorkey2` effect is separate
and is never replaced by this installer.

The audit used the locally installed official 2.0.0.161 OFX node's control
metadata, the [official panel reference](https://help.corridorkey.com/docs/panel/),
and the [public model source](https://github.com/nikopueringer/CorridorKey2.0)
at the specification's pinned revision. This repository does not contain the
exact official native 2.0.0.161 UI implementation. Proprietary binaries/assets
were inspected as a reference and were not copied into the personal package.

| Official control family | Personal implementation | Qualification scope |
| --- | --- | --- |
| Input is Linear | Linked to explicit sRGB / Linear Rec.709 Input Encoding; Gamma 2.4 remains available | Color conversion tests; native checks still required for the new UI |
| Internal Resolution | Full, Two Thirds, Half, Quarter; linear-light resampling and full-canvas output | Geometry, HDR and transfer tests; real profile comparisons pending |
| Reuse captured frames | Reuses content-verified staged payloads; upstream source/hint pixels are still revalidated | Deliberately stricter than the official documented stale-capture workflow |
| Time Awareness | Saved Single Frame / Temporal selection and linked checkbox; real continuous RVM, stage-one windows, tapered intermediate blending and stage two | Direct 4/2 reference comparisons passed; installed revised host test pending |
| Time Awareness amount | Window 1–48 with half-window stride | A visible request is not a claim that all windows fit or are qualified |
| GPU Memory Limit | Auto / 50–90% of Metal's recommended working set; Auto = 80% | Uses the MPS allocator ceiling, not NVIDIA VRAM heuristics |
| Low GPU Memory | Smaller equivalent MLP, attention-query and attention-window chunks | Requires native numerical comparison before being qualified |
| Alpha hint enable/source | None/legacy Source Alpha, explicit Source Alpha, connected Hint alpha or luminance | Source/hint alignment is checked; opaque camera alpha is not auto-enabled |
| Hint Frames | All Frames or one reference frame with temporal propagation | First-frame propagation is required; later-reference variant needs additional tests |
| Reference Frame / Set Current | Empty = shot start; integer frame = reset; Set Current uses the current host time | Later references run independent ordered passes outward in both directions |
| External / Internal Hint Strength | Independent external confidence and carried neural-hint confidence | Existing saved 0.95 values are retained; new external default 0.75 |
| Despill Color | Actual Auto estimate, Green, Blue, Picked | Post operation; does not pretend the neural model has a screen-color input |
| Freeze Auto Color | Last rendered background estimate is copied into Picked | Requires a completed keyed render before freezing |
| Despill Method / Amount | Average, Double Limit, Neutral; zero neutral | Green/blue reference math tested; representative native visual checks pending |
| Output | Premultiplied, Matte, Straight FG, Original with existing enum IDs | Native 0.9.1 single-frame Fusion/Deliver pixels matched exactly |
| Linearize Output | Decode foreground to linear before exactly-once host association | Transfer and alpha tests passed |
| Keep Original in Solid Areas | Original straight color above raw alpha 0.95, then despill | HDR/negative preservation tests passed |
| Alpha white point | Numeric matte white point, 1 neutral; straight foreground unchanged | Explicit personal behavior; exact 2.0.0.161 control semantics are not claimed |
| Render / Cancel | Saved Temporal selection/revision; legal host Render acquisition/progress; per-node cancellation | Revised native progress/cancel tests pending |
| Display rendered frames | Explicit saved Original / Premultiplied output selection | Documented personal mapping; never an error fallback |
| Render Folder / Choose / Open | Native Manager selects a per-user cache volume; shows measured storage and opens it | Applies across this user's nodes; unavailable-volume validation implemented |
| Delete this shot from Cache | Removes this live node's owned entries, retaining entries shared with other nodes; increments host revision | Persistent unowned older cache remains bounded by eviction; native sharing tests pending |
| Help / Support File | Installed local guide, notices and local diagnostics ZIP without media or uploads | Native Manager qualification pending |
| Updates | Matching offline-package picker and full protected validation | No online updater is added |

Status and memory readouts are intentionally truthful about their refresh path:
the OFX panel has stable guidance, synchronous host progress reports acquisition
and analysis waits, and the Manager reports live engine facts. No timer or worker
thread calls OFX suites. There is no fabricated memory-fit estimate.

Commercial license, activation, payment and public account controls are excluded
by the owner's personal offline product request. No official support service is
represented as supporting this independent personal build.

The release report, rather than this implementation map, determines what actually
passed on the exact installed artifact. Unfinished rows remain unqualified.
