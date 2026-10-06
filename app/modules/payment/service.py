from decimal import Decimal
from marshmallow import Schema, fields, validate, validates, ValidationError

from ...extensions import db
from ...models.event import EventStatusEnum
from ...models.payment import Payment, MethodEnum, StatusEnum
from ...models.user import User
from ...models.contribution_slip import ContributionSlip, SlipStatusEnum


class InitiatePaymentSchema(Schema):
    """Start an online (QR / cash / cheque) payment against an existing slip."""
    slip_id = fields.Int(required=True, data_key="slipId")
    amount  = fields.Decimal(required=True, places=2, as_string=False)
    method  = fields.Str(required=True, validate=validate.OneOf(["cash", "upi", "cheque"]))

    @validates("amount")
    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise ValidationError("amount must be greater than zero")


initiate_schema = InitiatePaymentSchema()


def initiate_payment(data: dict, collector_id: int, org_id: int,
                     allowed_event_ids: set[int] | None = None) -> tuple[Payment | None, str | None]:
    """Create a pending payment under a slip; the QR/confirm pages complete it."""
    slip = ContributionSlip.query.filter_by(id=data["slip_id"], org_id=org_id).first()
    if not slip:
        return None, "slip not found"
    if slip.collector_id != collector_id:
        return None, "forbidden"
    if allowed_event_ids is not None and slip.event_id not in allowed_event_ids:
        return None, "forbidden"
    if slip.status == SlipStatusEnum.cancelled:
        return None, "slip is cancelled"

    event = slip.event
    if not event or event.status != EventStatusEnum.published or not event.collection_enabled:
        return None, "event is not currently accepting collections"

    amount = Decimal(str(data["amount"]))
    if amount > slip.outstanding():
        return None, f"amount exceeds outstanding balance of ₹{slip.outstanding()}"

    payment = Payment(
        slip_id=slip.id,
        donor_id=slip.donor_id,
        collector_id=collector_id,
        amount=amount,
        method=MethodEnum(data["method"]),
        status=StatusEnum.pending,
        event_id=slip.event_id,
    )
    db.session.add(payment)
    db.session.commit()
    return payment, None


def get_payment(payment_id: int, org_id: int | None = None) -> Payment | None:
    p = Payment.query.get(payment_id)
    if p is None:
        return None
    if org_id is not None:
        user = User.query.get(p.collector_id)
        if not user or user.org_id != org_id:
            return None
    return p


def get_payment_by_receipt_no(receipt_no: str, org_id: int | None = None) -> Payment | None:
    q = Payment.query.filter_by(receipt_no=receipt_no.upper())
    if org_id is not None:
        q = q.join(User, Payment.collector_id == User.id).filter(User.org_id == org_id)
    return q.first()
