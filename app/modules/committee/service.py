from marshmallow import Schema, fields, validate

from ...extensions import db
from ...models.committee_member import CommitteeMember
from ...models.event import Event


# ── Schemas ────────────────────────────────────────────────────────────────

class CreateCommitteeMemberSchema(Schema):
    name       = fields.Str(required=True, validate=validate.Length(min=1, max=150))
    role_title = fields.Str(required=True, validate=validate.Length(min=1, max=150),
                            data_key="roleTitle")
    event_id   = fields.Int(load_default=None, data_key="eventId")
    phone      = fields.Str(load_default=None, validate=validate.Length(max=20))
    sort_order = fields.Int(load_default=0, data_key="sortOrder")
    is_active  = fields.Bool(load_default=True, data_key="isActive")


class UpdateCommitteeMemberSchema(Schema):
    name       = fields.Str(validate=validate.Length(min=1, max=150))
    role_title = fields.Str(validate=validate.Length(min=1, max=150), data_key="roleTitle")
    event_id   = fields.Int(load_default=None, data_key="eventId")
    phone      = fields.Str(load_default=None, validate=validate.Length(max=20))
    sort_order = fields.Int(data_key="sortOrder")
    is_active  = fields.Bool(data_key="isActive")


create_committee_member_schema = CreateCommitteeMemberSchema()
update_committee_member_schema = UpdateCommitteeMemberSchema()


# ── Service ────────────────────────────────────────────────────────────────

def list_committee_members() -> list[dict]:
    members = CommitteeMember.query.order_by(
        CommitteeMember.sort_order, CommitteeMember.name
    ).all()
    return [m.to_dict() for m in members]


def create_committee_member(data: dict) -> tuple[dict | None, str | None]:
    event_id = data.get("event_id")
    if event_id is not None:
        if not Event.query.get(event_id):
            return None, "event not found"

    member = CommitteeMember(
        name=data["name"].strip(),
        role_title=data["role_title"].strip(),
        event_id=event_id,
        phone=data.get("phone"),
        sort_order=data.get("sort_order", 0),
        is_active=data.get("is_active", True),
    )
    db.session.add(member)
    db.session.commit()
    return member.to_dict(), None


def get_committee_member(member_id: int) -> dict | None:
    member = CommitteeMember.query.get(member_id)
    return member.to_dict() if member else None


def update_committee_member(member_id: int, data: dict) -> tuple[dict | None, str | None]:
    member = CommitteeMember.query.get(member_id)
    if not member:
        return None, "committee member not found"

    if "name" in data:
        member.name = data["name"].strip()

    if "role_title" in data:
        member.role_title = data["role_title"].strip()

    if "event_id" in data:
        event_id = data["event_id"]
        if event_id is not None:
            if not Event.query.get(event_id):
                return None, "event not found"
        member.event_id = event_id

    if "phone" in data:
        member.phone = data["phone"]

    if "sort_order" in data:
        member.sort_order = data["sort_order"]

    if "is_active" in data:
        member.is_active = data["is_active"]

    db.session.commit()
    return member.to_dict(), None


def delete_committee_member(member_id: int) -> str | None:
    member = CommitteeMember.query.get(member_id)
    if not member:
        return "committee member not found"
    db.session.delete(member)
    db.session.commit()
    return None


def list_active_committee_members(event_id: int | None = None) -> list[dict]:
    query = CommitteeMember.query.filter_by(is_active=True)
    if event_id:
        query = query.filter_by(event_id=event_id)
    members = query.order_by(CommitteeMember.sort_order, CommitteeMember.name).all()
    return [m.to_dict() for m in members]
