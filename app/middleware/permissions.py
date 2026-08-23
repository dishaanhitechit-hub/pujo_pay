from functools import wraps
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request
from ..models.role_permission import RolePermission
from ..utils.helpers import res


def has_permission(role: str, permission_key: str) -> bool:
    return RolePermission.query.filter_by(
        role=role,
        permission_key=permission_key,
        granted=True,
    ).first() is not None


def require_collect_capable():
    """Enforce per-user collection capability.

    - admin role     → always denied (403)
    - collector role → always allowed
    - other roles    → allowed only if user.can_collect == True in the database
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role")

            if role == "admin":
                return res("admin accounts cannot access collection features", code=403)

            if role == "collector":
                return fn(*args, **kwargs)

            # For all other roles: check the per-user flag in the database
            from ..models.user import User
            user_id = int(get_jwt_identity())
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return res("user not found or inactive", code=403)
            if not user.can_collect:
                return res("collection capability is not enabled for this account", code=403)

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(permission_key: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role")

            if not role:
                return res("no role assigned to this token", code=403)

            granted = RolePermission.query.filter_by(
                role=role,
                permission_key=permission_key,
                granted=True,
            ).first()

            if not granted:
                return res(
                    f"access denied: '{permission_key}' not allowed for role '{role}'",
                    code=403,
                )

            return fn(*args, **kwargs)
        return wrapper
    return decorator
