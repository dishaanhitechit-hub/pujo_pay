from datetime import datetime, timezone

from flask import jsonify


def res(msg="", data=None, code=200):
    return jsonify({
        "message": msg,
        "data": data if data is not None else []
    }), code


def utcnow() -> datetime:
    """Naive UTC timestamp — matches the naive DateTime columns regardless of DB server timezone."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
