from ..extensions import db


class Donor(db.Model):
    __tablename__ = "donors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    notes = db.Column(db.Text)
    donor_type = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    payments = db.relationship("Payment", back_populates="donor", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "address": self.address,
            "notes": self.notes,
            "donorType": self.donor_type,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
