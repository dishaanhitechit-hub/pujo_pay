from ...extensions import db
from ...models.user import User


def get_user_by_credentials(email: str, password: str) -> tuple[User | None, str | None]:
    """
    Returns (user, None) on success.
    Returns (None, 'setup_required') if credentials are correct but first-setup OTP is pending.
    Returns (None, 'invalid') on bad credentials.
    """
    user = User.query.filter_by(email=email.strip().lower(), is_active=True).first()
    if not user or not user.check_password(password):
        return None, "invalid"
    if user.needs_first_setup:
        return None, "setup_required"
    return user, None


def get_active_user(user_id: int) -> User | None:
    return User.query.filter_by(id=user_id, is_active=True).first()


def first_setup(
    email: str,
    password: str,
    otp_code: str,
    new_password: str,
    org_code: str,
) -> tuple[User | None, str | None]:
    """Verify temp credentials + OTP + org code, set new password, clear the OTP."""
    user = User.query.filter_by(email=email, is_active=True).first()
    if not user or not user.check_password(password):
        return None, "invalid credentials"
    if not user.setup_otp_hash:
        return None, "no setup pending for this account"
    if user.setup_otp_used:
        return None, "one-time code has already been used"
    if not user.check_setup_otp(otp_code):
        return None, "invalid one-time code"

    # Verify org code (case-insensitive)
    from ...models.organisation import Organisation
    org = Organisation.query.get(user.org_id) if user.org_id else None
    if not org or not org.org_code:
        return None, "organisation code not configured — contact support"
    if org.org_code.upper() != (org_code or "").strip().upper():
        return None, "invalid organisation code"

    user.set_password(new_password)
    user.setup_otp_used = True
    db.session.commit()

    return user, None
