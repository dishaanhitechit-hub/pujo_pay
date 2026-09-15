import enum
from ..extensions import db


class PaymentMethodEnum(str, enum.Enum):
    cash          = "cash"
    upi           = "upi"
    bank_transfer = "bank_transfer"


class ContributionStatusEnum(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


class SelfContribution(db.Model):
    __tablename__ = "self_contributions"

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    event_id        = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=True, index=True)

    amount          = db.Column(db.Numeric(12, 2), nullable=False)
    payment_method  = db.Column(db.Enum(PaymentMethodEnum, native_enum=False), nullable=False)
    payment_date    = db.Column(db.Date, nullable=False)
    payment_time    = db.Column(db.String(10), nullable=True)   # "HH:MM", optional
    screenshot_path = db.Column(db.String(512), nullable=True)  # relative to MEDIA_STORAGE_PATH
    note            = db.Column(db.Text, nullable=True)

    status          = db.Column(
        db.Enum(ContributionStatusEnum, native_enum=False),
        nullable=False,
        default=ContributionStatusEnum.pending,
        index=True,
    )
    admin_note      = db.Column(db.Text, nullable=True)
    reviewed_by     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at     = db.Column(db.DateTime, nullable=True)

    created_at      = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at      = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    # Relationships — loaded eagerly in service queries via joinedload, not here
    user     = db.relationship("User", foreign_keys=[user_id])
    event    = db.relationship("Event", foreign_keys=[event_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])

    def to_dict(self, include_screenshot_url: bool = False) -> dict:
        d = {
            "id":            self.id,
            "amount":        float(self.amount),
            "paymentMethod": self.payment_method.value if self.payment_method else None,
            "paymentDate":   self.payment_date.isoformat() if self.payment_date else None,
            "paymentTime":   self.payment_time,
            "note":          self.note,
            "status":        self.status.value if self.status else None,
            "adminNote":     self.admin_note,
            "hasScreenshot": bool(self.screenshot_path),
            "event": {
                "id":   self.event.id,
                "name": self.event.name,
                "slug": self.event.slug,
            } if self.event else None,
            "user": {
                "id":   self.user.id,
                "name": self.user.name,
                "role": self.user.role.value if self.user.role else None,
            } if self.user else None,
            "reviewer": {
                "id":   self.reviewer.id,
                "name": self.reviewer.name,
            } if self.reviewer else None,
            "reviewedAt": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "createdAt":  self.created_at.isoformat() if self.created_at else None,
        }
        if include_screenshot_url and self.screenshot_path:
            d["screenshotUrl"] = f"/api/contributions/screenshot/{self.id}"
        return d
