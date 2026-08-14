from marshmallow import Schema, fields, validate

from ...extensions import db
from ...models.user import User, RoleEnum


class CreateUserSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=6))
    phone = fields.Str(load_default=None, validate=validate.Length(max=20))
    upi_id = fields.Str(load_default=None, validate=validate.Length(max=100))
    whatsapp_no = fields.Str(load_default=None, validate=validate.Length(max=20))
    role = fields.Str(
        load_default="general",
        validate=validate.OneOf(["admin", "executive", "committee", "general"]),
    )


class UpdateUserSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=120))
    phone = fields.Str(validate=validate.Length(max=20), allow_none=True)
    upi_id = fields.Str(validate=validate.Length(max=100), allow_none=True)
    whatsapp_no = fields.Str(validate=validate.Length(max=20), allow_none=True)
    role = fields.Str(
        validate=validate.OneOf(["admin", "executive", "committee", "general"])
    )
    password = fields.Str(validate=validate.Length(min=6))
    is_active = fields.Bool()


create_schema = CreateUserSchema()
update_schema = UpdateUserSchema()


def create_user(data: dict, created_by: int) -> User:
    user = User(
        name=data["name"].strip(),
        email=data["email"].strip().lower(),
        phone=data.get("phone"),
        upi_id=data.get("upi_id"),
        whatsapp_no=data.get("whatsapp_no"),
        role=RoleEnum(data["role"]),
        is_active=True,
        created_by=created_by,
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return user


def update_user(user: User, data: dict) -> User:
    field_map = {
        "name": lambda v: v.strip(),
        "phone": lambda v: v,
        "upi_id": lambda v: v,
        "whatsapp_no": lambda v: v,
        "is_active": lambda v: v,
    }
    for field, transform in field_map.items():
        if field in data:
            setattr(user, field, transform(data[field]))

    if "role" in data:
        user.role = RoleEnum(data["role"])
    if "password" in data:
        user.set_password(data["password"])

    db.session.commit()
    return user
