"""
Run once to create (or update) the platform super admin.

Usage:
    python seed_super_admin.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

SUPER_ADMIN_EMAIL    = os.getenv("SUPER_ADMIN_EMAIL", "superadmin@gmail.com")
SUPER_ADMIN_PASSWORD = os.getenv("SUPER_ADMIN_PASSWORD", "ChangeMe@2026!")
SUPER_ADMIN_NAME     = os.getenv("SUPER_ADMIN_NAME", "Super Admin")

from app import create_app
from app.extensions import db
from app.models.user import User, RoleEnum
from app.models.organisation import Organisation

app = create_app()

with app.app_context():
    # Ensure the platform org exists
    org = Organisation.query.filter_by(slug="platform").first()
    if not org:
        org = Organisation(name="Platform Admin", slug="platform")
        db.session.add(org)
        db.session.flush()

    existing = User.query.filter_by(role=RoleEnum.super_admin).first()

    if existing:
        existing.email = SUPER_ADMIN_EMAIL
        existing.name  = SUPER_ADMIN_NAME
        existing.set_password(SUPER_ADMIN_PASSWORD)
        db.session.commit()
        print(f"Updated super admin → {SUPER_ADMIN_EMAIL}")
    else:
        # Check if email already taken by a non-super-admin
        by_email = User.query.filter_by(email=SUPER_ADMIN_EMAIL).first()
        if by_email:
            by_email.role = RoleEnum.super_admin
            by_email.name = SUPER_ADMIN_NAME
            by_email.set_password(SUPER_ADMIN_PASSWORD)
            by_email.org_id = org.id
            by_email.is_active = True
            db.session.commit()
            print(f"Promoted existing user to super admin → {SUPER_ADMIN_EMAIL}")
        else:
            user = User(
                name=SUPER_ADMIN_NAME,
                email=SUPER_ADMIN_EMAIL,
                role=RoleEnum.super_admin,
                is_active=True,
                org_id=org.id,
            )
            user.set_password(SUPER_ADMIN_PASSWORD)
            db.session.add(user)
            db.session.commit()
            print(f"Created super admin → {SUPER_ADMIN_EMAIL}")
