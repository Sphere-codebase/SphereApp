"""API routers."""

from app.api.routes.admin import router as admin_router
from app.api.routes.admin_agencies import router as admin_agencies_router
from app.api.routes.admin_policy_links import router as admin_policy_links_router
from app.api.routes.admin_procedure_codes import router as admin_procedure_codes_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.chat_sessions import router as chat_sessions_router
from app.api.routes.claims import router as claims_router
from app.api.routes.health import router as health_router
from app.api.routes.patients import router as patients_router

__all__ = [
    "admin_router",
    "admin_agencies_router",
    "admin_policy_links_router",
    "admin_procedure_codes_router",
    "auth_router",
    "chat_router",
    "chat_sessions_router",
    "claims_router",
    "health_router",
    "patients_router",
]
