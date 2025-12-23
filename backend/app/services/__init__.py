"""All business logic services."""

from app.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash
from .auth_service import authenticate_user, login
from .user_service import get_user_by_id
from .dashboard_service import get_dashboard_summary, get_dashboard_charts, get_comprehensive_kpis

__all__ = [
    # Auth
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    # Users
    "get_user_by_id",
    "get_user_by_email",
    "create_user",
    # Emission Factors
    "get_active_emission_factor",
    "calculate_co2_with_factor",
    # Materials
    "create_material_token",
    "get_project_tokens",
    "redeem_token",
    "get_project_redemption_rate",
    # MRV Calculations
    "calculate_report_co2",
    "aggregate_reports_co2",
    # Anomalies
    "get_open_anomalies",
    "count_anomalies",
    "flag_anomaly",
    # Whistleblower
    "get_open_cases",
    "close_case",
    # Dashboard
    "get_dashboard_summary",
    "get_dashboard_charts",
]
