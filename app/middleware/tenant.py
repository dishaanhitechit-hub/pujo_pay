from functools import wraps

from flask import g
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from ..utils.helpers import res


def get_current_org_id() -> int | None:
    """Return the org_id of the currently authenticated user from JWT claims."""
    try:
        claims = get_jwt()
        return claims.get("org_id")
    except Exception:
        return None


def load_org_context() -> None:
    """Call inside a jwt_required route to populate g.org_id."""
    g.org_id = get_current_org_id()


def require_same_org(org_of, not_found: str = "not found"):
    """404 unless the URL's target belongs to the caller's org.

    `org_of(**view_kwargs)` returns a one-column row holding the target's org_id, or None
    when the target doesn't exist. Cross-org targets get the same 404 as missing ones so
    IDs from other orgs can't be probed.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            row = org_of(**kwargs)
            if row is None or row[0] != get_current_org_id():
                return res(not_found, code=404)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
