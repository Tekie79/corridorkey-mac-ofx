# Source references used in the personal installer work

The canonical model and orchestration source is the owner's identified official repository:
https://github.com/nikopueringer/CorridorKey2.0

The implementation keeps the specification's audited revision
`485f5e9ab759ead6138cc990776184b59d6ea971`. Model tensors use the separately
pinned `cf44a8db3f024bb49fd59daa408848ccf05f7477` Hugging Face snapshot.
`corridorkey/model.py`, `runtime.py`, `foundations.py`, `stage1.py`, `stage2.py`
and `video_io.py` are the algorithm reference. No newer revision was silently substituted.

The supplied `CorridorKey2_v2.0.0.161_macOS_AppleSilicon.dmg` was mounted
read-only and its package expanded into `.build/official-package-reference`.
It contains compiled native application/plugin binaries, a model-installation
program, notices, module-download manifests and a private Python runtime.
The model source is not present as `.py` files in that package's initial
`Resources/models` directory. These binaries were inspected as a reference;
they were not copied into this project's offline installer. The disk-image
contents do not establish access to the exact native v2 plugin's source.

An additional public native OFX/runtime repository was fetched for host-API
source comparison:
https://github.com/alexandremendoncaalvaro/CorridorKey-Runtime
at `e632fa5f9110b38cc102ed32d7f566210898e901`.
Its existing final-matte temporal smoothing is not the upstream v2 neural
temporal algorithm and cannot satisfy this specification's temporal gate.
Its license was read. No source from that repository has been copied into
the current implementation. It does not replace the canonical repository.

Reference applications are not qualification of this independent plugin.
