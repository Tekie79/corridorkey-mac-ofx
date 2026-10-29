#!/usr/bin/env python3
"""Verify prerequisites; this does not claim that full model inference passed."""
from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    upstream = root / ".deps/CorridorKey2.0"
    report = {"platform": platform.platform(), "architecture": platform.machine(),
              "python": sys.version.split()[0], "checks": {},
              "full_model_inference_tested": False, "resolve_render_tested": False}
    checks = report["checks"]
    checks["native_apple_silicon"] = platform.system() == "Darwin" and platform.machine() == "arm64"
    for package in ("torch", "torchvision", "numpy", "opencv-python", "transformers", "timm", "safetensors"):
        try:
            report[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            checks[f"installed_{package}"] = False
    try:
        import torch
        checks["mps_built"] = torch.backends.mps.is_built()
        checks["mps_available"] = torch.backends.mps.is_available()
        if checks["mps_available"]:
            sample = torch.ones((16, 16), device="mps")
            checks["mps_basic_compute"] = float((sample @ sample).sum().cpu()) == 4096.0
    except Exception as exc:
        checks["mps_basic_compute"] = False
        report["torch_error"] = str(exc)
    try:
        result = subprocess.run(["git", "-C", str(upstream), "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=True)
        report["upstream_commit"] = result.stdout.strip()
        checks["audited_upstream"] = report["upstream_commit"] == "485f5e9ab759ead6138cc990776184b59d6ea971"
    except (OSError, subprocess.CalledProcessError):
        checks["audited_upstream"] = False
    for path in ("weights/corridorkey_v2.safetensors", "weights/foundation_stats.safetensors",
                 "vfms/rvm/pretrain_rvm_small16_256_204031069.npz", "vfms/moge/model.pt",
                 "vfms/cradio/C-RADIOv4-SO400M/model.safetensors"):
        checks[path] = (upstream / path).is_file()
    report["prerequisites_passed"] = all(checks.values())
    print(json.dumps(report, indent=2))
    return 0 if report["prerequisites_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
