"""Per-event capability scoping.

A non-admin member's financial powers are granted per event through
EventRoleAssignment flags:
  - can_collect → collection (initiate payments, slips, handover submit) for that event
  - can_cashier → treasurer/cashier powers (view/approve payments, expenses,
                  handovers) for that event

Admin / super_admin are unrestricted: the helpers return ``None`` for them,
which every scoped query reads as "no event filter — all org events".

One DB query per request loads both capability sets; results are cached on
flask.g so repeated checks within a request are free.
"""
from flask import g
from flask_jwt_extended import get_jwt, get_jwt_identity

from ..models.user import RoleEnum
from ..models.committee_role import EventRoleAssignment

_ADMIN_ROLES = (RoleEnum.admin.value, RoleEnum.super_admin.value)


def _load_capabilities(user_id: int) -> dict[str, set[int]]:
    """{'collect': {event_ids}, 'cashier': {event_ids}} for a user, cached per request."""
    cache = getattr(g, "_cap_evt_cache", None)
    if cache is None:
        cache = {}
        g._cap_evt_cache = cache
    if user_id in cache:
        return cache[user_id]

    collect: set[int] = set()
    cashier: set[int] = set()
    rows = (
        EventRoleAssignment.query
        .with_entities(
            EventRoleAssignment.event_id,
            EventRoleAssignment.can_collect,
            EventRoleAssignment.can_cashier,
        )
        .filter(EventRoleAssignment.user_id == user_id)
        .all()
    )
    for event_id, can_collect, can_cashier in rows:
        if can_collect:
            collect.add(event_id)
        if can_cashier:
            cashier.add(event_id)

    result = {"collect": collect, "cashier": cashier}
    cache[user_id] = result
    return result


def _current_role_and_id() -> tuple[str | None, int | None]:
    claims = get_jwt()
    role = claims.get("role")
    try:
        uid = int(get_jwt_identity())
    except (TypeError, ValueError):
        uid = None
    return role, uid


def capability_event_ids(capability: str) -> set[int] | None:
    """Event ids where the current user holds ``capability`` ('collect' | 'cashier').

    Returns ``None`` for admin / super_admin (unrestricted — all org events).
    Returns a (possibly empty) set for everyone else.
    """
    role, uid = _current_role_and_id()
    if role in _ADMIN_ROLES:
        return None
    if uid is None:
        return set()
    return set(_load_capabilities(uid)[capability])


def is_unrestricted() -> bool:
    """True when the current user sees all org events (admin / super_admin)."""
    role, _ = _current_role_and_id()
    return role in _ADMIN_ROLES


def event_in_scope(capability: str, event_id: int | None) -> bool:
    """Whether the current user may act on ``event_id`` under ``capability``.

    Admin → always True. Others → only if the event is in their capability set.
    A ``None`` event_id (non-event resource) is allowed only for admin.
    """
    ids = capability_event_ids(capability)
    if ids is None:
        return True
    if event_id is None:
        return False
    return event_id in ids
