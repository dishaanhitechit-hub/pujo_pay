"""Effective-permission resolver.

Permissions are derived from, in union (additive — never removes access):
  1. a BASELINE every authenticated member gets,
  2. the member's legacy `role` grants (keeps all existing behaviour working),
  3. their committee role(s) — current club year + any event role,
  4. collection capability (event `can_collect`, mirrored to User.can_collect),
  5. admin / super_admin get everything.

Event role perms take priority conceptually; since this is a union they simply add.
"""
from flask import g

from ..models.role_permission import PERMISSION_KEYS
from ..models.user import RoleEnum
from ..models.committee_role import CommitteeRoleEnum

ALL_PERMISSIONS = frozenset(PERMISSION_KEYS)

# Every authenticated member gets these (member view pages are otherwise auth-only).
BASELINE_PERMISSIONS = frozenset({"dashboard.view"})

# Extra permissions granted by a committee role (year or event scope).
COMMITTEE_ROLE_PERMISSIONS: dict[str, frozenset] = {
    CommitteeRoleEnum.treasurer.value:  frozenset({"expense.manage", "handover.manage", "payment.view_receipt"}),
    CommitteeRoleEnum.accountant.value: frozenset({"payment.view_receipt", "expense.manage"}),
    # chairman / president / vice_president / secretary / junior_secretary /
    # advisory_member / member → baseline only
}

# Granted to anyone with collection capability (event can_collect).
COLLECT_PERMISSIONS = frozenset({
    "payment.initiate", "payment.confirm", "payment.view_receipt",
    "collector.view_own", "token.generate",
})


def _committee_role_perms(user_id: int) -> frozenset:
    from ..models.committee_role import ClubYear, YearRoleAssignment, EventRoleAssignment
    perms: set[str] = set()

    current_year = ClubYear.query.filter_by(is_current=True).first()
    if current_year:
        ya = YearRoleAssignment.query.filter_by(club_year_id=current_year.id, user_id=user_id).first()
        if ya:
            role = ya.role.value if isinstance(ya.role, CommitteeRoleEnum) else ya.role
            perms |= COMMITTEE_ROLE_PERMISSIONS.get(role, frozenset())

    for ea in EventRoleAssignment.query.filter_by(user_id=user_id).all():
        role = ea.role.value if isinstance(ea.role, CommitteeRoleEnum) else ea.role
        perms |= COMMITTEE_ROLE_PERMISSIONS.get(role, frozenset())
        if ea.can_collect:
            perms |= COLLECT_PERMISSIONS

    return frozenset(perms)


def effective_permissions(user_id: int, role: str | None) -> frozenset:
    """Full permission set for a user. Cached per-request in flask.g."""
    cache = getattr(g, "_eff_perms_cache", None)
    if cache is None:
        cache = {}
        g._eff_perms_cache = cache
    if user_id in cache:
        return cache[user_id]

    if role in (RoleEnum.admin.value, RoleEnum.super_admin.value):
        cache[user_id] = ALL_PERMISSIONS
        return ALL_PERMISSIONS

    from .permissions import _grants_for_role
    from ..models.user import User

    perms = set(BASELINE_PERMISSIONS)
    if role:
        perms |= _grants_for_role(role)          # legacy role grants (keeps existing working)
    perms |= _committee_role_perms(user_id)      # committee role grants

    user = User.query.get(user_id)
    if user and user.can_collect:
        perms |= COLLECT_PERMISSIONS

    result = frozenset(perms)
    cache[user_id] = result
    return result
