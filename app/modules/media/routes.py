from flask import Blueprint, send_file
from sqlalchemy import func

from ...extensions import db
from ...models.event import Event
from ...models.media_file import MediaFile
from ...middleware.permissions import require_permission
from ...middleware.tenant import require_same_org
from ...utils.helpers import res
from .service import delete_media, resolve_media_path

bp = Blueprint("media", __name__)

_media_in_org = require_same_org(
    lambda media_id, **_: db.session.query(func.coalesce(MediaFile.org_id, Event.org_id))
    .outerjoin(Event, MediaFile.event_id == Event.id)
    .filter(MediaFile.id == media_id).first(),
    "media not found",
)


@bp.route("/api/media/<int:media_id>", methods=["DELETE"])
@require_permission("event.manage")
@_media_in_org
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
