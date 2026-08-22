from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from marshmallow import ValidationError

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import (
    create_committee_member_schema, update_committee_member_schema,
    list_committee_members, create_committee_member, get_committee_member,
    update_committee_member, delete_committee_member,
)
from ..media.service import upload_committee_photo

bp = Blueprint("committee", __name__)


@bp.route("/", methods=["GET"])
@require_permission("content.manage")
def index():
    return res(data=list_committee_members())


@bp.route("/", methods=["POST"])
@require_permission("content.manage")
def create():
    body = request.get_json(silent=True) or {}
    try:
        data = create_committee_member_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    result, err = create_committee_member(data)
    if err:
        return res(err, code=400)
    return res("committee member created", data=result, code=201)


@bp.route("/<int:member_id>", methods=["GET"])
@require_permission("content.manage")
def detail(member_id):
    result = get_committee_member(member_id)
    if not result:
        return res("committee member not found", code=404)
    return res(data=result)


@bp.route("/<int:member_id>", methods=["PATCH"])
@require_permission("content.manage")
def update(member_id):
    body = request.get_json(silent=True) or {}
    try:
        data = update_committee_member_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    result, err = update_committee_member(member_id, data)
    if err == "committee member not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("committee member updated", data=result)


@bp.route("/<int:member_id>", methods=["DELETE"])
@require_permission("content.manage")
def delete(member_id):
    err = delete_committee_member(member_id)
    if err == "committee member not found":
        return res(err, code=404)
    return res("committee member deleted")


@bp.route("/<int:member_id>/photo", methods=["POST"])
@require_permission("content.manage")
def upload_photo(member_id):
    if "file" not in request.files:
        return res("no file in request", code=400)
    fileobj = request.files["file"]
    if not fileobj.filename:
        return res("no file selected", code=400)

    uploaded_by = int(get_jwt_identity())
    alt_text = request.form.get("altText") or None
    result, err = upload_committee_photo(
        member_id=member_id,
        fileobj=fileobj,
        mime_type=fileobj.mimetype,
        original_filename=fileobj.filename,
        alt_text=alt_text,
        uploaded_by=uploaded_by,
    )
    if err == "committee member not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("photo uploaded", data=result, code=201)
