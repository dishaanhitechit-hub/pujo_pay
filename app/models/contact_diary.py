from ..extensions import db


class ContactDiaryEntry(db.Model):
    __tablename__ = "contact_diary"

    id         = db.Column(db.Integer, primary_key=True)
    org_id     = db.Column(db.Integer, db.ForeignKey("organisations.id"), nullable=False)
    name       = db.Column(db.String(150), nullable=False)
    phone      = db.Column(db.String(30), nullable=False)
    address    = db.Column(db.String(300), nullable=True)
    occupation = db.Column(db.String(150), nullable=True)
    notes      = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "name":       self.name,
            "phone":      self.phone,
            "address":    self.address,
            "occupation": self.occupation,
            "notes":      self.notes,
            "createdBy":  {"id": self.creator.id, "name": self.creator.name} if self.creator else None,
            "createdAt":  self.created_at.isoformat() if self.created_at else None,
            "updatedAt":  self.updated_at.isoformat() if self.updated_at else None,
        }
