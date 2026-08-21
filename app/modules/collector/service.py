from decimal import Decimal
from datetime import datetime

from sqlalchemy import func

from ...extensions import db
from ...models.payment import Payment, MethodEnum, StatusEnum


def get_summary(collector_id: int) -> dict:
    base = Payment.query.filter_by(
        collector_id=collector_id,
        status=StatusEnum.confirmed,
    )

    cash_total = base.filter_by(method=MethodEnum.cash).with_entities(
        func.coalesce(func.sum(Payment.amount), 0)
    ).scalar()

    upi_total = base.filter_by(method=MethodEnum.upi).with_entities(
        func.coalesce(func.sum(Payment.amount), 0)
    ).scalar()

    count = base.count()
    pending_count = Payment.query.filter_by(
        collector_id=collector_id, status=StatusEnum.pending
    ).count()

    return {
        "cashTotal": str(Decimal(str(cash_total)).quantize(Decimal("0.01"))),
        "upiTotal": str(Decimal(str(upi_total)).quantize(Decimal("0.01"))),
        "grandTotal": str(
            (Decimal(str(cash_total)) + Decimal(str(upi_total))).quantize(Decimal("0.01"))
        ),
        "confirmedCount": count,
        "pendingCount": pending_count,
    }


def get_payments(
    collector_id: int,
    page: int = 1,
    per_page: int = 20,
    method: str | None = None,
    date: str | None = None,
) -> dict:
    query = Payment.query.filter_by(collector_id=collector_id)

    if method in ("cash", "upi"):
        query = query.filter_by(method=MethodEnum(method))

    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(func.date(Payment.created_at) == day)
        except ValueError:
            pass

    query = query.order_by(Payment.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)

    return {
        "payments": [p.to_dict() for p in pagination.items],
        "page": pagination.page,
        "perPage": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }
