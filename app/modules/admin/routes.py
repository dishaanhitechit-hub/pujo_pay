from flask import Blueprint, request

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import get_all, set_keys, ALLOWED_KEYS

bp = Blueprint("admin", __name__)


@bp.route("/config", methods=["GET"])
@require_permission("users.manage")
def get_config():
    return res(data={
        "config": get_all(),
        "allowedKeys": ALLOWED_KEYS,
    })


@bp.route("/config", methods=["POST"])
@require_permission("users.manage")
def update_config():
    body = request.get_json(silent=True) or {}
    if not body:
        return res("request body is empty", code=400)

    updated, errors = set_keys(body)

    if errors:
        return res("some keys were rejected", data={"updated": updated, "errors": errors}, code=400)

    return res("config updated", data=updated)
