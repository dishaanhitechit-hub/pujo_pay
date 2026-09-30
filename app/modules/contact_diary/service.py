from marshmallow import Schema, fields, validate
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models.contact_diary import ContactDiaryEntry


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateEntrySchema(Schema):
    name       = fields.Str(required=True, validate=validate.Length(min=1, max=150))
    phone      = fields.Str(required=True, validate=validate.Length(min=1, max=30))
    address    = fields.Str(load_default=None, validate=validate.Length(max=300))
    occupation = fields.Str(load_default=None, validate=validate.Length(max=150))
    notes      = fields.Str(load_default=None)


class UpdateEntrySchema(Schema):
    name       = fields.Str(validate=validate.Length(min=1, max=150))
    phone      = fields.Str(validate=validate.Length(min=1, max=30))
    address    = fields.Str(allow_none=True, validate=validate.Length(max=300))
    occupation = fields.Str(allow_none=True, validate=validate.Length(max=150))
    notes      = fields.Str(allow_none=True)


create_entry_schema = CreateEntrySchema()
update_entry_schema = UpdateEntrySchema()


# ── Service ────────────────────────────────────────────────────────────────────

def list_entries(
    org_id: int,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
) -> dict:
    per_page = min(per_page, 50)
    q = ContactDiaryEntry.query.filter_by(org_id=org_id).options(joinedload(ContactDiaryEntry.creator))
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            db.or_(
                ContactDiaryEntry.name.ilike(like),
                ContactDiaryEntry.phone.ilike(like),
                ContactDiaryEntry.occupation.ilike(like),
            )
        )
    q = q.order_by(ContactDiaryEntry.name.asc())
    pagination = db.paginate(q, page=page, per_page=per_page, error_out=False)
    return {
        "entries":  [e.to_dict() for e in pagination.items],
        "page":     pagination.page,
        "perPage":  pagination.per_page,
        "total":    pagination.total,
    }


def create_entry(data: dict, created_by: int, org_id: int) -> dict:
    entry = ContactDiaryEntry(
        org_id=org_id,
        created_by=created_by,
        name=data["name"].strip(),
        phone=data["phone"].strip(),
        address=(data.get("address") or "").strip() or None,
        occupation=(data.get("occupation") or "").strip() or None,
        notes=(data.get("notes") or "").strip() or None,
    )
    db.session.add(entry)
    db.session.commit()
    return entry.to_dict()


def get_entry(entry_id: int, org_id: int) -> dict | None:
    entry = ContactDiaryEntry.query.filter_by(id=entry_id, org_id=org_id).first()
    return entry.to_dict() if entry else None


def update_entry(entry_id: int, data: dict, org_id: int) -> tuple[dict | None, str | None]:
    entry = ContactDiaryEntry.query.filter_by(id=entry_id, org_id=org_id).first()
    if not entry:
        return None, "entry not found"

    if "name" in data:
        entry.name = data["name"].strip()
    if "phone" in data:
        entry.phone = data["phone"].strip()
    if "address" in data:
        entry.address = (data["address"] or "").strip() or None
    if "occupation" in data:
        entry.occupation = (data["occupation"] or "").strip() or None
    if "notes" in data:
        entry.notes = (data["notes"] or "").strip() or None

    db.session.commit()
    return entry.to_dict(), None


def delete_entry(entry_id: int, org_id: int) -> str | None:
    entry = ContactDiaryEntry.query.filter_by(id=entry_id, org_id=org_id).first()
    if not entry:
        return "entry not found"
    db.session.delete(entry)
    db.session.commit()
    return None
