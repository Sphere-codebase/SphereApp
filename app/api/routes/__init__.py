"""API routers."""

from app.api.routes.admin import router as admin_router
from app.api.routes.admin_claims import router as admin_claims_router
from app.api.routes.admin_diagnosis_codes import router as admin_diagnosis_codes_router
from app.api.routes.admin_insurance_companies import router as admin_insurance_companies_router
from app.api.routes.admin_mcp_codes import router as admin_mcp_codes_router
from app.api.routes.admin_patients import router as admin_patients_router
from app.api.routes.audit_logs import admin_router as admin_audit_logs_router
from app.api.routes.auth import router as auth_router
from app.api.routes.ai_history import router as ai_history_router
from app.api.routes.chat import router as chat_router
from app.api.routes.chat_actions import router as chat_actions_router
from app.api.routes.clinic_admin import router as clinic_admin_router
from app.api.routes.chat_sessions import router as chat_sessions_router
from app.api.routes.codes import router as codes_router
from app.api.routes.claims import router as claims_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.files import router as files_router
from app.api.routes.health import router as health_router
from app.api.routes.insurance_companies import router as insurance_companies_router
from app.api.routes.insurance_rules import router as insurance_rules_router
from app.api.routes.platform_admin import router as platform_admin_router
from app.api.routes.patients import router as patients_router
from app.api.routes.policy_links import router as policy_links_router

__all__ = [
    "admin_router",
    "admin_claims_router",
    "admin_diagnosis_codes_router",
    "admin_insurance_companies_router",
    "admin_mcp_codes_router",
    "admin_patients_router",
    "admin_audit_logs_router",
    "ai_history_router",
    "auth_router",
    "chat_router",
    "chat_actions_router",
    "clinic_admin_router",
    "chat_sessions_router",
    "codes_router",
    "claims_router",
    "dashboard_router",
    "files_router",
    "health_router",
    "insurance_companies_router",
    "insurance_rules_router",
    "platform_admin_router",
    "patients_router",
    "policy_links_router",
]
