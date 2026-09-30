from ...extensions import db
from ...models.user import User, RoleEnum
from ...models.organisation import Organisation


def _user_by_email_and_org_code(email: str, org_code: str) -> User | None:
    """Find the unique user row scoped to the org identified by org_code — single JOIN query."""
    return (
        User.query
        .join(Organisation, User.org_id == Organisation.id)
        .filter(
            User.email == email.strip().lower(),
            User.is_active == True,
            db.func.upper(Organisation.org_code) == org_code.strip().upper(),
        )
        .first()
    )


def get_user_by_credentials(email: str, password: str, org_code: str) -> tuple[User | None, str | None]:
    """
    Returns (user, None) on success.
    Returns (None, 'setup_required') if credentials are correct but first-setup OTP is pending.
    Returns (None, 'invalid') on bad credentials or unknown org_code.
    """
    user = _user_by_email_and_org_code(email, org_code)
    if not user or not user.check_password(password):
        return None, "invalid"
    if user.needs_first_setup:
        return None, "setup_required"
    return user, None


def get_super_admin_by_credentials(email: str, password: str) -> tuple[User | None, str | None]:
    """Login path for super admin only — no org_code required."""
    user = User.query.filter_by(email=email, is_active=True, role=RoleEnum.super_admin).first()
    if not user or not user.check_password(password):
        return None, "invalid"
    return user, None


def get_active_user(user_id: int) -> User | None:
    return User.query.filter_by(id=user_id, is_active=True).first()


def orgs_for_email(email: str) -> list[dict]:
    """Return all orgs a given email belongs to — single JOIN query, no N+1."""
    rows = (
        db.session.query(User, Organisation)
        .join(Organisation, User.org_id == Organisation.id)
        .filter(
            User.email == email.strip().lower(),
            User.is_active == True,
            Organisation.is_active == True,
            Organisation.org_code.isnot(None),
        )
        .all()
    )
    return [
        {
            "orgCode": org.org_code,
            "orgName": org.name,
            "role":    u.role.value if hasattr(u.role, "value") else u.role,
        }
        for u, org in rows
    ]


def first_setup(
    email: str,
    password: str,
    otp_code: str,
    new_password: str,
    org_code: str,
) -> tuple[User | None, str | None]:
    """Verify temp credentials + OTP + org code, set new password, clear the OTP."""
    # Scope lookup by org_code — prevents cross-org collision on same email
    user = _user_by_email_and_org_code(email, org_code)
    if not user or not user.check_password(password):
        return None, "invalid credentials or organisation code"
    if not user.setup_otp_hash:
        return None, "no setup pending for this account"
    if user.setup_otp_used:
        return None, "one-time code has already been used"
    if not user.check_setup_otp(otp_code):
        return None, "invalid one-time code"

    user.set_password(new_password)
    user.setup_otp_used = True
    db.session.commit()

    return user, None
