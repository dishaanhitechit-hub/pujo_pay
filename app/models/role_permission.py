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
    "event.manage",
    "content.manage",
]

# Default grants per role.
# New roles (managing_committee, core_committee, cashier, collector) require DB ALTER TYPE
# before their rows can be inserted — see migration notes in models/user.py.
_DEFAULTS: dict[str, list[str]] = {
    "admin":               PERMISSION_KEYS,
    "managing_committee":  ["payment.initiate", "payment.confirm", "payment.view_receipt",
                            "collector.view_own", "dashboard.view",
                            "token.generate", "token.view"],
    "core_committee":      ["payment.initiate", "payment.confirm", "payment.view_receipt",
                            "collector.view_own", "token.generate"],
    "executive":           ["payment.initiate", "payment.confirm", "payment.view_receipt",
                            "collector.view_own", "dashboard.view",
                            "token.generate", "token.view"],
    "cashier":             ["payment.initiate", "payment.confirm", "payment.view_receipt",
                            "collector.view_own", "dashboard.view",
                            "token.generate", "token.view"],
    "collector":           ["payment.initiate", "payment.confirm", "payment.view_receipt",
                            "collector.view_own", "token.generate"],
    # Legacy role values — kept for backward compatibility
    "committee":           ["payment.initiate", "payment.confirm", "payment.view_receipt",
                            "collector.view_own", "token.generate"],
    "general":             ["payment.initiate", "payment.confirm", "payment.view_receipt",
                            "collector.view_own", "token.generate"],
}


class RolePermission(db.Model):
    __tablename__ = "role_permissions"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.Enum(RoleEnum, native_enum=False), nullable=False)
    permission_key = db.Column(db.String(60), nullable=False)
    granted = db.Column(db.Boolean, default=True, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("role", "permission_key", name="uq_role_permission"),
    )

    @staticmethod
    def seed_defaults() -> None:
        """Insert missing permission rows (additive — safe to re-run on new keys).

        New role values (managing_committee, core_committee, cashier, collector) require
        the DB PostgreSQL ENUM type to be updated first — see models/user.py migration
        notes. Until then those role rows are skipped gracefully.
        """
        for role_str, keys in _DEFAULTS.items():
            try:
                role_enum = RoleEnum(role_str)
            except ValueError:
                continue  # unknown role value — skip

            changed = False
            for perm_key in PERMISSION_KEYS:
                try:
                    exists = RolePermission.query.filter_by(
                        role=role_enum, permission_key=perm_key
                    ).first()
                except Exception:
                    db.session.rollback()
                    break  # DB enum constraint not yet updated — skip this role
                if exists is None:
                    db.session.add(RolePermission(
                        role=role_enum,
                        permission_key=perm_key,
                        granted=(perm_key in keys),
                    ))
                    changed = True
            if changed:
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()  # DB rejected new enum value — skip silently
