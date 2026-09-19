from flask import g
from flask_jwt_extended import get_jwt


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
