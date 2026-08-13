from ..extensions import db
from .user import RoleEnum

# All permission keys used across the app
PERMISSION_KEYS = [
    "payment.initiate",
    "payment.confirm",
    "payment.view_receipt",
    "collector.view_own",
    "dashboard.view",
    "users.manage",
    "permissions.manage",
]

# Default grants per role
_DEFAULTS: dict[str, list[str]] = {
    "admin":     PERMISSION_KEYS,  # all
    "executive": ["payment.initiate", "payment.confirm", "payment.view_receipt",
                  "collector.view_own", "dashboard.view"],
    "committee": ["payment.initiate", "payment.confirm", "payment.view_receipt",
                  "collector.view_own"],
    "general":   ["payment.initiate", "payment.confirm", "payment.view_receipt"],
}


class RolePermission(db.Model):
    __tablename__ = "role_permissions"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.Enum(RoleEnum), nullable=False)
    permission_key = db.Column(db.String(60), nullable=False)
    granted = db.Column(db.Boolean, default=True, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("role", "permission_key", name="uq_role_permission"),
    )

    @staticmethod
    def seed_defaults() -> None:
        """Insert default permissions if the table is empty."""
        if RolePermission.query.first():
            return
        rows = [
            RolePermission(role=RoleEnum(role), permission_key=key, granted=(key in keys))
            for role, keys in _DEFAULTS.items()
            for key in PERMISSION_KEYS
        ]
        db.session.add_all(rows)
        db.session.commit()
