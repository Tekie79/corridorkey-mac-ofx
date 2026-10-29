#!/bin/bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$project_root/worker${PYTHONPATH:+:$PYTHONPATH}"
export PYTORCH_ENABLE_MPS_FALLBACK=0
exec "$project_root/.venv/bin/python" -m ckmac.server \
  --upstream "$project_root/.deps/CorridorKey2.0" "$@"
