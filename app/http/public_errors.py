from __future__ import annotations

from flask import jsonify

from app.brain.security.redaction import redact_text


def public_error_text(error: Exception) -> str:
    return redact_text(str(error))


def public_error_response(payload: dict, status_code: int):
    return jsonify(payload), status_code
