import random
import re
import secrets
import string
from datetime import datetime, timezone

from marshmallow import Schema, fields, validate, validates, ValidationError

from ...extensions import db
from ...models.org_provision import OrgProvision, ProvisionStatus
from ...models.organisation import Organisation, _slugify_org
from ...models.user import User, RoleEnum
from ...services.email_service import send_org_credentials_email


# ── Schemas ──────────────────────────────────────────────────────────────────

class CreateProvisionSchema(Schema):
    org_name      = fields.Str(required=True, validate=validate.Length(min=2, max=200),
                               data_key="orgName")
    contact_name  = fields.Str(required=True, validate=validate.Length(min=1, max=120),
                               data_key="contactName")
    contact_email = fields.Email(required=True, data_key="contactEmail")
    contact_phone = fields.Str(load_default=None, data_key="contactPhone")
    org_code      = fields.Str(load_default=None, data_key="orgCode",
                               validate=validate.Length(min=3, max=20))

    @validates("org_code")
    def validate_org_code(self, value):
        if value is None:
            return
        if not re.match(r'^[A-Z0-9][A-Z0-9\-]{2,19}$', value.upper()):
            raise ValidationError("orgCode must be 3-20 chars, uppercase letters, digits and hyphens only")


create_provision_schema = CreateProvisionSchema()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _gen_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _gen_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _gen_org_code(org_name: str) -> str:
    """Auto-generate: first 4 uppercase alpha chars of org name + 4 random digits."""
    letters = re.sub(r"[^A-Za-z]", "", org_name).upper()[:4].ljust(4, "X")
    digits = "".join(random.choices(string.digits, k=4))
    return letters + digits


def _unique_org_code(candidate: str) -> str:
    """Append random suffix until the code is unique across organisations."""
    base = candidate[:16]  # leave room for suffix
    code = candidate
    while Organisation.query.filter_by(org_code=code).first():
        code = base + "".join(random.choices(string.digits, k=2))
    return code


def _unique_org_slug(base: str) -> str:
    candidate = base
    suffix = 2
    while Organisation.query.filter_by(slug=candidate).first():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


# ── Service functions ─────────────────────────────────────────────────────────

def create_provision(data: dict, created_by: int | None) -> OrgProvision:
    raw_code = data.get("org_code")
    org_code = raw_code.strip().upper() if raw_code else None
    prov = OrgProvision(
        org_name=data["org_name"].strip(),
        contact_name=data["contact_name"].strip(),
        contact_email=data["contact_email"].strip().lower(),
        contact_phone=data.get("contact_phone"),
        org_code=org_code,
        status=ProvisionStatus.PENDING_PAYMENT,
        created_by=created_by,
    )
    db.session.add(prov)
    db.session.commit()
    return prov


def list_provisions() -> list[OrgProvision]:
    return OrgProvision.query.order_by(OrgProvision.created_at.desc()).all()


def get_provision(provision_id: int) -> OrgProvision | None:
    return OrgProvision.query.get(provision_id)


def confirm_payment_and_activate(prov: OrgProvision) -> tuple[OrgProvision, str, str] | tuple[None, str, str]:
    """
    Confirm payment, create org + admin user, send credentials email.
    Returns (prov, plain_temp_password, otp_code) or (None, error_msg, "").
    """
    if prov.status == ProvisionStatus.ACTIVE:
        return None, "already activated", ""

    email = prov.contact_email
    slug = _unique_org_slug(_slugify_org(prov.org_name))

    # Determine org_code: use provisioned value or auto-generate, ensure uniqueness
    if prov.org_code:
        if Organisation.query.filter_by(org_code=prov.org_code).first():
            return None, f"org code '{prov.org_code}' is already taken", ""
        org_code = prov.org_code
    else:
        org_code = _unique_org_code(_gen_org_code(prov.org_name))

    org = Organisation(name=prov.org_name.strip(), slug=slug, org_code=org_code)
    db.session.add(org)
    db.session.flush()

    temp_password = _gen_password()
    otp_code      = _gen_otp()

    admin = User(
        name=prov.contact_name.strip(),
        email=email,
        phone=prov.contact_phone,
        role=RoleEnum.admin,
        is_active=True,
        org_id=org.id,
    )
    admin.set_password(temp_password)
    admin.set_setup_otp(otp_code)
    db.session.add(admin)
    db.session.flush()

    prov.status               = ProvisionStatus.ACTIVE
    prov.payment_confirmed_at = datetime.now(timezone.utc)
    prov.org_id               = org.id
    prov.admin_user_id        = admin.id

    db.session.commit()

    send_org_credentials_email(
        to_email=email,
        contact_name=prov.contact_name,
        org_name=prov.org_name,
        admin_email=email,
        temp_password=temp_password,
        otp_code=otp_code,
        org_code=org_code,
    )

    return prov, temp_password, otp_code


def deactivate_org(prov: OrgProvision) -> tuple[bool, str]:
    """Deactivate the Organisation linked to a provision."""
    if prov.status != ProvisionStatus.ACTIVE or not prov.org_id:
        return False, "organisation is not active"
    org = Organisation.query.get(prov.org_id)
    if not org:
        return False, "organisation not found"
    if not org.is_active:
        return False, "organisation is already inactive"
    org.is_active = False
    db.session.commit()
    return True, "organisation deactivated"


def reactivate_org(prov: OrgProvision) -> tuple[bool, str]:
    """Reactivate a deactivated Organisation and resend fresh credentials."""
    if prov.status != ProvisionStatus.ACTIVE or not prov.org_id:
        return False, "provision has not been activated"
    org = Organisation.query.get(prov.org_id)
    if not org:
        return False, "organisation not found"
    if org.is_active:
        return False, "organisation is already active"
    org.is_active = True
    db.session.commit()
    # Immediately issue fresh credentials so admin can log back in
    resend_credentials(prov)
    return True, "organisation reactivated and credentials sent via email"


def resend_credentials(prov: OrgProvision) -> tuple[bool, str]:
    """Regenerate OTP and resend credentials email (password reset not exposed)."""
    if prov.status != ProvisionStatus.ACTIVE or not prov.admin_user_id:
        return False, "provision not yet activated"

    otp_code = _gen_otp()
    temp_password = _gen_password()

    admin = User.query.get(prov.admin_user_id)
    if not admin:
        return False, "admin user not found"

    admin.set_password(temp_password)
    admin.set_setup_otp(otp_code)
    db.session.commit()

    from ...models.organisation import Organisation as Org
    org = Org.query.get(prov.org_id)
    send_org_credentials_email(
        to_email=prov.contact_email,
        contact_name=prov.contact_name,
        org_name=prov.org_name,
        admin_email=prov.contact_email,
        temp_password=temp_password,
        otp_code=otp_code,
        org_code=org.org_code if org else None,
    )
    return True, "credentials resent"
