import io
import uuid
import base64
from datetime import datetime, timezone

from marshmallow import Schema, fields, validate, ValidationError  # noqa: F401
from sqlalchemy import text

import qrcode
from qrcode.image.pil import PilImage

from ...extensions import db
from ...models.token import Token, TokenTypeEnum, TokenStatusEnum
from ...models.app_config import AppConfig


# ── Schemas ────────────────────────────────────────────────────────────────

class GenerateTokenSchema(Schema):
    type = fields.Str(
        required=True,
        validate=validate.OneOf(["single", "dual"]),
    )
    participant_name = fields.Str(
        required=True,
        data_key="participantName",
        validate=validate.Length(min=1, max=120),
    )
    topic = fields.Str(
        load_default=None,
        validate=validate.Length(max=200),
    )


class BulkTokenSchema(Schema):
    count = fields.Int(required=True, validate=validate.Range(min=1, max=500))


generate_schema = GenerateTokenSchema()
bulk_schema = BulkTokenSchema()


# ── Config helpers ─────────────────────────────────────────────────────────

def get_token_config_dict() -> dict:
    return {
        "tokenPrefix":        AppConfig.get("token_prefix", ""),
        "tokenSuffix":        AppConfig.get("token_suffix", ""),
        "tokenPadWidth":      AppConfig.get("token_pad_width", "4"),
        "tokenStartNumber":   AppConfig.get("token_start_number", "1"),
        "tokenCurrentNumber": AppConfig.get("token_current_number"),
        "tokenDefaultTopic":  AppConfig.get("token_default_topic", ""),
    }


_TOKEN_CONFIG_MAP = {
    "tokenPrefix":       "token_prefix",
    "tokenSuffix":       "token_suffix",
    "tokenPadWidth":     "token_pad_width",
    "tokenStartNumber":  "token_start_number",
    "tokenDefaultTopic": "token_default_topic",
}


def set_token_config(payload: dict) -> dict:
    updated = {}
    for camel, db_key in _TOKEN_CONFIG_MAP.items():
        if camel in payload:
            AppConfig.set(db_key, str(payload[camel]).strip())
            updated[camel] = str(payload[camel]).strip()
    return updated


def reset_token_counter() -> int:
    db.session.execute(text("DELETE FROM app_config WHERE key = 'token_current_number'"))
    db.session.commit()
    return int(AppConfig.get("token_start_number", "1") or "1")


# ── Internal helpers ───────────────────────────────────────────────────────

def _cfg() -> dict:
    return {
        "prefix":        AppConfig.get("token_prefix", "") or "",
        "suffix":        AppConfig.get("token_suffix", "") or "",
        "pad_width":     int(AppConfig.get("token_pad_width", "4") or "4"),
        "default_topic": AppConfig.get("token_default_topic", "") or "",
        "org_name":      AppConfig.get("org_name", "Organisation") or "Organisation",
    }


def _build_token_no(serial: int, cfg: dict) -> str:
    return f"{cfg['prefix']}{str(serial).zfill(cfg['pad_width'])}{cfg['suffix']}"


def _next_serial() -> int:
    """Atomically increment and return next token serial (PostgreSQL CTE)."""
    result = db.session.execute(text("""
        WITH upsert AS (
            INSERT INTO app_config (key, value)
            VALUES (
                'token_current_number',
                COALESCE(
                    (SELECT (value::int + 1)::text
                       FROM app_config WHERE key = 'token_current_number'),
                    (SELECT COALESCE(value, '1')
                       FROM app_config WHERE key = 'token_start_number'),
                    '1'
                )
            )
            ON CONFLICT (key) DO UPDATE
                SET value = (app_config.value::int + 1)::text
            RETURNING value::int AS serial
        )
        SELECT serial FROM upsert
    """))
    return result.scalar()


def make_qr_b64(url: str) -> str:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=5,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(image_factory=PilImage)
    buf = io.BytesIO()
    img.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


# ── Token generation ───────────────────────────────────────────────────────

def generate_token(data: dict, generated_by_id: int) -> Token:
    cfg = _cfg()
    serial = _next_serial()
    token_no = _build_token_no(serial, cfg)
    topic = data.get("topic") or cfg["default_topic"] or None

    token = Token(
        token_no=token_no,
        token_serial=serial,
        type=TokenTypeEnum(data["type"]),
        participant_name=data["participant_name"],
        topic=topic,
        org_name=cfg["org_name"],
        generated_by_id=generated_by_id,
        generated_at=datetime.now(timezone.utc),
    )
    db.session.add(token)
    db.session.commit()
    return token


def generate_bulk(count: int, generated_by_id: int) -> tuple[list, str]:
    cfg = _cfg()
    batch_id = str(uuid.uuid4())
    tokens = []
    now = datetime.now(timezone.utc)
    for _ in range(count):
        serial = _next_serial()
        token = Token(
            token_no=_build_token_no(serial, cfg),
            token_serial=serial,
            type=TokenTypeEnum.bulk,
            participant_name=None,
            topic=None,
            org_name=cfg["org_name"],
            generated_by_id=generated_by_id,
            generated_at=now,
            batch_id=batch_id,
        )
        db.session.add(token)
        tokens.append(token)
    db.session.commit()
    return tokens, batch_id


# ── Queries ────────────────────────────────────────────────────────────────

def get_token(token_no: str) -> Token | None:
    return Token.query.filter_by(token_no=token_no).first()


def get_token_list(page: int = 1, per_page: int = 50, batch_id: str | None = None):
    q = Token.query.order_by(Token.token_serial.desc())
    if batch_id:
        q = q.filter_by(batch_id=batch_id)
    return q.paginate(page=page, per_page=per_page, error_out=False)


def get_batch(batch_id: str) -> list:
    return Token.query.filter_by(batch_id=batch_id).order_by(Token.token_serial).all()


def void_token(token: Token) -> Token:
    token.status = TokenStatusEnum.void
    db.session.commit()
    return token
