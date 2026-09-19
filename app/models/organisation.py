import re

from ..extensions import db


def _slugify_org(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


class Organisation(db.Model):
    __tablename__ = "organisations"

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(200), nullable=False)
    slug       = db.Column(db.String(200), unique=True, nullable=False, index=True)
    is_active  = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "name":      self.name,
            "slug":      self.slug,
            "isActive":  self.is_active,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
