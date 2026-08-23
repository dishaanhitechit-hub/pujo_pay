import enum
import re

from ..extensions import db


class EventStatusEnum(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


def _slugify(name: str) -> str:
    """Generate a URL-safe slug from a name string."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    location = db.Column(db.String(200))
    year = db.Column(db.Integer)
    status = db.Column(
        db.Enum(EventStatusEnum, native_enum=False),
        nullable=False,
        default=EventStatusEnum.draft,
    )
    collection_enabled = db.Column(db.Boolean, nullable=False, default=False)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    cover_image_path = db.Column(db.String(500))
    # Budget planning (informational only — does NOT restrict expenses)
    # DB: ALTER TABLE events ADD COLUMN IF NOT EXISTS budget NUMERIC(12, 2);
    #     ALTER TABLE events ADD COLUMN IF NOT EXISTS budget_notes TEXT;
    budget = db.Column(db.Numeric(12, 2), nullable=True)
    budget_notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    creator = db.relationship("User", foreign_keys=[created_by])
    days = db.relationship(
        "EventDay",
        back_populates="event",
        order_by="EventDay.sort_order",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_days: bool = False) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "endDate": self.end_date.isoformat() if self.end_date else None,
            "location": self.location,
            "year": self.year,
            "status": self.status.value,
            "collectionEnabled": self.collection_enabled,
            "isFeatured": self.is_featured,
            "coverImagePath": self.cover_image_path,
            "createdBy": {
                "id": self.creator.id,
                "name": self.creator.name,
            } if self.creator else None,
            "budget": str(self.budget) if self.budget is not None else None,
            "budgetNotes": self.budget_notes,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_days:
            d["days"] = [day.to_dict() for day in self.days]
        return d
