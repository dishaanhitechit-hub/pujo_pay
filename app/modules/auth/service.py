import secrets
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from werkzeug.security import generate_password_hash, check_password_hash

from ...extensions import db
from ...models.user import User, RoleEnum
from ...models.organisation import Organisation
from ...models.password_reset import PasswordResetCode
from ...services.email_service import (
    send_email_async, send_password_reset_email, send_password_changed_email,
)
from ...utils.helpers import utcnow

RESET_CODE_TTL_MINUTES = 5
MAX_CODE_ATTEMPTS = 5
_IST = ZoneInfo("Asia/Kolkata")


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


# ── Forgot / change password ─────────────────────────────────────────────────

def find_account(email: str, org_code: str) -> User | None:
    """Active user for (email, org code). An empty org code means the platform super admin."""
    email = email.strip().lower()
    if org_code.strip():
        return _user_by_email_and_org_code(email, org_code)
    return User.query.filter_by(email=email, is_active=True, role=RoleEnum.super_admin).first()


def request_password_reset(email: str, org_code: str, request_ip: str | None) -> None:
    """Email a reset code when the account exists. Silent either way so callers can't probe accounts."""
    user = find_account(email, org_code)
    if not user or not user.email:
        return

    now = utcnow()
    # Only the newest code works — retire any earlier unused ones.
    PasswordResetCode.query.filter_by(user_id=user.id, used_at=None).update({"used_at": now})
    code = f"{secrets.randbelow(10 ** 6):06d}"
    db.session.add(PasswordResetCode(
        user_id=user.id,
        code_hash=generate_password_hash(code),
        expires_at=now + timedelta(minutes=RESET_CODE_TTL_MINUTES),
        request_ip=request_ip,
        created_at=now,
    ))
    db.session.commit()

    org = Organisation.query.get(user.org_id) if user.org_id else None
    send_email_async(
        send_password_reset_email, user.email, user.name, code,
        org.name if org else None, RESET_CODE_TTL_MINUTES,
    )


def reset_password(email: str, org_code: str, otp_code: str, new_password: str) -> tuple[User | None, str | None]:
    invalid = "invalid or expired code"
    user = find_account(email, org_code)
    if not user:
        return None, invalid

    now = utcnow()
    code_row = (
        PasswordResetCode.query
        .filter(
            PasswordResetCode.user_id == user.id,
            PasswordResetCode.used_at.is_(None),
            PasswordResetCode.expires_at > now,
        )
        .order_by(PasswordResetCode.created_at.desc())
        .with_for_update()  # serialise concurrent guesses so the attempt counter can't be raced
        .first()
    )
    if not code_row:
        return None, invalid

    if not check_password_hash(code_row.code_hash, otp_code):
        code_row.attempts += 1
        if code_row.attempts >= MAX_CODE_ATTEMPTS:
            code_row.used_at = now
        db.session.commit()
        left = MAX_CODE_ATTEMPTS - code_row.attempts
        if left <= 0:
            return None, "too many wrong attempts — request a new code"
        return None, f"invalid code — {left} attempt{'s' if left != 1 else ''} left"

    code_row.used_at = now
    user.set_password(new_password)
    if user.needs_first_setup:
        user.setup_otp_used = True  # the emailed code already proves they own the address
    db.session.commit()
    _notify_password_changed(user)
    return user, None


def change_password(user: User, current_password: str, new_password: str) -> str | None:
    if not user.check_password(current_password):
        return "current password is incorrect"
    if current_password == new_password:
        return "new password must be different from the current one"
    user.set_password(new_password)
    db.session.commit()
    _notify_password_changed(user)
    return None


def _notify_password_changed(user: User) -> None:
    if not user.email:
        return
    when = (
        user.password_changed_at.replace(tzinfo=timezone.utc)
        .astimezone(_IST)
        .strftime("%d %b %Y, %I:%M %p IST")
    )
    send_email_async(send_password_changed_email, user.email, user.name, when)


def token_issued_before_password_change(jwt_payload: dict) -> bool:
    """True when the token's user no longer exists or changed their password after it was issued."""
    try:
        user_id = int(jwt_payload["sub"])
    except (KeyError, TypeError, ValueError):
        return True
    row = db.session.query(User.password_changed_at).filter(User.id == user_id).first()
    if row is None:
        return True
    changed_at = row[0]
    if changed_at is None:
        return False
    # `iat` has whole-second precision, so a token issued in the same second as the change stays valid.
    return jwt_payload.get("iat", 0) < int(changed_at.replace(tzinfo=timezone.utc).timestamp())
