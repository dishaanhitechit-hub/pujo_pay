from datetime import datetime

from ..extensions import db


class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=True)
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    published_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    event = db.relationship("Event", foreign_keys=[event_id])
    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "event": {"id": self.event.id, "name": self.event.name} if self.event else None,
            "isPublished": self.is_published,
            "publishedAt": self.published_at.isoformat() if self.published_at else None,
            "createdBy": {"id": self.creator.id, "name": self.creator.name} if self.creator else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
