from ..extensions import db

# Migration (run once on the database):
# ALTER TABLE app_config ADD COLUMN org_id INTEGER REFERENCES organisations(id);
# ALTER TABLE app_config DROP CONSTRAINT app_config_key_key;
# CREATE UNIQUE INDEX uq_app_config_org_key ON app_config (org_id, key);
# (For SQLite, recreate the table instead of ALTER/DROP CONSTRAINT.)


class AppConfig(db.Model):
    __tablename__ = "app_config"
    __table_args__ = (
        db.UniqueConstraint("org_id", "key", name="uq_app_config_org_key"),
    )

    id       = db.Column(db.Integer, primary_key=True)
    org_id   = db.Column(db.Integer, db.ForeignKey("organisations.id"), nullable=True, index=True)
    key      = db.Column(db.String(120), nullable=False)
    value    = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    @staticmethod
    def get(key: str, org_id: int | None = None, default: str | None = None) -> str | None:
        """Return the value for (org_id, key). Falls back to the NULL-org global row."""
        if org_id is not None:
            row = AppConfig.query.filter_by(org_id=org_id, key=key).first()
            if row:
                return row.value
        row = AppConfig.query.filter_by(org_id=None, key=key).first()
        return row.value if row else default

    @staticmethod
    def set(key: str, value: str, org_id: int | None = None) -> None:
        row = AppConfig.query.filter_by(org_id=org_id, key=key).first()
        if row:
            row.value = value
        else:
            db.session.add(AppConfig(org_id=org_id, key=key, value=value))
        db.session.commit()
