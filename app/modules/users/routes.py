import io
import qrcode
from flask import Blueprint, request, send_file
from flask_jwt_extended import get_jwt_identity
from marshmallow import ValidationError

from flask_jwt_extended import get_jwt

from ...extensions import db
from ...models.user import User
from ...middleware.permissions import require_permission
from ...middleware.tenant import get_current_org_id, require_same_org
from ...utils.helpers import res
from .service import (
    create_schema, update_schema, create_user, update_user,
    generate_next_member_id, member_id_exists,
)

bp = Blueprint("users", __name__)

_user_in_org = require_same_org(
    lambda user_id, **_: db.session.query(User.org_id).filter(User.id == user_id).first(),
    "user not found",
)


@bp.route("/", methods=["GET"])
@require_permission("users.manage")
def list_users():
    org_id = get_current_org_id()
    users = User.query.filter_by(org_id=org_id).order_by(User.created_at.desc()).all()
    return res(data=[u.to_dict() for u in users])


@bp.route("/next-member-id", methods=["GET"])
@require_permission("users.manage")
def next_member_id():
    return res(data={"memberId": generate_next_member_id(get_current_org_id())})


@bp.route("/", methods=["POST"])
@require_permission("users.manage")
def create_user_route():
    body = request.get_json(silent=True) or {}
    try:
        data = create_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    org_id = get_current_org_id()
    email = data.get("email")
    if email and User.query.filter_by(email=email.strip().lower(), org_id=org_id).first():
        return res("email already registered", code=409)

    member_id = (data.get("member_id") or "").strip()
    if member_id and member_id_exists(org_id, member_id):
        return res("member ID already in use", code=409)

    user = create_user(data, created_by=int(get_jwt_identity()), org_id=org_id)
    return res("user created", data=user.to_dict(), code=201)


@bp.route("/<int:user_id>", methods=["GET"])
@require_permission("users.manage")
def get_user(user_id):
    org_id = get_current_org_id()
    user = User.query.filter_by(id=user_id, org_id=org_id).first()
    if not user:
        return res("user not found", code=404)
    return res(data=user.to_dict())


@bp.route("/<int:user_id>", methods=["PATCH"])
@require_permission("users.manage")
def update_user_route(user_id):
    org_id = get_current_org_id()
    user = User.query.filter_by(id=user_id, org_id=org_id).first()
    if not user:
        return res("user not found", code=404)
    if not user.is_active:
        return res("cannot edit a deleted user", code=403)

    body = request.get_json(silent=True) or {}
    try:
        data = update_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    if "member_id" in data:
        member_id = (data.get("member_id") or "").strip()
        if member_id and member_id_exists(org_id, member_id, exclude_user_id=user.id):
            return res("member ID already in use", code=409)

    user = update_user(user, data)
    return res("user updated", data=user.to_dict())


@bp.route("/<int:user_id>", methods=["DELETE"])
@require_permission("users.manage")
def deactivate_user(user_id):
    if int(get_jwt_identity()) == user_id:
        return res("cannot deactivate your own account", code=400)

    org_id = get_current_org_id()
    user = User.query.filter_by(id=user_id, org_id=org_id).first()
    if not user:
        return res("user not found", code=404)

    user.is_active = False
    db.session.commit()
    return res(f"user '{user.name}' deactivated")


@bp.route("/<int:user_id>/soft-delete", methods=["POST"])
@require_permission("users.manage")
def soft_delete_user(user_id):
    if int(get_jwt_identity()) == user_id:
        return res("cannot delete your own account", code=400)

    org_id = get_current_org_id()
    user = User.query.filter_by(id=user_id, org_id=org_id).first()
    if not user:
        return res("user not found", code=404)

    user.is_active = False
    user.email     = None
    user.phone     = None
    db.session.commit()
    return res(f"user '{user.name}' deleted")


@bp.route("/<int:user_id>/login-qr", methods=["GET"])
@require_permission("users.manage")
@_user_in_org
def login_qr(user_id):
    user = User.query.get(user_id)
    if not user:
        return res("user not found", code=404)

    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(f"pujopay-login:{user.email}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png",
                     download_name=f"login-qr-{user.name}.png")
