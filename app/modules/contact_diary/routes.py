from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from marshmallow import ValidationError

from ...middleware.permissions import require_permission
from ...middleware.tenant import get_current_org_id
from ...utils.helpers import res
from .service import (
    create_entry_schema, update_entry_schema,
    list_entries, create_entry, get_entry, update_entry, delete_entry,
)

bp = Blueprint("contact_diary", __name__)


@bp.route("/", methods=["GET"])
@require_permission("users.manage")
def index():
    page     = request.args.get("page",    default=1,  type=int)
    per_page = request.args.get("perPage", default=20, type=int)
    search   = request.args.get("search",  "").strip() or None
    return res(data=list_entries(
        org_id=get_current_org_id(),
        page=page, per_page=per_page, search=search,
    ))


@bp.route("/", methods=["POST"])
@require_permission("users.manage")
def create():
    body = request.get_json(silent=True) or {}
    try:
        data = create_entry_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    result = create_entry(data, created_by=int(get_jwt_identity()), org_id=get_current_org_id())
    return res("contact added", data=result, code=201)


@bp.route("/<int:entry_id>", methods=["GET"])
@require_permission("users.manage")
def detail(entry_id: int):
    result = get_entry(entry_id, org_id=get_current_org_id())
    if not result:
        return res("entry not found", code=404)
    return res(data=result)


@bp.route("/<int:entry_id>", methods=["PATCH"])
@require_permission("users.manage")
def update(entry_id: int):
    body = request.get_json(silent=True) or {}
    try:
        data = update_entry_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    result, err = update_entry(entry_id, data, org_id=get_current_org_id())
    if err == "entry not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("contact updated", data=result)


@bp.route("/<int:entry_id>", methods=["DELETE"])
@require_permission("users.manage")
def delete(entry_id: int):
    err = delete_entry(entry_id, org_id=get_current_org_id())
    if err == "entry not found":
        return res(err, code=404)
    return res("contact deleted")
