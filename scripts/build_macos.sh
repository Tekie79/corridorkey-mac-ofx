#!/bin/bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "The distributable Mac bundle must be built on an Apple Silicon Mac." >&2
  exit 1
fi
build_cmake="$project_root/.venv/bin/cmake"
"$build_cmake" -S "$project_root" -B "$project_root/build" \
  -DOPENFX_SDK_ROOT="$project_root/.deps/openfx" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=14.0 -DBUILD_TESTING=ON
"$build_cmake" --build "$project_root/build" --parallel
"$project_root/.venv/bin/ctest" --test-dir "$project_root/build" --output-on-failure
PYTHONPATH="$project_root/worker" "$project_root/.venv/bin/python" -m pytest "$project_root/tests" -q
bundle="$project_root/build/CorridorKeyMac.ofx.bundle"
codesign --force --sign - "$bundle"
codesign --verify --verbose=2 "$bundle"
file "$bundle/Contents/MacOS/CorridorKeyMac.ofx"
echo "Local arm64 bundle built and ad-hoc signed. Resolve and real-model tests are still required."
echo "Install with: bash scripts/install_macos.sh"
