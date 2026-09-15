"""
Meeting attendance models.

MeetingAttendance  — one row per (meeting_id, user_id).
MeetingAttendanceDevice — used for casual device-abuse prevention.
  The device_token is self-reported by the client and stored in localStorage.
  It prevents casual multi-account abuse (two accounts, same device, same meeting),
  but is NOT cryptographically verified and will not stop a determined attacker.
"""
from ..extensions import db


class MeetingAttendance(db.Model):
    __tablename__ = "meeting_attendance"

    id         = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id"), nullable=False, index=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    marked_at  = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("meeting_id", "user_id", name="uq_meeting_attendance"),
    )

    meeting = db.relationship("Meeting", back_populates="attendances")
    user    = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "meetingId": self.meeting_id,
            "user": {
                "id": self.user.id, "name": self.user.name,
            } if self.user else None,
            "markedAt": self.marked_at.isoformat() if self.marked_at else None,
        }


class MeetingAttendanceDevice(db.Model):
    __tablename__ = "meeting_attendance_devices"

    id           = db.Column(db.Integer, primary_key=True)
    meeting_id   = db.Column(db.Integer, db.ForeignKey("meetings.id"), nullable=False, index=True)
    device_token = db.Column(db.String(100), nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at   = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("meeting_id", "device_token", name="uq_meeting_device"),
    )
