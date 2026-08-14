import enum
import uuid
from ..extensions import db


class MethodEnum(str, enum.Enum):
    cash = "cash"
    upi = "upi"


class StatusEnum(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    expired = "expired"
    cancelled = "cancelled"


def _generate_receipt_no() -> str:
    return "RCP-" + uuid.uuid4().hex[:8].upper()


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey("donors.id"), nullable=False)
    collector_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.Enum(MethodEnum), nullable=False)
    utr_number = db.Column(db.String(100))
    status = db.Column(db.Enum(StatusEnum), nullable=False, default=StatusEnum.pending)
    receipt_no = db.Column(db.String(20), unique=True)
    whatsapp_sent = db.Column(db.Boolean, default=False, nullable=False)
    # set when the QR page is first opened; used to enforce 10-min window
    payment_page_opened_at = db.Column(db.DateTime)
    confirmed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    receipt_pdf_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    donor = db.relationship("Donor", back_populates="payments")
    collector = db.relationship("User", foreign_keys=[collector_id])

    def assign_receipt_no(self) -> None:
        if not self.receipt_no:
            self.receipt_no = _generate_receipt_no()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "receiptNo": self.receipt_no,
            "donor": self.donor.to_dict() if self.donor else None,
            "collector": {
                "id": self.collector.id,
                "name": self.collector.name,
            } if self.collector else None,
            "amount": str(self.amount),
            "method": self.method.value,
            "utrNumber": self.utr_number,
            "status": self.status.value,
            "whatsappSent": self.whatsapp_sent,
            "confirmedAt": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "cancelledAt": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "receiptPdfPath": self.receipt_pdf_path,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
