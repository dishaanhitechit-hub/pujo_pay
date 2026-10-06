import threading
from functools import wraps
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request
from ..models.role_permission import RolePermission
from ..utils.helpers import res

# In-memory permission cache: role → frozenset of granted permission keys.
# Eliminates one DB roundtrip per request. Invalidated on any permission write.
_perm_cache: dict[str, frozenset] = {}
_cache_lock = threading.Lock()


def _grants_for_role(role: str) -> frozenset:
    """Return cached set of granted permission keys for a role."""
    if role in _perm_cache:
        return _perm_cache[role]
    with _cache_lock:
        if role in _perm_cache:
            return _perm_cache[role]
        rows = RolePermission.query.filter_by(role=role, granted=True).all()
        keys = frozenset(r.permission_key for r in rows)
        _perm_cache[role] = keys
        return keys


def invalidate_permission_cache(role: str | None = None) -> None:
    """Call after any RolePermission write so the next request re-loads from DB."""
    with _cache_lock:
        if role:
            _perm_cache.pop(role, None)
        else:
            _perm_cache.clear()


def has_permission(role: str, permission_key: str) -> bool:
    return permission_key in _grants_for_role(role)


def require_collect_capable():
    """Enforce collection capability.

    - admin / super_admin → always denied (403) — admins don't collect
    - everyone else       → allowed only if they hold ``can_collect`` on at
                            least one event. The per-event data scoping limits
                            what they can act on to exactly those events.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role")

            if role in ("admin", "super_admin"):
                return res("admin accounts cannot access collection features", code=403)

            from ..models.user import User
            from .event_scope import capability_event_ids
            user_id = int(get_jwt_identity())
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return res("user not found or inactive", code=403)

            if not capability_event_ids("collect"):
                return res("collection capability is not enabled for this account", code=403)

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_super_admin():
    """Allow only the platform super_admin role."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role")
            if role != "super_admin":
                return res("access denied: super admin only", code=403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def current_user_has_permission(permission_key: str) -> bool:
    """Whether the JWT's user has a permission, via the effective-permission resolver."""
    from .perm_resolver import effective_permissions
    claims = get_jwt()
    role = claims.get("role")
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return False
    return permission_key in effective_permissions(user_id, role)


def require_permission(permission_key: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            from .perm_resolver import effective_permissions
            claims = get_jwt()
            role = claims.get("role")
            try:
                user_id = int(get_jwt_identity())
            except (TypeError, ValueError):
                return res("invalid token", code=403)

            if permission_key not in effective_permissions(user_id, role):
                return res(
                    f"access denied: '{permission_key}' not allowed",
                    code=403,
                )

            return fn(*args, **kwargs)
        return wrapper
    return decorator
