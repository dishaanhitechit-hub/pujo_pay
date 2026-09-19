from datetime import datetime

from marshmallow import Schema, fields, validate
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models.circular import Circular
from ...models.event import Event


# ── Schemas ────────────────────────────────────────────────────────────────

class CreateCircularSchema(Schema):
    title       = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    body        = fields.Str(required=True, validate=validate.Length(min=1))
    circular_no = fields.Str(load_default=None, data_key="circularNo")
    event_id    = fields.Int(load_default=None, data_key="eventId")


class UpdateCircularSchema(Schema):
    title        = fields.Str(validate=validate.Length(min=1, max=200))
    body         = fields.Str(validate=validate.Length(min=1))
    circular_no  = fields.Str(allow_none=True, data_key="circularNo")
    event_id     = fields.Int(allow_none=True, data_key="eventId")
    is_published = fields.Bool(data_key="isPublished")


create_circular_schema = CreateCircularSchema()
update_circular_schema = UpdateCircularSchema()


# ── helpers ────────────────────────────────────────────────────────────────

def _q():
    return (
        Circular.query
        .options(joinedload(Circular.event), joinedload(Circular.creator))
    )


# ── Admin services ─────────────────────────────────────────────────────────

def list_circulars(page: int = 1, per_page: int = 20, org_id: int | None = None) -> dict:
    per_page = min(per_page, 100)
    q = _q()
    if org_id is not None:
        from ...models.user import User
        q = q.join(User, Circular.created_by == User.id).filter(User.org_id == org_id)
    pag = (
        q
        .order_by(Circular.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return {
        "circulars": [c.to_dict() for c in pag.items],
        "page":    pag.page,
        "pages":   pag.pages,
        "total":   pag.total,
        "perPage": pag.per_page,
    }


def create_circular(data: dict, created_by: int) -> tuple[dict | None, str | None]:
    event_id = data.get("event_id")
    if event_id is not None and not Event.query.get(event_id):
        return None, "event not found"

    c = Circular(
        title=data["title"].strip(),
        body=data["body"].strip(),
        circular_no=(data.get("circular_no") or "").strip() or None,
        event_id=event_id,
        created_by=created_by,
    )
    db.session.add(c)
    db.session.commit()
    return _q().get(c.id).to_dict(), None


def get_circular(circular_id: int) -> dict | None:
    c = _q().get(circular_id)
    return c.to_dict() if c else None


def update_circular(circular_id: int, data: dict) -> tuple[dict | None, str | None]:
    c = Circular.query.get(circular_id)
    if not c:
        return None, "circular not found"

    if "title" in data:
        c.title = data["title"].strip()
    if "body" in data:
        c.body = data["body"].strip()
    if "circular_no" in data:
        c.circular_no = (data["circular_no"] or "").strip() or None
    if "event_id" in data:
        eid = data["event_id"]
        if eid is not None and not Event.query.get(eid):
            return None, "event not found"
        c.event_id = eid
    if "is_published" in data:
        c.is_published = data["is_published"]
        if data["is_published"] and not c.published_at:
            c.published_at = datetime.utcnow()
        elif not data["is_published"]:
            c.published_at = None

    db.session.commit()
    return _q().get(c.id).to_dict(), None


def delete_circular(circular_id: int) -> str | None:
    c = Circular.query.get(circular_id)
    if not c:
        return "circular not found"
    db.session.delete(c)
    db.session.commit()
    return None


# ── Member services ────────────────────────────────────────────────────────

def list_published_circulars(
    search: str | None = None,
    event_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    per_page: int = 20,
    org_id: int | None = None,
) -> dict:
    per_page = min(per_page, 100)
    q = _q().filter(Circular.is_published.is_(True))
    if org_id is not None:
        from ...models.user import User
        q = q.join(User, Circular.created_by == User.id).filter(User.org_id == org_id)

    if search:
        term = f"%{search}%"
        q = q.filter(
            db.or_(Circular.title.ilike(term), Circular.body.ilike(term))
        )
    if event_id:
        q = q.filter(Circular.event_id == event_id)
    if date_from:
        q = q.filter(Circular.published_at >= date_from)
    if date_to:
        q = q.filter(Circular.published_at <= date_to + " 23:59:59")

    pag = q.order_by(Circular.published_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return {
        "circulars": [c.to_dict() for c in pag.items],
        "page":    pag.page,
        "pages":   pag.pages,
        "total":   pag.total,
        "perPage": pag.per_page,
    }
