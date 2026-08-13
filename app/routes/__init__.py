from flask import Flask


def register_blueprints(app: Flask) -> None:
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    # remaining blueprints registered in later steps
