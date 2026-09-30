from werkzeug.security import generate_password_hash, check_password_hash

from ..extensions import db


class ProvisionStatus:
    PENDING_PAYMENT  = "pending_payment"
    PAYMENT_CONFIRMED = "payment_confirmed"
    ACTIVE           = "active"


# ── DB migration note ──────────────────────────────────────────────────────
# ALTER TABLE org_provisions ADD COLUMN IF NOT EXISTS org_code VARCHAR(20);
# ──────────────────────────────────────────────────────────────────────────


class OrgProvision(db.Model):
    __tablename__ = "org_provisions"

    id                   = db.Column(db.Integer, primary_key=True)
    org_name             = db.Column(db.String(200), nullable=False)
    contact_name         = db.Column(db.String(120), nullable=False)
    contact_email        = db.Column(db.String(120), nullable=False)
    contact_phone        = db.Column(db.String(30), nullable=True)
    # org_code: optionally pre-set by super admin; used at activation
    org_code             = db.Column(db.String(20), nullable=True)
    status               = db.Column(db.String(30), default=ProvisionStatus.PENDING_PAYMENT, nullable=False)

    # generated on payment confirmation
    otp_hash             = db.Column(db.String(256), nullable=True)
    otp_used             = db.Column(db.Boolean, default=False, nullable=False)

    # linked after activation
    org_id               = db.Column(db.Integer, db.ForeignKey("organisations.id"), nullable=True)
    admin_user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    org = db.relationship("Organisation", foreign_keys=[org_id], lazy="select")

    payment_confirmed_at = db.Column(db.DateTime, nullable=True)
    created_at           = db.Column(db.DateTime, server_default=db.func.now())
    created_by           = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    def set_otp(self, otp: str) -> None:
        self.otp_hash = generate_password_hash(otp)

    def check_otp(self, otp: str) -> bool:
        if not self.otp_hash or self.otp_used:
            return False
        return check_password_hash(self.otp_hash, otp)

    def to_dict(self) -> dict:
        return {
            "id":                  self.id,
            "orgName":             self.org_name,
            "contactName":         self.contact_name,
            "contactEmail":        self.contact_email,
            "contactPhone":        self.contact_phone,
            "orgCode":             self.org_code,
            "status":              self.status,
            "otpUsed":             self.otp_used,
            "orgId":               self.org_id,
            "adminUserId":         self.admin_user_id,
            "paymentConfirmedAt":  self.payment_confirmed_at.isoformat() if self.payment_confirmed_at else None,
            "createdAt":           self.created_at.isoformat() if self.created_at else None,
            # live org state (None when not yet activated)
            "orgIsActive":         self.org.is_active if self.org else None,
            "resolvedOrgCode":     self.org.org_code if self.org else self.org_code,
        }
