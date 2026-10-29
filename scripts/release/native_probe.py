#!/usr/bin/env python3
"""Real neural inference probe; synthetic inputs never establish footage quality."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

os.environ.update(PYTORCH_ENABLE_MPS_FALLBACK="0", HF_HUB_OFFLINE="1",
                  TRANSFORMERS_OFFLINE="1", PYTHONDONTWRITEBYTECODE="1")
ap = argparse.ArgumentParser()
ap.add_argument('--code', type=Path, required=True)
ap.add_argument('--models', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--image', type=Path)
ap.add_argument('--width', type=int, default=256)
ap.add_argument('--capture', action='store_true')
args = ap.parse_args()
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'worker'))
import numpy as np
from PIL import Image
from ckmac.backend import CorridorKeyBackend
args.output.mkdir(parents=True, exist_ok=True)
record = {'status': 'Failed', 'hardware': platform.machine(), 'os': platform.mac_ver()[0],
          'python': sys.version, 'fixture': 'synthetic smoke input; not footage qualification'}
started = time.perf_counter()
try:
    b = CorridorKeyBackend(args.code.resolve(), args.models.resolve())
    b.load()
    record['load_seconds'] = time.perf_counter() - started
    if args.image:
        record['fixture'] = {'path': str(args.image), 'sha256': hashlib.sha256(args.image.read_bytes()).hexdigest()}
        if args.image.suffix.lower()=='.exr':
            os.environ['OPENCV_IO_ENABLE_OPENEXR']='1'
            import cv2
            rgb=cv2.imread(str(args.image),cv2.IMREAD_UNCHANGED)[...,:3][...,::-1].copy()
            if args.width and rgb.shape[1]>args.width:
                rgb=cv2.resize(rgb,(args.width,round(rgb.shape[0]*args.width/rgb.shape[1])),interpolation=cv2.INTER_AREA)
        else:
            im = Image.open(args.image).convert('RGB')
            if args.width and im.width > args.width:
                im = im.resize((args.width, round(im.height * args.width / im.width)))
            rgb = np.asarray(im, dtype=np.float32) / 255
    else:
        rgb = np.zeros((128, args.width, 3), dtype=np.float32)
        rgb[..., 1] = .6
        rgb[20:110, args.width//3:args.width*2//3] = [.5, .22, .15]
    rgba = np.concatenate((rgb, np.ones((*rgb.shape[:2], 1), dtype=np.float32)), axis=2)
    torch = b._torch
    import contextlib
    capture = torch.mps.profiler.metal_capture(str(args.output / 'inference.gputrace')) if args.capture else contextlib.nullcontext()
    t = time.perf_counter()
    with capture, torch.mps.profiler.profile(mode='interval,event', wait_until_completed=True):
        result = b.infer(rgba,input_space='linear' if args.image and args.image.suffix.lower()=='.exr' else 'srgb')
    record.update(status='Passed', inference_seconds=time.perf_counter()-t,
                  dimensions=[result.shape[1], result.shape[0]], backend=b.diagnostics(),
                  alpha_min=float(result[...,3].min()), alpha_max=float(result[...,3].max()),
                  foreground_min=float(result[...,:3].min()), foreground_max=float(result[...,:3].max()),
                  mps_recommended_bytes=int(torch.mps.recommended_max_memory()))
    np.save(args.output / 'straight_rgba.npy', result, allow_pickle=False)
    Image.fromarray((result[...,3]*255).astype('uint8')).save(args.output / 'alpha.png')
    Image.fromarray((np.clip(result[...,:3]*result[...,3:4],0,1)*255).astype('uint8')).save(args.output / 'over_black.png')
except Exception as exc:
    import traceback
    record['error'] = str(exc)
    record['traceback'] = traceback.format_exc()
    traceback.print_exc()
finally:
    record['total_seconds'] = time.perf_counter()-started
    (args.output / 'probe.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record, indent=2), flush=True)
if record['status'] != 'Passed':
    raise SystemExit(1)
