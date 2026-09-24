# app/admin/security.py
#
# Stateless, signed admin session tokens (HMAC-SHA256). No extra DB table is
# required beyond the existing `admins` table, since revocation isn't needed
# for this internal tool and tokens expire on their own.

import base64
import hashlib
import hmac
import json
import os
import time


ADMIN_SESSION_SECRET = os.getenv(
    "ADMIN_SESSION_SECRET",
    "dev-only-admin-secret-change-me",
)
ADMIN_SESSION_TTL_SECONDS = 8 * 60 * 60  # 8 hours


def _sign(payload: bytes) -> str:
    signature = hmac.new(
        ADMIN_SESSION_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")


def create_admin_token(admin_id: int) -> str:
    payload = {
        "admin_id": admin_id,
        "exp": int(time.time()) + ADMIN_SESSION_TTL_SECONDS,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    signature = _sign(payload_b64.encode("utf-8"))
    return f"{payload_b64}.{signature}"


def verify_admin_token(token: str) -> int | None:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return None

    expected_signature = _sign(payload_b64.encode("utf-8"))
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, json.JSONDecodeError):
        return None

    if payload.get("exp", 0) < time.time():
        return None

    return payload.get("admin_id")
