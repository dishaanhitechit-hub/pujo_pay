from decimal import Decimal
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import contains_eager

from ...extensions import db
from ...models.donor import Donor
from ...models.payment import Payment, MethodEnum, StatusEnum, COMPLETED_STATUSES
from ...models.pledge import Pledge, PledgeStatusEnum
from ...models.user import User


def get_grand_summary(event_id: int | None = None) -> dict:
    base = Payment.query.filter(Payment.status.in_(COMPLETED_STATUSES))
    if event_id:
        base = base.filter(Payment.event_id == event_id)

    cash_total = base.filter_by(method=MethodEnum.cash).with_entities(
        func.coalesce(func.sum(Payment.amount), 0)
    ).scalar()

    upi_total = base.filter_by(method=MethodEnum.upi).with_entities(
        func.coalesce(func.sum(Payment.amount), 0)
    ).scalar()

    cheque_total = base.filter_by(method=MethodEnum.cheque).with_entities(
        func.coalesce(func.sum(Payment.amount), 0)
    ).scalar()

    total_confirmed = base.count()

    pending_q = Payment.query.filter_by(status=StatusEnum.pending)
    if event_id:
        pending_q = pending_q.filter(Payment.event_id == event_id)
    total_pending = pending_q.count()

    donors_q = db.session.query(func.count(func.distinct(Payment.donor_id)))
    if event_id:
        donors_q = donors_q.filter(Payment.event_id == event_id)
    total_donors = donors_q.scalar()

    pledge_q = Pledge.query
    if event_id:
        pledge_q = pledge_q.filter(Pledge.event_id == event_id)

    total_pledged = pledge_q.with_entities(func.coalesce(func.sum(Pledge.total_amount), 0)).scalar()
    total_pledge_paid = pledge_q.with_entities(func.coalesce(func.sum(Pledge.paid_amount), 0)).scalar()
    open_pledge_count = pledge_q.filter(Pledge.status == PledgeStatusEnum.open).count()

    grand = Decimal(str(cash_total)) + Decimal(str(upi_total)) + Decimal(str(cheque_total))

    return {
        "cashTotal": _fmt(cash_total),
        "upiTotal": _fmt(upi_total),
        "chequeTotal": _fmt(cheque_total),
        "grandTotal": _fmt(grand),
        "confirmedCount": total_confirmed,
        "pendingCount": total_pending,
        "totalDonors": total_donors,
        "totalPledged": _fmt(total_pledged),
        "totalPledgePaid": _fmt(total_pledge_paid),
        "totalPledgeOutstanding": _fmt(Decimal(str(total_pledged)) - Decimal(str(total_pledge_paid))),
        "openPledgeCount": open_pledge_count,
    }


def get_collector_breakdown(event_id: int | None = None) -> list:
    collectors = User.query.filter_by(is_active=True).order_by(User.name).all()
    if not collectors:
        return []

    collector_ids = [c.id for c in collectors]
    agg_filters = [
        Payment.status.in_(COMPLETED_STATUSES),
        Payment.collector_id.in_(collector_ids),
    ]
    if event_id:
        agg_filters.append(Payment.event_id == event_id)

    agg_rows = (
        db.session.query(
            Payment.collector_id,
            Payment.method,
            func.coalesce(func.sum(Payment.amount), 0).label("total"),
            func.count(Payment.id).label("cnt"),
        )
        .filter(*agg_filters)
        .group_by(Payment.collector_id, Payment.method)
        .all()
    )

    totals: dict[int, dict] = {
        c.id: {"cash": Decimal("0"), "upi": Decimal("0"), "cheque": Decimal("0"), "count": 0}
        for c in collectors
    }
    for row in agg_rows:
        t = totals[row.collector_id]
        t[row.method.value] = Decimal(str(row.total))
        t["count"] += int(row.cnt)

    result = []
    for collector in collectors:
        t = totals[collector.id]
        cash, upi, cheque = t["cash"], t["upi"], t["cheque"]
        result.append({
            "collector": {"id": collector.id, "name": collector.name, "role": collector.role.value},
            "cashTotal": _fmt(cash),
            "upiTotal": _fmt(upi),
            "chequeTotal": _fmt(cheque),
            "grandTotal": _fmt(cash + upi + cheque),
            "confirmedCount": t["count"],
        })

    return result


def get_all_payments(
    page: int = 1,
    per_page: int = 20,
    method: str | None = None,
    status: str | None = None,
    collector_id: int | None = None,
    event_id: int | None = None,
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    donor_type: str | None = None,
    min_amount: str | None = None,
    max_amount: str | None = None,
    search: str | None = None,
) -> dict:
    query = (
        Payment.query
        .join(Donor, Payment.donor_id == Donor.id)
        .join(User, Payment.collector_id == User.id)
        .options(
            contains_eager(Payment.donor),
            contains_eager(Payment.collector),
        )
    )

    if method in ("cash", "upi", "cheque"):
        query = query.filter(Payment.method == MethodEnum(method))

    if status == "completed":
        query = query.filter(Payment.status.in_(COMPLETED_STATUSES))
    elif status in ("pending", "expired", "cancelled"):
        query = query.filter(Payment.status == StatusEnum(status))

    if collector_id:
        query = query.filter(Payment.collector_id == collector_id)

    if event_id:
        query = query.filter(Payment.event_id == event_id)

    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(func.date(Payment.created_at) == day)
        except ValueError:
            pass

    if date_from:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d").date()
            query = query.filter(Payment.created_at >= df)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").date()
            query = query.filter(Payment.created_at < dt + timedelta(days=1))
        except ValueError:
            pass

    if donor_type:
        query = query.filter(Donor.donor_type.ilike(donor_type))

    if min_amount:
        try:
            query = query.filter(Payment.amount >= Decimal(str(min_amount)))
        except Exception:
            pass

    if max_amount:
        try:
            query = query.filter(Payment.amount <= Decimal(str(max_amount)))
        except Exception:
            pass

    if search:
        like = f"%{search}%"
        query = query.filter(
            Payment.receipt_no.ilike(like)
            | Donor.name.ilike(like)
            | Donor.phone.ilike(like)
            | User.name.ilike(like)
        )

    query = query.order_by(Payment.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)

    return {
        "payments": [p.to_dict() for p in pagination.items],
        "page": pagination.page,
        "perPage": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }


def _get_expense_total(event_ids: list[int]) -> dict[int, Decimal]:
    """Return {event_id: total_expenses} for all given event_ids in one query."""
    try:
        from ..expense.service import get_expense_totals_for_events
        return get_expense_totals_for_events(event_ids)
    except Exception:
        return {}


def get_events_with_stats() -> list[dict]:
    """All events with per-event aggregated collection/pledge/expense stats."""
    from ...models.event import Event

    events = (
        Event.query
        .order_by(
            Event.year.desc().nullslast(),
            Event.start_date.desc().nullslast(),
            Event.created_at.desc(),
        )
        .all()
    )
    if not events:
        return []

    event_ids = [e.id for e in events]

    # Single grouped payment query (completed only)
    pay_rows = (
        db.session.query(
            Payment.event_id,
            func.coalesce(func.sum(Payment.amount), 0).label("total"),
            func.count(Payment.id).label("cnt"),
            func.count(func.distinct(Payment.donor_id)).label("donors"),
        )
        .filter(
            Payment.status.in_(COMPLETED_STATUSES),
            Payment.event_id.in_(event_ids),
        )
        .group_by(Payment.event_id)
        .all()
    )

    # Single grouped pledge query
    pledge_rows = (
        db.session.query(
            Pledge.event_id,
            func.coalesce(func.sum(Pledge.total_amount), 0).label("pledged"),
            func.coalesce(func.sum(Pledge.paid_amount), 0).label("paid"),
        )
        .filter(Pledge.event_id.in_(event_ids))
        .group_by(Pledge.event_id)
        .all()
    )

    expense_map = _get_expense_total(event_ids)

    # Budget totals from budget_categories (sum of planned_amount per event)
    try:
        from ...models.budget_category import BudgetCategory
        bud_rows = (
            db.session.query(
                BudgetCategory.event_id,
                func.coalesce(func.sum(BudgetCategory.planned_amount), 0).label("planned"),
            )
            .filter(BudgetCategory.event_id.in_(event_ids))
            .group_by(BudgetCategory.event_id)
            .all()
        )
        budget_map = {row.event_id: Decimal(str(row.planned)) for row in bud_rows}
    except Exception:
        budget_map = {}

    pay_map = {
        row.event_id: {
            "total":  Decimal(str(row.total)),
            "count":  int(row.cnt),
            "donors": int(row.donors),
        }
        for row in pay_rows
    }
    pledge_map = {
        row.event_id: {
            "pledged":     Decimal(str(row.pledged)),
            "outstanding": Decimal(str(row.pledged)) - Decimal(str(row.paid)),
        }
        for row in pledge_rows
    }

    result = []
    for e in events:
        pm      = pay_map.get(e.id, {"total": Decimal("0"), "count": 0, "donors": 0})
        pl      = pledge_map.get(e.id, {"pledged": Decimal("0"), "outstanding": Decimal("0")})
        exp_tot = expense_map.get(e.id, Decimal("0"))
        budget  = budget_map.get(e.id)
        balance = pm["total"] - exp_tot
        bud_rem = (budget - exp_tot) if budget is not None else None

        result.append({
            "event": {
                "id":        e.id,
                "name":      e.name,
                "year":      e.year,
                "status":    e.status.value,
                "startDate": e.start_date.isoformat() if e.start_date else None,
                "endDate":   e.end_date.isoformat() if e.end_date else None,
            },
            "donorCount":        pm["donors"],
            "totalReceived":     _fmt(pm["total"]),
            "paymentCount":      pm["count"],
            "totalPledged":      _fmt(pl["pledged"]),
            "pledgeOutstanding": _fmt(pl["outstanding"]),
            "expensesPaid":      _fmt(exp_tot),
            "balanceInHand":     _fmt(balance),
            "budget":            _fmt(budget) if budget is not None else None,
            "budgetRemaining":   _fmt(bud_rem) if bud_rem is not None else None,
            "overBudget":        (exp_tot > budget) if budget is not None else False,
        })

    return result


def get_event_report(event_id: int) -> dict:
    """Comprehensive report for a single event — used by admin event report panel."""
    from ...models.event import Event as EventModel

    event = EventModel.query.get(event_id)

    # ── Payment aggregations ──────────────────────────────────────────────────
    total_received = Decimal(str(
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.event_id == event_id, Payment.status.in_(COMPLETED_STATUSES))
        .scalar()
    ))

    donor_count = db.session.query(
        func.count(func.distinct(Payment.donor_id))
    ).filter(Payment.event_id == event_id).scalar() or 0

    # Status breakdown
    status_rows = (
        db.session.query(
            Payment.status,
            func.count(Payment.id).label("cnt"),
            func.coalesce(func.sum(Payment.amount), 0).label("total"),
        )
        .filter(Payment.event_id == event_id)
        .group_by(Payment.status)
        .all()
    )

    # Mode breakdown (completed payments only)
    mode_rows = (
        db.session.query(
            Payment.method,
            func.count(Payment.id).label("cnt"),
            func.coalesce(func.sum(Payment.amount), 0).label("total"),
        )
        .filter(Payment.event_id == event_id, Payment.status.in_(COMPLETED_STATUSES))
        .group_by(Payment.method)
        .all()
    )

    # ── Pledge aggregations ───────────────────────────────────────────────────
    pledge_q = Pledge.query.filter(Pledge.event_id == event_id)
    total_pledged = Decimal(str(
        pledge_q.with_entities(func.coalesce(func.sum(Pledge.total_amount), 0)).scalar()
    ))
    total_pledge_paid = Decimal(str(
        pledge_q.with_entities(func.coalesce(func.sum(Pledge.paid_amount), 0)).scalar()
    ))
    open_pledge_count = pledge_q.filter(Pledge.status == PledgeStatusEnum.open).count()

    # ── Expense aggregations ──────────────────────────────────────────────────
    try:
        from ..expense.service import get_event_expense_total, get_expense_summary
        from ..budget.service import get_budget_report
        from ...models.expense import Expense

        expenses_paid = get_event_expense_total(event_id)

        expense_mode_rows = (
            db.session.query(
                Expense.mode,
                func.coalesce(func.sum(Expense.amount), 0).label("total"),
                func.count(Expense.id).label("cnt"),
            )
            .filter(Expense.event_id == event_id)
            .group_by(Expense.mode)
            .all()
        )
        expense_mode_breakdown = [
            {
                "mode":  row.mode.value if hasattr(row.mode, "value") else row.mode,
                "total": _fmt(row.total),
                "count": int(row.cnt),
            }
            for row in expense_mode_rows
        ]
        try:
            budget_report = get_budget_report(event_id)
        except Exception:
            budget_report = None
    except Exception:
        expenses_paid = Decimal("0")
        expense_mode_breakdown = []
        budget_report = None

    # ── Budget & balance ──────────────────────────────────────────────────────
    # Budget is now category-based; pull totals from budget_report when available
    budget           = Decimal(budget_report["totals"]["totalPlanned"]) if budget_report else None
    budget_remaining = Decimal(budget_report["totals"]["remaining"])    if budget_report else None
    over_budget      = budget_report["totals"]["overBudget"]            if budget_report else False
    balance_in_hand  = total_received - expenses_paid

    # ── Derived status totals ─────────────────────────────────────────────────
    pending_total   = Decimal("0")
    cancelled_total = Decimal("0")
    completed_count = 0
    pending_count   = 0

    status_breakdown = []
    for row in status_rows:
        is_complete = row.status in COMPLETED_STATUSES
        status_label = "completed" if is_complete else row.status.value
        amt = Decimal(str(row.total))
        cnt = int(row.cnt)
        if is_complete:
            completed_count += cnt
        elif row.status == StatusEnum.pending:
            pending_total += amt
            pending_count += cnt
        elif row.status == StatusEnum.cancelled:
            cancelled_total += amt
        status_breakdown.append({
            "status": status_label,
            "count":  cnt,
            "total":  _fmt(amt),
        })

    # Consolidate duplicate "completed" rows (completed + confirmed both → completed)
    merged: dict[str, dict] = {}
    for s in status_breakdown:
        key = s["status"]
        if key in merged:
            merged[key]["count"] += s["count"]
            merged[key]["total"] = _fmt(Decimal(merged[key]["total"]) + Decimal(s["total"]))
        else:
            merged[key] = dict(s)
    status_breakdown = list(merged.values())

    # Collector breakdown (reuse existing function)
    collector_data = get_collector_breakdown(event_id=event_id)
    # Remove collectors with zero contributions from event-specific report
    collector_data = [c for c in collector_data if Decimal(c["grandTotal"]) > 0]

    return {
        "event": event.to_dict(include_days=False) if event else None,
        "summary": {
            "donorCount":       donor_count,
            "totalPledged":     _fmt(total_pledged),
            "totalReceived":    _fmt(total_received),
            "pendingAmount":    _fmt(pending_total),
            "cancelledAmount":  _fmt(cancelled_total),
            "budget":           _fmt(budget) if budget is not None else None,
            "expensesPaid":     _fmt(expenses_paid),
            "balanceInHand":    _fmt(balance_in_hand),
            "budgetRemaining":  _fmt(budget_remaining) if budget_remaining is not None else None,
            "overBudget":       over_budget,
            "completedCount":   completed_count,
            "pendingCount":     pending_count,
            "openPledgeCount":  open_pledge_count,
            "pledgeOutstanding": _fmt(total_pledged - total_pledge_paid),
            "pledgePaid":       _fmt(total_pledge_paid),
        },
        "paymentModes": [
            {
                "mode":  row.method.value if hasattr(row.method, "value") else row.method,
                "count": int(row.cnt),
                "total": _fmt(Decimal(str(row.total))),
            }
            for row in mode_rows
        ],
        "paymentStatusBreakdown": status_breakdown,
        "collectorBreakdown":     collector_data,
        "pledgeSummary": {
            "totalPledged": _fmt(total_pledged),
            "paid":         _fmt(total_pledge_paid),
            "outstanding":  _fmt(total_pledged - total_pledge_paid),
            "openCount":    open_pledge_count,
        },
        "expenseSummary": {
            "totalExpenses":    _fmt(expenses_paid),
            "modeBreakdown":    expense_mode_breakdown,
            "budgetReport":     budget_report,
        },
    }


def _fmt(value) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.01")))
