from decimal import Decimal
from datetime import datetime, timedelta

from marshmallow import Schema, fields, validate, validates, ValidationError  # noqa: F401
from sqlalchemy.orm import contains_eager, joinedload

from ...extensions import db
from ...models.donor import Donor
from ...models.event import Event, EventStatusEnum
from ...models.payment import Payment, MethodEnum, StatusEnum
from ...models.pledge import Pledge, PledgeStatusEnum
from ...models.user import User


# ── Schemas ────────────────────────────────────────────────────────────────

class CreatePledgeSchema(Schema):
    event_id      = fields.Int(required=True, data_key="eventId")
    donor_name    = fields.Str(required=True, data_key="donorName", validate=validate.Length(min=1, max=120))
    donor_phone   = fields.Str(load_default=None, data_key="donorPhone", validate=validate.Length(max=20))
    donor_address = fields.Str(load_default=None, data_key="donorAddress")
    donor_notes   = fields.Str(load_default=None, data_key="donorNotes")
    donor_type    = fields.Str(load_default=None, data_key="donorType")
    total_amount  = fields.Decimal(required=True, places=2, as_string=False, data_key="totalAmount")
    notes         = fields.Str(load_default=None)

    @validates("total_amount")
    def validate_total(self, value):
        if value <= Decimal("0"):
            raise ValidationError("totalAmount must be greater than zero")


class PayInstallmentSchema(Schema):
    amount = fields.Decimal(required=True, places=2, as_string=False)
    method = fields.Str(required=True, validate=validate.OneOf(["cash", "upi", "cheque"]))

    @validates("amount")
    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise ValidationError("amount must be greater than zero")


create_pledge_schema = CreatePledgeSchema()
pay_installment_schema = PayInstallmentSchema()


# ── Service ────────────────────────────────────────────────────────────────

def create_pledge(data: dict, collector_id: int) -> tuple[Pledge | None, str | None]:
    # Validate event — must exist, be published, and have collection enabled
    event = Event.query.get(data["event_id"])
    if not event:
        return None, "event not found"
    if event.status != EventStatusEnum.published or not event.collection_enabled:
        return None, "event is not currently accepting collections"

    donor = Donor(
        name=data["donor_name"].strip(),
        phone=data.get("donor_phone"),
        address=data.get("donor_address"),
        notes=data.get("donor_notes"),
        donor_type=data.get("donor_type"),
    )
    db.session.add(donor)
    db.session.flush()

    pledge = Pledge(
        donor_id=donor.id,
        collector_id=collector_id,
        event_id=data["event_id"],
        total_amount=data["total_amount"],
        paid_amount=Decimal("0"),
        notes=data.get("notes"),
    )
    db.session.add(pledge)
    db.session.commit()
    return pledge, None


def pay_installment(pledge_id: int, data: dict, collector_id: int) -> tuple[Payment | None, str | None]:
    pledge = Pledge.query.get(pledge_id)
    if not pledge:
        return None, "pledge not found"
    if pledge.collector_id != collector_id:
        return None, "forbidden"
    if pledge.status != PledgeStatusEnum.open:
        return None, f"pledge is {pledge.status.value} — cannot add payments"

    amount = Decimal(str(data["amount"]))
    outstanding = pledge.outstanding()
    if amount > outstanding:
        return None, f"amount exceeds outstanding balance of ₹{outstanding}"

    # Reuse the pledge's donor; inherit event from the pledge (collector cannot override)
    payment = Payment(
        donor_id=pledge.donor_id,
        collector_id=collector_id,
        amount=amount,
        method=MethodEnum(data["method"]),
        status=StatusEnum.pending,
        pledge_id=pledge.id,
        event_id=pledge.event_id,
    )
    db.session.add(payment)
    db.session.commit()
    return payment, None


def get_pledge(
    pledge_id: int,
    viewer_id: int,
    can_view_all: bool,
) -> tuple[dict | None, str | None]:
    pledge = Pledge.query.get(pledge_id)
    if not pledge:
        return None, "not_found"
    if not can_view_all and pledge.collector_id != viewer_id:
        return None, "forbidden"

    payments = (
        Payment.query.filter_by(pledge_id=pledge_id)
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
            "chequeNumber": p.cheque_number,
            "bankName": p.bank_name,
            "chequeDate": p.cheque_date.isoformat() if p.cheque_date else None,
            "collector": {
                "id": p.collector.id,
                "name": p.collector.name,
            } if p.collector else None,
            "confirmedAt": p.confirmed_at.isoformat() if p.confirmed_at else None,
            "createdAt": p.created_at.isoformat() if p.created_at else None,
        })

    return {"pledge": pledge.to_dict(), "payments": payment_list}, None


def get_pledge_list(
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    viewer_id: int | None = None,
    can_view_all: bool = False,
    collector_id: int | None = None,
    event_id: int | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_amount: str | None = None,
    max_amount: str | None = None,
) -> dict:
    # Always JOIN Donor (for search) and User/collector (for display) to eliminate N+1.
    query = (
        Pledge.query
        .join(Donor, Pledge.donor_id == Donor.id)
        .join(User, Pledge.collector_id == User.id)
        .options(
            contains_eager(Pledge.donor),
            contains_eager(Pledge.collector),
        )
    )

    if status in ("open", "complete", "cancelled"):
        query = query.filter(Pledge.status == PledgeStatusEnum(status))

    if can_view_all:
        # Admin/executive: optional filter by any collector
        if collector_id:
            query = query.filter(Pledge.collector_id == collector_id)
    else:
        # Committee/general: scope strictly to own pledges
        query = query.filter(Pledge.collector_id == viewer_id)

    if event_id:
        query = query.filter(Pledge.event_id == event_id)

    if search:
        like = f"%{search}%"
        query = query.filter(
            Donor.name.ilike(like) | Donor.phone.ilike(like)
        )

    if date_from:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d").date()
            query = query.filter(Pledge.created_at >= df)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").date()
            query = query.filter(Pledge.created_at < dt + timedelta(days=1))
        except ValueError:
            pass

    if min_amount:
        try:
            query = query.filter(Pledge.total_amount >= Decimal(str(min_amount)))
        except Exception:
            pass

    if max_amount:
        try:
            query = query.filter(Pledge.total_amount <= Decimal(str(max_amount)))
        except Exception:
            pass

    query = query.order_by(Pledge.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        "pledges": [p.to_dict() for p in pagination.items],
        "page": pagination.page,
        "perPage": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }


def cancel_pledge(pledge_id: int) -> tuple[Pledge | None, str | None]:
    pledge = Pledge.query.get(pledge_id)
    if not pledge:
        return None, "pledge not found"
    if pledge.status == PledgeStatusEnum.complete:
        return None, "cannot cancel a completed pledge"
    pledge.status = PledgeStatusEnum.cancelled
    db.session.commit()
    return pledge, None
