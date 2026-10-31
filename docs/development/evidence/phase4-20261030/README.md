# Installed-artifact evidence

Read `../../PHASE4_INSTALLER_QUALIFICATION.md` and `qualification.json` first.
The matrix keeps archive audits, isolated QA installations and the blocked
unchanged production-path installation separate. Every observation belongs to
its recorded package SHA-256; source tests do not qualify an installed package.

`qa4-source-candidate.json` freezes the exact source inventory used by the final
QA.4 package. `build-qa4.log` records its Python and QA-native regression checks;
`personal-qa4-ctest.log` records the corresponding production-profile source
checks without deploying that profile. Earlier logs/results remain historical.

The QA.4 JSON records cover analysis, cache-only requests, independently checked
EXR samples/hashes, actual native buttons/pickers, Saver/Deliver, source-sized
alpha, external storage, reanalysis, cancellation, crash recovery, protected
asset failure, repair and maintenance. `qualify_installed_qa.py` is the narrower
installed-worker isolation harness; its outbound-IP denial is not a whole-Mac
offline or clean-account Resolve test. `write-final-matrix.py` regenerates the
matrix while the retained artifact metadata exists locally.

Earlier QA.2/QA.3 records that describe Source disconnection do not independently
prove it from `Source = None` assignment alone. QA.4 explicitly repeated those
checks using `ConnectInput('Source', None)` and `GetConnectedOutput()`.

The user requested deletion of this round's disposable footage, bakes, renders,
caches and test installation. Small measurements/hashes are retained here;
large model/package/EXR binaries and copied projects are not committed. The
cleanup record identifies what was removed and what was preserved. Product
receipt lists are filtered to this product; credentials/tokens are excluded.
