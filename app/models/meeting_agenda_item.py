import enum
from ..extensions import db


class AgendaItemStatusEnum(str, enum.Enum):
    open   = "open"
    closed = "closed"
    tabled = "tabled"


class MeetingAgendaItem(db.Model):
    __tablename__ = "meeting_agenda_items"

    id          = db.Column(db.Integer, primary_key=True)
    meeting_id  = db.Column(db.Integer, db.ForeignKey("meetings.id"), nullable=False, index=True)
    title       = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    sort_order  = db.Column(db.Integer, nullable=False, default=0)
    owner_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    status      = db.Column(
        db.Enum(AgendaItemStatusEnum, native_enum=False, create_constraint=False),
        nullable=False,
        default=AgendaItemStatusEnum.open,
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    meeting = db.relationship("Meeting", back_populates="agenda_items")
    owner   = db.relationship("User", foreign_keys=[owner_id])

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "meetingId":   self.meeting_id,
            "title":       self.title,
            "description": self.description,
            "sortOrder":   self.sort_order,
            "owner": {
                "id": self.owner.id, "name": self.owner.name,
            } if self.owner else None,
            "status":    self.status.value if self.status else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
