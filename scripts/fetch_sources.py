#!/usr/bin/env python3
"""Fetch the audited upstream sources, without models or modifying existing clones."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

SOURCES = {
    "CorridorKey2.0": ("https://github.com/nikopueringer/CorridorKey2.0.git",
                       "485f5e9ab759ead6138cc990776184b59d6ea971"),
    "openfx": ("https://github.com/AcademySoftwareFoundation/openfx.git",
               "c3f1c2dcf4f51762b794c4fc21181b4a501be1bf"),
}


def git(directory: Path, *args) -> str:
    result = subprocess.run(["git", "-C", str(directory), *args], check=True,
                            capture_output=True, text=True)
    return result.stdout.strip()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=root / ".deps")
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    for name, (url, commit) in SOURCES.items():
        dest = args.directory / name
        if dest.exists():
            if not (dest / ".git").is_dir():
                raise RuntimeError(f"{dest} exists but is not a clone; it was left untouched")
            if git(dest, "remote", "get-url", "origin") != url:
                raise RuntimeError(f"Unexpected repository at {dest}; it was left untouched")
            if git(dest, "rev-parse", "HEAD") != commit:
                raise RuntimeError(f"{dest} is not at the audited commit; it was left untouched")
            if git(dest, "status", "--porcelain", "--untracked-files=no"):
                raise RuntimeError(f"{dest} has tracked modifications; it was left untouched")
        else:
            dest.mkdir()
            git(dest, "init")
            git(dest, "remote", "add", "origin", url)
            git(dest, "fetch", "--depth=1", "origin", commit)
            git(dest, "checkout", "--detach", "FETCH_HEAD")
        print(f"Verified {name}: {commit}")


if __name__ == "__main__":
    main()
