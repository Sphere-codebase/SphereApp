"""Centralized authorization policy for RBAC + tenancy."""

from __future__ import annotations

from enum import Enum
from typing import Any

from sqlalchemy.sql.elements import ColumnElement

from app.db.models import User


class Role(str, Enum):
    DOCTOR = "doctor"
    CHIEF_DOCTOR = "chief_doctor"
    CLINIC_ADMIN = "clinic_admin"
    PLATFORM_STAFF_ADMIN = "platform_staff_admin"


class Action(str, Enum):
    LIST = "list"
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class Resource(str, Enum):
    CLAIM = "claim"
    PATIENT = "patient"
    CHAT_SESSION = "chat_session"
    CHAT_MESSAGE = "chat_message"
    AUDIT_LOG = "audit_log"
    ADMIN_DIRECTORY = "admin_directory"


def role_for(user: User) -> Role:
    try:
        return Role(user.role)
    except Exception:
        return Role.DOCTOR


def is_platform_staff_admin(user: User) -> bool:
    return role_for(user) == Role.PLATFORM_STAFF_ADMIN


def is_platform_admin(user: User) -> bool:
    return role_for(user) == Role.PLATFORM_STAFF_ADMIN


def can(user: User, action: Action, resource: Resource, record: Any | None = None) -> bool:
    role = role_for(user)

    if resource == Resource.ADMIN_DIRECTORY:
        return role == Role.PLATFORM_STAFF_ADMIN

    if resource == Resource.CLAIM:
        return _can_claim(user, role, action, record)

    if resource == Resource.PATIENT:
        return _can_patient(user, role, action, record)

    if resource in {Resource.CHAT_SESSION, Resource.CHAT_MESSAGE}:
        return _can_chat(user, role, action, record)

    if resource == Resource.AUDIT_LOG:
        return _can_audit(user, role, action, record)

    return False


def _same_clinic(user: User, record: Any | None) -> bool:
    return record is not None and getattr(record, "clinic_id", None) == user.clinic_id


def _can_claim(user: User, role: Role, action: Action, record: Any | None) -> bool:
    if role == Role.PLATFORM_STAFF_ADMIN:
        role = Role.CLINIC_ADMIN

    if action in {Action.LIST, Action.READ}:
        if record is None:
            return True
        if not _same_clinic(user, record):
            return False
        if role == Role.DOCTOR:
            return getattr(record, "doctor_id", None) == user.id
        return True

    if action == Action.CREATE:
        return role in {Role.DOCTOR, Role.CHIEF_DOCTOR, Role.CLINIC_ADMIN}

    if action == Action.UPDATE:
        if record is None or not _same_clinic(user, record):
            return False
        if role == Role.DOCTOR:
            return getattr(record, "doctor_id", None) == user.id
        return role in {Role.CHIEF_DOCTOR, Role.CLINIC_ADMIN}

    if action == Action.DELETE:
        if record is None or not _same_clinic(user, record):
            return False
        if role == Role.DOCTOR:
            return getattr(record, "doctor_id", None) == user.id
        return role == Role.CLINIC_ADMIN

    return False


def _can_patient(user: User, role: Role, action: Action, record: Any | None) -> bool:
    if role == Role.PLATFORM_STAFF_ADMIN:
        role = Role.CLINIC_ADMIN

    if action in {Action.LIST, Action.READ}:
        if record is None:
            return True
        if not _same_clinic(user, record):
            return False
        if role == Role.DOCTOR:
            return getattr(record, "doctor_id", None) == user.id
        return True

    if action in {Action.CREATE, Action.UPDATE}:
        if role == Role.DOCTOR:
            return True
        return role in {Role.CHIEF_DOCTOR, Role.CLINIC_ADMIN}

    if action == Action.DELETE:
        if record is None or not _same_clinic(user, record):
            return False
        if role == Role.DOCTOR:
            return getattr(record, "doctor_id", None) == user.id
        return role == Role.CLINIC_ADMIN

    return False


def _can_chat(user: User, role: Role, action: Action, record: Any | None) -> bool:
    if role == Role.PLATFORM_STAFF_ADMIN:
        role = Role.CLINIC_ADMIN

    if action in {Action.LIST, Action.READ, Action.CREATE, Action.UPDATE, Action.DELETE}:
        if record is None:
            return True
        if not _same_clinic(user, record):
            return False
        return getattr(record, "doctor_id", None) == user.id

    return False


def _can_audit(user: User, role: Role, action: Action, record: Any | None) -> bool:
    if role == Role.PLATFORM_STAFF_ADMIN:
        role = Role.CLINIC_ADMIN
    if action in {Action.LIST, Action.READ}:
        if record is None:
            return True
        return _same_clinic(user, record)
    return False


def claim_scope_filters(user: User, model) -> list[ColumnElement[bool]]:
    role = role_for(user)
    filters: list[ColumnElement[bool]] = [model.clinic_id == user.clinic_id]
    if role == Role.DOCTOR:
        filters.append(model.doctor_id == user.id)
    return filters


def patient_scope_filters(user: User, model) -> list[ColumnElement[bool]]:
    role = role_for(user)
    filters: list[ColumnElement[bool]] = [model.clinic_id == user.clinic_id]
    if role == Role.DOCTOR:
        filters.append(model.doctor_id == user.id)
    return filters


def chat_scope_filters(user: User, model) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [
        model.clinic_id == user.clinic_id,
        model.doctor_id == user.id,
    ]
    return filters


def audit_scope_filters(user: User, model) -> list[ColumnElement[bool]]:
    return [model.clinic_id == user.clinic_id]
