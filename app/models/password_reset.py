from ..extensions import db
from ..utils.helpers import utcnow


class PasswordResetCode(db.Model):
    """One-time code emailed for "forgot password". Times are naive UTC."""
    __tablename__ = "password_reset_codes"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash  = db.Column(db.String(256), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts   = db.Column(db.Integer, nullable=False, default=0)
    # Set when the code is used, superseded by a newer code, or locked after too many wrong tries.
    used_at    = db.Column(db.DateTime, nullable=True)
    request_ip = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class RateLimitEvent(db.Model):
    """One row per rate-limited request, keyed by bucket (e.g. "forgot:ip:1.2.3.4").

    Kept in the database so limits survive restarts and are shared by all workers.
    """
    __tablename__ = "rate_limit_events"
    __table_args__ = (db.Index("ix_rate_limit_events_bucket_created", "bucket", "created_at"),)

    id         = db.Column(db.Integer, primary_key=True)
    bucket     = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
