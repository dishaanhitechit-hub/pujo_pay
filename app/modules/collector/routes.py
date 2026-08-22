from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import get_summary, get_payments, get_all_events

bp = Blueprint("collector", __name__)


@bp.route("/events", methods=["GET"])
@require_permission("collector.view_own")
def events():
    """All events for the collector's event filter dropdown in reporting pages."""
    return res(data=get_all_events())


@bp.route("/summary", methods=["GET"])
@require_permission("collector.view_own")
def summary():
    collector_id = int(get_jwt_identity())
    event_id = request.args.get("eventId", type=int)
    data = get_summary(collector_id, event_id=event_id)
    return res(data=data)


@bp.route("/payments", methods=["GET"])
@require_permission("collector.view_own")
def payments():
    collector_id = int(get_jwt_identity())

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("perPage", 20, type=int), 100)
    method = request.args.get("method")
    status = request.args.get("status")
    event_id = request.args.get("eventId", type=int)
    date = request.args.get("date")
    donor_type = request.args.get("donorType")
    search = request.args.get("search", "").strip() or None
    date_from = request.args.get("dateFrom", "").strip() or None
    date_to = request.args.get("dateTo", "").strip() or None
    min_amount = request.args.get("minAmount", "").strip() or None
    max_amount = request.args.get("maxAmount", "").strip() or None

    data = get_payments(
        collector_id=collector_id,
        page=page,
        per_page=per_page,
        method=method,
        status=status,
        event_id=event_id,
        date=date,
        donor_type=donor_type,
        search=search,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
    )
    return res(data=data)
