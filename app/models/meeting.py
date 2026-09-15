import enum
from ..extensions import db


class MeetingTypeEnum(str, enum.Enum):
    general   = "general"
    emergency = "emergency"
    committee = "committee"
    agm       = "agm"
    other     = "other"


class MeetingStatusEnum(str, enum.Enum):
    draft       = "draft"
    scheduled   = "scheduled"
    in_progress = "in_progress"
    completed   = "completed"
    cancelled   = "cancelled"


class Meeting(db.Model):
    __tablename__ = "meetings"

    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.String(200), nullable=False)
    description  = db.Column(db.Text, nullable=True)
    date         = db.Column(db.Date, nullable=False)
    start_time   = db.Column(db.String(8), nullable=False)   # "HH:MM"
    end_time     = db.Column(db.String(8), nullable=False)   # "HH:MM"
    venue        = db.Column(db.String(300), nullable=True)
    meeting_type = db.Column(
        db.Enum(MeetingTypeEnum, native_enum=False, create_constraint=False),
        nullable=False,
        default=MeetingTypeEnum.general,
    )
    status = db.Column(
        db.Enum(MeetingStatusEnum, native_enum=False, create_constraint=False),
        nullable=False,
        default=MeetingStatusEnum.draft,
    )
    event_id   = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    event   = db.relationship("Event", foreign_keys=[event_id])
    creator = db.relationship("User", foreign_keys=[created_by])
    invitees = db.relationship(
        "MeetingInvitee",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    agenda_items = db.relationship(
        "MeetingAgendaItem",
        back_populates="meeting",
        cascade="all, delete-orphan",
        order_by="MeetingAgendaItem.sort_order",
    )
    discussions = db.relationship(
        "MeetingDiscussion",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    attendances = db.relationship(
        "MeetingAttendance",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_invitees: bool = False) -> dict:
        d = {
            "id":          self.id,
            "title":       self.title,
            "description": self.description,
            "date":        self.date.isoformat() if self.date else None,
            "startTime":   self.start_time,
            "endTime":     self.end_time,
            "venue":       self.venue,
            "meetingType": self.meeting_type.value if self.meeting_type else None,
            "status":      self.status.value if self.status else None,
            "event":       {"id": self.event.id, "name": self.event.name} if self.event else None,
            "createdBy":   {"id": self.creator.id, "name": self.creator.name} if self.creator else None,
            "createdAt":   self.created_at.isoformat() if self.created_at else None,
            "updatedAt":   self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_invitees:
            d["invitees"] = [i.to_dict() for i in self.invitees]
        return d


class MeetingInvitee(db.Model):
    __tablename__ = "meeting_invitees"

    id              = db.Column(db.Integer, primary_key=True)
    meeting_id      = db.Column(db.Integer, db.ForeignKey("meetings.id"), nullable=False, index=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    invitation_type = db.Column(db.String(30), nullable=False, default="individual")

    __table_args__ = (
        db.UniqueConstraint("meeting_id", "user_id", name="uq_meeting_invitee"),
    )

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    meeting = db.relationship("Meeting", back_populates="invitees")
    user    = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "meetingId":      self.meeting_id,
            "user": {
                "id":   self.user.id,
                "name": self.user.name,
                "role": self.user.role.value if self.user and self.user.role else None,
            } if self.user else None,
            "invitationType": self.invitation_type,
            "createdAt":      self.created_at.isoformat() if self.created_at else None,
        }
