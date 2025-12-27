"""Request-scoped context for audit logging.

This avoids threading request objects through service layers while still allowing
audit logs to capture IP/user-agent/request-id for compliance.
"""

from __future__ import annotations

import contextvars
import uuid


_request_id_var: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar(
    "audit_request_id", default=None
)
_ip_address_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "audit_ip_address", default=None
)
_user_agent_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "audit_user_agent", default=None
)


def set_audit_request_context(
    *,
    request_id: uuid.UUID | None,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    _request_id_var.set(request_id)
    _ip_address_var.set(ip_address)
    _user_agent_var.set(user_agent)


def get_audit_request_id() -> uuid.UUID | None:
    return _request_id_var.get()


def get_audit_ip_address() -> str | None:
    return _ip_address_var.get()


def get_audit_user_agent() -> str | None:
    return _user_agent_var.get()
