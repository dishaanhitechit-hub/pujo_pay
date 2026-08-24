import io
import qrcode
from flask import Blueprint, request, send_file
from flask_jwt_extended import get_jwt_identity
from marshmallow import ValidationError

from ...models.user import User
from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import create_schema, update_schema, create_user, update_user

bp = Blueprint("users", __name__)


@bp.route("/", methods=["GET"])
@require_permission("users.manage")
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return res(data=[u.to_dict() for u in users])


@bp.route("/", methods=["POST"])
@require_permission("users.manage")
def create_user_route():
    body = request.get_json(silent=True) or {}
    try:
        data = create_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    if User.query.filter_by(email=data["email"].strip().lower()).first():
        return res("email already registered", code=409)

    user = create_user(data, created_by=int(get_jwt_identity()))
    return res("user created", data=user.to_dict(), code=201)


@bp.route("/<int:user_id>", methods=["GET"])
@require_permission("users.manage")
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return res("user not found", code=404)
    return res(data=user.to_dict())


@bp.route("/<int:user_id>", methods=["PATCH"])
@require_permission("users.manage")
def update_user_route(user_id):
    user = User.query.get(user_id)
    if not user:
        return res("user not found", code=404)

    body = request.get_json(silent=True) or {}
    try:
        data = update_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    user = update_user(user, data)
    return res("user updated", data=user.to_dict())


@bp.route("/<int:user_id>", methods=["DELETE"])
@require_permission("users.manage")
def deactivate_user(user_id):
    if int(get_jwt_identity()) == user_id:
        return res("cannot deactivate your own account", code=400)

    user = User.query.get(user_id)
    if not user:
        return res("user not found", code=404)

    user.is_active = False
    from ...extensions import db
    db.session.commit()
    return res(f"user '{user.name}' deactivated")


@bp.route("/<int:user_id>/login-qr", methods=["GET"])
@require_permission("users.manage")
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
