"""Color/shape/error-contract tests; these do NOT certify MPS model inference."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))

from ckmac.backend import (
    BackendError,
    CorridorKeyBackend,
    center_reflect_pad,
    decode_input_rgb,
    encode_output_rgb,
    finish_frame,
    linear_to_model,
    model_to_linear,
    prepare_frame,
)


class TransferFunctionTests(unittest.TestCase):
    def test_srgb_known_reference_values(self):
        encoded = np.array([0.0, 0.04045, 0.5, 1.0, -0.5], dtype=np.float32)
        expected = np.array([0.0, 0.00313080495, 0.2140411405, 1.0, -0.2140411405])
        np.testing.assert_allclose(decode_input_rgb(encoded, "srgb"), expected, rtol=2e-6, atol=1e-8)

    def test_display_gamma_24_is_not_camera_oetf(self):
        value = decode_input_rgb(np.array([0.5], dtype=np.float32), "rec709_gamma24")
        self.assertAlmostEqual(float(value[0]), 0.1894645708, places=7)

    def test_hdr_negative_round_trip_in_each_transfer(self):
        linear = np.array([-8.0, -0.25, -0.003, 0, 0.003, 0.18, 1, 16, 256], dtype=np.float32)
        for space in ("linear", "srgb", "rec709_gamma24"):
            with self.subTest(space=space):
                result = decode_input_rgb(encode_output_rgb(linear, space), space)
                np.testing.assert_allclose(result, linear, rtol=4e-6, atol=1e-7)

    def test_asinh_reference_and_unclipped_round_trip(self):
        linear = np.array([-64, -16, -0.008, 0, 0.008, 16, 64], dtype=np.float32)
        encoded = linear_to_model(linear)
        self.assertAlmostEqual(float(encoded[1]), -1.0, places=6)
        self.assertAlmostEqual(float(encoded[-2]), 1.0, places=6)
        self.assertGreater(float(encoded[-1]), 1.0)
        np.testing.assert_allclose(model_to_linear(encoded), linear, rtol=1e-6, atol=1e-7)

    def test_invalid_samples_fail_visibly(self):
        for invalid in (np.nan, np.inf, -np.inf):
            with self.subTest(invalid=invalid):
                rgba = np.ones((3, 3, 4), dtype=np.float32)
                rgba[1, 1, 0] = invalid
                with self.assertRaisesRegex(ValueError, "NaN, infinity"):
                    prepare_frame(rgba)
        with self.assertRaises(ValueError):
            decode_input_rgb(np.array([0.5], dtype=np.float32), "slog3")


class ShapeAndAlphaTests(unittest.TestCase):
    def test_reflection_matches_nonrepeating_edge(self):
        image = np.array([[[1], [2], [3]]], dtype=np.float32)
        padded, pad = center_reflect_pad(image, quantum=8)
        self.assertEqual(pad, (2, 3, 3, 4))
        np.testing.assert_array_equal(padded[3, :, 0], [3, 2, 1, 2, 3, 2, 1, 2])

    def test_odd_sizes_crop_without_shift_and_keep_foreground(self):
        rng = np.random.default_rng(42)
        rgba = rng.uniform(-0.2, 4.0, (137, 259, 4)).astype(np.float32)
        rgba[..., 3] = 0.2  # Never multiply the generated FG or matte by this.
        prepared = prepare_frame(rgba, input_space="linear")
        self.assertEqual(prepared["model"].shape, (256, 384, 3))
        synthetic_matte = np.full((256, 384, 1), 0.7, dtype=np.float32)
        result = finish_frame(prepared["model"], synthetic_matte, prepared, input_space="linear")
        self.assertEqual(result.shape, rgba.shape)
        np.testing.assert_allclose(result[..., :3], rgba[..., :3], rtol=2e-6, atol=2e-7)
        np.testing.assert_allclose(result[..., 3], 0.7)
        self.assertEqual(result.dtype, np.float32)
        self.assertTrue(result.flags.c_contiguous)

    def test_no_hint_has_negative_quality_and_ignores_input_alpha(self):
        rgba = np.ones((7, 9, 4), dtype=np.float32)
        prepared = prepare_frame(rgba)
        self.assertEqual(prepared["hint_quality"], -1.0)
        self.assertFalse(prepared["hint"].any())

    def test_explicit_hint_clamps_but_does_not_change_rgb(self):
        rgba = np.full((2, 3, 4), 0.5, dtype=np.float32)
        rgba[..., 3] = [-1, 0.5, 2]
        prepared = prepare_frame(rgba, hint_mode="source_alpha", hint_quality=0.75)
        left, _, top, _ = prepared["pad"]
        np.testing.assert_array_equal(prepared["hint"][top, left:left + 3, 0], [0, 0.5, 1])
        self.assertEqual(prepared["hint_quality"], 0.75)
        plain = prepare_frame(rgba, hint_mode="none")
        np.testing.assert_array_equal(prepared["model"], plain["model"])

    def test_sdr_proxy_clips_only_foundation_input(self):
        rgba = np.array([[[-2.0, 0.18, 16.0, 1.0]]], dtype=np.float32)
        prepared = prepare_frame(rgba, input_space="linear")
        left, _, top, _ = prepared["pad"]
        self.assertEqual(float(prepared["display"][top, left, 0]), 0.0)
        self.assertEqual(float(prepared["display"][top, left, 2]), 1.0)
        restored = model_to_linear(prepared["model"][top, left])
        np.testing.assert_allclose(restored, [-2, 0.18, 16], rtol=1e-6)

    def test_alpha_is_clamped_not_sigmoided(self):
        rgba = np.ones((2, 3, 4), dtype=np.float32)
        prepared = prepare_frame(rgba)
        alpha = np.zeros((128, 128, 1), dtype=np.float32)
        left, _, top, _ = prepared["pad"]
        alpha[top:top + 2, left:left + 3, 0] = [-2, 0, 2]
        result = finish_frame(prepared["model"], alpha, prepared, input_space="srgb")
        np.testing.assert_array_equal(result[0, :, 3], [0, 0, 1])

    def test_invalid_shapes_and_parameters_fail(self):
        with self.assertRaises(ValueError):
            prepare_frame(np.zeros((2, 3, 3), dtype=np.float32))
        with self.assertRaises(ValueError):
            prepare_frame(np.zeros((2, 3, 4), dtype=np.uint8))
        rgba = np.zeros((2, 3, 4), dtype=np.float32)
        for quality in (-0.1, 1.1, float("nan")):
            with self.assertRaises(ValueError):
                prepare_frame(rgba, hint_quality=quality)
        with self.assertRaises(ValueError):
            prepare_frame(rgba, hint_mode="automatic")


class HardwareContractTests(unittest.TestCase):
    def test_non_mac_does_not_claim_gpu_inference(self):
        backend = CorridorKeyBackend(Path(__file__).resolve().parent)
        with patch("ckmac.backend.platform.system", return_value="Linux"), patch.dict(os.environ, {"PYTORCH_ENABLE_MPS_FALLBACK": "0"}):
            with self.assertRaisesRegex(BackendError, "Apple Silicon"):
                backend.load()
        diagnostics = backend.diagnostics()
        self.assertFalse(diagnostics["loaded"])
        self.assertIsNone(diagnostics["device"])
        self.assertEqual(diagnostics["successful_frames"], 0)
        self.assertFalse(diagnostics["clip_temporal_analysis"])

    def test_global_fallback_is_rejected_and_not_modified(self):
        with patch.dict(os.environ, {"PYTORCH_ENABLE_MPS_FALLBACK": "1"}):
            with self.assertRaisesRegex(BackendError, "Disable PYTORCH_ENABLE_MPS_FALLBACK"):
                CorridorKeyBackend._validate_environment()
            self.assertEqual(os.environ["PYTORCH_ENABLE_MPS_FALLBACK"], "1")

    def test_relative_import_root_is_not_accepted(self):
        with self.assertRaisesRegex(ValueError, "absolute trusted local path"):
            CorridorKeyBackend("untrusted-relative-path")


if __name__ == "__main__":
    unittest.main()
