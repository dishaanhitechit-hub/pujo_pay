from flask import Blueprint, request
from marshmallow import ValidationError

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import (
    submit_query_schema,
    update_query_status_schema,
    submit_contact_query,
    list_contact_queries,
    get_contact_query,
    update_contact_query_status,
)

bp = Blueprint("contact", __name__)


# ── Public ─────────────────────────────────────────────────────────────────────

@bp.route("/submit", methods=["POST"])
def submit():
    body = request.get_json(silent=True) or {}
    try:
        data = submit_query_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)
    result = submit_contact_query(data)
    return res("query submitted", data=result, code=201)


# ── Admin ──────────────────────────────────────────────────────────────────────

@bp.route("/queries", methods=["GET"])
@require_permission("content.manage")
def list_queries():
    page     = request.args.get("page",    default=1,  type=int)
    per_page = request.args.get("perPage", default=20, type=int)
    status   = request.args.get("status", "").strip() or None
    search   = request.args.get("search", "").strip() or None
    return res(data=list_contact_queries(
        page=page, per_page=per_page, status=status, search=search,
    ))


@bp.route("/queries/<int:query_id>", methods=["GET"])
@require_permission("content.manage")
def query_detail(query_id: int):
    result = get_contact_query(query_id)
    if not result:
        return res("query not found", code=404)
    return res(data=result)


@bp.route("/queries/<int:query_id>/status", methods=["PATCH"])
@require_permission("content.manage")
def update_status(query_id: int):
    body = request.get_json(silent=True) or {}
    try:
        data = update_query_status_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)
    result, err = update_contact_query_status(query_id, data["status"])
    if err:
        code = 404 if "not found" in err else 400
        return res(err, code=code)
    return res("status updated", data=result)
