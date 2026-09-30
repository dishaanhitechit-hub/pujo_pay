import re

from ..extensions import db


def _slugify_org(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


# ── DB migration note ──────────────────────────────────────────────────────
# ALTER TABLE organisations ADD COLUMN IF NOT EXISTS org_code VARCHAR(20);
# ALTER TABLE organisations ADD CONSTRAINT IF NOT EXISTS uq_orgs_org_code UNIQUE (org_code);
# -- backfill existing rows before setting NOT NULL, e.g.:
# -- UPDATE organisations SET org_code = UPPER(SUBSTRING(REGEXP_REPLACE(name,'[^a-zA-Z0-9]','','g'),1,4)) || LPAD(FLOOR(RANDOM()*10000)::text,4,'0') WHERE org_code IS NULL;
# ALTER TABLE organisations ALTER COLUMN org_code SET NOT NULL;
# ──────────────────────────────────────────────────────────────────────────



class Organisation(db.Model):
    __tablename__ = "organisations"

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(200), nullable=False)
    slug       = db.Column(db.String(200), unique=True, nullable=False, index=True)
    # org_code: short human-readable ID (e.g. PUJA3847). Immutable after creation.
    org_code   = db.Column(db.String(20), unique=True, nullable=True)
    is_active  = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "name":      self.name,
            "slug":      self.slug,
            "orgCode":   self.org_code,
            "isActive":  self.is_active,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
