"""Wire-format checks only. These tests never load CorridorKey or exercise MPS."""
from __future__ import annotations

import socket
import struct
import threading

import pytest

from ckmac.protocol import (
    MAX_DIMENSION, MAX_PAYLOAD, MAX_PIXELS, MAX_TEXT, OP_HEALTH, OP_INFER,
    REQUEST, RESPONSE, ProtocolError, Request, parse_request, read_response,
    recv_exact, response_header,
)


def raw_request(**overrides):
    values = dict(magic=b"CKM1", version=1, op=OP_INFER, width=2, height=1,
                  count=32, flags=0, quality=750, despill=200, reserved=0)
    values.update(overrides)
    return REQUEST.pack(*values.values())


def test_request_has_exact_network_endian_layout_and_round_trips():
    request = Request(OP_INFER, 2, 1, 32, 6, 750, 200)
    wire = request.pack()
    assert wire == struct.pack(">4s9I", b"CKM1", 1, 1, 2, 1, 32, 6, 750, 200, 0)
    assert len(wire) == 40
    assert parse_request(wire) == request
    assert request.input_space == "rec709_gamma24"
    assert request.hint_mode == "source_alpha"


@pytest.mark.parametrize("flags,space,hint", [
    (0, "srgb", "none"), (1, "linear", "none"),
    (2, "rec709_gamma24", "none"), (4, "srgb", "source_alpha"),
    (5, "linear", "source_alpha"), (6, "rec709_gamma24", "source_alpha"),
])
def test_all_supported_flag_combinations(flags, space, hint):
    request = parse_request(raw_request(flags=flags))
    assert (request.input_space, request.hint_mode) == (space, hint)


@pytest.mark.parametrize("overrides", [
    {"magic": b"nope"}, {"version": 2}, {"reserved": 1}, {"op": 99},
    {"width": 0}, {"height": 0}, {"width": MAX_DIMENSION + 1},
    {"height": MAX_DIMENSION + 1}, {"count": 31}, {"count": 33},
    {"width": 8192, "height": 8192, "count": 8192 * 8192 * 16},
    {"flags": 3}, {"flags": 7}, {"flags": 8}, {"flags": 0xFFFFFFFF},
    {"quality": 1001}, {"despill": 1001},
])
def test_malformed_request_rejected_before_payload_read(overrides):
    with pytest.raises(ProtocolError):
        parse_request(raw_request(**overrides))


@pytest.mark.parametrize("size", [0, 1, 39, 41, 1024])
def test_wrong_header_length_rejected(size):
    with pytest.raises(ProtocolError, match="header length"):
        parse_request(b"x" * size)


def test_health_has_no_payload_or_inference_settings():
    assert parse_request(Request(OP_HEALTH).pack()) == Request(OP_HEALTH)
    for field in ("width", "height", "payload_bytes", "flags",
                  "hint_quality_milli", "despill_milli"):
        with pytest.raises(ProtocolError, match="zero data fields"):
            Request(OP_HEALTH, **{field: 1}).pack()


def test_largest_accepted_frame_boundary():
    request = Request(OP_INFER, 8192, 4096, MAX_PAYLOAD)
    assert request.width * request.height == MAX_PIXELS
    assert parse_request(request.pack()) == request


def test_recv_exact_handles_fragmented_data_and_eof_without_hanging():
    reader, writer = socket.socketpair()
    reader.settimeout(2)
    writer.settimeout(2)
    try:
        def send():
            for block in (b"C", b"KM", b"1abcdefgh"):
                writer.sendall(block)
            writer.shutdown(socket.SHUT_WR)
        thread = threading.Thread(target=send, daemon=True)
        thread.start()
        assert recv_exact(reader, 12) == b"CKM1abcdefgh"
        with pytest.raises(ConnectionError, match="disconnected"):
            recv_exact(reader, 1)
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert recv_exact(reader, 0) == b""
        for count in (-1, MAX_PAYLOAD + 1):
            with pytest.raises(ProtocolError):
                recv_exact(reader, count)
    finally:
        reader.close()
        writer.close()


def read_one_response(wire, **kwargs):
    reader, writer = socket.socketpair()
    reader.settimeout(2)
    try:
        writer.sendall(wire)
        writer.shutdown(socket.SHUT_WR)
        return read_response(reader, **kwargs)
    finally:
        reader.close()
        writer.close()


def test_response_round_trip_preserves_little_endian_float_pixels():
    pixels = struct.pack("<4f", 0.125, -0.25, 3.0, 0.5)
    status, data = read_one_response(response_header(0, 16, 1, 1) + pixels,
                                     expected_width=1, expected_height=1)
    assert status == 0
    assert data == pixels
    assert len(response_header(0, 16, 1, 1)) == 32


def test_error_response_is_text_and_not_an_image():
    status, data = read_one_response(response_header(1, 4) + b"oops",
                                     expected_width=1920, expected_height=1080)
    assert (status, data) == (1, b"oops")


@pytest.mark.parametrize("values,expected", [
    ((b"BAD!", 1, 0, 0, 0, 0, 0, 0), {}),
    ((b"CKR1", 2, 0, 0, 0, 0, 0, 0), {}),
    ((b"CKR1", 1, 0, 0, 0, 0, 1, 0), {}),
    ((b"CKR1", 1, 0, 0, 0, 0, 0, 1), {}),
    ((b"CKR1", 1, 1, 0, 0, MAX_TEXT + 1, 0, 0), {}),
    ((b"CKR1", 1, 1, 1, 0, 0, 0, 0), {}),
    ((b"CKR1", 1, 0, 0, 0, MAX_TEXT + 1, 0, 0), {}),
    ((b"CKR1", 1, 0, 1, 1, 16, 0, 0), {}),
    ((b"CKR1", 1, 0, 2, 1, 32, 0, 0), {"expected_width": 1, "expected_height": 1}),
    ((b"CKR1", 1, 0, 1, 1, 15, 0, 0), {"expected_width": 1, "expected_height": 1}),
])
def test_bad_response_rejected_without_waiting_for_body(values, expected):
    with pytest.raises(ProtocolError):
        read_one_response(RESPONSE.pack(*values), **expected)
