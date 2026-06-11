from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any

from flask import request

from app.brain.operator_auth import INTERNAL_READ_PERMISSION
from app.brain.runtime import RuntimeCompileError, compile_business_runtime, runtime_run_metadata
from app.brain.storage import SQLiteConfigStore, init_schema

from .common import (
    _authorize_internal_operator,
    _internal_brain_db_path,
    _internal_error,
    _internal_success,
    _require_internal_header_permission,
)

_ALLOWED_RUNTIME_MODES = {"preview", "forced", "scheduled", "operator_triggered"}


def _compile_preview_run_mode(payload: Any) -> str:
    if payload in (None, ""):
        return "preview"
    if not isinstance(payload, str):
        raise RuntimeCompileError(["run_mode must be a string"])
    candidate = payload.strip() or "preview"
    if candidate not in _ALLOWED_RUNTIME_MODES:
        raise RuntimeCompileError(
            [
                "run_mode must be one of: "
                + ", ".join(sorted(_ALLOWED_RUNTIME_MODES))
            ]
        )
    return candidate


def register_runtime_routes(app):
    @app.post("/internal/brain/businesses/<business_id>/runtime/compile-preview")
    def internal_brain_runtime_compile_preview(business_id: str):
        auth_error = _authorize_internal_operator(business_id)
        if auth_error is not None:
            return auth_error
        permission_error = _require_internal_header_permission(
            business_id,
            INTERNAL_READ_PERMISSION,
            audit_denial=True,
        )
        if permission_error is not None:
            return permission_error

        payload = request.get_json(silent=True)
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return _internal_error(
                business_id,
                "invalid_runtime_compile_preview_payload",
                "runtime compile-preview payload must be a JSON object",
                status_code=400,
            )

        try:
            run_mode = _compile_preview_run_mode(payload.get("run_mode", "preview"))
        except RuntimeCompileError as exc:
            return _internal_error(
                business_id,
                "invalid_runtime_compile_preview_request",
                "; ".join(exc.errors),
                status_code=400,
            )

        with closing(sqlite3.connect(_internal_brain_db_path())) as conn:
            init_schema(conn)
            config_store = SQLiteConfigStore(conn)
            business = config_store.load_business_config(business_id)
            if business is None:
                return _internal_error(
                    business_id,
                    "business_config_not_found",
                    "Business config not found.",
                    status_code=404,
                )
            schedules = config_store.list_schedules(business_id)

        try:
            runtime = compile_business_runtime(
                business,
                schedules=schedules,
                run_mode=run_mode,  # type: ignore[arg-type]
            )
        except RuntimeCompileError as exc:
            return _internal_error(
                business_id,
                "runtime_compile_failed",
                "; ".join(exc.errors),
                status_code=400,
            )

        return _internal_success(
            business_id,
            {
                "runtime": runtime.model_dump(mode="json"),
                "run_metadata": runtime_run_metadata(runtime),
                "validation_errors": [],
            },
        )
