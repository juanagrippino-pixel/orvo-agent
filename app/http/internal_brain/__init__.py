"""Internal Orvo Brain HTTP routes."""

from .cases_activity import register_case_activity_routes
from .cases_recent import register_case_recent_routes
from .cases_resolution_latency import register_case_resolution_latency_routes
from .cases_stagnation import register_case_stagnation_routes
from .cases_suggested_actions import register_case_suggested_action_routes
from .cases_summary import register_case_summary_routes
from .connectors_readiness import register_connector_readiness_routes
from .dashboard_views import register_dashboard_view_routes
from .operator_audit import register_operator_audit_routes
from .owner_brief import register_owner_brief_routes
from .runs_delivery import register_run_delivery_routes
from .runtime import register_runtime_routes
from .session import register_session_routes
from .workflow_actions import register_case_action_routes


def register_internal_brain_routes(app):
    register_session_routes(app)
    register_connector_readiness_routes(app)
    register_runtime_routes(app)
    register_case_summary_routes(app)
    register_case_resolution_latency_routes(app)
    register_case_stagnation_routes(app)
    register_case_activity_routes(app)
    register_case_recent_routes(app)
    register_case_suggested_action_routes(app)
    register_dashboard_view_routes(app)
    register_owner_brief_routes(app)
    register_operator_audit_routes(app)
    register_run_delivery_routes(app)
    register_case_action_routes(app)
