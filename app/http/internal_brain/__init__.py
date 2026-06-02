"""Internal Orvo Brain HTTP routes."""

from .cases_activity import register_case_activity_routes
from .cases_summary import register_case_summary_routes
from .dashboard_views import register_dashboard_view_routes
from .runs_delivery import register_run_delivery_routes
from .session import register_session_routes


def register_internal_brain_routes(app):
    register_session_routes(app)
    register_case_summary_routes(app)
    register_case_activity_routes(app)
    register_dashboard_view_routes(app)
    register_run_delivery_routes(app)
