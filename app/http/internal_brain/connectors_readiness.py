from __future__ import annotations

import sqlite3
from contextlib import closing

from app.brain.operator_api import OperatorAPIError, connector_readiness_projection
from app.brain.operator_auth import INTERNAL_READ_PERMISSION
from app.brain.storage import SQLiteConfigStore, SQLiteRunLedger, init_schema

from .common import (
    _authorize_internal_operator,
    _internal_brain_db_path,
    _internal_error,
    _internal_principal_or_error,
    _internal_success,
)


def register_connector_readiness_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/connectors/readiness")
    def internal_brain_connector_readiness(business_id: str):
        auth_error = _authorize_internal_operator(business_id)
        if auth_error is not None:
            return auth_error
        _principal, permission_error = _internal_principal_or_error(
            business_id,
            INTERNAL_READ_PERMISSION,
            audit_denial=True,
        )
        if permission_error is not None:
            return permission_error
        try:
            with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
                init_schema(conn)
                business = SQLiteConfigStore(conn).load_business_config(business_id)
                if business is None:
                    return _internal_error(
                        business_id,
                        "business_config_not_found",
                        "Business config not found.",
                        status_code=404,
                    )
                data = connector_readiness_projection(business, SQLiteRunLedger(conn))
                return _internal_success(business_id, data)
        except OperatorAPIError as exc:
            return _internal_error(business_id, exc.code, exc.message, status_code=exc.status_code)
