import re
from marshmallow import Schema, fields, validate, validates, ValidationError

from ...extensions import db
from ...models.user import User, RoleEnum
from ...models.app_config import AppConfig

# All selectable role values (new + backward-compat legacy)
_ALL_ROLES = [r.value for r in RoleEnum]

# Membership tiers — independent of `role` (which drives permissions).
MEMBER_CATEGORIES = ["lifetime_executive", "premium_executive", "executive", "general"]

# Members created via the admin "Members" page get this placeholder permission-role
# (dashboard-only: no collect, no admin). Real permissions will come from the future
# committee/event-role system. Stored as VARCHAR (native_enum=False) so no enum migration.
DEFAULT_MEMBER_ROLE = RoleEnum.executive

# Valid Indian mobile number: 10 digits starting with 6-9
_IN_MOBILE_RE = re.compile(r'^[6-9]\d{9}$')

# Member ID format defaults (overridable via AppConfig keys member_id.prefix / member_id.digits)
_MEMBER_ID_DEFAULT_DIGITS = 4
_MEMBER_ID_MIN_DIGITS = 3
_MEMBER_ID_MAX_DIGITS = 6


def _member_id_settings(org_id: int | None = None) -> tuple[str, int]:
    """Return (prefix, digits) for member-id generation, clamped to sane bounds."""
    prefix = (AppConfig.get("member_id.prefix", org_id=org_id) or "").strip()
    try:
        digits = int(AppConfig.get("member_id.digits", org_id=org_id) or _MEMBER_ID_DEFAULT_DIGITS)
    except (TypeError, ValueError):
        digits = _MEMBER_ID_DEFAULT_DIGITS
    digits = max(_MEMBER_ID_MIN_DIGITS, min(_MEMBER_ID_MAX_DIGITS, digits))
    return prefix, digits


def generate_next_member_id(org_id: int | None) -> str:
    """Suggest the next member id (e.g. ABC-0001) based on existing members in the org."""
    prefix, digits = _member_id_settings(org_id)
    sep = "-" if prefix else ""
    head = f"{prefix}{sep}"

    rows = (
        User.query
        .filter(User.org_id == org_id, User.member_id.isnot(None))
        .with_entities(User.member_id)
        .all()
    )
    max_n = 0
    for (mid,) in rows:
        if not mid or not mid.startswith(head):
            continue
        tail = mid[len(head):]
        if tail.isdigit():
            max_n = max(max_n, int(tail))

    return f"{head}{max_n + 1:0{digits}d}"


def member_id_exists(org_id: int | None, member_id: str, exclude_user_id: int | None = None) -> bool:
    """Whether a member id is already taken within the organisation."""
    q = User.query.filter_by(org_id=org_id, member_id=member_id)
    if exclude_user_id is not None:
        q = q.filter(User.id != exclude_user_id)
    return db.session.query(q.exists()).scalar()


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
    # `role` is no longer sent by the Members form; kept optional for backward compat.
    role        = fields.Str(
        load_default=None, allow_none=True,
        validate=validate.OneOf(_ALL_ROLES, error="Invalid role."),
    )
    member_category = fields.Str(
        required=True, data_key="memberCategory",
        validate=validate.OneOf(MEMBER_CATEGORIES, error="Invalid member category."),
    )
    member_since = fields.Date(load_default=None, data_key="memberSince", allow_none=True)
    member_id   = fields.Str(load_default=None, data_key="memberId",
                             validate=validate.Length(max=40), allow_none=True)
    phone       = fields.Str(required=True, validate=validate.Length(min=1, max=30))
    whatsapp_no = fields.Str(load_default=None, data_key="whatsappNo",
                             validate=validate.Length(max=30), allow_none=True)
    email       = fields.Email(load_default=None, allow_none=True)
    address     = fields.Str(load_default=None, validate=validate.Length(max=300), allow_none=True)
    password    = fields.Str(required=True, validate=validate.Length(min=6))
    can_collect = fields.Bool(load_default=False, data_key="canCollect")

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
    member_category = fields.Str(data_key="memberCategory",
                                 validate=validate.OneOf(MEMBER_CATEGORIES, error="Invalid member category."))
    member_since = fields.Date(data_key="memberSince", allow_none=True)
    member_id   = fields.Str(data_key="memberId", validate=validate.Length(max=40), allow_none=True)
    phone       = fields.Str(validate=validate.Length(max=30), allow_none=True)
    whatsapp_no = fields.Str(data_key="whatsappNo", validate=validate.Length(max=30),
                             allow_none=True)
    email       = fields.Email(allow_none=True)
    address     = fields.Str(validate=validate.Length(max=300), allow_none=True)
    password    = fields.Str(validate=validate.Length(min=6))
    is_active   = fields.Bool(data_key="isActive")
    can_collect = fields.Bool(data_key="canCollect")


create_schema = CreateUserSchema()
update_schema = UpdateUserSchema()


def create_user(data: dict, created_by: int, org_id: int | None = None) -> User:
    email = data.get("email")
    # Members no longer carry a chosen role — default to the placeholder member role.
    role = RoleEnum(data["role"]) if data.get("role") else DEFAULT_MEMBER_ROLE
    # Compute effective can_collect: collector always True, admin always False, others from input
    raw_can_collect = bool(data.get("can_collect", False))
    if role == RoleEnum.admin:
        can_collect = False
    elif role == RoleEnum.collector:
        can_collect = True
    else:
        can_collect = raw_can_collect
    user = User(
        name=data["name"].strip(),
        email=email.strip().lower() if email else None,
        phone=_normalize_phone(data.get("phone")),
        whatsapp_no=_normalize_phone(data.get("whatsapp_no")),
        address=data.get("address") or None,
        role=role,
        member_category=data.get("member_category"),
        member_since=data.get("member_since"),
        member_id=(data.get("member_id") or "").strip() or None,
        is_active=True,
        can_collect=can_collect,
        created_by=created_by,
        org_id=org_id,
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

    if "member_category" in data:
        user.member_category = data["member_category"]

    if "member_since" in data:
        user.member_since = data["member_since"]

    if "member_id" in data:
        user.member_id = (data["member_id"] or "").strip() or None

    if "role" in data:
        user.role = RoleEnum(data["role"])

    if "password" in data:
        user.set_password(data["password"])

    if "is_active" in data:
        user.is_active = data["is_active"]

    if "can_collect" in data:
        # Enforce role constraints: admin always False, collector always True
        current_role = user.role if isinstance(user.role, RoleEnum) else RoleEnum(user.role)
        if current_role == RoleEnum.admin:
            user.can_collect = False
        elif current_role == RoleEnum.collector:
            user.can_collect = True
        else:
            user.can_collect = bool(data["can_collect"])

    # If role itself changed, recompute can_collect constraints
    if "role" in data:
        new_role = user.role if isinstance(user.role, RoleEnum) else RoleEnum(user.role)
        if new_role == RoleEnum.admin:
            user.can_collect = False
        elif new_role == RoleEnum.collector:
            user.can_collect = True
        # else: leave can_collect as currently set

    db.session.commit()
    return user
