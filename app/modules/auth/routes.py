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
from .service import get_user_by_credentials, get_super_admin_by_credentials, get_active_user, first_setup, orgs_for_email

bp = Blueprint("auth", __name__)


def _user_data(user) -> dict:
    """User payload including their resolved effective permissions."""
    role = user.role.value if hasattr(user.role, "value") else user.role
    return {**user.to_dict(), "permissions": sorted(effective_permissions(user.id, role))}


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

    token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role.value, "org_id": user.org_id},
    )
    return res("login successful", data={"accessToken": token, "user": _user_data(user)})


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

    token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role.value, "org_id": user.org_id},
    )
    return res("account activated", data={"accessToken": token, "user": _user_data(user)})


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
