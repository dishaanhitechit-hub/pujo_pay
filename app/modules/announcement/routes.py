from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from marshmallow import ValidationError

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import (
    create_announcement_schema, update_announcement_schema,
    list_announcements, create_announcement, get_announcement,
    update_announcement, delete_announcement,
)

bp = Blueprint("announcement", __name__)


@bp.route("/", methods=["GET"])
@require_permission("content.manage")
def index():
    return res(data=list_announcements())


@bp.route("/", methods=["POST"])
@require_permission("content.manage")
def create():
    body = request.get_json(silent=True) or {}
    try:
        data = create_announcement_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    created_by = int(get_jwt_identity())
    result, err = create_announcement(data, created_by)
    if err:
        return res(err, code=400)
    return res("announcement created", data=result, code=201)


@bp.route("/<int:announcement_id>", methods=["GET"])
@require_permission("content.manage")
def detail(announcement_id):
    result = get_announcement(announcement_id)
    if not result:
        return res("announcement not found", code=404)
    return res(data=result)


@bp.route("/<int:announcement_id>", methods=["PATCH"])
@require_permission("content.manage")
def update(announcement_id):
    body = request.get_json(silent=True) or {}
    try:
        data = update_announcement_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    result, err = update_announcement(announcement_id, data)
    if err == "announcement not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("announcement updated", data=result)


@bp.route("/<int:announcement_id>", methods=["DELETE"])
@require_permission("content.manage")
def delete(announcement_id):
    err = delete_announcement(announcement_id)
    if err == "announcement not found":
        return res(err, code=404)
    return res("announcement deleted")
