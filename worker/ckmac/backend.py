"""Experimental CorridorKey 2.0 inference adapter for Apple Silicon.

Only the native PyTorch MPS backend executes the neural network.  This module
does not substitute a conventional chroma key when MPS, weights, or an operator
is unavailable.  The upstream CUDA video orchestration is deliberately unused.

The initial host contract is a complete, *straight* RGB(A) frame, with Rec.709 /
sRGB primaries and a declared transfer function.  Output is straight foreground
RGB in that same space plus the predicted alpha.  The host performs any required
unpremultiplication before this call and premultiplication after it.

This adapter implements independent T=1 inference. It does not implement the
official application's clip analysis, recurrent carry, or overlapping temporal
windows. Keeping state out of the render call is essential for random-access
OFX hosts, which may request frames in any order.
"""

from __future__ import annotations

import gc
import importlib
import math
import os
from pathlib import Path
import platform
import sys
import threading
from typing import Any

import numpy as np


UPSTREAM_COMMIT = "485f5e9ab759ead6138cc990776184b59d6ea971"
INPUT_SPACES = ("srgb", "linear", "rec709_gamma24")
HINT_MODES = ("none", "source_alpha")
SHAPE_QUANTUM = 128
_ASINH_KNEE = 0.008
_ASINH_DENOM = math.asinh(16.0 / _ASINH_KNEE)


class BackendError(RuntimeError):
    """A load, hardware, or inference failure that must be visible in the host."""


def _finite_float32(value: np.ndarray, *, what: str) -> np.ndarray:
    """Reject invalid model/host values instead of silently making a bad matte."""
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.asarray(value, dtype=np.float32)
    if not np.isfinite(result).all():
        raise ValueError(f"{what} contains NaN, infinity, or values outside float32 range")
    return np.ascontiguousarray(result)


def decode_input_rgb(rgb: np.ndarray, input_space: str) -> np.ndarray:
    """Decode the declared transfer to scene-linear Rec.709 RGB.

    Sign-preserving extensions retain negative and super-white values. Gamma
    2.4 is a display gamma, not the piecewise Rec.709 camera OETF. No gamut
    conversion, log decoding, tone mapping, or automatic color detection occurs.
    """
    if input_space not in INPUT_SPACES:
        raise ValueError(f"input_space must be one of {INPUT_SPACES}")
    x = _finite_float32(rgb, what="Input RGB")
    if input_space == "linear":
        return x
    magnitude = np.abs(x.astype(np.float64))
    with np.errstate(over="ignore", invalid="ignore"):
        if input_space == "srgb":
            decoded = np.where(
                magnitude <= 0.04045,
                magnitude / 12.92,
                np.power((magnitude + 0.055) / 1.055, 2.4),
            )
        else:
            decoded = np.power(magnitude, 2.4)
    return _finite_float32(np.copysign(decoded, x), what="Decoded linear RGB")


def encode_output_rgb(linear: np.ndarray, input_space: str) -> np.ndarray:
    """Encode predicted straight foreground without clipping negative/HDR RGB."""
    if input_space not in INPUT_SPACES:
        raise ValueError(f"input_space must be one of {INPUT_SPACES}")
    x = _finite_float32(linear, what="Predicted linear foreground")
    if input_space == "linear":
        return x
    magnitude = np.abs(x.astype(np.float64))
    if input_space == "srgb":
        encoded = np.where(
            magnitude <= 0.0031308,
            12.92 * magnitude,
            1.055 * np.power(magnitude, 1.0 / 2.4) - 0.055,
        )
    else:
        encoded = np.power(magnitude, 1.0 / 2.4)
    return _finite_float32(np.copysign(encoded, x), what="Encoded foreground")


def linear_to_model(linear: np.ndarray) -> np.ndarray:
    """The upstream signed-asinh model encoding (knee .008, reference 16)."""
    x = _finite_float32(linear, what="Linear model input")
    # CPU float64 intermediate avoids overflow for finite float32 HDR values.
    return _finite_float32(
        np.arcsinh(x.astype(np.float64) / _ASINH_KNEE) / _ASINH_DENOM,
        what="Asinh model input",
    )


def model_to_linear(encoded: np.ndarray) -> np.ndarray:
    """Decode the model's foreground; do not sigmoid or clamp its RGB."""
    y = _finite_float32(encoded, what="Model foreground")
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.sinh(y.astype(np.float64) * _ASINH_DENOM) * _ASINH_KNEE
    return _finite_float32(result, what="Decoded model foreground")


def center_reflect_pad(
    image: np.ndarray, quantum: int = SHAPE_QUANTUM,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Match upstream BORDER_REFLECT_101, returning (left,right,top,bottom).

    NumPy's reflect mode is the equivalent non-edge-repeating reflection. A
    singleton axis repeats its only sample, as OpenCV does for that case.
    """
    if image.ndim != 3 or image.shape[0] < 1 or image.shape[1] < 1:
        raise ValueError("Expected a nonempty HxWxC array")
    if quantum < 1:
        raise ValueError("Shape quantum must be positive")
    height, width = image.shape[:2]
    out_h = ((height + quantum - 1) // quantum) * quantum
    out_w = ((width + quantum - 1) // quantum) * quantum
    top = (out_h - height) // 2
    bottom = out_h - height - top
    left = (out_w - width) // 2
    right = out_w - width - left
    padded = np.pad(image, ((top, bottom), (left, right), (0, 0)), mode="reflect")
    return np.ascontiguousarray(padded), (left, right, top, bottom)


def prepare_frame(
    rgba: np.ndarray,
    *,
    input_space: str = "srgb",
    hint_mode: str = "none",
    hint_quality: float = 0.95,
) -> dict[str, Any]:
    """Prepare exact model encodings on CPU, independent of torch availability.

    Foundation models receive a clamped SDR sRGB proxy; the actual keying model
    receives unclipped signed-asinh linear RGB. These are distinct inputs.
    """
    array = np.asarray(rgba)
    if array.ndim != 3 or array.shape[2] != 4 or min(array.shape[:2]) < 1:
        raise ValueError("Input must be a nonempty HxWx4 float RGBA frame")
    if not np.issubdtype(array.dtype, np.floating):
        raise ValueError("Input must contain floating-point RGBA samples")
    array = _finite_float32(array, what="Input RGBA")
    if hint_mode not in HINT_MODES:
        raise ValueError(f"hint_mode must be one of {HINT_MODES}")
    quality = float(hint_quality)
    if not math.isfinite(quality) or not 0 <= quality <= 1:
        raise ValueError("Hint quality must be finite and between 0 and 1")
    linear = decode_input_rgb(array[..., :3], input_space)
    linear, pad = center_reflect_pad(linear)
    model = linear_to_model(linear)
    display = np.clip(encode_output_rgb(np.maximum(linear, 0), "srgb"), 0, 1)
    if hint_mode == "source_alpha":
        hint, hint_pad = center_reflect_pad(np.clip(array[..., 3:4], 0, 1))
        assert hint_pad == pad
        model_quality = quality
    else:
        hint = np.zeros((*linear.shape[:2], 1), dtype=np.float32)
        # Upstream semantic contract: -1 means "decide subject"; 0 means a
        # frame lacking an explicit hint inside an otherwise hinted window.
        model_quality = -1.0
    return {
        "model": model,
        "display": _finite_float32(display, what="Foundation SDR proxy"),
        "hint": _finite_float32(hint, what="Hint"),
        "hint_quality": model_quality,
        "pad": pad,
        "native_hw": array.shape[:2],
    }


def finish_frame(
    fg_asinh: np.ndarray,
    alpha: np.ndarray,
    prepared: dict[str, Any],
    *,
    input_space: str,
    despill_strength: float = 0.0,
) -> np.ndarray:
    """Convert/crop real model output to a straight RGBA host frame."""
    strength = float(despill_strength)
    if not math.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("Despill strength must be finite and between 0 and 1")
    padded_h, padded_w = prepared["model"].shape[:2]
    if fg_asinh.shape != (padded_h, padded_w, 3):
        raise BackendError(f"Unexpected predicted foreground shape: {fg_asinh.shape}")
    if alpha.shape != (padded_h, padded_w, 1):
        raise BackendError(f"Unexpected predicted alpha shape: {alpha.shape}")
    left, _, top, _ = prepared["pad"]
    height, width = prepared["native_hw"]
    fg = fg_asinh[top:top + height, left:left + width]
    matte = _finite_float32(alpha[top:top + height, left:left + width], what="Model alpha")
    linear = model_to_linear(fg)
    if strength:
        # An explicit extra green-channel correction, in display sRGB. It is
        # not the learned foreground prediction and is off by default. RGB
        # values retain their full floating-point range throughout.
        srgb = encode_output_rgb(linear, "srgb")
        spill = np.maximum(srgb[..., 1:2] - (srgb[..., 0:1] + srgb[..., 2:3]) * 0.5, 0)
        srgb = srgb + strength * np.concatenate((spill * 0.5, -spill, spill * 0.5), axis=2)
        linear = decode_input_rgb(srgb, "srgb")
    fg_output = encode_output_rgb(linear, input_space)
    return np.ascontiguousarray(np.concatenate((fg_output, np.clip(matte, 0, 1)), axis=2), dtype=np.float32)


class CorridorKeyBackend:
    """One persistent, serialized, actual CorridorKey model on the Mac GPU."""

    def __init__(self, upstream_root: str | Path, model_root: str | Path | None = None):
        root = Path(upstream_root).expanduser()
        if not root.is_absolute():
            raise ValueError("upstream_root must be an absolute trusted local path")
        self.upstream_root = root.resolve()
        self.model_root = Path(model_root).resolve() if model_root else self.upstream_root
        self._model: Any = None
        self._torch: Any = None
        self._lock = threading.RLock()
        self._last_error: str | None = None
        self._successful_frames = 0
        self._network_calls: dict[str, int] = {}
        self._temporal_completed = 0

    @staticmethod
    def _validate_environment() -> None:
        if os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK", "0") not in ("", "0"):
            raise BackendError(
                "Disable PYTORCH_ENABLE_MPS_FALLBACK before starting this worker. "
                "This experimental GPU backend fails explicitly on unsupported "
                "operators instead of silently running the model on CPU."
            )
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise BackendError(
                "CorridorKey Mac requires native arm64 Python on an Apple Silicon Mac. "
                "Linux, Intel Macs, and Rosetta Python cannot run this backend."
            )

    def load(self) -> "CorridorKeyBackend":
        """Load user-fetched official weights and put every network tensor on MPS.

        Initial module construction deliberately occurs on CPU: upstream uses
        QR-based random initialization before loading its checkpoint, and some
        supported PyTorch releases lack the corresponding MPS initialization
        kernels. Initialization is not inference. No torch APIs are patched.
        """
        with self._lock:
            if self._model is not None:
                return self
            self._validate_environment()
            package_dir = self.upstream_root / "corridorkey"
            for name in ("model.py", "runtime.py", "color_utils.py"):
                if not (package_dir / name).is_file():
                    raise BackendError(f"Missing upstream file: {package_dir / name}")
            existing = sys.modules.get("corridorkey")
            if existing is not None:
                existing_path = getattr(existing, "__file__", None)
                if existing_path is None or Path(existing_path).resolve().parent != package_dir:
                    raise BackendError("A different CorridorKey package is already loaded in this worker")
            # The only permitted network access belongs to the separate setup
            # command. All model assets and executable model snapshot code must
            # already be present under the user-selected, trusted upstream root.
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["XFORMERS_DISABLED"] = "1"
            if str(self.upstream_root) not in sys.path:
                sys.path.insert(0, str(self.upstream_root))
            try:
                torch = importlib.import_module("torch")
            except ImportError as exc:
                raise BackendError("PyTorch is not installed in the worker environment; run Mac setup") from exc
            self._torch = torch
            if not torch.backends.mps.is_built() or not torch.backends.mps.is_available():
                raise BackendError(
                    "PyTorch reports MPS unavailable. Use a native Apple Silicon "
                    "PyTorch build on a supported macOS release."
                )
            try:
                runtime = importlib.import_module("corridorkey.runtime")
                assets = runtime.RuntimePaths.from_package(self.model_root)
                paths = runtime.RuntimePaths(
                    package_root=self.upstream_root, weights=assets.weights,
                    foundation_stats=assets.foundation_stats, rvm_ckpt=assets.rvm_ckpt,
                    moge_checkpoint=assets.moge_checkpoint, cradio_dir=assets.cradio_dir)
                paths.validate()
                # Prefer safetensors for CK weights/stats. MoGe's official
                # source still supplies a .pt; download only publisher assets.
                if paths.weights.suffix != ".safetensors" or paths.foundation_stats.suffix != ".safetensors":
                    raise BackendError("Download official CorridorKey .safetensors weights and foundation stats")
                model = runtime.load_model(paths, device="cpu")
                runtime.configure_low_vram_inference(model, runtime.InferenceConfig())
                model.requires_grad_(False)
                model.eval()
                model = model.to(device=torch.device("mps"), dtype=torch.float32)
                misplaced = [
                    name for name, value in list(model.named_parameters()) + list(model.named_buffers())
                    if value.device.type != "mps"
                ]
                if misplaced:
                    raise BackendError(f"Model tensors remained outside MPS: {misplaced[:5]}")
                torch.mps.synchronize()
                self._model = model
                # Record real execution of each foundation and learned stage.
                # Hooks retain only integer counters, never tensors or host handles.
                for name, module in (("cradio",model.foundations.cradio),
                                     ("moge_encoder",model.foundations.moge.encoder if model.foundations.moge is not None else None),
                                     ("rvm",model.foundations.rvm),
                                     ("stage1",model.stage1),("stage2",model.stage2)):
                    if module is not None:
                        def counted(_module, _inputs, _output, key=name):
                            self._network_calls[key] = self._network_calls.get(key, 0) + 1
                        module.register_forward_hook(counted)
                self._last_error = None
                gc.collect()
            except Exception as exc:
                self._last_error = str(exc)
                self._model = None
                if isinstance(exc, BackendError):
                    raise
                raise BackendError(f"CorridorKey MPS model load failed: {exc}") from exc
            return self

    def infer(
        self,
        rgba: np.ndarray,
        *,
        input_space: str = "srgb",
        hint_mode: str = "none",
        hint_quality: float = 0.95,
        despill_strength: float = 0.0,
    ) -> np.ndarray:
        """Infer one full frame with fresh recurrent state, returning straight RGBA."""
        strength = float(despill_strength)
        if not math.isfinite(strength) or not 0 <= strength <= 1:
            raise ValueError("Despill strength must be finite and between 0 and 1")
        prepared = prepare_frame(
            rgba, input_space=input_space, hint_mode=hint_mode, hint_quality=hint_quality,
        )
        with self._lock:
            if self._model is None:
                self.load()
            torch = self._torch
            try:
                def cpu_btchw(array: np.ndarray):
                    return torch.from_numpy(np.ascontiguousarray(array.transpose(2, 0, 1))).unsqueeze(0).unsqueeze(0)

                model_rgb = cpu_btchw(prepared["model"]).to(device="mps", dtype=torch.float32)
                hint = cpu_btchw(prepared["hint"]).to(device="mps", dtype=torch.float32)
                proxy = cpu_btchw(prepared["display"])
                _, _, _, height, width = proxy.shape
                # CPU resize is deliberate and reported in diagnostics. PyTorch
                # area reduction to MoGe's 7/32 shape has non-divisible bins;
                # some MPS versions cannot execute this adaptive-average-pool
                # operation. Use the SAME PyTorch area math on CPU, not bilinear.
                flat = proxy.reshape(1, 3, height, width)
                radio = torch.nn.functional.interpolate(flat, size=(height // 4, width // 4), mode="area")
                moge = torch.nn.functional.interpolate(flat, size=(height * 7 // 32, width * 7 // 32), mode="area")
                radio = radio.unsqueeze(0).to(device="mps", dtype=torch.float32)
                moge = moge.unsqueeze(0).to(device="mps", dtype=torch.float32)
                quality = torch.tensor([[prepared["hint_quality"]]], device="mps", dtype=torch.float32)
                with torch.inference_mode():
                    outputs = self._model(
                        rgb=model_rgb,
                        hint=hint,
                        rgb_cradio=radio,
                        rgb_moge=moge,
                        rgb_rvm=None,
                        rvm_state=None,
                        stage1_recurrent_states=None,
                        hint_quality=quality,
                        t_stride=1.0,
                    )
                torch.mps.synchronize()
                fg = outputs["fg"][0, 0].permute(1, 2, 0).detach().to(device="cpu", dtype=torch.float32).numpy()
                alpha = outputs["alpha"][0, 0].permute(1, 2, 0).detach().to(device="cpu", dtype=torch.float32).numpy()
                result = finish_frame(
                    fg, alpha, prepared, input_space=input_space, despill_strength=strength,
                )
                self._successful_frames += 1
                self._last_error = None
                return result
            except Exception as exc:
                self._last_error = str(exc)
                raise BackendError(
                    f"CorridorKey MPS inference failed; no fallback image was produced: {exc}. "
                    "If this is an unsupported MPS operation, capture the worker traceback "
                    "for the compatibility port. If it is out of memory, test a smaller frame."
                ) from exc

    def diagnostics(self) -> dict[str, Any]:
        """JSON-serializable facts; model placement is not a passed inference test."""
        with self._lock:
            torch = self._torch
            loaded = self._model is not None
            report: dict[str, Any] = {
                "backend": "pytorch_mps",
                "loaded": loaded,
                "device": "mps" if loaded else None,
                "dtype": "float32" if loaded else None,
                "torch_version": str(torch.__version__) if torch is not None else None,
                "upstream_root": str(self.upstream_root),
                "model_root": str(self.model_root),
                "audited_upstream_commit": UPSTREAM_COMMIT,
                "temporal_mode": "upstream_float32_continuous_RVM_Hann_configurable" if self._temporal_completed else "independent_frame_T1",
                "clip_temporal_analysis": self._temporal_completed > 0,
                "completed_temporal_shots": self._temporal_completed,
                "automatic_cpu_model_fallback": False,
                "cpu_preprocessing": ["transfer_functions", "reflect_padding", "foundation_area_resize"],
                "cpu_postprocessing": ["asinh_decode", "crop", "transfer_functions", "optional_green_despill"],
                "input_spaces": list(INPUT_SPACES),
                "input_alpha": "only used as a hint when explicitly selected",
                "output_alpha": "straight foreground RGB plus clamped model matte",
                "successful_frames": self._successful_frames,
                "completed_network_calls": dict(self._network_calls),
                "last_error": self._last_error,
            }
            if loaded:
                try:
                    report["mps_current_allocated_bytes"] = int(torch.mps.current_allocated_memory())
                    report["mps_driver_allocated_bytes"] = int(torch.mps.driver_allocated_memory())
                except (AttributeError, RuntimeError):
                    pass
            return report
