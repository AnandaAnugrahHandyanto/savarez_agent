from __future__ import annotations

import pytest

from gateway.calls.native.simplex_session_codec import (
    compress_json,
    decompress_json,
    decode_webrtc_session,
    encode_webrtc_session,
)


def test_compress_json_matches_ec2_simplex_bridge_vector():
    sdp = {"type": "offer", "sdp": "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"}

    compressed = compress_json(sdp)

    assert (
        compressed
        == "N4IgLgngDgpiBcID2AzFMBOIA0IDOAJlAiAG4C8ADADobUB2AtuQIYCuBAlkgAQCcPAKoARAAoB6ACoAZAMriASpImyAggDVRAMR4BGfbQYgAvkA"
    )
    assert decompress_json(compressed) == sdp


def test_encode_webrtc_session_roundtrips_sdp_and_ice_candidates():
    sdp = {"type": "answer", "sdp": "v=0\r\na=ice-ufrag:test\r\n"}
    ice = [
        {
            "candidate": "candidate:1 1 udp 2113937151 192.168.1.1 5000 typ host",
            "sdpMid": "0",
        }
    ]

    encoded = encode_webrtc_session(sdp, ice)
    decoded_sdp, decoded_ice = decode_webrtc_session(encoded)

    assert set(encoded) == {"rtcSession", "rtcIceCandidates"}
    assert decoded_sdp == sdp
    assert decoded_ice == ice


def test_decompress_json_rejects_invalid_payload():
    with pytest.raises(ValueError, match="Failed to decompress"):
        decompress_json("not-valid-lzstring-data")
