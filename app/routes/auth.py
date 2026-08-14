from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from ..models.user import User
from ..extensions import add_to_blocklist
from ..utils.helpers import success, error

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or not password:
        return error("email and password are required", 400)

    user = User.query.filter_by(email=email, is_active=True).first()
    if not user or not user.check_password(password):
        return error("invalid credentials", 401)

    token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role.value},
    )
    return success(
        data={"access_token": token, "user": user.to_dict()},
        message="login successful",
    )


@bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    add_to_blocklist(jti)
    return success(message="logged out")


@bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return error("user not found", 404)
    return success(data=user.to_dict())
