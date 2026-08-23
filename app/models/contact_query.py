import enum

from ..extensions import db


class ContactQueryStatusEnum(str, enum.Enum):
    new      = "new"
    read     = "read"
    resolved = "resolved"


class ContactQuery(db.Model):
    __tablename__ = "contact_queries"

    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(150), nullable=False)
    phone    = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    message  = db.Column(db.Text, nullable=False)
    status   = db.Column(
        db.Enum(ContactQueryStatusEnum),
        nullable=False,
        default=ContactQueryStatusEnum.new,
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "name":      self.name,
            "phone":     self.phone,
            "location":  self.location,
            "message":   self.message,
            "status":    self.status.value,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
