from flask import Blueprint, request

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import get_grand_summary, get_collector_breakdown, get_all_payments, get_events_with_stats, get_event_report

bp = Blueprint("dashboard", __name__)


@bp.route("/events", methods=["GET"])
@require_permission("dashboard.view")
def events_stats():
    """All events with per-event aggregated stats (includes budget/expense when available)."""
    return res(data=get_events_with_stats())


@bp.route("/event-report/<int:event_id>", methods=["GET"])
@require_permission("event.manage")
def event_report(event_id: int):
    """Comprehensive event report: summary, modes, collector breakdown, pledges, expenses."""
    from ...models.event import Event as EventModel
    if not EventModel.query.get(event_id):
        return res("event not found", code=404)
    return res(data=get_event_report(event_id))


@bp.route("/summary", methods=["GET"])
@require_permission("dashboard.view")
def summary():
    event_id = request.args.get("eventId", type=int)
    return res(data=get_grand_summary(event_id=event_id))


@bp.route("/collectors", methods=["GET"])
@require_permission("dashboard.view")
def collectors():
    event_id = request.args.get("eventId", type=int)
    return res(data=get_collector_breakdown(event_id=event_id))


@bp.route("/payments", methods=["GET"])
@require_permission("dashboard.view")
def payments():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("perPage", 20, type=int), 100)
    method = request.args.get("method")
    status = request.args.get("status")
    collector_id = request.args.get("collectorId", type=int)
    event_id = request.args.get("eventId", type=int)
    date = request.args.get("date")
    donor_type = request.args.get("donorType")
    search = request.args.get("search", "").strip() or None
    date_from = request.args.get("dateFrom", "").strip() or None
    date_to = request.args.get("dateTo", "").strip() or None
    min_amount = request.args.get("minAmount", "").strip() or None
    max_amount = request.args.get("maxAmount", "").strip() or None

    data = get_all_payments(
        page=page,
        per_page=per_page,
        method=method,
        status=status,
        collector_id=collector_id,
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
