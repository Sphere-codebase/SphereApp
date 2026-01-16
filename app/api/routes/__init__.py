"""API routers."""

from app.api.routes.admin import router as admin_router
from app.api.routes.admin_claims import router as admin_claims_router
from app.api.routes.admin_diagnosis_codes import router as admin_diagnosis_codes_router
from app.api.routes.admin_insurance_companies import router as admin_insurance_companies_router
from app.api.routes.admin_mcp_codes import router as admin_mcp_codes_router
from app.api.routes.admin_patients import router as admin_patients_router
from app.api.routes.policy_links import router as policy_links_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.chat_sessions import router as chat_sessions_router
from app.api.routes.claims import router as claims_router
from app.api.routes.health import router as health_router
from app.api.routes.patients import router as patients_router

__all__ = [
    "admin_router",
    "admin_claims_router",
    "admin_diagnosis_codes_router",
    "admin_insurance_companies_router",
    "admin_mcp_codes_router",
    "admin_patients_router",
    "policy_links_router",
    "auth_router",
    "chat_router",
    "chat_sessions_router",
    "claims_router",
    "health_router",
    "patients_router",
]
