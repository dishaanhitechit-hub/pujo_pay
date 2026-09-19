from flask import Blueprint, request
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required
from marshmallow import ValidationError

from ...utils.helpers import res
from ...middleware.permissions import require_permission
from .service import register_org_schema, register_org, get_org, update_org

bp = Blueprint("org", __name__)


@bp.route("/register", methods=["POST"])
def register():
    body = request.get_json(silent=True) or {}
    try:
        data = register_org_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    result = register_org(data)
    if isinstance(result[1], str):
        return res(result[1], code=409)

    org, admin = result
    token = create_access_token(
        identity=str(admin.id),
        additional_claims={"role": admin.role.value, "org_id": org.id},
    )
    return res(
        "organisation registered",
        data={"org": org.to_dict(), "user": admin.to_dict(), "accessToken": token},
        code=201,
    )


@bp.route("/me", methods=["GET"])
@jwt_required()
def get_my_org():
    org_id = get_jwt().get("org_id")
    if not org_id:
        return res("no organisation linked to this account", code=404)
    org = get_org(org_id)
    if not org:
        return res("organisation not found", code=404)
    return res(data=org.to_dict())


@bp.route("/me", methods=["PATCH"])
@require_permission("org.manage")
def update_my_org():
    org_id = get_jwt().get("org_id")
    if not org_id:
        return res("no organisation linked to this account", code=404)
    org = get_org(org_id)
    if not org:
        return res("organisation not found", code=404)

    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return res("name is required", code=400)

    org = update_org(org, name)
    return res("organisation updated", data=org.to_dict())
