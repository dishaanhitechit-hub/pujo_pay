from datetime import datetime

from marshmallow import Schema, fields, validate

from ...extensions import db
from ...models.announcement import Announcement
from ...models.event import Event, EventStatusEnum


# ── Schemas ────────────────────────────────────────────────────────────────

class CreateAnnouncementSchema(Schema):
    title    = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    body     = fields.Str(required=True, validate=validate.Length(min=1))
    event_id = fields.Int(load_default=None, data_key="eventId")


class UpdateAnnouncementSchema(Schema):
    title        = fields.Str(validate=validate.Length(min=1, max=200))
    body         = fields.Str(validate=validate.Length(min=1))
    event_id     = fields.Int(load_default=None, data_key="eventId")
    is_published = fields.Bool(data_key="isPublished")


create_announcement_schema = CreateAnnouncementSchema()
update_announcement_schema = UpdateAnnouncementSchema()


# ── Service ────────────────────────────────────────────────────────────────

def list_announcements() -> list[dict]:
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return [a.to_dict() for a in announcements]


def create_announcement(data: dict, created_by: int) -> tuple[dict | None, str | None]:
    event_id = data.get("event_id")
    if event_id is not None:
        event = Event.query.get(event_id)
        if not event:
            return None, "event not found"

    ann = Announcement(
        title=data["title"].strip(),
        body=data["body"].strip(),
        event_id=event_id,
        created_by=created_by,
    )
    db.session.add(ann)
    db.session.commit()
    return ann.to_dict(), None


def get_announcement(announcement_id: int) -> dict | None:
    ann = Announcement.query.get(announcement_id)
    return ann.to_dict() if ann else None


def update_announcement(announcement_id: int, data: dict) -> tuple[dict | None, str | None]:
    ann = Announcement.query.get(announcement_id)
    if not ann:
        return None, "announcement not found"

    if "title" in data:
        ann.title = data["title"].strip()

    if "body" in data:
        ann.body = data["body"].strip()

    if "event_id" in data:
        event_id = data["event_id"]
        if event_id is not None:
            event = Event.query.get(event_id)
            if not event:
                return None, "event not found"
        ann.event_id = event_id

    if "is_published" in data:
        new_state = data["is_published"]
        if new_state and not ann.is_published:
            ann.published_at = datetime.utcnow()
        ann.is_published = new_state

    db.session.commit()
    return ann.to_dict(), None


def delete_announcement(announcement_id: int) -> str | None:
    ann = Announcement.query.get(announcement_id)
    if not ann:
        return "announcement not found"
    db.session.delete(ann)
    db.session.commit()
    return None


def list_public_announcements(event_id: int | None = None) -> list[dict]:
    query = Announcement.query.filter_by(is_published=True)
    if event_id:
        query = query.filter_by(event_id=event_id)
    announcements = query.order_by(Announcement.published_at.desc()).all()
    return [a.to_dict() for a in announcements]
