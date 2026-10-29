"""Real Unix transport with fake inference: no weights, Mac, or GPU validation.

Every fixture closes clients, shuts the listener down, and joins its thread.
Blocking fake backends have independent release events and bounded waits.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import stat
import tempfile
import threading

import numpy as np
import pytest

from ckmac.protocol import OP_HEALTH, OP_INFER, REQUEST, Request, read_response
from ckmac.server import FrameCache, LocalServer, Runtime, prepare_socket


class FakeBackend:
    """Explicit test double. It does not claim to be CorridorKey or use MPS."""
    def __init__(self):
        self.calls = []
        self.load_error = None
        self.infer_error = None
        self.output = None
        self.entered = None
        self.release = None

    def load(self):
        if self.load_error:
            raise self.load_error

    def diagnostics(self):
        return {"test_backend": "fake", "real_gpu_validation": False}

    def infer(self, rgba, **options):
        self.calls.append((rgba.copy(), options))
        if self.entered:
            self.entered.set()
            if not self.release.wait(timeout=5):
                raise TimeoutError("Test failed to release fake backend")
        if self.infer_error:
            raise self.infer_error
        if self.output is not None:
            return self.output(rgba)
        result = rgba.copy()
        result[..., :3] *= 0.5
        result[..., 3] = 0.25
        return result


@pytest.fixture
def private_dir():
    # pytest's normal temporary paths can exceed the macOS Unix socket limit.
    with tempfile.TemporaryDirectory(prefix="ckw-", dir="/tmp") as directory:
        path = Path(directory)
        path.chmod(0o700)
        yield path


@contextmanager
def running_server(private_dir, backend=None, *, load=True, cache_bytes=1024):
    backend = backend or FakeBackend()
    runtime = Runtime(backend, cache_bytes)
    if load:
        runtime.load()
    path = private_dir / "worker.sock"
    lock_fd = prepare_socket(path)
    try:
        server = LocalServer(path, runtime)
    except BaseException:
        os.close(lock_fd)
        raise
    path.chmod(0o600)
    thread = threading.Thread(target=server.serve_forever,
                              kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield path, runtime, backend
    finally:
        if backend.release:
            backend.release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        path.unlink(missing_ok=True)
        os.close(lock_fd)
        assert not thread.is_alive(), "Unix server thread did not shut down"


def exchange(path, header, payload=b"", *, width=0, height=0):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(str(path))
        client.sendall(header)
        if payload:
            client.sendall(payload)
        return read_response(client, expected_width=width, expected_height=height)


def frame_request(path, rgba, *, flags=0, quality=750, despill=250):
    rgba = np.ascontiguousarray(rgba, dtype="<f4")
    height, width, _ = rgba.shape
    request = Request(OP_INFER, width, height, rgba.nbytes, flags, quality, despill)
    return exchange(path, request.pack(), rgba.tobytes(), width=width, height=height)


def health(path):
    status, data = exchange(path, Request(OP_HEALTH).pack())
    assert status == 0
    return json.loads(data)


def test_real_unix_roundtrip_and_model_option_mapping(private_dir):
    rgba = np.array([[[0.2, -0.1, 1.5, 1], [0.8, 0.5, 0.4, 0.2]]], dtype="<f4")
    with running_server(private_dir) as (path, runtime, backend):
        status, data = frame_request(path, rgba, flags=6, quality=625, despill=375)
        assert status == 0
        keyed = np.frombuffer(data, dtype="<f4").reshape(rgba.shape)
        np.testing.assert_array_equal(keyed[..., :3], rgba[..., :3] * 0.5)
        np.testing.assert_array_equal(keyed[..., 3], 0.25)
        np.testing.assert_array_equal(backend.calls[0][0], rgba)
        assert backend.calls[0][1] == dict(input_space="rec709_gamma24",
                                         hint_mode="source_alpha", hint_quality=0.625,
                                         despill_strength=0.375)
        state = health(path)
        assert state["state"] == "ready"
        assert state["completed_frames"] == 1
        assert state["last_inference_seconds"] >= 0
        assert state["backend"]["real_gpu_validation"] is False
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_source_rejected_before_inference(private_dir, bad):
    rgba = np.ones((1, 1, 4), dtype="<f4")
    rgba[0, 0, 0] = bad
    with running_server(private_dir) as (path, runtime, backend):
        status, data = frame_request(path, rgba)
        assert status != 0
        assert b"NaN or infinity" in data
        assert not backend.calls
        assert runtime.completed == 0
        assert not runtime.cache.items


@pytest.mark.parametrize("output,reason", [
    (lambda x: np.full_like(x, np.nan), b"invalid image"),
    (lambda x: np.full_like(x, np.inf), b"invalid image"),
    (lambda x: np.zeros((2, 2, 4), dtype=np.float32), b"invalid image"),
    (lambda x: np.full_like(x, -0.01), b"alpha outside"),
    (lambda x: np.full_like(x, 1.01), b"alpha outside"),
])
def test_bad_model_output_is_error_never_passthrough(private_dir, output, reason):
    backend = FakeBackend()
    backend.output = output
    rgba = np.ones((1, 1, 4), dtype="<f4")
    with running_server(private_dir, backend) as (path, runtime, backend):
        status, data = frame_request(path, rgba)
        assert status != 0
        assert reason in data
        assert data != rgba.tobytes()
        assert runtime.completed == 0
        assert runtime.cache.size == 0


def test_backend_failure_is_propagated_and_retry_remains_possible(private_dir):
    backend = FakeBackend()
    backend.infer_error = RuntimeError("Unsupported MPS operation (fake test error)")
    rgba = np.ones((1, 1, 4), dtype="<f4")
    with running_server(private_dir, backend) as (path, runtime, backend):
        status, data = frame_request(path, rgba)
        assert status == 1
        assert b"Unsupported MPS operation" in data
        assert data != rgba.tobytes()
        assert runtime.completed == 0
        assert runtime.cache.size == 0
        backend.infer_error = None
        assert frame_request(path, rgba)[0] == 0
        assert runtime.completed == 1


def test_truncated_payload_releases_lock_for_next_render(private_dir):
    rgba = np.ones((1, 1, 4), dtype="<f4")
    with running_server(private_dir) as (path, runtime, backend):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(str(path))
            client.sendall(Request(OP_INFER, 1, 1, 16).pack() + b"1234")
            client.shutdown(socket.SHUT_WR)
            status, data = read_response(client, expected_width=1, expected_height=1)
            assert status == 1
            assert b"disconnected" in data
        assert not backend.calls
        assert frame_request(path, rgba)[0] == 0
        assert runtime.completed == 1


@pytest.mark.parametrize("field,value", [("width", 0), ("count", 15),
                                          ("flags", 3), ("flags", 8),
                                          ("reserved", 1), ("quality", 1001)])
def test_server_rejects_malformed_header_without_body(private_dir, field, value):
    values = dict(magic=b"CKM1", version=1, op=OP_INFER, width=1, height=1,
                  count=16, flags=0, quality=750, despill=0, reserved=0)
    values[field] = value
    with running_server(private_dir) as (path, runtime, backend):
        status, data = exchange(path, REQUEST.pack(*values.values()))
        assert status == 1
        assert b"ProtocolError" in data
        assert not backend.calls


def test_cache_identity_includes_pixels_dimensions_and_all_settings(private_dir):
    rgba = np.ones((1, 2, 4), dtype="<f4")
    with running_server(private_dir) as (path, runtime, backend):
        first = frame_request(path, rgba)
        assert frame_request(path, rgba) == first
        assert len(backend.calls) == 1
        assert runtime.cache_hits == 1
        changed = rgba.copy()
        changed[0, 0, 0] = 0.5
        cases = [
            (changed, {}), (rgba.reshape(2, 1, 4), {}),
            (rgba, {"flags": 1}), (rgba, {"flags": 4}),
            (rgba, {"quality": 500}), (rgba, {"despill": 500}),
        ]
        for image, options in cases:
            assert frame_request(path, image, **options)[0] == 0
        assert len(backend.calls) == 7
        assert runtime.completed == 7
        assert runtime.cache_hits == 1


def test_frame_cache_bounds_lru_and_replacement_accounting():
    cache = FrameCache(32)
    one = np.zeros((1, 1, 4), dtype=np.float32)
    cache.put(b"a", one.copy())
    cache.put(b"b", one.copy())
    assert cache.size == 32
    assert cache.get(b"a") is not None
    cache.put(b"c", one.copy())
    assert cache.get(b"b") is None
    assert list(cache.items) == [b"a", b"c"]
    cache.put(b"a", np.zeros((1, 2, 4), dtype=np.float32))
    assert cache.size == 32
    assert list(cache.items) == [b"a"]
    with pytest.raises(ValueError):
        cache.get(b"a")[0, 0, 0] = 1
    cache.put(b"a", np.zeros((1, 3, 4), dtype=np.float32))
    assert cache.size == 0
    assert not cache.items


@pytest.mark.parametrize("cache_bytes", [0, 15])
def test_disabled_or_undersized_cache_does_not_claim_hits(private_dir, cache_bytes):
    rgba = np.ones((1, 1, 4), dtype="<f4")
    with running_server(private_dir, cache_bytes=cache_bytes) as (path, runtime, backend):
        assert frame_request(path, rgba)[0] == 0
        assert frame_request(path, rgba)[0] == 0
        assert len(backend.calls) == 2
        assert runtime.cache_hits == 0
        assert runtime.cache.size == 0


def test_loading_and_load_error_health_never_report_ready(private_dir):
    backend = FakeBackend()
    backend.load_error = RuntimeError("missing weights (fake test error)")
    with running_server(private_dir, backend, load=False) as (path, runtime, backend):
        assert health(path)["state"] == "loading"
        status, data = frame_request(path, np.ones((1, 1, 4), dtype="<f4"))
        assert status == 1
        assert b"still loading" in data
        runtime.load()
        state = health(path)
        assert state["state"] == "error"
        assert "missing weights" in state["error"]
        status, data = frame_request(path, np.ones((1, 1, 4), dtype="<f4"))
        assert status == 1
        assert b"missing weights" in data
        assert not backend.calls


def test_inference_is_serialized_but_health_remains_responsive(private_dir):
    backend = FakeBackend()
    backend.entered = threading.Event()
    backend.release = threading.Event()
    rgba = np.ones((1, 1, 4), dtype="<f4")
    with running_server(private_dir, backend) as (path, runtime, backend):
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(frame_request, path, rgba)
            try:
                assert backend.entered.wait(timeout=2)
                second = executor.submit(frame_request, path, rgba * 0.5)
                state = health(path)  # socket timeout also guards liveness
                assert state["state"] == "ready"
                assert state["completed_frames"] == 0
                assert state["backend"] == {}  # avoid touching active model
                assert len(backend.calls) == 1
            finally:
                backend.release.set()
            assert first.result(timeout=3)[0] == 0
            assert second.result(timeout=3)[0] == 0
        assert runtime.completed == 2


def test_socket_parent_must_be_private(private_dir):
    public = private_dir / "public"
    public.mkdir(mode=0o755)
    public.chmod(0o755)
    with pytest.raises(PermissionError, match="private"):
        prepare_socket(public / "worker.sock")
    assert not (public / "worker.sock").exists()


def test_symlink_parent_socket_and_lock_are_not_followed(private_dir):
    target = private_dir / "real"
    target.mkdir(mode=0o700)
    alias = private_dir / "alias"
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(PermissionError):
        prepare_socket(alias / "worker.sock")
    assert not (target / "worker.sock").exists()

    victim = private_dir / "victim"
    victim.write_bytes(b"keep this")
    path = private_dir / "worker.sock"
    path.symlink_to(victim)
    with pytest.raises(PermissionError):
        prepare_socket(path)
    assert victim.read_bytes() == b"keep this"
    path.unlink()

    lock = private_dir / "worker.sock.lock"
    lock.unlink()
    lock.symlink_to(victim)
    with pytest.raises(OSError):
        prepare_socket(path)
    assert victim.read_bytes() == b"keep this"


def test_existing_regular_file_is_never_replaced(private_dir):
    path = private_dir / "worker.sock"
    path.write_bytes(b"not a socket")
    with pytest.raises(PermissionError, match="non-socket"):
        prepare_socket(path)
    assert path.read_bytes() == b"not a socket"


def test_existing_lock_prevents_a_second_worker(private_dir):
    path = private_dir / "worker.sock"
    lock_fd = prepare_socket(path)
    try:
        with pytest.raises(BlockingIOError):
            prepare_socket(path)
    finally:
        os.close(lock_fd)


def test_active_socket_without_lock_is_never_replaced(private_dir):
    path = private_dir / "worker.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as active:
        active.bind(str(path))
        active.listen(2)
        before = path.stat().st_ino
        with pytest.raises(RuntimeError, match="already listening"):
            prepare_socket(path)
        assert path.stat().st_ino == before
        assert stat.S_ISSOCK(path.stat().st_mode)


def test_stale_socket_is_reclaimed_but_lock_is_retained(private_dir):
    path = private_dir / "worker.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stale:
        stale.bind(str(path))
    lock_fd = prepare_socket(path)
    try:
        assert not path.exists()
        assert (private_dir / "worker.sock.lock").exists()
    finally:
        os.close(lock_fd)


def test_public_or_nonregular_lock_is_rejected(private_dir):
    path = private_dir / "worker.sock"
    lock = private_dir / "worker.sock.lock"
    lock.write_bytes(b"")
    lock.chmod(0o644)
    with pytest.raises(PermissionError, match="private"):
        prepare_socket(path)


def test_long_socket_path_rejected_before_creating_directories(private_dir):
    parent = private_dir / ("x" * 104)
    with pytest.raises(ValueError, match="too long"):
        prepare_socket(parent / "worker.sock")
    assert not parent.exists()
