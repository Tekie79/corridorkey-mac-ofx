#!/bin/bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "Run setup natively on an Apple Silicon Mac; Rosetta and Intel are unsupported." >&2
  exit 1
fi
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Install Apple's command-line tools with: xcode-select --install" >&2
  exit 1
fi
if [[ -z "${CKMAC_PYTHON:-}" ]]; then
  if command -v python3.12 >/dev/null 2>&1; then
    CKMAC_PYTHON="$(command -v python3.12)"
  elif command -v python3.11 >/dev/null 2>&1; then
    CKMAC_PYTHON="$(command -v python3.11)"
  else
    echo "Install native arm64 Python 3.11 or 3.12, then rerun setup." >&2
    exit 1
  fi
fi
"$CKMAC_PYTHON" - <<'PY'
import platform, sys
assert platform.machine() == 'arm64', 'Python must be native arm64, not Rosetta'
assert sys.version_info[:2] in ((3, 11), (3, 12)), 'Use Python 3.11 or 3.12'
assert int(platform.mac_ver()[0].split('.')[0]) >= 14, 'Use macOS 14 or newer'
PY
"$CKMAC_PYTHON" "$project_root/scripts/fetch_sources.py"
"$CKMAC_PYTHON" -m venv "$project_root/.venv"
worker_python="$project_root/.venv/bin/python"
"$worker_python" -m pip install --upgrade pip
# Pin the upstream-tested torch pair; opencv 4.11 keeps NumPy 1.26 compatibility.
"$worker_python" -m pip install \
  'torch==2.9.1' 'torchvision==0.24.1' 'numpy==1.26.4' \
  'opencv-python==4.11.0.86' 'cmake>=3.22,<5' 'pytest>=8,<10' \
  -r "$project_root/.deps/CorridorKey2.0/requirements.txt"
"$worker_python" -m pip check
"$worker_python" -m pip freeze > "$project_root/installed-requirements.txt"
echo "Downloading publisher model assets (approximately 5 GB, no footage uploaded)."
"$worker_python" "$project_root/.deps/CorridorKey2.0/scripts/download_weights.py" \
  --corridorkey_revision cf44a8db3f024bb49fd59daa408848ccf05f7477
"$worker_python" "$project_root/scripts/doctor.py"
echo "Setup complete. Next: bash scripts/build_macos.sh"
