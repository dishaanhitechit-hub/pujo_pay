from ..extensions import db

# DB: Run manually — no migration file:
#   CREATE TABLE IF NOT EXISTS budget_categories (
#       id             SERIAL PRIMARY KEY,
#       event_id       INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
#       title          VARCHAR(200) NOT NULL,
#       planned_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
#       notes          TEXT,
#       sort_order     INTEGER NOT NULL DEFAULT 0,
#       created_by     INTEGER NOT NULL REFERENCES users(id),
#       created_at     TIMESTAMP DEFAULT NOW(),
#       updated_at     TIMESTAMP DEFAULT NOW()
#   );


class BudgetCategory(db.Model):
    __tablename__ = "budget_categories"

    id             = db.Column(db.Integer, primary_key=True)
    event_id       = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    title          = db.Column(db.String(200), nullable=False)
    planned_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    notes          = db.Column(db.Text, nullable=True)
    sort_order     = db.Column(db.Integer, nullable=False, default=0)
    created_by     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at     = db.Column(db.DateTime, server_default=db.func.now())
    updated_at     = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    event   = db.relationship("Event",  foreign_keys=[event_id])
    creator = db.relationship("User",   foreign_keys=[created_by])

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "eventId":       self.event_id,
            "title":         self.title,
            "plannedAmount": str(self.planned_amount),
            "notes":         self.notes,
            "sortOrder":     self.sort_order,
            "createdBy":     {"id": self.creator.id, "name": self.creator.name} if self.creator else None,
            "createdAt":     self.created_at.isoformat() if self.created_at else None,
            "updatedAt":     self.updated_at.isoformat() if self.updated_at else None,
        }
