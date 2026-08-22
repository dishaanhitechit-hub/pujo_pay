from decimal import Decimal

from sqlalchemy import func

from ...extensions import db
from ...models.donor import Donor
from ...models.payment import Payment, StatusEnum, COMPLETED_STATUSES


def _aggregate_subquery():
    """Returns a subquery: donor_id → totalDonated, confirmedCount, lastDonatedAt."""
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
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


def _donor_with_stats(donor, agg) -> dict:
    d = donor.to_dict()
    d["totalDonated"] = _fmt(agg.total_donated) if agg else "0.00"
    d["confirmedCount"] = agg.confirmed_count if agg else 0
    d["lastDonatedAt"] = (
        agg.last_donated_at.isoformat() if agg and agg.last_donated_at else None
    )
    return d


def get_donor_list(
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
    donor_type: str | None = None,
) -> dict:
    agg = _aggregate_subquery()

    query = (
        db.session.query(Donor, agg)
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

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        "donors": [_donor_with_stats(d, a) for d, a in pagination.items],
        "page": pagination.page,
        "perPage": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }


def get_donor_detail(donor_id: int) -> dict | None:
    agg = _aggregate_subquery()

    row = (
        db.session.query(Donor, agg)
        .outerjoin(agg, Donor.id == agg.c.donor_id)
        .filter(Donor.id == donor_id)
        .first()
    )

    if not row:
        return None

    donor, agg_row = row
    payments = (
        Payment.query.filter_by(donor_id=donor_id)
        .order_by(Payment.created_at.desc())
        .all()
    )

    payment_list = []
    for p in payments:
        payment_list.append({
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
            "confirmedAt": p.confirmed_at.isoformat() if p.confirmed_at else None,
            "createdAt": p.created_at.isoformat() if p.created_at else None,
        })

    return {
        "donor": _donor_with_stats(donor, agg_row),
        "payments": payment_list,
    }
