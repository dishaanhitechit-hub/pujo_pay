from decimal import Decimal
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import contains_eager, joinedload

from ...extensions import db
from ...models.donor import Donor
from ...models.payment import Payment, MethodEnum, StatusEnum, COMPLETED_STATUSES


def get_summary(collector_id: int) -> dict:
    base = Payment.query.filter(
        Payment.collector_id == collector_id,
        Payment.status.in_(COMPLETED_STATUSES),
    )

    cash_total = base.filter_by(method=MethodEnum.cash).with_entities(
        func.coalesce(func.sum(Payment.amount), 0)
    ).scalar()

    upi_total = base.filter_by(method=MethodEnum.upi).with_entities(
        func.coalesce(func.sum(Payment.amount), 0)
    ).scalar()

    cheque_total = base.filter_by(method=MethodEnum.cheque).with_entities(
        func.coalesce(func.sum(Payment.amount), 0)
    ).scalar()

    count = base.count()
    pending_count = Payment.query.filter_by(
        collector_id=collector_id, status=StatusEnum.pending
    ).count()

    return {
        "cashTotal": str(Decimal(str(cash_total)).quantize(Decimal("0.01"))),
        "upiTotal": str(Decimal(str(upi_total)).quantize(Decimal("0.01"))),
        "chequeTotal": str(Decimal(str(cheque_total)).quantize(Decimal("0.01"))),
        "grandTotal": str(
            (Decimal(str(cash_total)) + Decimal(str(upi_total)) + Decimal(str(cheque_total))).quantize(Decimal("0.01"))
        ),
        "confirmedCount": count,
        "pendingCount": pending_count,
    }


def get_payments(
    collector_id: int,
    page: int = 1,
    per_page: int = 20,
    method: str | None = None,
    status: str | None = None,
    event_id: int | None = None,
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    donor_type: str | None = None,
    min_amount: str | None = None,
    max_amount: str | None = None,
    search: str | None = None,
) -> dict:
    # Join Donor to eliminate N+1 and enable donor-based filtering/search.
    # Collector is always the logged-in user, so joinedload (no filter needed).
    query = (
        Payment.query
        .filter(Payment.collector_id == collector_id)
        .join(Donor, Payment.donor_id == Donor.id)
        .options(
            contains_eager(Payment.donor),
            joinedload(Payment.collector),
        )
    )

    if method in ("cash", "upi", "cheque"):
        query = query.filter(Payment.method == MethodEnum(method))

    if event_id:
        query = query.filter(Payment.event_id == event_id)

    if status == "completed":
        query = query.filter(Payment.status.in_(COMPLETED_STATUSES))
    elif status in ("pending", "expired", "cancelled"):
        query = query.filter(Payment.status == StatusEnum(status))

    # Legacy single-day filter (backward compat)
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
        # Collector name excluded — it's always the logged-in user
        query = query.filter(
            Payment.receipt_no.ilike(like)
            | Donor.name.ilike(like)
            | Donor.phone.ilike(like)
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
