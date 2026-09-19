from marshmallow import Schema, fields, validate, ValidationError

from ...extensions import db
from ...models.organisation import Organisation, _slugify_org
from ...models.user import User, RoleEnum


class RegisterOrgSchema(Schema):
    org_name       = fields.Str(required=True, validate=validate.Length(min=2, max=200),
                                data_key="orgName")
    admin_name     = fields.Str(required=True, validate=validate.Length(min=1, max=120),
                                data_key="adminName")
    admin_email    = fields.Email(required=True, data_key="adminEmail")
    admin_password = fields.Str(required=True, validate=validate.Length(min=6),
                                data_key="adminPassword")
    admin_phone    = fields.Str(load_default=None, data_key="adminPhone")


register_org_schema = RegisterOrgSchema()


def _unique_org_slug(base: str) -> str:
    candidate = base
    suffix = 2
    while Organisation.query.filter_by(slug=candidate).first():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def register_org(data: dict) -> tuple[Organisation, User] | tuple[None, str]:
    email = data["admin_email"].strip().lower()

    if User.query.filter_by(email=email).first():
        return None, "email already registered"

    slug = _unique_org_slug(_slugify_org(data["org_name"]))

    org = Organisation(name=data["org_name"].strip(), slug=slug)
    db.session.add(org)
    db.session.flush()  # get org.id before creating user

    admin = User(
        name=data["admin_name"].strip(),
        email=email,
        phone=data.get("admin_phone"),
        role=RoleEnum.admin,
        is_active=True,
        org_id=org.id,
    )
    admin.set_password(data["admin_password"])
    db.session.add(admin)
    db.session.commit()

    return org, admin


def get_org(org_id: int) -> Organisation | None:
    return Organisation.query.get(org_id)


def update_org(org: Organisation, name: str) -> Organisation:
    org.name = name.strip()
    db.session.commit()
    return org
