from flask import Flask, jsonify

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

    # ── Error handlers ──────────────────────────────────────
    @app.errorhandler(413)
    def request_entity_too_large(_e):
        return jsonify({"message": "File too large — maximum 10 MB allowed"}), 413

    @app.errorhandler(500)
    def internal_error(e):
        import traceback
        app.logger.error("Unhandled 500: %s", traceback.format_exc())
        return jsonify({"message": "Internal server error", "detail": str(e)}), 500

    # ── Blueprints ──────────────────────────────────────────
    from .modules import register_all
    register_all(app)

    # ── Import models so Flask-Migrate can detect all tables ─
    from .models.organisation import Organisation  # noqa: F401
    from .models import User, Donor, Payment, RolePermission, AppConfig  # noqa: F401
    from .models.token import Token  # noqa: F401
    from .models.pledge import Pledge  # noqa: F401
    from .models.event import Event  # noqa: F401
    from .models.event_day import EventDay  # noqa: F401
    from .models.announcement import Announcement  # noqa: F401
    from .models.committee_member import CommitteeMember  # noqa: F401
    from .models.media_file import MediaFile  # noqa: F401
    from .models.contact_query import ContactQuery  # noqa: F401
    from .models.expense import Expense  # noqa: F401
    from .models.budget_category import BudgetCategory  # noqa: F401
    from .models.self_contribution import SelfContribution  # noqa: F401
    from .models.meeting import Meeting, MeetingInvitee  # noqa: F401
    from .models.meeting_agenda_item import MeetingAgendaItem  # noqa: F401
    from .models.meeting_discussion import MeetingDiscussion  # noqa: F401
    from .models.meeting_attendance import MeetingAttendance, MeetingAttendanceDevice  # noqa: F401
    from .models.action_plan import ActionPlan, ActionPlanAssignee  # noqa: F401
    from .models.circular import Circular  # noqa: F401
    from .models.org_provision import OrgProvision  # noqa: F401

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
    """Create the platform super-admin on first run if none exists."""
    import os
    from .models.user import User, RoleEnum
    from .models.organisation import Organisation

    if User.query.filter_by(role=RoleEnum.super_admin).first():
        return

    org = Organisation.query.filter_by(slug="platform").first()
    if not org:
        org = Organisation(name=os.getenv("ADMIN_ORG_NAME", "Platform Admin"), slug="platform")
        db.session.add(org)
        db.session.flush()

    admin = User(
        name=os.getenv("ADMIN_NAME", "Super Admin"),
        email=os.environ["ADMIN_EMAIL"],
        role=RoleEnum.super_admin,
        is_active=True,
        org_id=org.id,
    )
    admin.set_password(os.environ["ADMIN_PASSWORD"])
    db.session.add(admin)
    db.session.commit()


def _seed_permissions():
    from .models.role_permission import RolePermission
    RolePermission.seed_defaults()
