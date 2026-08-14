from functools import wraps
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from ..models.role_permission import RolePermission
from ..utils.helpers import res


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
