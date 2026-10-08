from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity

from ...middleware.permissions import require_permission
from ...middleware.tenant import get_current_org_id
from ...utils.helpers import res
from .service import get_all, set_keys, ALLOWED_KEYS

bp = Blueprint("admin", __name__)


@bp.route("/config", methods=["GET"])
@require_permission("users.manage")
def get_config():
    return res(data={
        "config": get_all(org_id=get_current_org_id()),
        "allowedKeys": ALLOWED_KEYS,
    })


@bp.route("/config", methods=["POST"])
@require_permission("users.manage")
def update_config():
    body = request.get_json(silent=True) or {}
    if not body:
        return res("request body is empty", code=400)

    updated, errors = set_keys(body, org_id=get_current_org_id())

    if errors:
        return res("some keys were rejected", data={"updated": updated, "errors": errors}, code=400)

    return res("config updated", data=updated)


@bp.route("/theme", methods=["GET"])
@require_permission("users.manage")
def get_theme():
    import json as _json
    from ...models.app_config import AppConfig
    raw = AppConfig.get("theme.colors", org_id=get_current_org_id())
    theme = None
    if raw:
        try:
            theme = _json.loads(raw)
        except Exception:
            theme = None
    return res(data={"theme": theme})


@bp.route("/theme", methods=["POST"])
@require_permission("users.manage")
def save_theme():
    import json as _json
    from ...models.app_config import AppConfig
    body = request.get_json(silent=True) or {}
    theme = body.get("theme")
    org_id = get_current_org_id()
    if theme is None:
        AppConfig.set("theme.colors", "", org_id=org_id)
    else:
        AppConfig.set("theme.colors", _json.dumps(theme), org_id=org_id)
    return res("theme saved", data={"theme": theme})


@bp.route("/config/media", methods=["POST"])
@require_permission("users.manage")
def upload_config_media():
    from ..media.service import upload_config_media as _upload

    if "file" not in request.files:
        return res("no file in request", code=400)
    fileobj = request.files["file"]
    if not fileobj.filename:
        return res("no file selected", code=400)

    result, err = _upload(
        org_id=get_current_org_id(),
        fileobj=fileobj,
        mime_type=fileobj.mimetype,
        original_filename=fileobj.filename,
        uploaded_by=int(get_jwt_identity()),
    )
    if err:
        return res(err, code=400)
    return res("uploaded", data=result, code=201)
