#!/bin/bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$(uname -s)" != Darwin ]]; then
  echo "This installer runs only on macOS." >&2
  exit 1
fi
bundle="$project_root/build/CorridorKeyMac.ofx.bundle"
destination="/Library/OFX/Plugins/CorridorKeyMac.ofx.bundle"
if [[ ! -f "$bundle/Contents/MacOS/CorridorKeyMac.ofx" ]]; then
  echo "Build the Mac bundle before installing." >&2
  exit 1
fi
codesign --verify --verbose=2 "$bundle"
if pgrep -x Resolve >/dev/null 2>&1; then
  echo "Quit DaVinci Resolve before installing the plugin." >&2
  exit 1
fi
if [[ -e "$destination" ]]; then
  backup="${destination}.backup-$(date +%Y%m%d-%H%M%S)"
  if [[ -e "$backup" ]]; then
    echo "Backup already exists; retry in a moment." >&2
    exit 1
  fi
  sudo mv "$destination" "$backup"
  echo "Previous custom plugin retained at $backup"
fi
sudo mkdir -p /Library/OFX/Plugins
sudo ditto "$bundle" "$destination"
echo "Installed CorridorKey Mac (Experimental). Start the worker, then open Resolve."
