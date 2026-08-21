from flask import Flask

from .config import get_config
from flask_cors import CORS

from .extensions import db, migrate, jwt, is_blocklisted


def create_app():
    app = Flask(__name__, template_folder="templates")
    app.config.from_object(get_config())

    # ── Extensions ──────────────────────────────────────────
    CORS(app)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # ── JWT blocklist check ─────────────────────────────────
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return is_blocklisted(jwt_payload["jti"])

    # ── Blueprints ──────────────────────────────────────────
    from .modules import register_all
    register_all(app)

    # ── Import models so Flask-Migrate can detect all tables ─
    from .models import User, Donor, Payment, RolePermission, AppConfig  # noqa: F401
    from .models.token import Token  # noqa: F401

    # ── DB seed (first-run admin + default permissions) ─────
    # Skipped silently if tables don't exist yet (before first migration)
    with app.app_context():
        try:
            _seed_admin()
            _seed_permissions()
        except Exception:
            pass

    return app


def _seed_admin():
    """Create the admin user on first run if none exists."""
    import os
    from .models.user import User, RoleEnum

    if User.query.filter_by(role=RoleEnum.admin).first():
        return

    admin = User(
        name=os.getenv("ADMIN_NAME", "Admin"),
        email=os.environ["ADMIN_EMAIL"],
        role=RoleEnum.admin,
        is_active=True,
    )
    admin.set_password(os.environ["ADMIN_PASSWORD"])
    db.session.add(admin)
    db.session.commit()


def _seed_permissions():
    from .models.role_permission import RolePermission
    RolePermission.seed_defaults()
