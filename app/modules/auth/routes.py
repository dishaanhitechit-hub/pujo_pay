from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from ...extensions import add_to_blocklist
from ...utils.helpers import res
from ...middleware.perm_resolver import effective_permissions
from ...services.rate_limiter import check_and_record, retry_message
from .service import (
    get_user_by_credentials, get_super_admin_by_credentials, get_active_user, first_setup, orgs_for_email,
    request_password_reset, reset_password, change_password,
)

bp = Blueprint("auth", __name__)

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
FORGOT_RESPONSE = "If an account matches these details, a 6-digit code has been sent to its email."


def _user_data(user) -> dict:
    """User payload including their resolved effective permissions."""
    role = user.role.value if hasattr(user.role, "value") else user.role
    return {**user.to_dict(), "permissions": sorted(effective_permissions(user.id, role))}


def _issue_session(user) -> dict:
    token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role.value, "org_id": user.org_id},
    )
    return {"accessToken": token, "user": _user_data(user)}


def _client_ip() -> str:
    return request.remote_addr or "unknown"


def _rate_limited(*checks):
    """Each check is (bucket, (limit, window_seconds), ...). Returns a 429 response or None."""
    for bucket, *rules in checks:
        wait = check_and_record(bucket, *rules)
        if wait:
            return res(retry_message(wait), data={"retryAfter": wait}, code=429)
    return None


def _password_problem(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"password must be at least {MIN_PASSWORD_LENGTH} characters"
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"password must be at most {MAX_PASSWORD_LENGTH} characters"
    return None


@bp.route("/orgs-by-email", methods=["GET"])
def orgs_by_email():
    """
    Public endpoint — returns orgs (code, name, role) for a given email.
    Used by the login page to populate the org-code dropdown.
    Body: ?email=...
    """
    email = (request.args.get("email") or "").strip().lower()
    if not email:
        return res("email is required", code=400)
    return res(data=orgs_for_email(email))


@bp.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    email    = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    org_code = (body.get("orgCode") or "").strip()

    if not email or not password:
        return res("email and password are required", code=400)

    # Super admin login — no org_code required (platform org has none)
    if not org_code:
        user, reason = get_super_admin_by_credentials(email, password)
    else:
        user, reason = get_user_by_credentials(email, password, org_code)

    if reason == "invalid":
        return res("invalid credentials or organisation code", code=401)
    if reason == "setup_required":
        return res(
            "account setup required — use your one-time code to complete first login",
            data={"code": "SETUP_REQUIRED", "email": email, "orgCode": org_code},
            code=403,
        )

    return res("login successful", data=_issue_session(user))


@bp.route("/first-setup", methods=["POST"])
def first_setup_route():
    """
    One-time account activation for newly provisioned org admins.
    Body: { email, password, otpCode, orgCode, newPassword }
    """
    body = request.get_json(silent=True) or {}
    email        = (body.get("email") or "").strip().lower()
    password     = body.get("password") or ""
    otp_code     = (body.get("otpCode") or "").strip()
    org_code     = (body.get("orgCode") or "").strip()
    new_password = body.get("newPassword") or ""

    if not email or not password or not otp_code or not org_code or not new_password:
        return res("email, password, otpCode, orgCode and newPassword are required", code=400)
    if len(new_password) < 6:
        return res("newPassword must be at least 6 characters", code=400)

    user, error = first_setup(email, password, otp_code, new_password, org_code)
    if error:
        return res(error, code=401)

    return res("account activated", data=_issue_session(user))


# ── Forgot password (public) ───────────────────────────────────────────────
# Wrong codes / passwords return 400, never 401: the frontend logs the user out on any 401.

@bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """Body: { email, orgCode } — orgCode empty for the platform super admin."""
    body = request.get_json(silent=True) or {}
    email    = (body.get("email") or "").strip().lower()
    org_code = (body.get("orgCode") or "").strip().upper()
    if not email or "@" not in email:
        return res("a valid email is required", code=400)

    # The account bucket is counted whether or not the account exists, so a 429 reveals nothing.
    limited = _rate_limited(
        (f"forgot:ip:{_client_ip()}", (10, 3600)),
        (f"forgot:acct:{email}:{org_code}", (1, 60), (5, 3600)),
    )
    if limited:
        return limited

    request_password_reset(email, org_code, _client_ip())
    return res(FORGOT_RESPONSE)


@bp.route("/reset-password", methods=["POST"])
def reset_password_route():
    """Body: { email, orgCode, otpCode, newPassword } — logs the user in on success."""
    body = request.get_json(silent=True) or {}
    email        = (body.get("email") or "").strip().lower()
    org_code     = (body.get("orgCode") or "").strip().upper()
    otp_code     = (body.get("otpCode") or "").strip()
    new_password = body.get("newPassword") or ""

    if not email or not otp_code or not new_password:
        return res("email, otpCode and newPassword are required", code=400)
    if not (otp_code.isdigit() and len(otp_code) == 6):
        return res("code must be 6 digits", code=400)
    problem = _password_problem(new_password)
    if problem:
        return res(problem, code=400)

    limited = _rate_limited((f"reset:ip:{_client_ip()}", (20, 3600)))
    if limited:
        return limited

    user, error = reset_password(email, org_code, otp_code, new_password)
    if error:
        return res(error, code=400)
    return res("password reset", data=_issue_session(user))


@bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password_route():
    """Body: { currentPassword, newPassword } — returns a fresh token; all other sessions end."""
    user = get_active_user(int(get_jwt_identity()))
    if not user:
        return res("user not found", code=404)

    body = request.get_json(silent=True) or {}
    current_password = body.get("currentPassword") or ""
    new_password     = body.get("newPassword") or ""
    if not current_password or not new_password:
        return res("currentPassword and newPassword are required", code=400)
    problem = _password_problem(new_password)
    if problem:
        return res(problem, code=400)

    limited = _rate_limited((f"change:user:{user.id}", (5, 900)))
    if limited:
        return limited

    error = change_password(user, current_password, new_password)
    if error:
        return res(error, code=400)
    return res("password changed", data=_issue_session(user))


@bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    add_to_blocklist(jti)
    return res("logged out")


@bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user = get_active_user(int(get_jwt_identity()))
    if not user:
        return res("user not found", code=404)
    return res(data=_user_data(user))
