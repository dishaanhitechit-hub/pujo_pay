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
    "token.generate",
    "token.bulk",
    "token.view",
]

# Default grants per role
_DEFAULTS: dict[str, list[str]] = {
    "admin":     PERMISSION_KEYS,  # all
    "executive": ["payment.initiate", "payment.confirm", "payment.view_receipt",
                  "collector.view_own", "dashboard.view",
                  "token.generate", "token.view"],
    "committee": ["payment.initiate", "payment.confirm", "payment.view_receipt",
                  "collector.view_own", "token.generate"],
    "general":   ["payment.initiate", "payment.confirm", "payment.view_receipt",
                  "token.generate"],
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
        """Insert missing permission rows (additive — safe to re-run on new keys)."""
        changed = False
        for role_str, keys in _DEFAULTS.items():
            for perm_key in PERMISSION_KEYS:
                exists = RolePermission.query.filter_by(
                    role=RoleEnum(role_str), permission_key=perm_key
                ).first()
                if exists is None:
                    db.session.add(RolePermission(
                        role=RoleEnum(role_str),
                        permission_key=perm_key,
                        granted=(perm_key in keys),
                    ))
                    changed = True
        if changed:
            db.session.commit()
