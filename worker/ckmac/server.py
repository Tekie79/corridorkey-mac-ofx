"""Run locally: python -m ckmac.server --upstream /absolute/CorridorKey2.0.

One model is loaded, inference is serialized, health requests remain responsive.
No TCP listener, arbitrary file RPC, executable deserialization, or CPU fallback.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import signal
import socket
import socketserver
import stat
import threading
import time

import numpy as np

from . import __version__
from .protocol import (OP_HEALTH, REQUEST, MAX_TEXT, Request, parse_request,
                       recv_exact, response_header)

LOG = logging.getLogger("ckmac")


def default_socket() -> Path:
    return Path.home() / "Library/Caches/CorridorKeyMac/worker.sock"


class FrameCache:
    """Byte-bounded RAM cache. Identity includes all model-affecting options."""
    def __init__(self, byte_limit: int = 256 * 1024 * 1024):
        self.limit = max(0, byte_limit)
        self.size = 0
        self.items: OrderedDict[bytes, np.ndarray] = OrderedDict()

    def get(self, key: bytes):
        result = self.items.get(key)
        if result is not None:
            self.items.move_to_end(key)
        return result

    def put(self, key: bytes, value: np.ndarray):
        old = self.items.pop(key, None)
        if old is not None:
            self.size -= old.nbytes
        if value.nbytes > self.limit:
            return
        while self.items and self.size + value.nbytes > self.limit:
            _, evicted = self.items.popitem(last=False)
            self.size -= evicted.nbytes
        value.setflags(write=False)
        self.items[key] = value
        self.size += value.nbytes


class Runtime:
    def __init__(self, backend, cache_bytes: int = 256 * 1024 * 1024):
        self.backend = backend
        self.lock = threading.Lock()
        self.cache = FrameCache(cache_bytes)
        self.state = "loading"
        self.error = ""
        self.completed = 0
        self.cache_hits = 0
        self.last_inference_seconds = None

    def load(self):
        with self.lock:
            try:
                self.backend.load()
                self.state = "ready"
                LOG.info("Model loaded on MPS; ready for single-frame requests")
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                self.state = "error"
                LOG.exception("GPU model could not load")

    def health(self) -> dict:
        # Do not touch a mutating model during load/inference.
        details = {}
        if self.state == "ready" and self.lock.acquire(blocking=False):
            try:
                details = self.backend.diagnostics()
            finally:
                self.lock.release()
        return {"version": __version__, "state": self.state, "error": self.error,
                "requested_device": "mps", "temporal_frames": 1,
                "full_model_inference_succeeded": self.completed > 0,
                "completed_frames": self.completed, "cache_hits": self.cache_hits,
                "last_inference_seconds": self.last_inference_seconds,
                "backend": details}

    def infer_locked(self, request: Request, payload: bytearray) -> np.ndarray:
        if self.state != "ready":
            raise RuntimeError(self.error or "Model is still loading. Check worker status and retry.")
        digest = hashlib.sha256(request.pack())
        digest.update(payload)
        key = digest.digest()
        cached = self.cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        rgba = np.frombuffer(payload, dtype="<f4").reshape(request.height, request.width, 4)
        if not np.isfinite(rgba).all():
            raise ValueError("Source contains NaN or infinity; correct the upstream image first")
        started = time.perf_counter()
        result = self.backend.infer(
            rgba, input_space=request.input_space, hint_mode=request.hint_mode,
            hint_quality=request.hint_quality_milli / 1000.0,
            despill_strength=request.despill_milli / 1000.0)
        result = np.ascontiguousarray(result, dtype="<f4")
        if result.shape != rgba.shape or not np.isfinite(result).all():
            raise RuntimeError("Model returned an invalid image; render was rejected")
        if np.any(result[..., 3] < 0) or np.any(result[..., 3] > 1):
            raise RuntimeError("Model returned alpha outside [0, 1]")
        self.last_inference_seconds = time.perf_counter() - started
        self.completed += 1
        self.cache.put(key, result)
        LOG.info("Frame %dx%d inferred in %.3fs", request.width, request.height,
                 self.last_inference_seconds)
        return result


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        connection = self.request
        connection.settimeout(600)
        try:
            request = parse_request(recv_exact(connection, REQUEST.size))
            runtime = self.server.runtime
            if request.operation == OP_HEALTH:
                data = json.dumps(runtime.health(), allow_nan=False).encode("utf-8")
                if len(data) > MAX_TEXT:
                    raise RuntimeError("Health response exceeds protocol limit")
                connection.sendall(response_header(0, len(data)))
                connection.sendall(data)
                return
            # Acquire before receiving a large frame, bounding simultaneous allocation.
            if not runtime.lock.acquire(timeout=600):
                raise TimeoutError("GPU queue is busy; retry once the current frame finishes")
            try:
                payload = recv_exact(connection, request.payload_bytes)
                result = runtime.infer_locked(request, payload)
                connection.sendall(response_header(0, result.nbytes, request.width, request.height))
                connection.sendall(memoryview(result).cast("B"))
            finally:
                runtime.lock.release()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            LOG.info("Host cancelled or disconnected")
        except Exception as exc:
            LOG.warning("Request failed: %s: %s", type(exc).__name__, exc)
            data = f"{type(exc).__name__}: {exc}".encode("utf-8")[:MAX_TEXT]
            try:
                connection.sendall(response_header(1, len(data)))
                connection.sendall(data)
            except OSError:
                pass


class LocalServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, path: Path, runtime: Runtime):
        self.runtime = runtime
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(str(path), Handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def prepare_socket(path: Path):
    """Hold an advisory lock for the server lifetime, refuse symlinks and live peers."""
    if len(os.fsencode(path)) > 103:
        raise ValueError("Socket path is too long for macOS; choose a shorter private directory")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise PermissionError("Socket parent must be a private, user-owned directory (mode 0700)")
    lock_path = path.parent / (path.name + ".lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise PermissionError("Worker lock must be a private, user-owned regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                raise PermissionError("Refusing to replace a non-socket or foreign-owned path")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                probe.settimeout(1)
                try:
                    probe.connect(str(path))
                except ConnectionRefusedError:
                    path.unlink()
                else:
                    raise RuntimeError("A worker is already listening on this socket")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument("--socket", type=Path, default=default_socket())
    parser.add_argument("--cache-mib", type=int, default=256)
    args = parser.parse_args(argv)
    if not 0 <= args.cache_mib <= 4096:
        parser.error("--cache-mib must be in 0..4096")
    # Set BEFORE importing torch. A caller cannot silently opt into CPU kernels.
    if os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK", "0") not in ("", "0"):
        parser.error("CPU fallback is disabled in this build; unset PYTORCH_ENABLE_MPS_FALLBACK")
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "0"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from .backend import CorridorKeyBackend
    runtime = Runtime(CorridorKeyBackend(args.upstream), args.cache_mib * 1024 * 1024)
    path = args.socket.expanduser().absolute()
    lock_fd = prepare_socket(path)
    old_umask = os.umask(0o077)
    try:
        server = LocalServer(path, runtime)
        os.chmod(path, 0o600)
    except BaseException:
        os.close(lock_fd)
        raise
    finally:
        os.umask(old_umask)
    def stop(_signum, _frame):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    threading.Thread(target=runtime.load, name="ckmac-model-load", daemon=True).start()
    LOG.info("Listening at %s (MPS only; temporal context: 1 frame)", path)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        path.unlink(missing_ok=True)
        os.close(lock_fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
