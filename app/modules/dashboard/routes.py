from flask import Blueprint, request

from ...middleware.permissions import require_permission
from ...middleware.tenant import get_current_org_id
from ...middleware.event_scope import capability_event_ids, is_unrestricted, event_in_scope
from ...utils.helpers import res
from .service import get_grand_summary, get_collector_breakdown, get_all_payments, get_events_with_stats, get_event_report

bp = Blueprint("dashboard", __name__)


@bp.route("/events", methods=["GET"])
@require_permission("dashboard.view")
def events_stats():
    """Per-event aggregated stats. Admin sees all events; a cashier sees only the
    events they hold the cashier capability for; a plain member sees an overview of
    events they are part of."""
    from flask_jwt_extended import get_jwt_identity
    all_events = is_unrestricted()
    cashier_ids = None if all_events else capability_event_ids("cashier")
    # Cashier → restrict to their events; plain member (no cashier) → overview fallback.
    scope = cashier_ids if cashier_ids else None
    return res(data=get_events_with_stats(
        org_id=get_current_org_id(),
        viewer_id=int(get_jwt_identity()),
        all_events=all_events,
        scope_event_ids=scope,
    ))


@bp.route("/event-report/<int:event_id>", methods=["GET"])
@require_permission("payment.view_all")
def event_report(event_id: int):
    """Comprehensive event report: summary, modes, collector breakdown, pledges, expenses."""
    org_id = get_current_org_id()
    # A cashier may only view reports for events they hold the capability for.
    if not event_in_scope("cashier", event_id):
        return res("access denied: not a cashier for this event", code=403)
    from ...models.event import Event as EventModel
    q = EventModel.query.filter_by(id=event_id)
    if org_id is not None:
        q = q.filter(EventModel.org_id == org_id)
    if not q.first():
        return res("event not found", code=404)
    return res(data=get_event_report(event_id, org_id=org_id))


@bp.route("/summary", methods=["GET"])
@require_permission("dashboard.view")
def summary():
    event_id = request.args.get("eventId", type=int)
    scope = capability_event_ids("cashier")  # None for admin
    if event_id and not event_in_scope("cashier", event_id):
        return res("access denied: not a cashier for this event", code=403)
    return res(data=get_grand_summary(event_id=event_id, org_id=get_current_org_id(), scope_event_ids=scope))


@bp.route("/collectors", methods=["GET"])
@require_permission("payment.view_all")
def collectors():
    event_id = request.args.get("eventId", type=int)
    if event_id and not event_in_scope("cashier", event_id):
        return res("access denied: not a cashier for this event", code=403)
    return res(data=get_collector_breakdown(
        event_id=event_id, org_id=get_current_org_id(),
        scope_event_ids=capability_event_ids("cashier"),
    ))


@bp.route("/payments", methods=["GET"])
@require_permission("payment.view_all")
def payments():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("perPage", 20, type=int), 100)
    method = request.args.get("method")
    status = request.args.get("status")
    collector_id = request.args.get("collectorId", type=int)
    event_id = request.args.get("eventId", type=int)
    if event_id and not event_in_scope("cashier", event_id):
        return res("access denied: not a cashier for this event", code=403)
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
        org_id=get_current_org_id(),
        scope_event_ids=capability_event_ids("cashier"),
    )
    return res(data=data)
