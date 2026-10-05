import enum

from ..extensions import db


class HandoverStatusEnum(str, enum.Enum):
    pending  = "pending"
    accepted = "accepted"
    rejected = "rejected"


class Handover(db.Model):
    """A collector handing over collected cash to the treasurer for an event."""
    __tablename__ = "handovers"

    id            = db.Column(db.Integer, primary_key=True)
    org_id        = db.Column(db.Integer, db.ForeignKey("organisations.id"), nullable=True, index=True)
    event_id      = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    collector_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount        = db.Column(db.Numeric(10, 2), nullable=False)
    handover_date = db.Column(db.Date, nullable=False)
    note          = db.Column(db.Text)
    status           = db.Column(db.Enum(HandoverStatusEnum, native_enum=False), nullable=False,
                                 default=HandoverStatusEnum.pending, index=True)
    reviewed_by      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at      = db.Column(db.DateTime)
    reject_reason    = db.Column(db.Text)
    # The specific user this handover is directed to (cashier / treasurer)
    handover_to_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at       = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    event       = db.relationship("Event", foreign_keys=[event_id])
    collector   = db.relationship("User", foreign_keys=[collector_id])
    reviewer    = db.relationship("User", foreign_keys=[reviewed_by])
    handover_to = db.relationship("User", foreign_keys=[handover_to_id])

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "event":        {"id": self.event.id, "name": self.event.name} if self.event else None,
            "collector":    {"id": self.collector.id, "name": self.collector.name} if self.collector else None,
            "handoverTo":   {"id": self.handover_to.id, "name": self.handover_to.name} if self.handover_to else None,
            "amount":       str(self.amount),
            "handoverDate": self.handover_date.isoformat() if self.handover_date else None,
            "note":         self.note,
            "status":       self.status.value if isinstance(self.status, HandoverStatusEnum) else self.status,
            "reviewedBy":   {"id": self.reviewer.id, "name": self.reviewer.name} if self.reviewer else None,
            "reviewedAt":   self.reviewed_at.isoformat() if self.reviewed_at else None,
            "rejectReason": self.reject_reason,
            "createdAt":    self.created_at.isoformat() if self.created_at else None,
        }
