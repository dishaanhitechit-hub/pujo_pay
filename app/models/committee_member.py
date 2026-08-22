from ..extensions import db


class CommitteeMember(db.Model):
    __tablename__ = "committee_members"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    role_title = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    photo_path = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    event = db.relationship("Event", foreign_keys=[event_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event": {"id": self.event.id, "name": self.event.name} if self.event else None,
            "name": self.name,
            "roleTitle": self.role_title,
            "phone": self.phone,
            "photoPath": self.photo_path,
            "sortOrder": self.sort_order,
            "isActive": self.is_active,
        }
