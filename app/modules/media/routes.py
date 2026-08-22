from flask import Blueprint, send_file

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import delete_media, resolve_media_path

bp = Blueprint("media", __name__)


@bp.route("/api/media/<int:media_id>", methods=["DELETE"])
@require_permission("event.manage")
def delete(media_id):
    err = delete_media(media_id)
    if err == "media not found":
        return res(err, code=404)
    return res("media deleted")


@bp.route("/media/<path:filepath>", methods=["GET"])
def serve(filepath):
    abs_path = resolve_media_path(filepath)
    if not abs_path:
        return res("media not found", code=404)
    return send_file(abs_path)
