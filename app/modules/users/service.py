import re
from marshmallow import Schema, fields, validate, validates, ValidationError

from ...extensions import db
from ...models.user import User, RoleEnum

# All selectable role values (new + backward-compat legacy)
_ALL_ROLES = [r.value for r in RoleEnum]

# Valid Indian mobile number: 10 digits starting with 6-9
_IN_MOBILE_RE = re.compile(r'^[6-9]\d{9}$')


def _normalize_phone(raw: str | None) -> str | None:
    """
    Accept either a 10-digit local number or a +91-prefixed number.
    Returns '+91 XXXXXXXXXX' or None.
    """
    if not raw or not raw.strip():
        return None
    # Strip everything except digits
    digits = re.sub(r'\D', '', raw.strip())
    # Drop leading country code 91 if present and 12 digits total
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    if len(digits) == 10 and _IN_MOBILE_RE.match(digits):
        return f'+91 {digits}'
    # Return as-is if doesn't match expected format (validation will catch it)
    return raw.strip()


class CreateUserSchema(Schema):
    name        = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    role        = fields.Str(
        required=True,
        validate=validate.OneOf(_ALL_ROLES, error="Invalid role."),
    )
    phone       = fields.Str(required=True, validate=validate.Length(min=1, max=30))
    whatsapp_no = fields.Str(load_default=None, data_key="whatsappNo",
                             validate=validate.Length(max=30), allow_none=True)
    email       = fields.Email(load_default=None, allow_none=True)
    address     = fields.Str(load_default=None, validate=validate.Length(max=300), allow_none=True)
    password    = fields.Str(required=True, validate=validate.Length(min=6))

    @validates('phone')
    def validate_phone(self, value):
        digits = re.sub(r'\D', '', value or '')
        if len(digits) == 12 and digits.startswith('91'):
            digits = digits[2:]
        if not (len(digits) == 10 and _IN_MOBILE_RE.match(digits)):
            raise ValidationError('Enter a valid 10-digit Indian mobile number.')


class UpdateUserSchema(Schema):
    name        = fields.Str(validate=validate.Length(min=1, max=120))
    role        = fields.Str(validate=validate.OneOf(_ALL_ROLES, error="Invalid role."))
    phone       = fields.Str(validate=validate.Length(max=30), allow_none=True)
    whatsapp_no = fields.Str(data_key="whatsappNo", validate=validate.Length(max=30),
                             allow_none=True)
    email       = fields.Email(allow_none=True)
    address     = fields.Str(validate=validate.Length(max=300), allow_none=True)
    password    = fields.Str(validate=validate.Length(min=6))
    is_active   = fields.Bool(data_key="isActive")


create_schema = CreateUserSchema()
update_schema = UpdateUserSchema()


def create_user(data: dict, created_by: int) -> User:
    email = data.get("email")
    user = User(
        name=data["name"].strip(),
        email=email.strip().lower() if email else None,
        phone=_normalize_phone(data.get("phone")),
        whatsapp_no=_normalize_phone(data.get("whatsapp_no")),
        address=data.get("address") or None,
        role=RoleEnum(data["role"]),
        is_active=True,
        created_by=created_by,
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return user


def update_user(user: User, data: dict) -> User:
    if "name" in data:
        user.name = data["name"].strip()

    if "phone" in data:
        user.phone = _normalize_phone(data["phone"])

    if "whatsapp_no" in data:
        user.whatsapp_no = _normalize_phone(data["whatsapp_no"])

    if "email" in data:
        raw = data["email"]
        user.email = raw.strip().lower() if raw else None

    if "address" in data:
        user.address = data["address"] or None

    if "role" in data:
        user.role = RoleEnum(data["role"])

    if "password" in data:
        user.set_password(data["password"])

    if "is_active" in data:
        user.is_active = data["is_active"]

    db.session.commit()
    return user
