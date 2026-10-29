# Remaining physical Mac checks

This checklist does not record a pass. The installer remains a personal beta until
actual evidence closes the remaining universal gates and restart requirement.
The exact acceptance matrix is in NATIVE_QUALIFICATION.md.

The developer account has completed actual MPS/Fusion/Deliver, crash recovery,
source-change safety, repair and both installed uninstall paths. Those tests do
not substitute for a clean account or networking disabled for the whole Mac.

1. Save other work. Create a **Standard** test user in macOS System Settings →
   Users & Groups. Enter any new password locally; do not send it to an agent.
2. Make the delivered offline installer and a short authorized green-screen clip
   accessible to that account, for example through a local shared folder. Keep
   the original footage in place. The 0.9.7 package SHA-256 is
   `f58245db7b45ce9ead793732c7e05f12d97c9c9a6e6681c744437b040ff07e86`.
3. Disable Wi-Fi, unplug Ethernet and disconnect VPN/network adapters locally.
   Leave networking disabled through installation, first key and test export.
4. Log into the Standard account. Do not install Python, pip, Homebrew, Git,
   developer tools, a model cache or the build checkout there.
5. Open the offline package in normal Installer. Approve its administrator
   authorization locally. Record the successful Installer screen and time.
6. Open Resolve Studio. Use a separate test project. Follow chapters 02–04 of
   `CorridorKey2.0-hp-beta-User-Book.html`: explicitly resize the keyer's input to
   1920×1080, add **CorridorKey2.0 hp beta**, choose sRGB when appropriate,
   Single Frame, Full, Premultiplied. Do not open Manager before the first key.
7. Let first-use preparation and a real frame finish. Inspect the removed backing
   and useful alpha. Export a short EXR RGBA float32 test with Export Alpha.
   Save a screenshot and the exported test in a clearly named temporary folder.
8. After that first key, open **CorridorKey Mac Manager**, click GPU status, and
   save the diagnostic text or screenshot. It must report MPS, float32, a passed
   real-model fixture and completed actual user/network work. Verify installed
   files and create a local Support File if needed. No report is uploaded.
9. Save the test project. Restart the Mac locally. Reopen the saved test with
   networking still disabled and request a new, previously unprocessed frame.
   Confirm automatic restart and a correct key without a Terminal worker.
10. Preserve the Installer, network-state, first-key/export, GPU diagnostic and
    post-restart evidence. Restore networking when ready and resume this Codex
    task so the evidence can be checked against QA-02, QA-03 and DONE-08. A generic
    “done” response alone is not treated as proof of all three checks.

The ten-minute automatic idle shutdown is a separate QA-12 observation. Restarting
or manually releasing an engine does not count as an idle-expiry test. UHD, the
unavailable second Mac, other host versions and transferred-package Gatekeeper
routes remain outside the support claim.
