"""Unified audit logging service."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.logging import request_id_ctx
from app.db.id_utils import next_id
from app.db.models import AuditLog, User
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditContext:
    request_id: str | None = None
    ip: str | None = None
    user_agent: str | None = None

    @classmethod
    def from_request(cls, request: Request) -> AuditContext:
        request_id = getattr(request.state, "request_id", None) or request.headers.get(
            "x-request-id"
        )
        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        return cls(request_id=request_id, ip=ip, user_agent=user_agent)


class AuditLogger:
    def __init__(
        self,
        db: Session,
        *,
        context: AuditContext | None = None,
        fail_open: bool = True,
    ) -> None:
        self._db = db
        self._context = context or AuditContext()
        self._fail_open = fail_open

    def log_event(
        self,
        *,
        action: str,
        entity: str,
        actor: User | None = None,
        entity_id: str | int | None = None,
        clinic_id: int | None = None,
        target_clinic_id: int | None = None,
        target_user_id: int | None = None,
        diff: dict[str, Any] | None = None,
        scope: str | None = None,
        actor_role: str | None = None,
    ) -> None:
        resolved_actor_role = actor_role or (getattr(actor, "role", None) if actor else None)
        resolved_clinic_id = (
            clinic_id
            or target_clinic_id
            or (getattr(actor, "clinic_id", None) if actor is not None else None)
        )
        if resolved_clinic_id is None:
            self._handle_failure("audit log missing clinic_id action=%s entity=%s", action, entity)
            return

        resolved_scope = scope or (
            "platform" if resolved_actor_role == "platform_staff_admin" else "clinic"
        )
        request_id = self._resolve_request_id()

        try:
            audit_session = self._new_session()
            try:
                log_entry = AuditLog(
                    id=next_id(audit_session, AuditLog),
                    clinic_id=resolved_clinic_id,
                    actor_id=getattr(actor, "id", None) if actor is not None else None,
                    actor_role=resolved_actor_role,
                    action=action,
                    entity=entity,
                    entity_id=str(entity_id) if entity_id is not None else None,
                    diff_json=diff,
                    request_id=request_id,
                    ip=self._context.ip,
                    user_agent=self._context.user_agent,
                    target_clinic_id=target_clinic_id,
                    target_user_id=target_user_id,
                    scope=resolved_scope,
                    created_at=utcnow(),
                )
                audit_session.add(log_entry)
                audit_session.commit()
            finally:
                audit_session.close()
        except Exception as exc:  # pragma: no cover - defensive guard
            self._handle_failure("audit log write failed: %s", exc)

    def _resolve_request_id(self) -> str:
        request_id = self._context.request_id
        if not request_id or request_id == "-":
            request_id = request_id_ctx.get()
        if not request_id or request_id == "-":
            request_id = str(uuid.uuid4())
        return request_id

    def _new_session(self) -> Session:
        bind = self._db.get_bind()
        return Session(bind=bind, expire_on_commit=False)

    def _handle_failure(self, message: str, *args: object) -> None:
        logger.error(message, *args)
        if not self._fail_open:
            raise RuntimeError(message % args)
