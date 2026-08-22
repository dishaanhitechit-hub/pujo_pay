from datetime import date

from marshmallow import Schema, fields, validate, validates, ValidationError

from ...extensions import db
from ...models.event import Event, EventStatusEnum, _slugify
from ...models.event_day import EventDay


# ── Schemas ────────────────────────────────────────────────────────────────

class EventDaySchema(Schema):
    key         = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    label       = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    date        = fields.Date(load_default=None)
    description = fields.Str(load_default=None)
    rituals     = fields.List(fields.Str(), load_default=None)
    sort_order  = fields.Int(load_default=0, data_key="sortOrder")


class CreateEventSchema(Schema):
    name               = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    description        = fields.Str(load_default=None)
    start_date         = fields.Date(load_default=None, data_key="startDate")
    end_date           = fields.Date(load_default=None, data_key="endDate")
    location           = fields.Str(load_default=None, validate=validate.Length(max=200))
    year               = fields.Int(load_default=None)
    status             = fields.Str(load_default="draft",
                                    validate=validate.OneOf(["draft", "published", "archived"]))
    collection_enabled = fields.Bool(load_default=False, data_key="collectionEnabled")
    is_featured        = fields.Bool(load_default=False, data_key="isFeatured")

    @validates("end_date")
    def validate_end_date(self, value):
        # Defer cross-field check to service; marshmallow validates field in isolation
        pass


class UpdateEventSchema(Schema):
    name               = fields.Str(validate=validate.Length(min=1, max=120))
    description        = fields.Str(load_default=None)
    start_date         = fields.Date(data_key="startDate", load_default=None)
    end_date           = fields.Date(data_key="endDate", load_default=None)
    location           = fields.Str(validate=validate.Length(max=200))
    year               = fields.Int()
    status             = fields.Str(validate=validate.OneOf(["draft", "published", "archived"]))
    collection_enabled = fields.Bool(data_key="collectionEnabled")
    is_featured        = fields.Bool(data_key="isFeatured")


create_event_schema   = CreateEventSchema()
update_event_schema   = UpdateEventSchema()
event_day_schema      = EventDaySchema()
event_days_list_schema = EventDaySchema(many=True)


# ── Slug helpers ────────────────────────────────────────────────────────────

def _unique_slug(base: str) -> str:
    """Return base slug, or base-2, base-3, ... until unique."""
    candidate = base
    suffix = 2
    while Event.query.filter_by(slug=candidate).first():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


# ── Service ────────────────────────────────────────────────────────────────

def list_events(
    search: str | None = None,
    status: str | None = None,
    collection_enabled: bool | None = None,
    is_featured: bool | None = None,
    year: int | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    query = Event.query

    if search:
        like = f"%{search}%"
        query = query.filter(Event.name.ilike(like) | Event.slug.ilike(like))

    if status and status in ("draft", "published", "archived"):
        query = query.filter(Event.status == EventStatusEnum(status))

    if collection_enabled is not None:
        query = query.filter(Event.collection_enabled == collection_enabled)

    if is_featured is not None:
        query = query.filter(Event.is_featured == is_featured)

    if year is not None:
        query = query.filter(Event.year == year)

    query = query.order_by(Event.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)

    return {
        "events": [e.to_dict() for e in pagination.items],
        "page": pagination.page,
        "perPage": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }


def get_active_events() -> list[dict]:
    """Events that collectors may currently collect against."""
    events = (
        Event.query
        .filter_by(status=EventStatusEnum.published, collection_enabled=True)
        .order_by(Event.start_date.desc())
        .all()
    )
    return [e.to_dict() for e in events]


def create_event(data: dict, created_by: int) -> tuple[Event | None, str | None]:
    slug = _unique_slug(_slugify(data["name"]))

    if data.get("is_featured"):
        _clear_featured()

    event = Event(
        name=data["name"].strip(),
        slug=slug,
        description=data.get("description"),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        location=data.get("location"),
        year=data.get("year"),
        status=EventStatusEnum(data.get("status", "draft")),
        collection_enabled=data.get("collection_enabled", False),
        is_featured=data.get("is_featured", False),
        created_by=created_by,
    )
    db.session.add(event)
    db.session.commit()
    return event, None


def get_event(event_id: int) -> dict | None:
    event = Event.query.get(event_id)
    if not event:
        return None
    result = event.to_dict(include_days=True)
    from ..media.service import get_event_gallery
    result["gallery"] = get_event_gallery(event_id)
    return result


def update_event(event_id: int, data: dict) -> tuple[dict | None, str | None]:
    event = Event.query.get(event_id)
    if not event:
        return None, "event not found"

    if "name" in data:
        event.name = data["name"].strip()

    if "description" in data:
        event.description = data["description"]

    if "start_date" in data:
        event.start_date = data["start_date"]

    if "end_date" in data:
        event.end_date = data["end_date"]

    if "location" in data:
        event.location = data["location"]

    if "year" in data:
        event.year = data["year"]

    if "status" in data:
        new_status = EventStatusEnum(data["status"])
        # Archiving forces collection off
        if new_status == EventStatusEnum.archived:
            event.collection_enabled = False
        event.status = new_status

    if "collection_enabled" in data:
        # Cannot enable collection on archived events
        if event.status == EventStatusEnum.archived and data["collection_enabled"]:
            return None, "cannot enable collection on an archived event"
        event.collection_enabled = data["collection_enabled"]

    if "is_featured" in data:
        if data["is_featured"] and not event.is_featured:
            _clear_featured()
        event.is_featured = data["is_featured"]

    db.session.commit()
    return event.to_dict(include_days=True), None


def set_event_days(event_id: int, days_data: list[dict]) -> tuple[dict | None, str | None]:
    """Replace all EventDays for an event with the provided list."""
    event = Event.query.get(event_id)
    if not event:
        return None, "event not found"

    # Delete all existing days (cascade via relationship)
    for day in list(event.days):
        db.session.delete(day)
    db.session.flush()

    for item in days_data:
        day = EventDay(
            event_id=event.id,
            key=item["key"].strip(),
            label=item["label"].strip(),
            date=item.get("date"),
            description=item.get("description"),
            rituals=item.get("rituals") or [],
            sort_order=item.get("sort_order", 0),
        )
        db.session.add(day)

    db.session.commit()
    return event.to_dict(include_days=True), None


def _clear_featured() -> None:
    """Unset is_featured on all events (called before setting a new featured event)."""
    Event.query.filter_by(is_featured=True).update({"is_featured": False})
