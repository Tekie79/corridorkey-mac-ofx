"""Health and real-image smoke test client for the local MPS worker."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import time

import numpy as np

from .protocol import OP_HEALTH, OP_INFER, SPACES, Request, read_response


def exchange(path: Path, request: Request, payload=b"", timeout=600):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect(str(path))
        connection.sendall(request.pack())
        if payload:
            connection.sendall(payload)
        status, body = read_response(connection, expected_width=request.width,
                                     expected_height=request.height)
    if status:
        raise RuntimeError(body.decode("utf-8", errors="replace"))
    return body


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path,
                        default=Path.home() / "Library/Caches/CorridorKeyMac/worker.sock")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Report actual model/device state")
    smoke = commands.add_parser("smoke", help="Infer an image; save straight float RGBA .npy and PNG previews")
    smoke.add_argument("image", type=Path)
    smoke.add_argument("--output", required=True, type=Path, help="New output directory (must not exist)")
    smoke.add_argument("--max-width", type=int, default=512,
                       help="Preview resize width; 0 preserves native size")
    smoke.add_argument("--source-alpha-hint", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "status":
        body = exchange(args.socket, Request(OP_HEALTH), timeout=5)
        report = json.loads(body)
        print(json.dumps(report, indent=2))
        return 0 if report["state"] == "ready" else 2
    if args.max_width < 0:
        parser.error("--max-width must be nonnegative")
    if args.output.exists():
        parser.error("Output directory already exists; choose a new directory")
    from PIL import Image
    with Image.open(args.image) as opened:
        if opened.mode not in ("RGB", "RGBA"):
            parser.error("Smoke input must be an 8-bit RGB/RGBA sRGB image; use OFX for floating-point footage")
        picture = opened.convert("RGBA")
        if args.max_width and picture.width > args.max_width:
            height = max(1, round(picture.height * args.max_width / picture.width))
            picture = picture.resize((args.max_width, height), Image.Resampling.LANCZOS)
        rgba = np.asarray(picture, dtype=np.float32) / 255.0
    rgba = np.ascontiguousarray(rgba, dtype="<f4")
    height, width = rgba.shape[:2]
    request = Request(OP_INFER, width, height, rgba.nbytes,
                      4 if args.source_alpha_hint else 0, 950, 0)
    started = time.perf_counter()
    body = exchange(args.socket, request, rgba.tobytes())
    elapsed = time.perf_counter() - started
    result = np.frombuffer(body, dtype="<f4").reshape(height, width, 4)
    if not np.isfinite(result).all() or np.any(result[..., 3] < 0) or np.any(result[..., 3] > 1):
        raise RuntimeError("Invalid model output; no files written")
    args.output.mkdir(parents=True, exist_ok=False)
    np.save(args.output / "foreground_straight_rgba.npy", result, allow_pickle=False)
    preview = np.round(np.clip(result, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(preview, mode="RGBA").save(args.output / "cutout_srgb_preview.png")
    Image.fromarray(preview[..., 3], mode="L").save(args.output / "matte_preview.png")
    report = {"width": width, "height": height, "request_seconds": elapsed,
              "output": str(args.output.resolve()), "input_space": SPACES[0],
              "float_output": "foreground_straight_rgba.npy",
              "png_previews": "8-bit clipped display previews; not final HDR masters",
              "quality_validation": "Requires visual comparison against real source/reference matte"}
    (args.output / "smoke_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
