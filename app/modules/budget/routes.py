from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from marshmallow import ValidationError

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import (
    create_budget_category_schema, update_budget_category_schema, reorder_schema,
    get_categories, get_budget_report, get_all_events_budget_summary,
    create_category, update_category, delete_category, reorder_categories,
)

bp = Blueprint("budget", __name__)


@bp.route("/all-summary", methods=["GET"])
@require_permission("dashboard.view")
def all_summary():
    return res(data=get_all_events_budget_summary())


@bp.route("/", methods=["GET"])
@require_permission("dashboard.view")
def list_categories():
    event_id = request.args.get("eventId", type=int)
    search   = request.args.get("search", "").strip() or None
    page     = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("perPage", 50, type=int), 200)
    return res(data=get_categories(event_id=event_id, search=search, page=page, per_page=per_page))


@bp.route("/report", methods=["GET"])
@require_permission("dashboard.view")
def budget_report():
    event_id = request.args.get("eventId", type=int)
    if not event_id:
        return res("eventId is required", code=400)
    from ...models.event import Event as EventModel
    if not EventModel.query.get(event_id):
        return res("event not found", code=404)
    return res(data=get_budget_report(event_id))


@bp.route("/", methods=["POST"])
@require_permission("event.manage")
def create():
    body = request.get_json(silent=True) or {}
    try:
        data = create_budget_category_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    from ...models.event import Event as EventModel
    if not EventModel.query.get(data["event_id"]):
        return res("event not found", code=404)

    created_by = int(get_jwt_identity())
    cat = create_category(data, created_by)
    return res("budget category created", data=cat.to_dict(), code=201)


@bp.route("/<int:cat_id>", methods=["PATCH"])
@require_permission("event.manage")
def update(cat_id: int):
    body = request.get_json(silent=True) or {}
    try:
        data = update_budget_category_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    cat, err = update_category(cat_id, data)
    if err:
        return res(err, code=404)
    return res("budget category updated", data=cat.to_dict())


@bp.route("/<int:cat_id>", methods=["DELETE"])
@require_permission("event.manage")
def delete(cat_id: int):
    found = delete_category(cat_id)
    if not found:
        return res("budget category not found", code=404)
    return res("budget category deleted")


@bp.route("/reorder", methods=["POST"])
@require_permission("event.manage")
def reorder():
    body = request.get_json(silent=True) or {}
    event_id = body.get("eventId")
    if not event_id:
        return res("eventId is required", code=400)
    try:
        data = reorder_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    ok = reorder_categories(int(event_id), data["ids"])
    if not ok:
        return res("some category ids do not belong to this event", code=400)
    return res("categories reordered")
