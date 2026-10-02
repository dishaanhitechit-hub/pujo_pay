import enum
from decimal import Decimal

from ..extensions import db


class SlipStatusEnum(str, enum.Enum):
    open      = "open"
    closed    = "closed"      # fully paid (auto) or closed manually
    cancelled = "cancelled"


class DonorKindEnum(str, enum.Enum):
    member = "member"   # an org member (linked to a user)
    other  = "other"    # external donor with a donor-type category


class ContributionSlip(db.Model):
    """A contribution commitment that is collected via one or many payments."""
    __tablename__ = "contribution_slips"
    __table_args__ = (
        db.UniqueConstraint("org_id", "slip_number", name="uq_slip_org_number"),
    )

    id           = db.Column(db.Integer, primary_key=True)
    org_id       = db.Column(db.Integer, db.ForeignKey("organisations.id"), nullable=True, index=True)
    event_id     = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    collector_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    slip_number  = db.Column(db.String(40), nullable=False, index=True)

    donor_kind     = db.Column(db.Enum(DonorKindEnum, native_enum=False), nullable=False, default=DonorKindEnum.other)
    donor_id       = db.Column(db.Integer, db.ForeignKey("donors.id"), nullable=True)
    member_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid_amount  = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status       = db.Column(db.Enum(SlipStatusEnum, native_enum=False), nullable=False, default=SlipStatusEnum.open, index=True)
    notes        = db.Column(db.Text)
    created_at   = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    closed_at    = db.Column(db.DateTime)

    event     = db.relationship("Event", foreign_keys=[event_id])
    collector = db.relationship("User", foreign_keys=[collector_id])
    donor     = db.relationship("Donor", foreign_keys=[donor_id])
    member    = db.relationship("User", foreign_keys=[member_user_id])
    payments  = db.relationship("Payment", back_populates="slip", lazy="dynamic")

    def outstanding(self) -> Decimal:
        return Decimal(str(self.total_amount)) - Decimal(str(self.paid_amount))

    def to_dict(self, with_payments: bool = False) -> dict:
        data = {
            "id":          self.id,
            "slipNumber":  self.slip_number,
            "event":       {"id": self.event.id, "name": self.event.name} if self.event else None,
            "collector":   {"id": self.collector.id, "name": self.collector.name} if self.collector else None,
            "donorKind":   self.donor_kind.value if isinstance(self.donor_kind, DonorKindEnum) else self.donor_kind,
            "donor":       self.donor.to_dict() if self.donor else None,
            "memberUserId": self.member_user_id,
            "memberName":  self.member.name if self.member else None,
            "totalAmount": str(self.total_amount),
            "paidAmount":  str(self.paid_amount),
            "outstanding": str(self.outstanding()),
            "status":      self.status.value if isinstance(self.status, SlipStatusEnum) else self.status,
            "notes":       self.notes,
            "createdAt":   self.created_at.isoformat() if self.created_at else None,
            "closedAt":    self.closed_at.isoformat() if self.closed_at else None,
        }
        if with_payments:
            data["payments"] = [p.to_dict() for p in self.payments.order_by(db.desc("created_at")).all()]
        return data
