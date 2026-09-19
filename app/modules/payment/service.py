from decimal import Decimal
from marshmallow import Schema, fields, validate, validates, ValidationError

from ...extensions import db
from ...models.donor import Donor
from ...models.event import Event, EventStatusEnum
from ...models.payment import Payment, MethodEnum, StatusEnum
from ...models.pledge import Pledge, PledgeStatusEnum
from ...models.user import User


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


def initiate_payment(data: dict, collector_id: int, org_id: int) -> tuple[Payment, str | None]:
    """
    Returns (payment, error_message).
    error_message is None on success.
    """
    # Validate event — must exist, belong to this org, be published, and have collection enabled
    event = Event.query.get(data["event_id"])
    if not event or event.org_id != org_id:
        return None, "event not found"
    if event.status != EventStatusEnum.published or not event.collection_enabled:
        return None, "event is not currently accepting collections"

    pledge = None
    if data.get("pledge_id"):
        pledge = Pledge.query.filter_by(id=data["pledge_id"]).join(
            User, Pledge.collector_id == User.id
        ).filter(User.org_id == org_id).first()
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
        org_id=org_id,
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
