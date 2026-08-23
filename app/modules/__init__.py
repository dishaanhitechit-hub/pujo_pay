from flask import Flask


def register_all(app: Flask) -> None:
    from .auth.routes import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    from .users.routes import bp as users_bp
    app.register_blueprint(users_bp, url_prefix="/api/users")

    from .admin.routes import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    from .payment.routes import bp as payment_bp
    app.register_blueprint(payment_bp, url_prefix="/api/payment")

    from .qr.routes import bp as qr_bp
    app.register_blueprint(qr_bp, url_prefix="/pay")

    from .collector.routes import bp as collector_bp
    app.register_blueprint(collector_bp, url_prefix="/api/collector")

    from .dashboard.routes import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")

    from .receipt.routes import bp as receipt_bp
    app.register_blueprint(receipt_bp, url_prefix="")

    from .token.routes import bp as token_bp
    app.register_blueprint(token_bp, url_prefix="")

    from .donor.routes import bp as donor_bp
    app.register_blueprint(donor_bp, url_prefix="/api/donor")

    from .pledge.routes import bp as pledge_bp
    app.register_blueprint(pledge_bp, url_prefix="/api/pledge")

    from .event.routes import bp as event_bp
    app.register_blueprint(event_bp, url_prefix="/api/events")

    from .announcement.routes import bp as announcement_bp
    app.register_blueprint(announcement_bp, url_prefix="/api/announcements")

    from .committee.routes import bp as committee_bp
    app.register_blueprint(committee_bp, url_prefix="/api/committee")

    from .public.routes import bp as public_bp
    app.register_blueprint(public_bp, url_prefix="/api/public")

    from .media.routes import bp as media_bp
    app.register_blueprint(media_bp, url_prefix="")

    from .contact.routes import bp as contact_bp
    app.register_blueprint(contact_bp, url_prefix="/api/contact")
