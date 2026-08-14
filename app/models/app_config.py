from ..extensions import db


class AppConfig(db.Model):
    __tablename__ = "app_config"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    @staticmethod
    def get(key: str, default: str | None = None) -> str | None:
        row = AppConfig.query.filter_by(key=key).first()
        return row.value if row else default

    @staticmethod
    def set(key: str, value: str) -> None:
        row = AppConfig.query.filter_by(key=key).first()
        if row:
            row.value = value
        else:
            db.session.add(AppConfig(key=key, value=value))
        db.session.commit()
