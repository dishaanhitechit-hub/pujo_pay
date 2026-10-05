from decimal import Decimal
from datetime import datetime, timezone, date

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models.payment import Payment, MethodEnum, COMPLETED_STATUSES
from ...models.event import Event
from ...models.user import User
from ...models.handover import Handover, HandoverStatusEnum
from ...models.committee_role import YearRoleAssignment, EventRoleAssignment, CommitteeRoleEnum


def _cash_collected(collector_id: int, event_id: int) -> Decimal:
    """Total completed CASH collected by a collector for an event (what's physically in hand)."""
    total = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.collector_id == collector_id,
        Payment.event_id == event_id,
        Payment.status.in_(COMPLETED_STATUSES),
        Payment.method == MethodEnum.cash,
    ).scalar()
    return Decimal(str(total))


def _collected_by_method(collector_id: int, event_id: int) -> tuple[Decimal, Decimal]:
    """Return (total_collected_all_methods, online_collected) for a collector+event."""
    total = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.collector_id == collector_id,
        Payment.event_id == event_id,
        Payment.status.in_(COMPLETED_STATUSES),
    ).scalar()
    total = Decimal(str(total))
    cash = _cash_collected(collector_id, event_id)
    return total, total - cash


def _handover_sums(collector_id: int, event_id: int) -> tuple[Decimal, Decimal]:
    """Return (accepted_total, pending_total) for a collector+event."""
    rows = db.session.query(
        Handover.status, func.coalesce(func.sum(Handover.amount), 0),
    ).filter(
        Handover.collector_id == collector_id, Handover.event_id == event_id,
    ).group_by(Handover.status).all()
    accepted = Decimal("0")
    pending = Decimal("0")
    for status, total in rows:
        if status == HandoverStatusEnum.accepted:
            accepted = Decimal(str(total))
        elif status == HandoverStatusEnum.pending:
            pending = Decimal(str(total))
    return accepted, pending


def _event_summary(collector_id: int, event: Event) -> dict:
    collected = _cash_collected(collector_id, event.id)
    total_all, online = _collected_by_method(collector_id, event.id)
    accepted, pending = _handover_sums(collector_id, event.id)
    in_hand = collected - accepted            # still held (incl. amounts in pending handovers)
    available = collected - accepted - pending  # free to hand over now
    return {
        "eventId":    event.id,
        "eventName":  event.name,
        "totalCollected": str(total_all),   # all methods
        "onlineCollected": str(online),     # UPI/cheque — already in the account
        "cashCollected": str(collected),    # physical cash the collector holds
        "handedOver":    str(accepted),
        "pending":       str(pending),
        "inHand":        str(in_hand),
        "available":     str(available),
    }


def get_collector_summary(org_id: int | None, collector_id: int) -> list[dict]:
    """Per-event cash-in-hand summary for a collector (events where they collected cash or have handovers)."""
    # events with cash collected
    ev_cash = db.session.query(Payment.event_id).filter(
        Payment.collector_id == collector_id,
        Payment.status.in_(COMPLETED_STATUSES),
        Payment.method == MethodEnum.cash,
    ).distinct()
    ev_handover = db.session.query(Handover.event_id).filter(Handover.collector_id == collector_id).distinct()
    event_ids = {e[0] for e in ev_cash} | {e[0] for e in ev_handover}
    if not event_ids:
        return []
    q = Event.query.filter(Event.id.in_(event_ids))
    if org_id is not None:
        q = q.filter(Event.org_id == org_id)
    events = q.order_by(Event.year.desc().nulls_last(), Event.id.desc()).all()
    return [_event_summary(collector_id, ev) for ev in events]


def get_handover_receivers(org_id: int | None) -> list[dict]:
    """Users who can receive a handover: admin, cashier (role), or treasurer (committee role)."""
    # Users with base role admin or cashier
    q_role = db.session.query(User.id).filter(
        User.role.in_(["admin", "cashier"]),
        User.is_active == True,
    )
    if org_id is not None:
        q_role = q_role.filter(User.org_id == org_id)

    # Users with treasurer or accountant year role assignment
    q_year = db.session.query(YearRoleAssignment.user_id).filter(
        YearRoleAssignment.role.in_([CommitteeRoleEnum.treasurer, CommitteeRoleEnum.accountant]),
    )
    if org_id is not None:
        q_year = q_year.filter(YearRoleAssignment.org_id == org_id)

    # Users with treasurer or accountant event role assignment
    q_event = db.session.query(EventRoleAssignment.user_id).filter(
        EventRoleAssignment.role.in_([CommitteeRoleEnum.treasurer, CommitteeRoleEnum.accountant]),
    )
    if org_id is not None:
        q_event = q_event.filter(EventRoleAssignment.org_id == org_id)

    all_ids = (
        {r[0] for r in q_role.all()}
        | {r[0] for r in q_year.all()}
        | {r[0] for r in q_event.all()}
    )
    if not all_ids:
        return []

    users = User.query.filter(User.id.in_(all_ids), User.is_active == True).order_by(User.name).all()
    return [{"id": u.id, "name": u.name, "role": u.role.value if hasattr(u.role, "value") else u.role} for u in users]


def create_handover(
    org_id, collector_id, event_id, amount, handover_date, note, handover_to_id=None
) -> tuple[dict | None, str | None]:
    event = Event.query.get(event_id)
    if not event or (org_id is not None and event.org_id != org_id):
        return None, "event not found"
    amount = Decimal(str(amount))
    if amount <= 0:
        return None, "amount must be greater than zero"
    summary = _event_summary(collector_id, event)
    available = Decimal(summary["available"])
    if amount > available:
        return None, f"amount exceeds cash available to hand over (₹{available})"
    if handover_to_id is not None:
        receiver = User.query.get(handover_to_id)
        if not receiver:
            return None, "handover recipient not found"
    h = Handover(
        org_id=org_id, event_id=event_id, collector_id=collector_id,
        amount=amount, handover_date=handover_date or date.today(), note=note,
        status=HandoverStatusEnum.pending,
        handover_to_id=handover_to_id,
    )
    db.session.add(h)
    db.session.commit()
    return h.to_dict(), None


def list_handovers(
    org_id, collector_id=None, status=None, event_id=None,
    recipient_id=None, is_admin=False,
) -> list[dict]:
    q = Handover.query.options(
        joinedload(Handover.event),
        joinedload(Handover.collector),
        joinedload(Handover.reviewer),
        joinedload(Handover.handover_to),
    ).filter(Handover.org_id == org_id)
    if collector_id is not None:
        q = q.filter(Handover.collector_id == collector_id)
    if status:
        q = q.filter(Handover.status == HandoverStatusEnum(status))
    if event_id:
        q = q.filter(Handover.event_id == event_id)
    # Non-admin recipients only see handovers directed to them
    if not is_admin and recipient_id is not None:
        q = q.filter(Handover.handover_to_id == recipient_id)
    q = q.order_by(Handover.created_at.desc())
    return [h.to_dict() for h in q.all()]


def _review(
    org_id, handover_id, reviewer_id, new_status, reason=None, is_admin=False
) -> tuple[dict | None, str | None]:
    h = Handover.query.filter_by(id=handover_id, org_id=org_id).first()
    if not h:
        return None, "handover not found"
    if h.status != HandoverStatusEnum.pending:
        return None, f"handover already {h.status.value}"
    # Only the designated recipient (or admin) can approve/reject
    if h.handover_to_id is not None and not is_admin:
        if h.handover_to_id != reviewer_id:
            return None, "only the designated recipient can review this handover"
    h.status = new_status
    h.reviewed_by = reviewer_id
    h.reviewed_at = datetime.now(timezone.utc)
    if reason is not None:
        h.reject_reason = reason
    db.session.commit()
    return h.to_dict(), None


def accept_handover(org_id, handover_id, reviewer_id, is_admin=False):
    return _review(org_id, handover_id, reviewer_id, HandoverStatusEnum.accepted, is_admin=is_admin)


def reject_handover(org_id, handover_id, reviewer_id, reason, is_admin=False):
    return _review(org_id, handover_id, reviewer_id, HandoverStatusEnum.rejected, reason=reason or None, is_admin=is_admin)
