from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models.user import User, RoleEnum
from ...models.committee_role import (
    ClubYear, YearRoleAssignment, EventRoleAssignment, CommitteeOrdering,
    CommitteeRoleEnum, COMMITTEE_ROLE_ORDER,
)

VALID_ROLES = [r.value for r in CommitteeRoleEnum]

ORDER_SCOPE_YEAR = "year"
ORDER_SCOPE_EVENT = "event"
# Members without a manual order sort after ordered ones (then by role, then name).
_UNORDERED = 10 ** 6


def _order_map(org_id: int | None, scope: str, scope_id: int) -> dict[int, int]:
    """user_id -> manual sort_order for a given scope (club year or event)."""
    rows = CommitteeOrdering.query.filter_by(org_id=org_id, scope=scope, scope_id=scope_id).all()
    return {r.user_id: r.sort_order for r in rows}


def _apply_order(org_id: int | None, scope: str, scope_id: int, user_ids: list) -> None:
    """Upsert manual order from an ordered list of user ids (index = position).

    Only ids that are real non-admin members of this org are stored; duplicates
    and unknown ids are ignored. Members omitted from the list keep their row.
    """
    valid_ids = {u.id for u in _non_admin_members(org_id)}
    existing = {
        r.user_id: r
        for r in CommitteeOrdering.query.filter_by(org_id=org_id, scope=scope, scope_id=scope_id).all()
    }
    position = 0
    seen: set[int] = set()
    for raw in user_ids:
        try:
            uid = int(raw)
        except (TypeError, ValueError):
            continue
        if uid not in valid_ids or uid in seen:
            continue
        seen.add(uid)
        row = existing.get(uid)
        if row:
            row.sort_order = position
        else:
            db.session.add(CommitteeOrdering(
                org_id=org_id, scope=scope, scope_id=scope_id, user_id=uid, sort_order=position,
            ))
        position += 1


def _valid_role(role: str) -> bool:
    return role in VALID_ROLES


def _committee_member_dict(a) -> dict:
    """Read-only committee entry — NO phone number is included."""
    role = a.role.value if isinstance(a.role, CommitteeRoleEnum) else a.role
    return {
        "userId":         a.user_id,
        "name":           a.user.name if a.user else "—",
        "memberId":       a.user.member_id if a.user else None,
        "memberCategory": a.user.member_category if a.user else None,
        "role":           role,
    }


def list_committee_years(org_id: int | None) -> list[dict]:
    """Years that have committee assignments (for the member read-only view)."""
    years = (
        ClubYear.query.filter_by(org_id=org_id)
        .order_by(ClubYear.is_current.desc(), ClubYear.created_at.desc(), ClubYear.id.desc())
        .all()
    )
    return [y.to_dict() for y in years]


def list_year_committee(org_id: int | None, club_year_id: int) -> tuple[dict | None, str | None]:
    year = ClubYear.query.filter_by(id=club_year_id, org_id=org_id).first()
    if not year:
        return None, "year not found"
    rows = (
        YearRoleAssignment.query.filter_by(club_year_id=club_year_id)
        .options(joinedload(YearRoleAssignment.user))
        .all()
    )
    members = [_committee_member_dict(a) for a in rows if a.user]
    omap = _order_map(org_id, ORDER_SCOPE_YEAR, club_year_id)
    members.sort(key=lambda m: (
        omap.get(m["userId"], _UNORDERED), COMMITTEE_ROLE_ORDER.get(m["role"], 99), m["name"].lower(),
    ))
    return {"year": year.to_dict(), "members": members}, None


def list_committee_events(org_id: int | None) -> list[dict]:
    """Events that have committee assignments."""
    from ...models.event import Event
    event_ids = [
        r[0] for r in db.session.query(EventRoleAssignment.event_id)
        .filter(EventRoleAssignment.org_id == org_id).distinct().all()
    ]
    if not event_ids:
        return []
    events = Event.query.filter(Event.id.in_(event_ids)).order_by(
        Event.year.desc().nulls_last(), Event.id.desc()
    ).all()
    return [{"id": e.id, "name": e.name, "year": e.year} for e in events]


def list_event_committee(org_id: int | None, event_id: int) -> tuple[dict | None, str | None]:
    event = _event_in_org(org_id, event_id)
    if not event:
        return None, "event not found"
    rows = (
        EventRoleAssignment.query.filter_by(event_id=event_id)
        .options(joinedload(EventRoleAssignment.user))
        .all()
    )
    members = [_committee_member_dict(a) for a in rows if a.user]
    omap = _order_map(org_id, ORDER_SCOPE_EVENT, event_id)
    members.sort(key=lambda m: (
        omap.get(m["userId"], _UNORDERED), COMMITTEE_ROLE_ORDER.get(m["role"], 99), m["name"].lower(),
    ))
    return {
        "event": {"id": event.id, "name": event.name, "year": event.year},
        "members": members,
    }, None


def get_my_roles(org_id: int | None, user_id: int) -> dict:
    """The logged-in member's own committee roles — current club year + per-event."""
    current_year = ClubYear.query.filter_by(org_id=org_id, is_current=True).first()
    year_role = None
    if current_year:
        a = YearRoleAssignment.query.filter_by(club_year_id=current_year.id, user_id=user_id).first()
        if a:
            year_role = {
                "yearLabel": current_year.label,
                "role": a.role.value if isinstance(a.role, CommitteeRoleEnum) else a.role,
            }

    from ...models.event import Event
    event_rows = (
        db.session.query(EventRoleAssignment, Event)
        .join(Event, EventRoleAssignment.event_id == Event.id)
        .filter(EventRoleAssignment.user_id == user_id)
        .order_by(Event.year.desc().nulls_last(), Event.id.desc())
        .all()
    )
    event_roles = [{
        "eventId":   ev.id,
        "eventName": ev.name,
        "role":      a.role.value if isinstance(a.role, CommitteeRoleEnum) else a.role,
        "canCollect": a.can_collect,
    } for a, ev in event_rows]

    return {"yearRole": year_role, "eventRoles": event_roles}


def _non_admin_members(org_id: int | None):
    """Active members of the org, excluding admin/super_admin accounts, ordered by name."""
    return (
        User.query
        .filter(
            User.org_id == org_id,
            User.is_active.is_(True),
            User.role.notin_([RoleEnum.admin, RoleEnum.super_admin]),
        )
        .order_by(User.name.asc())
        .all()
    )


def _member_dict(u: User) -> dict:
    return {"id": u.id, "name": u.name, "phone": u.phone, "memberId": u.member_id,
            "memberCategory": u.member_category}


# ── Club years ───────────────────────────────────────────────────────────────

def list_club_years(org_id: int | None) -> list[dict]:
    years = (
        ClubYear.query
        .filter_by(org_id=org_id)
        .order_by(ClubYear.is_current.desc(), ClubYear.created_at.desc(), ClubYear.id.desc())
        .all()
    )
    return [y.to_dict() for y in years]


def create_club_year(org_id: int | None, label: str) -> tuple[dict | None, str | None]:
    label = (label or "").strip()
    if not label:
        return None, "label is required"
    if ClubYear.query.filter_by(org_id=org_id, label=label).first():
        return None, "a year with this label already exists"

    # The year to copy assignments from — the current one, else the newest.
    source = (
        ClubYear.query.filter_by(org_id=org_id, is_current=True).first()
        or ClubYear.query.filter_by(org_id=org_id)
        .order_by(ClubYear.created_at.desc(), ClubYear.id.desc()).first()
    )

    # New year becomes the current one.
    ClubYear.query.filter_by(org_id=org_id, is_current=True).update({"is_current": False})
    year = ClubYear(org_id=org_id, label=label, is_current=True)
    db.session.add(year)
    db.session.flush()  # need year.id

    if source:
        prev = YearRoleAssignment.query.filter_by(club_year_id=source.id).all()
        for a in prev:
            db.session.add(YearRoleAssignment(
                org_id=org_id, club_year_id=year.id, user_id=a.user_id,
                role=a.role, is_public=a.is_public,
            ))
        # Carry the manual member order over to the new year too.
        for o in CommitteeOrdering.query.filter_by(
            org_id=org_id, scope=ORDER_SCOPE_YEAR, scope_id=source.id,
        ).all():
            db.session.add(CommitteeOrdering(
                org_id=org_id, scope=ORDER_SCOPE_YEAR, scope_id=year.id,
                user_id=o.user_id, sort_order=o.sort_order,
            ))

    db.session.commit()
    return year.to_dict(), None


def set_current_year(org_id: int | None, club_year_id: int) -> tuple[dict | None, str | None]:
    year = ClubYear.query.filter_by(id=club_year_id, org_id=org_id).first()
    if not year:
        return None, "year not found"
    ClubYear.query.filter_by(org_id=org_id, is_current=True).update({"is_current": False})
    year.is_current = True
    db.session.commit()
    return year.to_dict(), None


# ── Year role assignments ────────────────────────────────────────────────────

def list_year_assignments(org_id: int | None, club_year_id: int) -> tuple[dict | None, str | None]:
    year = ClubYear.query.filter_by(id=club_year_id, org_id=org_id).first()
    if not year:
        return None, "year not found"

    assignments = {
        a.user_id: a for a in YearRoleAssignment.query.filter_by(club_year_id=club_year_id).all()
    }
    members = []
    for u in _non_admin_members(org_id):
        a = assignments.get(u.id)
        members.append({
            **_member_dict(u),
            "role":     (a.role.value if a and isinstance(a.role, CommitteeRoleEnum) else (a.role if a else None)),
            "isPublic": a.is_public if a else True,
        })
    omap = _order_map(org_id, ORDER_SCOPE_YEAR, club_year_id)
    members.sort(key=lambda m: (
        omap.get(m["id"], _UNORDERED), COMMITTEE_ROLE_ORDER.get(m["role"], 99), m["name"].lower(),
    ))
    return {"year": year.to_dict(), "members": members}, None


def set_year_assignment(org_id, club_year_id, user_id, role, is_public=True) -> tuple[dict | None, str | None]:
    year = ClubYear.query.filter_by(id=club_year_id, org_id=org_id).first()
    if not year:
        return None, "year not found"
    if not _valid_role(role):
        return None, "invalid role"
    user = User.query.filter_by(id=user_id, org_id=org_id).first()
    if not user or user.role in (RoleEnum.admin, RoleEnum.super_admin):
        return None, "member not found"

    a = YearRoleAssignment.query.filter_by(club_year_id=club_year_id, user_id=user_id).first()
    if a:
        a.role = CommitteeRoleEnum(role)
        if is_public is not None:
            a.is_public = bool(is_public)
    else:
        a = YearRoleAssignment(
            org_id=org_id, club_year_id=club_year_id, user_id=user_id,
            role=CommitteeRoleEnum(role), is_public=bool(is_public),
        )
        db.session.add(a)
    db.session.commit()
    return a.to_dict(), None


def clear_year_assignment(org_id, club_year_id, user_id) -> tuple[bool, str | None]:
    year = ClubYear.query.filter_by(id=club_year_id, org_id=org_id).first()
    if not year:
        return False, "year not found"
    a = YearRoleAssignment.query.filter_by(club_year_id=club_year_id, user_id=user_id).first()
    if a:
        db.session.delete(a)
        db.session.commit()
    return True, None


# ── Event role assignments ───────────────────────────────────────────────────

def _sync_user_can_collect(user_id: int) -> None:
    """TEMPORARY bridge: mirror collect capability from a member's event assignments.

    Collection endpoints are gated two ways: some by User.can_collect (require_collect_capable),
    others by the permission role (e.g. /events/active needs 'payment.initiate'). So while a member
    has 'can collect' on any event we make them a functional collector — set the flag AND switch the
    permission role to `collector` (which carries the collection permissions). When they no longer
    have any collect assignment, revert to the member default role. Replaced by the per-event
    permission resolver in the full restructure.
    """
    has_collect = db.session.query(
        EventRoleAssignment.query.filter_by(user_id=user_id, can_collect=True).exists()
    ).scalar()
    user = User.query.get(user_id)
    if not user or user.role in (RoleEnum.admin, RoleEnum.super_admin):
        return
    user.can_collect = bool(has_collect)
    if has_collect:
        user.role = RoleEnum.collector
    elif user.role == RoleEnum.collector:
        # revert to the member baseline only if we were the ones who set collector
        user.role = RoleEnum.executive


def _event_in_org(org_id, event_id):
    from ...models.event import Event
    return Event.query.filter_by(id=event_id, org_id=org_id).first() if org_id is not None \
        else Event.query.get(event_id)


def list_event_assignments(org_id: int | None, event_id: int) -> tuple[dict | None, str | None]:
    event = _event_in_org(org_id, event_id)
    if not event:
        return None, "event not found"

    assignments = {
        a.user_id: a for a in EventRoleAssignment.query.filter_by(event_id=event_id).all()
    }
    members = []
    for u in _non_admin_members(org_id):
        a = assignments.get(u.id)
        members.append({
            **_member_dict(u),
            "role":       (a.role.value if a and isinstance(a.role, CommitteeRoleEnum) else (a.role if a else None)),
            "canCollect": a.can_collect if a else False,
            "isPublic":   a.is_public if a else True,
        })
    omap = _order_map(org_id, ORDER_SCOPE_EVENT, event_id)
    members.sort(key=lambda m: (
        omap.get(m["id"], _UNORDERED), COMMITTEE_ROLE_ORDER.get(m["role"], 99), m["name"].lower(),
    ))
    return {
        "event": {"id": event.id, "name": event.name, "year": event.year,
                  "status": event.status.value if hasattr(event.status, "value") else event.status},
        "members": members,
    }, None


def set_event_assignment(org_id, event_id, user_id, role, can_collect=False, is_public=True) -> tuple[dict | None, str | None]:
    event = _event_in_org(org_id, event_id)
    if not event:
        return None, "event not found"
    if not _valid_role(role):
        return None, "invalid role"
    user = User.query.filter_by(id=user_id, org_id=org_id).first()
    if not user or user.role in (RoleEnum.admin, RoleEnum.super_admin):
        return None, "member not found"

    a = EventRoleAssignment.query.filter_by(event_id=event_id, user_id=user_id).first()
    if a:
        a.role = CommitteeRoleEnum(role)
        a.can_collect = bool(can_collect)
        if is_public is not None:
            a.is_public = bool(is_public)
    else:
        a = EventRoleAssignment(
            org_id=org_id, event_id=event_id, user_id=user_id,
            role=CommitteeRoleEnum(role), can_collect=bool(can_collect), is_public=bool(is_public),
        )
        db.session.add(a)
    db.session.flush()
    _sync_user_can_collect(user_id)
    db.session.commit()
    return a.to_dict(), None


def clear_event_assignment(org_id, event_id, user_id) -> tuple[bool, str | None]:
    event = _event_in_org(org_id, event_id)
    if not event:
        return False, "event not found"
    a = EventRoleAssignment.query.filter_by(event_id=event_id, user_id=user_id).first()
    if a:
        db.session.delete(a)
        db.session.flush()
        _sync_user_can_collect(user_id)
        db.session.commit()
    return True, None


# ── Manual ordering ──────────────────────────────────────────────────────────

def reorder_year_assignments(org_id, club_year_id, user_ids) -> tuple[bool, str | None]:
    year = ClubYear.query.filter_by(id=club_year_id, org_id=org_id).first()
    if not year:
        return False, "year not found"
    _apply_order(org_id, ORDER_SCOPE_YEAR, club_year_id, user_ids or [])
    db.session.commit()
    return True, None


def reorder_event_assignments(org_id, event_id, user_ids) -> tuple[bool, str | None]:
    event = _event_in_org(org_id, event_id)
    if not event:
        return False, "event not found"
    _apply_order(org_id, ORDER_SCOPE_EVENT, event_id, user_ids or [])
    db.session.commit()
    return True, None
