"""Real C++ client ↔ Python worker seam; neural inference is explicitly mocked."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

import numpy as np
import pytest

from ckmac.server import LocalServer, Runtime


class ExplicitFakeBackend:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def load(self):
        return self

    def diagnostics(self):
        return {"device": "test_fake", "real_model": False}

    def infer(self, rgba, **settings):
        self.calls.append((rgba.copy(), settings))
        if self.fail:
            raise RuntimeError("intentional test model failure")
        result = rgba.copy()
        result[..., :3] *= 2
        result[..., 3] = 0.25
        return result


@pytest.mark.parametrize("fail", [False, True])
def test_cpp_client_talks_to_python_worker(fail):
    root = Path(__file__).resolve().parents[1]
    probe = Path(os.environ.get("CKMAC_BRIDGE_PROBE", str(root / "build/bridge_probe")))
    if not probe.is_file():
        pytest.skip("Build bridge_probe and set CKMAC_BRIDGE_PROBE to run the C++/Python integration test")
    with tempfile.TemporaryDirectory(prefix="ckx-", dir="/tmp") as folder:
        path = Path(folder) / "worker.sock"
        backend = ExplicitFakeBackend(fail=fail)
        runtime = Runtime(backend)
        runtime.load()
        server = LocalServer(path, runtime)
        os.chmod(path, 0o600)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            result = subprocess.run([str(probe), str(path)], capture_output=True, text=True, timeout=10)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        assert not thread.is_alive()
        assert len(backend.calls) == 1
        image, settings = backend.calls[0]
        assert settings == {"input_space": "rec709_gamma24", "hint_mode": "source_alpha",
                            "hint_quality": 0.75, "despill_strength": 0.125}
        np.testing.assert_allclose(image.reshape(-1), [0.1, 0.2, 0.3, 1,
                                                       0.4, 0.5, 0.6, 0.8,
                                                       0.7, 0.2, 0.9, 0.5,
                                                       0.01, 0.02, 0.03, 0.25], rtol=1e-6)
        if fail:
            assert result.returncode == 1
            assert "intentional test model failure" in result.stderr
            assert runtime.completed == 0
        else:
            assert result.returncode == 0, result.stderr
            report = json.loads(result.stdout)
            assert report["health"]["backend"]["real_model"] is False
            assert report["health"]["full_model_inference_succeeded"] is False
            output = np.asarray(report["rgba"]).reshape(2, 2, 4)
            np.testing.assert_allclose(output[..., :3], image[..., :3] * 2, rtol=1e-6)
            np.testing.assert_allclose(output[..., 3], 0.25)
            assert runtime.completed == 1
