"""Versioned, bounded Unix socket protocol; metadata is big endian, pixels LE f32."""
from __future__ import annotations

from dataclasses import dataclass
import socket
import struct

VERSION = 1
REQUEST = struct.Struct(">4s9I")
RESPONSE = struct.Struct(">4s7I")
OP_INFER = 1
OP_HEALTH = 2
MAX_DIMENSION = 8192
MAX_PIXELS = 33_554_432
MAX_PAYLOAD = MAX_PIXELS * 16
MAX_TEXT = 65_536
SPACES = ("srgb", "linear", "rec709_gamma24")


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Request:
    operation: int
    width: int = 0
    height: int = 0
    payload_bytes: int = 0
    flags: int = 0
    hint_quality_milli: int = 0
    despill_milli: int = 0

    @property
    def input_space(self) -> str:
        return SPACES[self.flags & 3]

    @property
    def hint_mode(self) -> str:
        return "source_alpha" if self.flags & 4 else "none"

    def pack(self) -> bytes:
        data = REQUEST.pack(b"CKM1", VERSION, self.operation, self.width,
                            self.height, self.payload_bytes, self.flags,
                            self.hint_quality_milli, self.despill_milli, 0)
        parse_request(data)
        return data


def parse_request(data: bytes) -> Request:
    if len(data) != REQUEST.size:
        raise ProtocolError("Invalid request header length")
    magic, version, op, w, h, n, flags, quality, despill, reserved = REQUEST.unpack(data)
    if magic != b"CKM1" or version != VERSION or reserved:
        raise ProtocolError("Unknown protocol or nonzero reserved field")
    if op == OP_HEALTH:
        if any((w, h, n, flags, quality, despill)):
            raise ProtocolError("Health requests must have zero data fields")
    elif op == OP_INFER:
        if not (1 <= w <= MAX_DIMENSION and 1 <= h <= MAX_DIMENSION):
            raise ProtocolError("Frame dimension outside 1..8192")
        if w * h > MAX_PIXELS or n != w * h * 16:
            raise ProtocolError("Frame payload size is invalid or too large")
        if flags & ~7 or flags & 3 == 3:
            raise ProtocolError("Unsupported inference flags")
        if quality > 1000 or despill > 1000:
            raise ProtocolError("Hint quality and despill must be in 0..1000")
    else:
        raise ProtocolError("Unsupported operation")
    return Request(op, w, h, n, flags, quality, despill)


def recv_exact(connection: socket.socket, count: int) -> bytearray:
    if not 0 <= count <= MAX_PAYLOAD:
        raise ProtocolError("Read size exceeds protocol limit")
    output = bytearray(count)
    view = memoryview(output)
    position = 0
    while position < count:
        received = connection.recv_into(view[position:])
        if not received:
            raise ConnectionError("Peer disconnected before completing the message")
        position += received
    return output


def response_header(status: int, payload_bytes: int, width: int = 0, height: int = 0) -> bytes:
    return RESPONSE.pack(b"CKR1", VERSION, status, width, height, payload_bytes, 0, 0)


def read_response(connection: socket.socket, *, expected_width: int = 0,
                  expected_height: int = 0) -> tuple[int, bytearray]:
    magic, version, status, w, h, n, flags, reserved = RESPONSE.unpack(
        recv_exact(connection, RESPONSE.size))
    if magic != b"CKR1" or version != VERSION or flags or reserved:
        raise ProtocolError("Invalid response header")
    if status:
        if n > MAX_TEXT or w or h:
            raise ProtocolError("Invalid error response")
    elif expected_width or expected_height:
        if (w, h) != (expected_width, expected_height) or n != w * h * 16 or n > MAX_PAYLOAD:
            raise ProtocolError("Response dimensions do not match the requested frame")
    elif w or h or n > MAX_TEXT:
        raise ProtocolError("Invalid health response")
    return status, recv_exact(connection, n)
