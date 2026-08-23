from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from marshmallow import ValidationError

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import (
    create_event_schema, update_event_schema, event_days_list_schema,
    list_events, get_active_events, create_event, get_event,
    update_event, set_event_days,
)
from ..media.service import upload_event_cover, upload_event_gallery, reorder_event_gallery, get_event_gallery

bp = Blueprint("event", __name__)


@bp.route("/", methods=["GET"])
@require_permission("event.manage")
def index():
    search = request.args.get("search", "").strip() or None
    status = request.args.get("status", "").strip() or None
    year = request.args.get("year", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("perPage", 20, type=int), 100)

    collection_raw = request.args.get("collectionEnabled", "").strip()
    collection_enabled = None
    if collection_raw == "true":
        collection_enabled = True
    elif collection_raw == "false":
        collection_enabled = False

    featured_raw = request.args.get("isFeatured", "").strip()
    is_featured = None
    if featured_raw == "true":
        is_featured = True
    elif featured_raw == "false":
        is_featured = False

    return res(data=list_events(
        search=search,
        status=status,
        collection_enabled=collection_enabled,
        is_featured=is_featured,
        year=year,
        page=page,
        per_page=per_page,
    ))


@bp.route("/active", methods=["GET"])
@require_permission("payment.initiate")
def active():
    """Events currently open for collection — used by collector dropdown."""
    return res(data=get_active_events())


@bp.route("/", methods=["POST"])
@require_permission("event.manage")
def create():
    body = request.get_json(silent=True) or {}
    try:
        data = create_event_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    created_by = int(get_jwt_identity())
    event, err = create_event(data, created_by)
    if err:
        return res(err, code=400)
    return res("event created", data=event.to_dict(include_days=True), code=201)


@bp.route("/<int:event_id>", methods=["GET"])
@require_permission("event.manage")
def detail(event_id):
    result = get_event(event_id)
    if not result:
        return res("event not found", code=404)
    return res(data=result)


@bp.route("/<int:event_id>", methods=["PATCH"])
@require_permission("event.manage")
def update(event_id):
    body = request.get_json(silent=True) or {}
    try:
        data = update_event_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    result, err = update_event(event_id, data)
    if err == "event not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("event updated", data=result)


@bp.route("/<int:event_id>/days", methods=["POST"])
@require_permission("event.manage")
def set_days(event_id):
    body = request.get_json(silent=True)
    if not isinstance(body, list):
        return res("request body must be a JSON array of days", code=400)
    try:
        days_data = event_days_list_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    result, err = set_event_days(event_id, days_data)
    if err == "event not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("event days updated", data=result)


@bp.route("/<int:event_id>/gallery/reorder", methods=["POST"])
@require_permission("event.manage")
def reorder_gallery(event_id):
    from ...models.event import Event as EventModel
    if not EventModel.query.get(event_id):
        return res("event not found", code=404)
    body = request.get_json(silent=True) or {}
    ordered_ids = body.get("ids")
    if not isinstance(ordered_ids, list) or not all(isinstance(i, int) for i in ordered_ids):
        return res("ids must be a list of integers", code=400)
    err = reorder_event_gallery(event_id, ordered_ids)
    if err:
        return res(err, code=400)
    return res("gallery reordered", data=get_event_gallery(event_id))


@bp.route("/<int:event_id>/cover", methods=["POST"])
@require_permission("event.manage")
def upload_cover(event_id):
    if "file" not in request.files:
        return res("no file in request", code=400)
    fileobj = request.files["file"]
    if not fileobj.filename:
        return res("no file selected", code=400)

    uploaded_by = int(get_jwt_identity())
    alt_text = request.form.get("altText") or None
    result, err = upload_event_cover(
        event_id=event_id,
        fileobj=fileobj,
        mime_type=fileobj.mimetype,
        original_filename=fileobj.filename,
        alt_text=alt_text,
        uploaded_by=uploaded_by,
    )
    if err == "event not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("cover uploaded", data=result, code=201)


@bp.route("/<int:event_id>/gallery", methods=["POST"])
@require_permission("event.manage")
def upload_gallery(event_id):
    if "file" not in request.files:
        return res("no file in request", code=400)
    fileobj = request.files["file"]
    if not fileobj.filename:
        return res("no file selected", code=400)

    uploaded_by = int(get_jwt_identity())
    alt_text = request.form.get("altText") or None
    result, err = upload_event_gallery(
        event_id=event_id,
        fileobj=fileobj,
        mime_type=fileobj.mimetype,
        original_filename=fileobj.filename,
        alt_text=alt_text,
        uploaded_by=uploaded_by,
    )
    if err == "event not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("image added to gallery", data=result, code=201)


@bp.route("/<int:event_id>/summary", methods=["GET"])
@require_permission("event.manage")
def event_summary(event_id):
    from ...models.event import Event as EventModel
    ev = EventModel.query.get(event_id)
    if not ev:
        return res("event not found", code=404)
    from ..dashboard.service import get_grand_summary
    data = get_grand_summary(event_id=event_id)
    return res(data=data)
