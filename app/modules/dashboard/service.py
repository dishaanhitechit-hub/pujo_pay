from decimal import Decimal
from datetime import datetime

from sqlalchemy import func

from ...extensions import db
from ...models.donor import Donor
from ...models.payment import Payment, MethodEnum, StatusEnum
from ...models.pledge import Pledge, PledgeStatusEnum
from ...models.user import User


def get_grand_summary() -> dict:
    base = Payment.query.filter_by(status=StatusEnum.confirmed)

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
    total_pending = Payment.query.filter_by(status=StatusEnum.pending).count()
    total_donors = db.session.query(func.count(func.distinct(Payment.donor_id))).scalar()

    total_pledged = db.session.query(
        func.coalesce(func.sum(Pledge.total_amount), 0)
    ).scalar()
    total_pledge_paid = db.session.query(
        func.coalesce(func.sum(Pledge.paid_amount), 0)
    ).scalar()
    open_pledge_count = Pledge.query.filter_by(status=PledgeStatusEnum.open).count()

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


def get_collector_breakdown() -> list:
    collectors = User.query.filter_by(is_active=True).order_by(User.name).all()
    result = []

    for collector in collectors:
        base = Payment.query.filter_by(
            collector_id=collector.id,
            status=StatusEnum.confirmed,
        )
        cash = base.filter_by(method=MethodEnum.cash).with_entities(
            func.coalesce(func.sum(Payment.amount), 0)
        ).scalar()
        upi = base.filter_by(method=MethodEnum.upi).with_entities(
            func.coalesce(func.sum(Payment.amount), 0)
        ).scalar()
        count = base.count()

        result.append({
            "collector": {"id": collector.id, "name": collector.name, "role": collector.role.value},
            "cashTotal": _fmt(cash),
            "upiTotal": _fmt(upi),
            "grandTotal": _fmt(Decimal(str(cash)) + Decimal(str(upi))),
            "confirmedCount": count,
        })

    return result


def get_all_payments(
    page: int = 1,
    per_page: int = 20,
    method: str | None = None,
    status: str | None = None,
    collector_id: int | None = None,
    date: str | None = None,
    donor_type: str | None = None,
) -> dict:
    query = Payment.query

    if method in ("cash", "upi", "cheque"):
        query = query.filter_by(method=MethodEnum(method))

    if status in ("pending", "confirmed", "expired"):
        query = query.filter_by(status=StatusEnum(status))

    if collector_id:
        query = query.filter_by(collector_id=collector_id)

    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(func.date(Payment.created_at) == day)
        except ValueError:
            pass

    if donor_type:
        query = query.join(Donor, Payment.donor_id == Donor.id).filter(Donor.donor_type == donor_type)

    query = query.order_by(Payment.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)

    return {
        "payments": [p.to_dict() for p in pagination.items],
        "page": pagination.page,
        "perPage": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }


def _fmt(value) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.01")))
