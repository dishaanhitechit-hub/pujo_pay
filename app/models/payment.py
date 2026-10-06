import enum
import uuid
from ..extensions import db
from ..utils.pay_token import make_receipt_token


class MethodEnum(str, enum.Enum):
    cash = "cash"
    upi = "upi"
    cheque = "cheque"


class StatusEnum(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    confirmed = "confirmed"   # legacy — kept so SQLAlchemy can read old DB rows
    expired = "expired"
    cancelled = "cancelled"


# Both values represent a successfully completed payment (new writes use `completed`).
COMPLETED_STATUSES = frozenset({StatusEnum.completed, StatusEnum.confirmed})


def _generate_receipt_no() -> str:
    return "RCP-" + uuid.uuid4().hex[:8].upper()



class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    # Every payment belongs to a contribution slip; donor/event are derived from the slip.
    slip_id      = db.Column(db.Integer, db.ForeignKey("contribution_slips.id", ondelete="CASCADE"), nullable=True, index=True)
    donor_id     = db.Column(db.Integer, db.ForeignKey("donors.id"), nullable=True, index=True)
    collector_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount       = db.Column(db.Numeric(10, 2), nullable=False)
    method       = db.Column(db.Enum(MethodEnum, native_enum=False), nullable=False)
    utr_number   = db.Column(db.String(100))
    status       = db.Column(db.Enum(StatusEnum, native_enum=False), nullable=False, default=StatusEnum.pending, index=True)
    receipt_no   = db.Column(db.String(20), unique=True)
    cheque_number = db.Column(db.String(50))
    bank_name    = db.Column(db.String(100))
    cheque_date  = db.Column(db.Date)
    # Manually-entered payments carry the date the money was actually received.
    received_date = db.Column(db.Date)
    event_id     = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=True, index=True)
    whatsapp_sent = db.Column(db.Boolean, default=False, nullable=False)
    # set when the QR page is first opened; used to enforce 10-min window
    payment_page_opened_at = db.Column(db.DateTime)
    confirmed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    receipt_pdf_path = db.Column(db.String(500))
    created_at   = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    donor = db.relationship("Donor", back_populates="payments")
    collector = db.relationship("User", foreign_keys=[collector_id])
    slip = db.relationship("ContributionSlip", back_populates="payments", foreign_keys=[slip_id])
    event = db.relationship("Event", foreign_keys=[event_id])

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
            "chequeNumber": self.cheque_number,
            "bankName": self.bank_name,
            "chequeDate": self.cheque_date.isoformat() if self.cheque_date else None,
            "receivedDate": self.received_date.isoformat() if self.received_date else None,
            "slipId": self.slip_id,
            "slipNumber": self.slip.slip_number if self.slip else None,
            "slipTotal":  str(self.slip.total_amount) if self.slip else None,
            "slipPaid":   str(self.slip.paid_amount) if self.slip else None,
            "slipStatus": (self.slip.status.value if hasattr(self.slip.status, "value") else self.slip.status) if self.slip else None,
            "event": {"id": self.event.id, "name": self.event.name} if self.event else None,
            "status": "completed" if self.status.value == "confirmed" else self.status.value,
            "whatsappSent": self.whatsapp_sent,
            "confirmedAt": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "cancelledAt": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "receiptPdfPath": self.receipt_pdf_path,
            "receiptToken": make_receipt_token(self.id),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
