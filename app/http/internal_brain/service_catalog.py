from __future__ import annotations

from app.brain.operator_auth import INTERNAL_READ_PERMISSION
from app.brain.service_catalog import service_catalog_manifest

from .common import (
    _authorize_internal_operator,
    _gateway_policy_or_error,
    _internal_principal_or_error,
    _internal_success,
)


SERVICE_CATALOG_ROUTE_KEY = "operator_api.service_catalog.read"


def register_service_catalog_routes(app):
    @app.get("/internal/brain/businesses/<business_id>/service-catalog")
    def internal_brain_service_catalog(business_id: str):
        auth_error = _authorize_internal_operator(business_id)
        if auth_error is not None:
            return auth_error
        principal, permission_error = _internal_principal_or_error(
            business_id,
            INTERNAL_READ_PERMISSION,
            audit_denial=True,
        )
        if permission_error is not None:
            return permission_error
        assert principal is not None
        _decision, gateway_error = _gateway_policy_or_error(
            route_key=SERVICE_CATALOG_ROUTE_KEY,
            business_id=business_id,
            principal=principal,
        )
        if gateway_error is not None:
            return gateway_error
        return _internal_success(business_id, service_catalog_manifest())
