# Native qualification — personal beta

UNQUALIFIED PERSONAL BETA

**Exact installed artifact: 0.9.7-beta.1, build 0.9.7-b1.027347b5a7e5.**

41 of 43 universal acceptance gates currently pass. Real MPS, both 60-frame
1080p modes, native Fusion Merge/Deliver, 30000/1001 timing, source-edit safety,
crash recovery and cached playback ran on this Mac. Remaining rows below are
explicit; owner-account installation and per-process IP denial do not establish
clean-account or globally offline acceptance. A physical Mac reboot is also
outstanding for DONE-08. This remains a beta, with no fully qualified combination.

Full 1080p model inference remains offline (representative distinct frame 2.822 s).
Temporal analysis of 60 frames took 245.895 s. Actual unlocked Fusion disk-cache
playback measured 24.681 fps on the 25 fps loop. Cached playback is separate from
uncached inference; a component cache benchmark is not an end-to-end speedup.

The illustrated offline [user book](CorridorKey2.0-hp-beta-User-Book.html) has 12
bookmarked chapters and five embedded actual screenshots. Static anchors, PNGs,
JavaScript syntax and offline asset checks pass. Browser visual preview was
blocked by Browser Use policy; screenshots themselves were inspected. The HTML
and delivery Markdown are a later documentation revision; the source ZIP retains
the exact packaged build source and its original embedded documentation.

Installer: `CorridorKeyMac-0.9.7-beta.1-arm64-Offline.pkg`
Bytes: 4050857822
SHA-256: `f58245db7b45ce9ead793732c7e05f12d97c9c9a6e6681c744437b040ff07e86`

Primary: Apple M5 Pro MacBook Pro (20-core GPU, 48 GB), macOS 26.3.2 (25D2150), Resolve Studio 21.1.1 build 10.
No fully qualified release combination is claimed while universal gates remain incomplete.

| Gate | Class | Result | Evidence / limitation |
| --- | --- | --- | --- |
| QA-01: Offline package inventory | U | Passed | Final0.9.7 archive expanded and27117 records verified, including executable hooks and contained ad-hoc signatures. |
| QA-02: Clean-account installation | U | Blocked | Requires a clean standard account and local normal Installer authorization; unavailable in this session so far. |
| QA-03: First use offline | U | Blocked | Requires actual clean-account first use with whole-Mac networking disabled; per-process denial on0.9.6 is not this test. |
| QA-04: Relocated/deleted checkout | U | Passed | During a real native temporal request the worker was killed and the complete checkout renamed away. Automatic restart produced the correct frame while the checkout was absent. |
| QA-05: Conflicting Python environment | U | Passed | Production native supervisor launched the installed worker under poisoned PYTHONHOME/PYTHONPATH/Conda, requested fallback1 and online flags. Actual MPS inference succeeded; OS denied outbound IP. This is not the clean-account/global-offline gate. |
| QA-06: Native architecture | U | Passed | Actual installed273 native images: arm64, no external loader roots, deployment target14 or earlier. Actual native plugin/PyTorch execution. |
| QA-07: Plugin discovery | U | Passed | Fresh Resolve startup with no model worker during scan; installed plugin subsequently keys60 actual1080p frames. |
| QA-08: Real MPS inference | U | Passed | Actual installed MPS Single Frame and Temporal execution, float32, all foundation/stage network counters, no automatic CPU fallback; native Metal/MPSGraph trace. |
| QA-09: Readiness truth | U | Passed | Native startup was observed checking installation before Ready. Real hardware fixture, actual MPS network counters and completed user frames are separate from loaded state. |
| QA-10: Multiple nodes | U | Passed | Two simultaneous production C++ supervisor clients and an actual copied Resolve keyer shared one cold worker. Clearing one owner retained the other result; native cancellation and deletion preserved the other copied node. |
| QA-11: Worker crash | U | Passed | Verified worker killed during actual Full1080 temporal inference; Resolve survived and automatically restarted one worker. The same render completed correctly within26.446s. |
| QA-12: Host crash/quit | U | Passed | Actual Resolve quit after fresh native inference. Unmodified installed worker exited after600.700s idle, socket removed and clean shutdown marker present; no signal, release, fake clock or health polling. |
| QA-13: Cancellation | U | Passed | Actual host AbortRender ended the wait in0.040s with no obsolete output, while the other copied node remained usable. An executing GPU operation may finish later. |
| QA-14: Lifecycle | U | Passed | Actual add/copy, disable/re-enable, deletion/Undo, saved-project close/reopen all completed; pixel comparisons exact and other copied node retained. |
| QA-15: Geometry | U | Passed | Actual odd385x217 native MPS/Fusion output and preview/final geometry; arm64 production pixel tests cover nonzero origins, negative stride, orientation and bounds. Synthetic layouts are unit evidence, not invented host layouts. |
| QA-16: Color inputs | U | Passed | Actual native sRGB, scene-linear709 and gamma2.4 fixtures agree within1e-4 RGBA; largest measured error5.543e-6. |
| QA-17: S-Log3 workflow | U | Passed | Actual native synthetic SLog3 transfer removal followed by linear709 keying matches declared reference within1e-4. Unchanged Rec709 primaries; no untested camera-gamut claim. |
| QA-18: Alpha association | U | Passed | Actual float Fusion Merge over black, white and saturated red agrees with exactly-once premultiplication within1.02e-6. |
| QA-19: HDR and negatives | U | Passed | Actual native float path retains finite RGB from-0.00746 to18.1633. |
| QA-20: Hints | U | Passed | 72 real odd-size temporal native outputs cover None, source alpha all/reference0/reference4, separate Hint Alpha and Luma. Reference semantics and nonreference edit invalidation checked. |
| QA-21: True temporal algorithm | U | Passed | Actual ordered continuous RVM/Hann8/4/stage2 agrees with retained pinned upstream CPU golden within8.56e-6; a separate blue cut reference agrees within1.36e-5. Full1080 temporal60 also completed. |
| QA-22: Random access | U | Passed | Actual shuffled/reverse requests59,41,3,30,0 exactly match the sequential analyzed output. |
| QA-23: Temporal boundaries | U | Passed | Actual first/last/window boundaries and independent green/blue shots across a cut preserve stamped source identity and upstream temporal reference; no shared recurrence across keyers. |
| QA-24: Time mapping | U | Passed | Actual25fps60frames and30000/1001 nonzero timeline/source starts preserve frame stamps, order and frame counts in EXR and ProRes4444alpha Deliver. |
| QA-25: Source invalidation | U | Passed | Native early-frame edit changes a later unchanged-input temporal result. Color/range/hint edits invalidate expected outputs; nonreference hints are ignored correctly. Model/profile cache identity covered by production tests. |
| QA-26: Preview/final cache | U | Passed | Quarter preview then Full native1080 Deliver in the same Resolve session: exported frames5/6 exactly match proper Full output. |
| QA-27: Cache corruption/full disk | U | Passed | Actual installed production cache under isolated5GB APFS low-space, warm-cache extent corruption and incomplete writer checks; valid entry preserved. |
| QA-28: Memory pressure | U | Passed | Real MPS OOM using installed production Engine in isolated QA process is bounded, returns Ready/active0, then identical512float32 inference succeeds. |
| QA-29: 1080p sequence | U | Passed | Both required modes completed60 consecutive Full1920x1080 native float RGBA frames and actual Deliver sequences with exact equality; real MPS telemetry retained. |
| QA-30: UHD target | C | Not run | Native UHD excluded. Prior direct4K numerical-quality failure; this candidate explicitly refuses internal sizes above2048x1152. |
| QA-31: Final export | U | Passed | Actual Resolve Deliver60frame float RGBA EXRs in each mode exactly match native Saver; actual12frame30000/1001 ProRes4444alpha export has correct timing/count. |
| QA-32: Frame-quality review | U | Passed | Fresh native1080 green/blue/glass source/matte/composites visually inspected. Hair, green clothing, propeller blur and partial glass alpha retained; refraction/backing color may need manual despill. |
| QA-33: Performance report | U | Passed | Cold verification/model/fixture, actual distinct-frame, cached sequence, temporal60 timing and sampled memory recorded with Resolve open. Native unlocked Fusion cache playback24.681fps at25fps; offline inference is not real-time. |
| QA-34: Read-only payload | U | Passed | After genuine fresh Full1080 MPS inference following final reinstall, actual Manager Verify confirms all27113 installed files unchanged; generated captures/results are in user-local cache. |
| QA-35: Upgrade | U | Passed | Saved historical project opens with stable creative values after normal full-package upgrade; all60 Single Frame outputs exactly match the prior native result. |
| QA-36: Interrupted activation | U | Passed | Actual root filesystem interrupted Maintenance transaction recovered through normal repair Installer. Durable complete component backup preceded the missing-file change. All-component partial activation/repeated recovery states also pass unchanged production arm64 transaction tests; not a claimed power-loss test. |
| QA-37: Repair | U | Passed | Actual Manager detected a missing file, located and verified the complete matching offline package moved into a Unicode/spaces folder, and normal Installer repaired it. All27113 installed files verify. |
| QA-38: Uninstall | U | Passed | Both actual installed Manager removal paths completed through normal Installer with the original full-package path absent. Keep Models retained models; Remove All removed them. Official plugin/app, original DMG and3 footage hashes unchanged. Final reinstall completed and genuine fresh native MPS output was verified; existing production projects are still listed and the saved QA project opens. |
| QA-39: Signing/provenance | U | Passed | Exact Personal Local package installed normally; contained ad-hoc signatures verify and actual Resolve load/inference succeeds. Not notarized; transfer route unclaimed. |
| QA-40: Second Mac | C | Blocked | Second Mac is not available in this session; no support claim. |
| QA-41: Host analysis cache | U | Passed | Native unchanged-settings explicit reanalysis advanced revision with identical inputs and new output identities. Viewer/Saver/Deliver consumed the new result; safe source-UID refresh retry is documented. |
| QA-42: Source changes during analysis | U | Passed | Actual upstream edit after2 full4K captures with active_jobs0: inconsistent capture never submitted. Stable retry all12 inputs exactly match independent current-source Savers; keyed output exactly matches worker. |
| QA-43: Maintenance and workers | U | Passed | Actual Manager refused release during real temporal GPU work. Root fixture safely drained idle worker84000 before changing Maintenance; normal repair/removals ran with host closed, with no broad process kill. Installed preflight refuses a live host before mutation. |
| QA-44: Installer destination | U | Passed | Final archive only permits system startup volume. Actual unchanged hook rejects an alternate target before mutation. |
| QA-45: Progress and host calls | U | Passed | Actual Render acquisition/progress, source-edit rejection, reanalysis and prompt host AbortRender recorded. Source and host-suite tests enforce action-scoped callbacks; no background host image retention. |

## Durable native evidence

Every acceptance row has exact-artifact evidence paths and SHA-256 hashes in
`qualification.json`. Compact historical development/reference records retain
their original build identity under `evidence/development/`; they do not silently
qualify this installer. Heavy test exports and caches were removed as requested.
The render-file inventory preserves their hashes before cleanup.

The measured compatibility boundary and performance are in `KNOWN_LIMITATIONS.md`
and `PERFORMANCE.md`. The physical Mac handoff steps are in
`COMPLETE_NATIVE_QUALIFICATION.md`.

See `USER_GUIDE.md`, `KNOWN_LIMITATIONS.md`, source references and the original specification. Each evidence file preserves its actual scope.
