from ..extensions import db


class MeetingDiscussion(db.Model):
    __tablename__ = "meeting_discussions"

    id                    = db.Column(db.Integer, primary_key=True)
    meeting_id            = db.Column(db.Integer, db.ForeignKey("meetings.id"), nullable=False, index=True)
    agenda_item_id        = db.Column(db.Integer, db.ForeignKey("meeting_agenda_items.id"), nullable=True, index=True)
    content               = db.Column(db.Text, nullable=False)
    is_visible_to_members = db.Column(db.Boolean, nullable=False, default=True)
    created_by            = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at            = db.Column(db.DateTime, server_default=db.func.now())
    updated_at            = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    meeting     = db.relationship("Meeting", back_populates="discussions")
    agenda_item = db.relationship("MeetingAgendaItem", foreign_keys=[agenda_item_id])
    creator     = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self) -> dict:
        return {
            "id":                 self.id,
            "meetingId":          self.meeting_id,
            "agendaItemId":       self.agenda_item_id,
            "content":            self.content,
            "isVisibleToMembers": self.is_visible_to_members,
            "createdBy": {
                "id": self.creator.id, "name": self.creator.name,
            } if self.creator else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
