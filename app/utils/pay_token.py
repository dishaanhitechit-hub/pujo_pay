"""Signed links for the server-rendered /pay pages.

Browsers open these pages by plain navigation, so they can't send the JWT. Instead the
authenticated API hands out a signed token bound to one payment id:
  - action token  — returned by /api/payment/initiate; opens the QR/cash/cheque page and
                    allows confirm/cancel.
  - receipt token — included in payment API responses; only opens the receipt page.
"""
from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer

ACTION_MAX_AGE = 24 * 3600
RECEIPT_MAX_AGE = 30 * 24 * 3600


def _serializer(kind: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=f"pay-{kind}")


def make_action_token(payment_id: int) -> str:
    return _serializer("action").dumps(payment_id)


def make_receipt_token(payment_id: int) -> str:
    return _serializer("receipt").dumps(payment_id)


def _valid(kind: str, token: str | None, payment_id: int, max_age: int) -> bool:
    if not token:
        return False
    try:
        return _serializer(kind).loads(token, max_age=max_age) == payment_id
    except BadSignature:  # also covers SignatureExpired
        return False


def valid_action_token(token: str | None, payment_id: int) -> bool:
    return _valid("action", token, payment_id, ACTION_MAX_AGE)


def valid_receipt_token(token: str | None, payment_id: int) -> bool:
    return (
        _valid("receipt", token, payment_id, RECEIPT_MAX_AGE)
        or valid_action_token(token, payment_id)
    )
