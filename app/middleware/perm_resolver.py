"""Effective-permission resolver.

Model (post committee-capability restructure):
  * admin / super_admin           → every permission.
  * every other authenticated user → a fixed BASELINE, plus capability grants
    derived purely from their per-event flags:
      - can_collect on any event  → COLLECT_PERMISSIONS
      - can_cashier on any event  → CASHIER_PERMISSIONS

Committee roles (chairman … treasurer … member) and the legacy ``User.role``
grants no longer confer any permission — roles are titles only. The *gate*
(require_permission) opens the screen when the user holds a capability on at
least one event; the per-event data scoping (see middleware/event_scope.py)
then limits what they can see or act on to exactly those events.
"""
from flask import g

from ..models.role_permission import PERMISSION_KEYS
from ..models.user import RoleEnum

ALL_PERMISSIONS = frozenset(PERMISSION_KEYS)

# Every authenticated member gets these (member view pages are otherwise auth-only).
BASELINE_PERMISSIONS = frozenset({"dashboard.view"})

# Granted to anyone with collection capability on at least one event.
COLLECT_PERMISSIONS = frozenset({
    "payment.initiate", "payment.confirm", "payment.view_receipt",
    "collector.view_own", "token.generate",
})

# Granted to anyone with cashier capability on at least one event — the old
# treasurer/cashier powers (approve + view payments, manage expenses/handovers).
CASHIER_PERMISSIONS = frozenset({
    "payment.view_all", "payment.view_receipt", "payment.confirm",
    "expense.manage", "handover.manage",
})

_ADMIN_ROLES = (RoleEnum.admin.value, RoleEnum.super_admin.value)


def effective_permissions(user_id: int, role: str | None) -> frozenset:
    """Full permission set for a user. Cached per-request in flask.g."""
    cache = getattr(g, "_eff_perms_cache", None)
    if cache is None:
        cache = {}
        g._eff_perms_cache = cache
    if user_id in cache:
        return cache[user_id]

    if role in _ADMIN_ROLES:
        cache[user_id] = ALL_PERMISSIONS
        return ALL_PERMISSIONS

    from .event_scope import _load_capabilities

    perms = set(BASELINE_PERMISSIONS)
    caps = _load_capabilities(user_id)
    if caps["collect"]:
        perms |= COLLECT_PERMISSIONS
    if caps["cashier"]:
        perms |= CASHIER_PERMISSIONS

    result = frozenset(perms)
    cache[user_id] = result
    return result
