from marshmallow import Schema, fields, validate

from ...extensions import db
from ...models.contact_query import ContactQuery, ContactQueryStatusEnum


# ── Schemas ────────────────────────────────────────────────────────────────────

class SubmitQuerySchema(Schema):
    name     = fields.Str(required=True, validate=validate.Length(min=1, max=150))
    phone    = fields.Str(required=True, validate=validate.Length(min=1, max=20))
    location = fields.Str(load_default=None, validate=validate.Length(max=200))
    message  = fields.Str(required=True, validate=validate.Length(min=1))


class UpdateQueryStatusSchema(Schema):
    status = fields.Str(
        required=True,
        validate=validate.OneOf([s.value for s in ContactQueryStatusEnum]),
    )


submit_query_schema        = SubmitQuerySchema()
update_query_status_schema = UpdateQueryStatusSchema()


# ── Service ────────────────────────────────────────────────────────────────────

def submit_contact_query(data: dict) -> dict:
    query = ContactQuery(
        name=data["name"].strip(),
        phone=data["phone"].strip(),
        location=(data.get("location") or "").strip() or None,
        message=data["message"].strip(),
        status=ContactQueryStatusEnum.new,
    )
    db.session.add(query)
    db.session.commit()
    return query.to_dict()


def list_contact_queries(
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    search: str | None = None,
) -> dict:
    per_page = min(per_page, 50)
    q = ContactQuery.query
    if status:
        try:
            q = q.filter(ContactQuery.status == ContactQueryStatusEnum(status))
        except ValueError:
            pass
    if search:
        like = f"%{search}%"
        q = q.filter(
            db.or_(
                ContactQuery.name.ilike(like),
                ContactQuery.phone.ilike(like),
                ContactQuery.message.ilike(like),
            )
        )
    q = q.order_by(ContactQuery.created_at.desc())
    pagination = db.paginate(q, page=page, per_page=per_page, error_out=False)
    return {
        "queries": [item.to_dict() for item in pagination.items],
        "page":    pagination.page,
        "perPage": pagination.per_page,
        "total":   pagination.total,
        "pages":   pagination.pages,
    }


def get_contact_query(query_id: int) -> dict | None:
    item = db.session.get(ContactQuery, query_id)
    return item.to_dict() if item else None


def update_contact_query_status(
    query_id: int, status_str: str
) -> tuple[dict | None, str | None]:
    item = db.session.get(ContactQuery, query_id)
    if not item:
        return None, "query not found"
    try:
        item.status = ContactQueryStatusEnum(status_str)
    except ValueError:
        return None, "invalid status"
    db.session.commit()
    return item.to_dict(), None
