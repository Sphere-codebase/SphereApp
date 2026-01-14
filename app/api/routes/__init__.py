"""API routers."""

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.chat_sessions import router as chat_sessions_router
from app.api.routes.health import router as health_router

__all__ = [
    "admin_router",
    "auth_router",
    "chat_router",
    "chat_sessions_router",
    "health_router",
]
