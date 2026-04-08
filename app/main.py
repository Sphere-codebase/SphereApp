"""FastAPI application entrypoint.

Codex: implement the app wiring, include routers, middleware, and dependencies.
"""

import logging
import os
import platform
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
    agent_router,
    ai_history_router,
    auth_router,
    chat_actions_router,
    chat_router,
    chat_sessions_router,
    claims_router,
    clinic_admin_router,
    codes_router,
    dashboard_router,
    files_router,
    health_router,
    insurance_companies_router,
    insurance_rules_router,
    patients_router,
    platform_admin_router,
    policy_links_router,
)
from app.core.config import settings
from app.core.exceptions import ClinicBlockedError
from app.core.logging import (
    clinic_blocked_handler,
    configure_logging,
    db_timeout_handler,
    http_exception_handler,
    llm_unavailable_handler,
    retry_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.performance_logging import (
    configure_performance_logging,
    performance_logging_middleware,
    setup_sqlalchemy_query_logging,
)
from app.db.session import engine
from app.llm.client import LLMUnavailable
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.parsers.pdf.remote_client import close_remote_pdf_parser_http_client
from app.parsers.policy.policy_parse import router as policy_parse_router

configure_logging(settings.log_level)
configure_performance_logging()
setup_sqlalchemy_query_logging(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler."""
    logger = logging.getLogger(__name__)
    logger.info(
        "startup env=%s is_vercel=%s is_serverless=%s python=%s cwd=%s",
        settings.env,
        settings.is_vercel,
        settings.is_serverless,
        platform.python_version(),
        os.getcwd(),
    )
    for warning in settings.runtime_warnings():
        logger.warning("runtime configuration issue: %s", warning)

    # Startup: Verify key routes are registered
    target_path = "/api/admin/policy-links/{policy_link_id}/rules"
    all_paths = [route.path for route in app.routes if hasattr(route, "path")]
    if target_path in all_paths:
        logger.info("route registered: %s", target_path)
    else:
        logger.error("route missing: %s", target_path)

    yield

    close_remote_pdf_parser_http_client()


app = FastAPI(title="claims-assistant", lifespan=lifespan)
app.middleware("http")(performance_logging_middleware)

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
