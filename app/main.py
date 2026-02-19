"""FastAPI application entrypoint.

Codex: implement the app wiring, include routers, middleware, and dependencies.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from tenacity import RetryError

from app.api.routes import (
    admin_audit_logs_router,
    admin_claims_router,
    admin_diagnosis_codes_router,
    admin_insurance_companies_router,
    admin_mcp_codes_router,
    admin_patients_router,
    admin_router,
    auth_router,
    ai_history_router,
    agent_router,
    chat_router,
    chat_actions_router,
    clinic_admin_router,
    chat_sessions_router,
    codes_router,
    claims_router,
    dashboard_router,
    files_router,
    health_router,
    insurance_companies_router,
    insurance_rules_router,
    platform_admin_router,
    patients_router,
    policy_links_router,
)
from app.core.config import settings
from app.core.logging import (
    configure_logging,
    clinic_blocked_handler,
    db_timeout_handler,
    http_exception_handler,
    llm_unavailable_handler,
    retry_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.security import ClinicBlockedError
from app.llm.client import LLMUnavailable
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.parsers.policy.policy_parse import router as policy_parse_router

configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler."""
    # Startup: Verify key routes are registered
    logger = logging.getLogger(__name__)
    target_path = "/api/admin/policy-links/{policy_link_id}/rules"
    all_paths = [route.path for route in app.routes if hasattr(route, "path")]
    if target_path in all_paths:
        logger.info(f"Route registered: {target_path}")
    else:
        logger.error(f"Route MISSING: {target_path}")

    yield

    # Shutdown: (None currently)


app = FastAPI(title="claims-assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(RequestLoggingMiddleware)

app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(ClinicBlockedError, clinic_blocked_handler)  # type: ignore[arg-type]
app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,  # type: ignore[arg-type]
)
app.add_exception_handler(LLMUnavailable, llm_unavailable_handler)  # type: ignore[arg-type]
app.add_exception_handler(RetryError, retry_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(SQLAlchemyTimeoutError, db_timeout_handler)  # type: ignore[arg-type]
app.add_exception_handler(
    Exception, lambda request, exc: unhandled_exception_handler(request, exc, settings)
)

# Admin routers
app.include_router(admin_router)
app.include_router(admin_audit_logs_router)
app.include_router(admin_claims_router)
app.include_router(admin_diagnosis_codes_router)
app.include_router(admin_insurance_companies_router)
app.include_router(admin_mcp_codes_router)
app.include_router(admin_patients_router)
app.include_router(policy_links_router)

# Core features
app.include_router(auth_router)
app.include_router(ai_history_router)
app.include_router(chat_router)
app.include_router(chat_actions_router)
app.include_router(clinic_admin_router)
app.include_router(chat_sessions_router)
app.include_router(codes_router)
app.include_router(dashboard_router)
app.include_router(files_router)
app.include_router(patients_router)
app.include_router(insurance_companies_router)
app.include_router(insurance_rules_router)
app.include_router(platform_admin_router)
app.include_router(claims_router)
app.include_router(health_router)
app.include_router(agent_router)
app.include_router(policy_parse_router)
