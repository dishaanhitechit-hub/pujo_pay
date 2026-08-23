from ..extensions import db


def _normalize_activities(raw):
    """
    Normalize the stored rituals JSON into {time, name, description} dicts.
    Handles legacy string-list, old {time,name} objects, and new {time,name,description}.
    """
    items = raw or []
    result = []
    for item in items:
        if isinstance(item, str):
            result.append({"time": "", "name": item, "description": None})
        elif isinstance(item, dict) and "name" in item:
            result.append({
                "time":        item.get("time", ""),
                "name":        item["name"],
                "description": item.get("description") or None,
            })
    return result


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
    rituals = db.Column(db.JSON)                       # [{time, name}] or legacy [str]
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    event = db.relationship("Event", back_populates="days")

    def to_dict(self) -> dict:
        activities = _normalize_activities(self.rituals)
        return {
            "id":          self.id,
            "key":         self.key,
            "label":       self.label,
            "date":        self.date.isoformat() if self.date else None,
            "description": self.description,
            "rituals":     [a["name"] for a in activities],   # backward compat
            "activities":  activities,
            "sortOrder":   self.sort_order,
        }
