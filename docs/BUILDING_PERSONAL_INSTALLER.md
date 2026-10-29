# Developer rebuild and qualification

These instructions are for maintaining the source. The installed product does
not require Python, Git, developer tools, model downloads, or a shell worker.

Build natively on an Apple Silicon Mac with Command Line Tools, Git, a developer
Python 3, and sufficient storage for the asset cache, staging, expanded packages,
and rollback copies. The first build needs publisher access; subsequent builds
reuse verified assets. Do not substitute a developer virtual environment for the
locked standalone runtime.

From the source root:

```sh
bash scripts/release/build_personal_installer.sh --profile personal --verify
```

The release helpers acquire the pinned source revisions, standalone CPython,
hashed arm64 wheels, and publisher models. The lock files are in
`scripts/release/requirements.lock` and `scripts/release/model-lock.json`.
The standalone archive identity is recorded in `scripts/release/common.py`.
The small pinned utils3d wheel is retained in `scripts/release/vendor-wheels`.
Native dependencies are audited, normalized where necessary, signed inside out,
and verified. Generated runtime/model/install manifests go into `dist`.

The source build ID hashes implementation and release-helper files. Preserve the
exact source snapshot associated with a candidate. Do not attribute later source
fixes or older native tests to a different installer hash.

The package uses native `pkgbuild` and `productbuild`. The latest compression
profile explicitly targets macOS 14.0. Its installer stages components outside
the live installation, verifies them, drains compatible user engines, writes a
durable transaction journal, then activates the complete generation. Root code
performs filesystem maintenance only; it never imports or runs neural models.

Verify the final archive before installation:

```sh
python3 scripts/release/verify_package.py \
  dist/CorridorKeyMac-0.9.4-beta.1-arm64-Offline.pkg \
  --output .build/evidence/package-0.9.4-verified.json
```

Use normal macOS Installer and authorization. Never bypass trust protections or
alter Resolve's signature. All native tests must use separate qualification
projects and authorized local fixtures. Preserve exact artifact identity, hardware,
host version, measurements, errors, and visual observations. Tests of portable
code or relocated developer runtimes are not installed-product acceptance.

The native transaction test executable exercises the production recovery routines
against private filesystem fixtures. It is not installed and cannot be used to
redirect the production helper to arbitrary paths.

After recording the specification's matrix in `.build/qualification-events.json`,
generate the report with `python3 scripts/release/report.py`. Keep every unexecuted
gate explicit. The final command below promotes the unchanged existing artifact;
it does not rebuild it. It refuses incomplete, reclassified, artifact-mismatched,
or changed-evidence gates:

```sh
bash scripts/release/build_personal_installer.sh --profile personal --final
```

The Personal Local profile uses ad-hoc code signatures and an unsigned package.
It is not notarization. Only tested local or transferred installation routes may
be claimed in the qualification report.
