"""WhatsApp native-location directive parsing.

This module is shared by both the gateway WhatsApp adapter and the standalone
send_message tool so the LOCATION contract evolves in exactly one place.
"""

from __future__ import annotations

from typing import TypedDict

_LOCATION_PREFIX = "LOCATION:"


class WhatsAppLocationPayload(TypedDict, total=False):
    """JSON payload fields accepted by the WhatsApp bridge location endpoint."""

    latitude: float
    longitude: float
    name: str
    address: str


def parse_whatsapp_location_directive(content: str | None) -> WhatsAppLocationPayload | None:
    """Parse a full-message WhatsApp native location directive.

    Supported format:
        LOCATION:<lat>,<lon>|optional name|optional address

    The directive must begin the whole stripped message. That keeps ordinary
    prose containing the word ``LOCATION:`` from being treated as a native send.
    """
    stripped = (content or "").strip()
    if not stripped.startswith(_LOCATION_PREFIX):
        return None

    body = stripped[len(_LOCATION_PREFIX):]
    parts = body.split("|", 2)
    coord_text = parts[0].strip()
    if "," not in coord_text:
        raise ValueError("LOCATION directive must use '<latitude>,<longitude>'")

    lat_text, lon_text = [piece.strip() for piece in coord_text.split(",", 1)]
    try:
        latitude = float(lat_text)
        longitude = float(lon_text)
    except ValueError as exc:
        raise ValueError("LOCATION directive latitude/longitude must be numeric") from exc

    if not (-90 <= latitude <= 90):
        raise ValueError("LOCATION directive latitude must be between -90 and 90")
    if not (-180 <= longitude <= 180):
        raise ValueError("LOCATION directive longitude must be between -180 and 180")

    location: WhatsAppLocationPayload = {
        "latitude": latitude,
        "longitude": longitude,
    }
    if len(parts) > 1 and parts[1].strip():
        location["name"] = parts[1].strip()
    if len(parts) > 2 and parts[2].strip():
        location["address"] = parts[2].strip()
    return location
