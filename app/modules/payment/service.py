from decimal import Decimal
from marshmallow import Schema, fields, validate, validates, ValidationError

from ...extensions import db
from ...models.donor import Donor
from ...models.event import Event, EventStatusEnum
from ...models.payment import Payment, MethodEnum, StatusEnum
from ...models.pledge import Pledge, PledgeStatusEnum


class InitiatePaymentSchema(Schema):
    donor_name    = fields.Str(required=True, data_key="donorName", validate=validate.Length(min=1, max=120))
    donor_phone   = fields.Str(load_default=None, data_key="donorPhone", validate=validate.Length(max=20))
    donor_address = fields.Str(load_default=None, data_key="donorAddress")
    donor_notes   = fields.Str(load_default=None, data_key="donorNotes")
    donor_type    = fields.Str(load_default=None, data_key="donorType")
    amount = fields.Decimal(required=True, places=2, as_string=False)
    method = fields.Str(
        required=True,
        validate=validate.OneOf(["cash", "upi", "cheque"]),
    )
    pledge_id = fields.Int(load_default=None, data_key="pledgeId")
    event_id  = fields.Int(required=True, data_key="eventId")

    @validates("amount")
    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise ValidationError("amount must be greater than zero")


initiate_schema = InitiatePaymentSchema()


def initiate_payment(data: dict, collector_id: int) -> tuple[Payment, str | None]:
    """
    Returns (payment, error_message).
    error_message is None on success.
    """
    # Validate event — must exist, be published, and have collection enabled
    event = Event.query.get(data["event_id"])
    if not event:
        return None, "event not found"
    if event.status != EventStatusEnum.published or not event.collection_enabled:
        return None, "event is not currently accepting collections"

    pledge = None
    if data.get("pledge_id"):
        pledge = Pledge.query.get(data["pledge_id"])
        if not pledge:
            return None, "pledge not found"
        if pledge.status != PledgeStatusEnum.open:
            return None, f"pledge is {pledge.status.value} — cannot add payments"
        outstanding = pledge.outstanding()
        if Decimal(str(data["amount"])) > outstanding:
            return None, f"amount exceeds outstanding balance of ₹{outstanding}"

    donor = Donor(
        name=data["donor_name"].strip(),
        phone=data.get("donor_phone"),
        address=data.get("donor_address"),
        notes=data.get("donor_notes"),
        donor_type=data.get("donor_type"),
    )
    db.session.add(donor)
    db.session.flush()

    payment = Payment(
        donor_id=donor.id,
        collector_id=collector_id,
        amount=data["amount"],
        method=MethodEnum(data["method"]),
        status=StatusEnum.pending,
        pledge_id=data.get("pledge_id"),
        event_id=data["event_id"],
    )
    db.session.add(payment)
    db.session.commit()
    return payment, None


def get_payment(payment_id: int) -> Payment | None:
    return Payment.query.get(payment_id)


def get_payment_by_receipt_no(receipt_no: str) -> Payment | None:
    return Payment.query.filter_by(receipt_no=receipt_no.upper()).first()
