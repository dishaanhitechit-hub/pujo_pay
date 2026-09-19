"""
Meetings service — handles Meetings, Invitees, Agenda, Discussions, and Attendance.
All queries use joinedload to avoid N+1 queries.
Attendance window is enforced in IST (Asia/Kolkata).
"""
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models.meeting import Meeting, MeetingInvitee, MeetingStatusEnum, MeetingTypeEnum
from ...models.meeting_agenda_item import MeetingAgendaItem, AgendaItemStatusEnum
from ...models.meeting_discussion import MeetingDiscussion
from ...models.meeting_attendance import MeetingAttendance, MeetingAttendanceDevice
from ...models.user import User

IST = ZoneInfo("Asia/Kolkata")


# ── Helpers ────────────────────────────────────────────────────────────────

def _now_ist() -> datetime:
    return datetime.now(IST)


def _meeting_window(meeting: Meeting) -> tuple[datetime, datetime]:
    """Return (start_dt, end_dt) as IST-aware datetimes."""
    def _parse_time(t_str: str) -> time:
        parts = t_str.split(":")
        h, m = int(parts[0]), int(parts[1])
        return time(h, m)

    start = datetime.combine(meeting.date, _parse_time(meeting.start_time), tzinfo=IST)
    end   = datetime.combine(meeting.date, _parse_time(meeting.end_time),   tzinfo=IST)
    return start, end


def _load_meeting(meeting_id: int) -> Meeting | None:
    return (
        Meeting.query
        .options(
            joinedload(Meeting.creator),
            joinedload(Meeting.event),
        )
        .get(meeting_id)
    )


# ── Admin: Meeting CRUD ────────────────────────────────────────────────────

def list_meetings(
    status: str | None = None,
    event_id: int | None = None,
    page: int = 1,
    per_page: int = 20,
    org_id: int | None = None,
) -> dict:
    q = Meeting.query.options(
        joinedload(Meeting.creator),
        joinedload(Meeting.event),
    )
    if org_id is not None:
        q = q.join(User, Meeting.created_by == User.id).filter(User.org_id == org_id)
    if status:
        q = q.filter(Meeting.status == status)
    if event_id:
        q = q.filter(Meeting.event_id == event_id)

    q = q.order_by(Meeting.date.desc(), Meeting.start_time.desc())
    total   = q.count()
    meetings = q.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "meetings": [m.to_dict() for m in meetings],
        "page":     page,
        "perPage":  per_page,
        "total":    total,
        "pages":    max(1, -(-total // per_page)),
    }


def create_meeting(data: dict, created_by: int) -> tuple[dict | None, str | None]:
    from ...models.event import Event

    event_id = data.get("event_id")
    if event_id:
        if not Event.query.get(event_id):
            return None, "event not found"

    meeting = Meeting(
        title=data["title"].strip(),
        description=(data.get("description") or "").strip() or None,
        date=data["date"],
        start_time=data["start_time"],
        end_time=data["end_time"],
        venue=(data.get("venue") or "").strip() or None,
        meeting_type=MeetingTypeEnum(data.get("meeting_type", "general")),
        status=MeetingStatusEnum(data.get("status", "draft")),
        event_id=event_id,
        created_by=created_by,
    )
    db.session.add(meeting)
    db.session.commit()
    db.session.refresh(meeting)
    return _load_meeting(meeting.id).to_dict(), None


def get_meeting_admin(meeting_id: int) -> dict | None:
    m = _load_meeting(meeting_id)
    return m.to_dict(include_invitees=True) if m else None


def update_meeting(meeting_id: int, data: dict) -> tuple[dict | None, str | None]:
    from ...models.event import Event

    m = Meeting.query.get(meeting_id)
    if not m:
        return None, "meeting not found"

    if "title" in data:        m.title        = data["title"].strip()
    if "description" in data:  m.description  = (data["description"] or "").strip() or None
    if "date" in data:         m.date         = data["date"]
    if "start_time" in data:   m.start_time   = data["start_time"]
    if "end_time" in data:     m.end_time     = data["end_time"]
    if "venue" in data:        m.venue        = (data["venue"] or "").strip() or None
    if "meeting_type" in data: m.meeting_type = MeetingTypeEnum(data["meeting_type"])
    if "status" in data:       m.status       = MeetingStatusEnum(data["status"])
    if "event_id" in data:
        eid = data["event_id"]
        if eid and not Event.query.get(eid):
            return None, "event not found"
        m.event_id = eid

    db.session.commit()
    return _load_meeting(meeting_id).to_dict(), None


def delete_meeting(meeting_id: int) -> str | None:
    m = Meeting.query.get(meeting_id)
    if not m:
        return "meeting not found"
    db.session.delete(m)
    db.session.commit()
    return None


# ── Admin: Invitees ────────────────────────────────────────────────────────

def list_invitees(meeting_id: int) -> list[dict] | None:
    m = Meeting.query.get(meeting_id)
    if not m:
        return None
    rows = (
        MeetingInvitee.query
        .filter_by(meeting_id=meeting_id)
        .options(joinedload(MeetingInvitee.user))
        .all()
    )
    return [r.to_dict() for r in rows]


def add_invitees(meeting_id: int, payload: dict) -> tuple[dict | None, str | None]:
    """
    payload keys:
      - user_ids: list[int]          — specific user IDs (individual)
      - roles: list[str]             — invite all active users with these roles (role_based)
      - invite_all: bool             — invite every active non-admin user (all)
    Deduplicates: only inserts rows that don't already exist.
    """
    m = Meeting.query.get(meeting_id)
    if not m:
        return None, "meeting not found"

    user_ids: set[int] = set()
    invitation_types: dict[int, str] = {}

    if payload.get("invite_all"):
        users = User.query.filter(
            User.is_active == True,
            User.role != "admin",
        ).all()
        for u in users:
            user_ids.add(u.id)
            invitation_types[u.id] = "all"

    if payload.get("roles"):
        for role in payload["roles"]:
            users = User.query.filter(
                User.is_active == True,
                User.role == role,
            ).all()
            for u in users:
                user_ids.add(u.id)
                invitation_types.setdefault(u.id, "role_based")

    for uid in (payload.get("user_ids") or []):
        user_ids.add(uid)
        invitation_types.setdefault(uid, "individual")

    # Verify all user IDs exist
    existing_ids = {u.id for u in User.query.filter(User.id.in_(user_ids)).all()}
    bad = user_ids - existing_ids
    if bad:
        return None, f"user ids not found: {sorted(bad)}"

    # Existing invitees for this meeting
    already = {
        row.user_id
        for row in MeetingInvitee.query.filter_by(meeting_id=meeting_id).all()
    }

    added = 0
    for uid in user_ids:
        if uid not in already:
            db.session.add(MeetingInvitee(
                meeting_id=meeting_id,
                user_id=uid,
                invitation_type=invitation_types.get(uid, "individual"),
            ))
            added += 1

    db.session.commit()
    rows = (
        MeetingInvitee.query
        .filter_by(meeting_id=meeting_id)
        .options(joinedload(MeetingInvitee.user))
        .all()
    )
    return {"added": added, "invitees": [r.to_dict() for r in rows]}, None


def remove_invitee(meeting_id: int, user_id: int) -> str | None:
    row = MeetingInvitee.query.filter_by(meeting_id=meeting_id, user_id=user_id).first()
    if not row:
        return "invitee not found"
    db.session.delete(row)
    db.session.commit()
    return None


# ── Member: meetings ───────────────────────────────────────────────────────

def list_member_meetings(user_id: int) -> list[dict]:
    """Return all meetings where the user has an invitee record."""
    rows = (
        MeetingInvitee.query
        .filter_by(user_id=user_id)
        .options(
            joinedload(MeetingInvitee.meeting).joinedload(Meeting.event),
            joinedload(MeetingInvitee.meeting).joinedload(Meeting.creator),
        )
        .all()
    )
    meetings = [r.meeting for r in rows if r.meeting]
    meetings.sort(key=lambda m: (m.date, m.start_time), reverse=True)
    return [m.to_dict() for m in meetings]


def get_meeting_member(meeting_id: int, user_id: int) -> dict | None:
    """Return meeting detail if the user is invited; None otherwise."""
    inv = MeetingInvitee.query.filter_by(meeting_id=meeting_id, user_id=user_id).first()
    if not inv:
        return None
    m = _load_meeting(meeting_id)
    if not m:
        return None
    return m.to_dict()


# ── Agenda ─────────────────────────────────────────────────────────────────

def list_agenda(meeting_id: int) -> list[dict] | None:
    if not Meeting.query.get(meeting_id):
        return None
    items = (
        MeetingAgendaItem.query
        .filter_by(meeting_id=meeting_id)
        .options(joinedload(MeetingAgendaItem.owner))
        .order_by(MeetingAgendaItem.sort_order)
        .all()
    )
    return [i.to_dict() for i in items]


def create_agenda_item(meeting_id: int, data: dict) -> tuple[dict | None, str | None]:
    if not Meeting.query.get(meeting_id):
        return None, "meeting not found"
    item = MeetingAgendaItem(
        meeting_id=meeting_id,
        title=data["title"].strip(),
        description=(data.get("description") or "").strip() or None,
        sort_order=data.get("sort_order", 0),
        owner_id=data.get("owner_id"),
        status=AgendaItemStatusEnum(data.get("status", "open")),
    )
    db.session.add(item)
    db.session.commit()
    db.session.refresh(item)
    return item.to_dict(), None


def update_agenda_item(item_id: int, data: dict) -> tuple[dict | None, str | None]:
    item = MeetingAgendaItem.query.get(item_id)
    if not item:
        return None, "agenda item not found"
    if "title" in data:       item.title       = data["title"].strip()
    if "description" in data: item.description = (data["description"] or "").strip() or None
    if "sort_order" in data:  item.sort_order  = data["sort_order"]
    if "owner_id" in data:    item.owner_id    = data["owner_id"]
    if "status" in data:      item.status      = AgendaItemStatusEnum(data["status"])
    db.session.commit()
    return item.to_dict(), None


def delete_agenda_item(item_id: int) -> str | None:
    item = MeetingAgendaItem.query.get(item_id)
    if not item:
        return "agenda item not found"
    db.session.delete(item)
    db.session.commit()
    return None


# ── Discussions ────────────────────────────────────────────────────────────

def list_discussions(meeting_id: int, member_only: bool = False) -> list[dict] | None:
    if not Meeting.query.get(meeting_id):
        return None
    q = (
        MeetingDiscussion.query
        .filter_by(meeting_id=meeting_id)
        .options(joinedload(MeetingDiscussion.creator))
        .order_by(MeetingDiscussion.created_at.asc())
    )
    if member_only:
        q = q.filter_by(is_visible_to_members=True)
    return [d.to_dict() for d in q.all()]


def create_discussion(meeting_id: int, data: dict, created_by: int) -> tuple[dict | None, str | None]:
    if not Meeting.query.get(meeting_id):
        return None, "meeting not found"
    agenda_item_id = data.get("agenda_item_id")
    if agenda_item_id and not MeetingAgendaItem.query.get(agenda_item_id):
        return None, "agenda item not found"
    disc = MeetingDiscussion(
        meeting_id=meeting_id,
        agenda_item_id=agenda_item_id,
        content=data["content"].strip(),
        is_visible_to_members=data.get("is_visible_to_members", True),
        created_by=created_by,
    )
    db.session.add(disc)
    db.session.commit()
    db.session.refresh(disc)
    return disc.to_dict(), None


def update_discussion(disc_id: int, data: dict) -> tuple[dict | None, str | None]:
    disc = MeetingDiscussion.query.get(disc_id)
    if not disc:
        return None, "discussion not found"
    if "content" in data:               disc.content               = data["content"].strip()
    if "is_visible_to_members" in data: disc.is_visible_to_members = data["is_visible_to_members"]
    if "agenda_item_id" in data:        disc.agenda_item_id        = data["agenda_item_id"]
    db.session.commit()
    return disc.to_dict(), None


def delete_discussion(disc_id: int) -> str | None:
    disc = MeetingDiscussion.query.get(disc_id)
    if not disc:
        return "discussion not found"
    db.session.delete(disc)
    db.session.commit()
    return None


# ── Attendance ─────────────────────────────────────────────────────────────

def get_attendance_status(meeting_id: int, user_id: int) -> dict | None:
    """Return attendance state for a user. None if meeting not found or user not invited."""
    m = Meeting.query.get(meeting_id)
    if not m:
        return None

    now = _now_ist()
    start, end = _meeting_window(m)

    record = MeetingAttendance.query.filter_by(
        meeting_id=meeting_id, user_id=user_id,
    ).first()

    if record:
        phase = "marked"
    elif now < start:
        phase = "before"
    elif now <= end:
        phase = "open"
    else:
        phase = "closed"

    return {
        "phase":     phase,        # before | open | marked | closed
        "startTime": m.start_time,
        "endTime":   m.end_time,
        "markedAt":  record.marked_at.isoformat() if record else None,
    }


def mark_attendance(meeting_id: int, user_id: int, device_token: str | None) -> tuple[dict | None, str | None]:
    m = Meeting.query.get(meeting_id)
    if not m:
        return None, "meeting not found"

    # Must be invited
    if not MeetingInvitee.query.filter_by(meeting_id=meeting_id, user_id=user_id).first():
        return None, "you are not invited to this meeting"

    # Enforce time window using IST
    now = _now_ist()
    start, end = _meeting_window(m)
    if now < start:
        return None, f"attendance opens at {m.start_time} IST"
    if now > end:
        return None, "attendance window has closed"

    # Device-abuse check (optional — only when client sends a token)
    if device_token:
        existing_device = MeetingAttendanceDevice.query.filter_by(
            meeting_id=meeting_id, device_token=device_token,
        ).first()
        if existing_device and existing_device.user_id != user_id:
            return None, "this device has already been used by a different user for this meeting"

    # Idempotency check
    if MeetingAttendance.query.filter_by(meeting_id=meeting_id, user_id=user_id).first():
        return {"alreadyMarked": True}, None

    record = MeetingAttendance(meeting_id=meeting_id, user_id=user_id)
    db.session.add(record)

    if device_token and not MeetingAttendanceDevice.query.filter_by(
        meeting_id=meeting_id, device_token=device_token,
    ).first():
        db.session.add(MeetingAttendanceDevice(
            meeting_id=meeting_id,
            device_token=device_token,
            user_id=user_id,
        ))

    db.session.commit()
    return {"marked": True, "markedAt": record.marked_at.isoformat() if record.marked_at else None}, None


def list_attendance(meeting_id: int) -> list[dict] | None:
    if not Meeting.query.get(meeting_id):
        return None
    rows = (
        MeetingAttendance.query
        .filter_by(meeting_id=meeting_id)
        .options(joinedload(MeetingAttendance.user))
        .all()
    )
    return [r.to_dict() for r in rows]
