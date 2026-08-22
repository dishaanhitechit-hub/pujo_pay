from ..extensions import db


class EventDay(db.Model):
    __tablename__ = "event_days"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id"), nullable=False, index=True
    )
    key = db.Column(db.String(50), nullable=False)     # e.g. "saptami"
    label = db.Column(db.String(100), nullable=False)  # e.g. "Maha Saptami"
    date = db.Column(db.Date)
    description = db.Column(db.Text)
    rituals = db.Column(db.JSON)                       # list of ritual strings
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    event = db.relationship("Event", back_populates="days")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "label": self.label,
            "date": self.date.isoformat() if self.date else None,
            "description": self.description,
            "rituals": self.rituals or [],
            "sortOrder": self.sort_order,
        }
