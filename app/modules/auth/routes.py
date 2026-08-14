from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from ...extensions import add_to_blocklist
from ...utils.helpers import res
from .service import get_user_by_credentials, get_active_user

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""

    if not email or not password:
        return res("email and password are required", code=400)

    user = get_user_by_credentials(email, password)
    if not user:
        return res("invalid credentials", code=401)

    token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role.value},
    )
    return res("login successful", data={"accessToken": token, "user": user.to_dict()})


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
    return res(data=user.to_dict())
