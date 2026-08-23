from ..extensions import db
from .payment import MethodEnum

# DB migration (run manually — no migration file):
#   CREATE TABLE IF NOT EXISTS expenses (
#       id         SERIAL PRIMARY KEY,
#       event_id   INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
#       purpose    VARCHAR(200) NOT NULL,
#       mode       VARCHAR(20) NOT NULL,
#       amount     NUMERIC(12, 2) NOT NULL,
#       expense_date DATE NOT NULL,
#       notes      TEXT,
#       created_by INTEGER NOT NULL REFERENCES users(id),
#       created_at TIMESTAMP DEFAULT NOW(),
#       updated_at TIMESTAMP DEFAULT NOW()
#   );


class Expense(db.Model):
    __tablename__ = "expenses"

    id           = db.Column(db.Integer, primary_key=True)
    event_id     = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    purpose      = db.Column(db.String(200), nullable=False)
    mode         = db.Column(
        db.Enum(MethodEnum, native_enum=False, create_constraint=False),
        nullable=False,
    )
    amount       = db.Column(db.Numeric(12, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    notes        = db.Column(db.Text, nullable=True)
    created_by   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at   = db.Column(db.DateTime, server_default=db.func.now())
    updated_at   = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    event   = db.relationship("Event", foreign_keys=[event_id])
    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "eventId":     self.event_id,
            "purpose":     self.purpose,
            "mode":        self.mode.value if isinstance(self.mode, MethodEnum) else self.mode,
            "amount":      str(self.amount),
            "expenseDate": self.expense_date.isoformat() if self.expense_date else None,
            "notes":       self.notes,
            "createdBy":   {"id": self.creator.id, "name": self.creator.name} if self.creator else None,
            "createdAt":   self.created_at.isoformat() if self.created_at else None,
            "updatedAt":   self.updated_at.isoformat() if self.updated_at else None,
        }
