import enum
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db


class RoleEnum(str, enum.Enum):
    admin               = "admin"
    managing_committee  = "managing_committee"
    core_committee      = "core_committee"
    executive           = "executive"
    cashier             = "cashier"
    collector           = "collector"
    # Kept for backward compatibility with existing DB records — do not use for new users
    committee           = "committee"
    general             = "general"


# ── Database migration notes (run manually — NOT an Alembic migration file) ──
#
# 1. Add new role values to the PostgreSQL native enum type:
#    ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'managing_committee';
#    ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'core_committee';
#    ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'cashier';
#    ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'collector';
#    (Must be run outside a transaction block — cannot be inside BEGIN/COMMIT)
#
# 2. Make email optional (nullable):
#    ALTER TABLE users ALTER COLUMN email DROP NOT NULL;
#
# 3. Add address field:
#    ALTER TABLE users ADD COLUMN IF NOT EXISTS address VARCHAR(300);
#
# 4. Add collection capability flag:
#    ALTER TABLE users ADD COLUMN IF NOT EXISTS can_collect BOOLEAN DEFAULT FALSE;
#    (nullable; NULL is treated as False for backward compatibility)
#
# Until these are applied: only existing role values work; email remains required;
# address and can_collect are silently ignored on write. Existing records are never touched.


class User(db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    phone         = db.Column(db.String(30), nullable=True)
    # upi_id: legacy column — intentionally unused in application logic; do not remove from DB
    upi_id        = db.Column(db.String(100))
    whatsapp_no   = db.Column(db.String(30), nullable=True)
    address       = db.Column(db.String(300), nullable=True)
    role          = db.Column(
        db.Enum(RoleEnum, native_enum=False, create_constraint=False),
        nullable=False,
        default=RoleEnum.collector,
    )
    is_active     = db.Column(db.Boolean, default=True, nullable=False)
    # Collection capability: False for admin (always), True for collector role (always),
    # and explicitly set for other roles. NULL treated as False for old records.
    can_collect   = db.Column(db.Boolean, default=False, nullable=True)
    created_at    = db.Column(db.DateTime, server_default=db.func.now())
    created_by    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def _effective_can_collect(self) -> bool:
        """Computed collection capability — not stored directly for admin/collector roles."""
        role = self.role if isinstance(self.role, RoleEnum) else RoleEnum(self.role)
        if role == RoleEnum.admin:
            return False
        if role == RoleEnum.collector:
            return True
        return bool(self.can_collect)

    def to_dict(self) -> dict:
        from .role_permission import RolePermission
        role_val = self.role.value if isinstance(self.role, RoleEnum) else self.role
        granted_rows = RolePermission.query.filter_by(role=self.role, granted=True).all()
        permissions = [r.permission_key for r in granted_rows]
        return {
            "id":          self.id,
            "name":        self.name,
            "email":       self.email,
            "phone":       self.phone,
            "whatsappNo":  self.whatsapp_no,
            "address":     self.address,
            "role":        role_val,
            "isActive":    self.is_active,
            "canCollect":  self._effective_can_collect(),
            "permissions": permissions,
            "createdAt":   self.created_at.isoformat() if self.created_at else None,
        }
