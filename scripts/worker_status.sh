#!/bin/bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$project_root/worker${PYTHONPATH:+:$PYTHONPATH}"
exec "$project_root/.venv/bin/python" -m ckmac.client "$@" status
