from decimal import Decimal
from marshmallow import Schema, fields, validate, validates, ValidationError

from ...extensions import db
from ...models.donor import Donor
from ...models.payment import Payment, MethodEnum, StatusEnum


class InitiatePaymentSchema(Schema):
    donor_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    donor_phone = fields.Str(load_default=None, validate=validate.Length(max=20))
    donor_address = fields.Str(load_default=None)
    donor_notes = fields.Str(load_default=None)
    amount = fields.Decimal(required=True, places=2, as_string=False)
    method = fields.Str(
        required=True,
        validate=validate.OneOf(["cash", "upi"]),
    )

    @validates("amount")
    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise ValidationError("amount must be greater than zero")


initiate_schema = InitiatePaymentSchema()


def initiate_payment(data: dict, collector_id: int) -> Payment:
    donor = Donor(
        name=data["donor_name"].strip(),
        phone=data.get("donor_phone"),
        address=data.get("donor_address"),
        notes=data.get("donor_notes"),
    )
    db.session.add(donor)
    db.session.flush()  # get donor.id before committing

    payment = Payment(
        donor_id=donor.id,
        collector_id=collector_id,
        amount=data["amount"],
        method=MethodEnum(data["method"]),
        status=StatusEnum.pending,
    )
    db.session.add(payment)
    db.session.commit()
    return payment


def get_payment(payment_id: int) -> Payment | None:
    return Payment.query.get(payment_id)


def get_payment_by_receipt_no(receipt_no: str) -> Payment | None:
    return Payment.query.filter_by(receipt_no=receipt_no.upper()).first()
