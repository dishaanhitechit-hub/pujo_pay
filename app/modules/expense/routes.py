from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from marshmallow import ValidationError

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import (
    create_expense_schema, update_expense_schema,
    get_expenses, get_event_expense_summary,
    create_expense, update_expense, delete_expense,
)

bp = Blueprint("expense", __name__)


def _get_event(event_id: int):
    from ...models.event import Event as EventModel
    return EventModel.query.get(event_id)


@bp.route("/", methods=["GET"])
@require_permission("event.manage")
def list_expenses(event_id: int):
    if not _get_event(event_id):
        return res("event not found", code=404)

    page      = request.args.get("page", 1, type=int)
    per_page  = min(request.args.get("perPage", 20, type=int), 100)
    search    = request.args.get("search", "").strip() or None
    mode      = request.args.get("mode", "").strip() or None
    date_from = request.args.get("dateFrom", "").strip() or None
    date_to   = request.args.get("dateTo", "").strip() or None
    min_amt   = request.args.get("minAmount", "").strip() or None
    max_amt   = request.args.get("maxAmount", "").strip() or None

    data    = get_expenses(event_id, page, per_page, search, mode, date_from, date_to, min_amt, max_amt)
    summary = get_event_expense_summary(event_id)
    return res(data={**data, "summary": summary})


@bp.route("/", methods=["POST"])
@require_permission("event.manage")
def create(event_id: int):
    if not _get_event(event_id):
        return res("event not found", code=404)

    body = request.get_json(silent=True) or {}
    try:
        data = create_expense_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    created_by = int(get_jwt_identity())
    expense = create_expense(event_id, data, created_by)
    return res("expense created", data=expense.to_dict(), code=201)


@bp.route("/<int:expense_id>", methods=["PATCH"])
@require_permission("event.manage")
def update(event_id: int, expense_id: int):
    body = request.get_json(silent=True) or {}
    try:
        data = update_expense_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    expense, err = update_expense(expense_id, event_id, data)
    if err:
        return res(err, code=404)
    return res("expense updated", data=expense.to_dict())


@bp.route("/<int:expense_id>", methods=["DELETE"])
@require_permission("event.manage")
def delete(event_id: int, expense_id: int):
    found = delete_expense(expense_id, event_id)
    if not found:
        return res("expense not found", code=404)
    return res("expense deleted")
