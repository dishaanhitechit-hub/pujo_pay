from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models.donor import Donor
from ...models.payment import Payment, COMPLETED_STATUSES


def _aggregate_subquery():
    """
    Subquery: donor_id → total_donated, confirmed_count, last_donated_at.
    Only counts payments whose status is in COMPLETED_STATUSES.
    """
    return (
        db.session.query(
            Payment.donor_id,
            func.coalesce(func.sum(Payment.amount), 0).label("total_donated"),
            func.count(Payment.id).label("confirmed_count"),
            func.max(Payment.confirmed_at).label("last_donated_at"),
        )
        .filter(Payment.status.in_(COMPLETED_STATUSES))
        .group_by(Payment.donor_id)
        .subquery()
    )


def _fmt(value) -> str:
    return str(Decimal(str(value or 0)).quantize(Decimal("0.01")))


def _donor_row_to_dict(donor, total_donated, confirmed_count, last_donated_at) -> dict:
    """Build the API dict for one donor row from the joined query result."""
    d = donor.to_dict()
    d["totalDonated"] = _fmt(total_donated)
    d["confirmedCount"] = int(confirmed_count) if confirmed_count is not None else 0
    d["lastDonatedAt"] = last_donated_at.isoformat() if last_donated_at else None
    return d


def _donor_query(
    search: str | None = None,
    donor_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
):
    """
    Returns a SQLAlchemy query yielding 4-tuples:
        (Donor, total_donated, confirmed_count, last_donated_at)

    Single LEFT OUTER JOIN on the aggregation subquery — no N+1.
    The outer coalesce handles donors with no completed payments (NULL from LEFT JOIN).

    Date filters apply to last_donated_at (the donor's most recent completed payment).
    Amount filters apply to total_donated (sum of all completed payments).
    Donors with no completed payments have total_donated=0 and last_donated_at=NULL;
    any date or min-amount filter naturally excludes them.
    """
    agg = _aggregate_subquery()

    query = (
        db.session.query(
            Donor,
            func.coalesce(agg.c.total_donated, 0).label("total_donated"),
            func.coalesce(agg.c.confirmed_count, 0).label("confirmed_count"),
            agg.c.last_donated_at,
        )
        .outerjoin(agg, Donor.id == agg.c.donor_id)
        .order_by(Donor.created_at.desc())
    )

    if search:
        like = f"%{search}%"
        query = query.filter(
            Donor.name.ilike(like) | Donor.phone.ilike(like)
        )

    if donor_type:
        query = query.filter(Donor.donor_type.ilike(donor_type))

    # Amount filters: compare against the subquery's total_donated column.
    # func.coalesce wraps it so donors with no payments (NULL) evaluate to 0.
    if min_amount is not None:
        query = query.filter(func.coalesce(agg.c.total_donated, 0) >= min_amount)

    if max_amount is not None:
        query = query.filter(func.coalesce(agg.c.total_donated, 0) <= max_amount)

    # Date filters: compare against last_donated_at in the subquery.
    # NULL last_donated_at (no payments) is excluded by inequality comparisons — correct.
    # dateTo upper bound uses < next day to include the full last day.
    if date_from is not None:
        query = query.filter(agg.c.last_donated_at >= date_from)

    if date_to is not None:
        query = query.filter(agg.c.last_donated_at < date_to + timedelta(days=1))

    return query


def get_donor_list(
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
    donor_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
) -> dict:
    query = _donor_query(
        search=search,
        donor_type=donor_type,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
    )
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    donors = [
        _donor_row_to_dict(donor, total_donated, confirmed_count, last_donated_at)
        for donor, total_donated, confirmed_count, last_donated_at in pagination.items
    ]

    return {
        "donors": donors,
        "page": pagination.page,
        "perPage": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }


def get_donor_detail(donor_id: int) -> dict | None:
    agg = _aggregate_subquery()

    row = (
        db.session.query(
            Donor,
            func.coalesce(agg.c.total_donated, 0).label("total_donated"),
            func.coalesce(agg.c.confirmed_count, 0).label("confirmed_count"),
            agg.c.last_donated_at,
        )
        .outerjoin(agg, Donor.id == agg.c.donor_id)
        .filter(Donor.id == donor_id)
        .first()
    )

    if not row:
        return None

    donor, total_donated, confirmed_count, last_donated_at = row

    payments = (
        Payment.query.filter_by(donor_id=donor_id)
        .options(joinedload(Payment.collector), joinedload(Payment.event))
        .order_by(Payment.created_at.desc())
        .all()
    )

    payment_list = [
        {
            "id": p.id,
            "receiptNo": p.receipt_no,
            "amount": str(p.amount),
            "method": p.method.value,
            "status": "completed" if p.status.value == "confirmed" else p.status.value,
            "utrNumber": p.utr_number,
            "collector": {
                "id": p.collector.id,
                "name": p.collector.name,
            } if p.collector else None,
            "event": {
                "id": p.event.id,
                "name": p.event.name,
            } if p.event else None,
            "confirmedAt": p.confirmed_at.isoformat() if p.confirmed_at else None,
            "createdAt": p.created_at.isoformat() if p.created_at else None,
        }
        for p in payments
    ]

    return {
        "donor": _donor_row_to_dict(donor, total_donated, confirmed_count, last_donated_at),
        "payments": payment_list,
    }
