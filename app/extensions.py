from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

# In-memory JWT blocklist (revoked tokens after logout)
_token_blocklist: set[str] = set()


def add_to_blocklist(jti: str) -> None:
    _token_blocklist.add(jti)


def is_blocklisted(jti: str) -> bool:
    return jti in _token_blocklist
