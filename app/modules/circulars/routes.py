from flask import Blueprint, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from marshmallow import ValidationError

from ...extensions import db
from ...models.circular import Circular
from ...models.user import User
from ...middleware.permissions import require_permission
from ...middleware.tenant import get_current_org_id, require_same_org
from ...utils.helpers import res
from .service import (
    create_circular_schema, update_circular_schema,
    list_circulars, create_circular, get_circular,
    update_circular, delete_circular,
    list_published_circulars,
)

bp = Blueprint("circulars", __name__)

_circular_in_org = require_same_org(
    lambda circular_id, **_: db.session.query(User.org_id)
    .join(Circular, Circular.created_by == User.id)
    .filter(Circular.id == circular_id).first(),
    "circular not found",
)


# ── Admin: full management ─────────────────────────────────────────────────

@bp.route("/", methods=["GET"])
@require_permission("content.manage")
def admin_list():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("perPage", 20, type=int)
    return res(data=list_circulars(page=page, per_page=per_page, org_id=get_current_org_id()))


@bp.route("/", methods=["POST"])
@require_permission("content.manage")
def admin_create():
    body = request.get_json(silent=True) or {}
    try:
        data = create_circular_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    created_by = int(get_jwt_identity())
    result, err = create_circular(data, created_by)
    if err:
        return res(err, code=400)
    return res("circular created", data=result, code=201)


@bp.route("/<int:circular_id>", methods=["GET"])
@require_permission("content.manage")
@_circular_in_org
def admin_detail(circular_id: int):
    result = get_circular(circular_id)
    if not result:
        return res("circular not found", code=404)
    return res(data=result)


@bp.route("/<int:circular_id>", methods=["PATCH"])
@require_permission("content.manage")
@_circular_in_org
def admin_update(circular_id: int):
    body = request.get_json(silent=True) or {}
    try:
        data = update_circular_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    result, err = update_circular(circular_id, data)
    if err == "circular not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("circular updated", data=result)


@bp.route("/<int:circular_id>", methods=["DELETE"])
@require_permission("content.manage")
@_circular_in_org
def admin_delete(circular_id: int):
    err = delete_circular(circular_id)
    if err:
        return res(err, code=404)
    return res("circular deleted")


# ── Member: published circulars only ───────────────────────────────────────

@bp.route("/published", methods=["GET"])
def member_list():
    verify_jwt_in_request()
    return res(data=list_published_circulars(
        search=request.args.get("search") or None,
        event_id=request.args.get("eventId", type=int),
        date_from=request.args.get("dateFrom") or None,
        date_to=request.args.get("dateTo") or None,
        page=request.args.get("page", 1, type=int),
        per_page=request.args.get("perPage", 20, type=int),
        org_id=get_current_org_id(),
    ))


@bp.route("/published/<int:circular_id>", methods=["GET"])
@_circular_in_org
def member_detail(circular_id: int):
    verify_jwt_in_request()
    from ...models.circular import Circular
    from sqlalchemy.orm import joinedload
    c = (
        Circular.query
        .options(joinedload(Circular.event), joinedload(Circular.creator))
        .filter_by(id=circular_id, is_published=True)
        .first()
    )
    if not c:
        return res("circular not found", code=404)
    return res(data=c.to_dict())
