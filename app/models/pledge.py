import enum
from decimal import Decimal
from ..extensions import db


class PledgeStatusEnum(str, enum.Enum):
    open = "open"
    complete = "complete"
    cancelled = "cancelled"


class Pledge(db.Model):
    __tablename__ = "pledges"

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey("donors.id"), nullable=False)
    collector_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(
        db.Enum(PledgeStatusEnum, native_enum=False), nullable=False, default=PledgeStatusEnum.open
    )
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    donor = db.relationship("Donor", foreign_keys=[donor_id])
    collector = db.relationship("User", foreign_keys=[collector_id])
    payments = db.relationship("Payment", back_populates="pledge", lazy="dynamic")

    def outstanding(self) -> Decimal:
        return Decimal(str(self.total_amount)) - Decimal(str(self.paid_amount))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "donor": self.donor.to_dict() if self.donor else None,
            "collector": {
                "id": self.collector.id,
                "name": self.collector.name,
            } if self.collector else None,
            "totalAmount": str(self.total_amount),
            "paidAmount": str(self.paid_amount),
            "outstandingAmount": str(self.outstanding()),
            "status": self.status.value,
            "notes": self.notes,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
