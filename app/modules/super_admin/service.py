import random
import secrets
import string
from datetime import datetime, timezone

from marshmallow import Schema, fields, validate

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


create_provision_schema = CreateProvisionSchema()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _gen_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _gen_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _unique_org_slug(base: str) -> str:
    candidate = base
    suffix = 2
    while Organisation.query.filter_by(slug=candidate).first():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


# ── Service functions ─────────────────────────────────────────────────────────

def create_provision(data: dict, created_by: int) -> OrgProvision:
    prov = OrgProvision(
        org_name=data["org_name"].strip(),
        contact_name=data["contact_name"].strip(),
        contact_email=data["contact_email"].strip().lower(),
        contact_phone=data.get("contact_phone"),
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

    if User.query.filter_by(email=email).first():
        return None, "email already registered as a user", ""

    slug = _unique_org_slug(_slugify_org(prov.org_name))

    org = Organisation(name=prov.org_name.strip(), slug=slug)
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
    )

    return prov, temp_password, otp_code


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

    send_org_credentials_email(
        to_email=prov.contact_email,
        contact_name=prov.contact_name,
        org_name=prov.org_name,
        admin_email=prov.contact_email,
        temp_password=temp_password,
        otp_code=otp_code,
    )
    return True, "credentials resent"
