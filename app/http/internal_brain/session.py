from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from app.brain.operator_api import *  # noqa: F401,F403
from app.brain.operator_auth import CASE_ACTION_PERMISSION, INTERNAL_READ_PERMISSION, project_internal_operator_session

from .common import (
    _authorize_internal_operator,
    _internal_success,
    _internal_error,
    _internal_principal_or_error,
    _require_internal_header_permission,
    _with_internal_stores,
)


def register_session_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/operator-session")
    def internal_brain_operator_session(business_id: str):
        auth_error = _authorize_internal_operator(business_id)
        if auth_error is not None:
            return auth_error
        principal, permission_error = _internal_principal_or_error(business_id, INTERNAL_READ_PERMISSION)
        if permission_error is not None:
            return permission_error
        assert principal is not None
        return _internal_success(business_id, project_internal_operator_session(principal))
