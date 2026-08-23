import uuid
from datetime import datetime

from ..extensions import db


class AttendanceSession(db.Model):
    __tablename__ = "atd_sessions"

    id             = db.Column(db.Integer, primary_key=True)
    date           = db.Column(db.Date, nullable=False, index=True)
    session_number = db.Column(db.Integer, nullable=False, default=1)
    qr_token       = db.Column(db.String(64), nullable=False, unique=True)
    is_active      = db.Column(db.Boolean, nullable=False, default=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    records = db.relationship("AttendanceRecord", back_populates="session", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("date", "session_number", name="uq_atd_session_date_num"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "sessionNumber": self.session_number,
            "qrToken": self.qr_token,
            "isActive": self.is_active,
            "recordCount": self.records.count(),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class AttendanceRecord(db.Model):
    __tablename__ = "atd_records"

    id                 = db.Column(db.Integer, primary_key=True)
    session_id         = db.Column(db.Integer, db.ForeignKey("atd_sessions.id"), nullable=False)
    name               = db.Column(db.String(120), nullable=False)
    phone              = db.Column(db.String(20), nullable=False)
    address            = db.Column(db.Text, nullable=True)
    device_fingerprint = db.Column(db.String(64), nullable=True)
    ip_address         = db.Column(db.String(45), nullable=True)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship("AttendanceSession", back_populates="records")

    __table_args__ = (
        db.UniqueConstraint("session_id", "phone", name="uq_atd_record_session_phone"),
        db.UniqueConstraint("session_id", "device_fingerprint", name="uq_atd_record_session_device"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "name": self.name,
            "phone": self.phone,
            "address": self.address,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
