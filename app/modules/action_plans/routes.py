from datetime import date as date_type

from flask import Blueprint, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity

from ...utils.helpers import res
from ...middleware.permissions import require_permission
from .service import (
    list_action_plans, create_action_plan, get_action_plan,
    update_action_plan, delete_action_plan,
    add_assignees, remove_assignee,
    list_my_action_plans,
)

bp = Blueprint("action_plans", __name__)


def _auth():
    verify_jwt_in_request()
    claims = get_jwt()
    return int(get_jwt_identity()), claims.get("role", "")


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return date_type.fromisoformat(value)
    except (ValueError, TypeError):
        return None


# ── Admin CRUD ─────────────────────────────────────────────────────────────

@bp.route("/", methods=["GET"])
@require_permission("meeting.manage")
def admin_list():
    return res(data=list_action_plans(
        status=request.args.get("status"),
        priority=request.args.get("priority"),
        event_id=request.args.get("eventId", type=int),
        meeting_id=request.args.get("meetingId", type=int),
        assignee_id=request.args.get("assigneeId", type=int),
        search=request.args.get("search"),
        due_date_from=request.args.get("dueDateFrom"),
        due_date_to=request.args.get("dueDateTo"),
        page=request.args.get("page", 1, type=int),
        per_page=request.args.get("perPage", 20, type=int),
    ))


@bp.route("/", methods=["POST"])
@require_permission("meeting.manage")
def admin_create():
    body = request.get_json(silent=True) or {}
    if not body.get("title"):
        return res("title is required", code=422)

    verify_jwt_in_request()
    created_by = int(get_jwt_identity())

    data = {
        "title":       body["title"],
        "description": body.get("description"),
        "event_id":    body.get("eventId"),
        "meeting_id":  body.get("meetingId"),
        "start_date":  _parse_date(body.get("startDate")),
        "due_date":    _parse_date(body.get("dueDate")),
        "priority":    body.get("priority", "medium"),
        "status":      body.get("status", "not_started"),
        "notes":       body.get("notes"),
    }
    result, err = create_action_plan(data, created_by)
    if err:
        return res(err, code=400)
    return res("action plan created", data=result, code=201)


@bp.route("/<int:plan_id>", methods=["GET"])
@require_permission("meeting.manage")
def admin_detail(plan_id):
    result = get_action_plan(plan_id)
    if not result:
        return res("action plan not found", code=404)
    return res(data=result)


@bp.route("/<int:plan_id>", methods=["PATCH"])
@require_permission("meeting.manage")
def admin_update(plan_id):
    body = request.get_json(silent=True) or {}
    data = {}
    if "title"       in body: data["title"]       = body["title"]
    if "description" in body: data["description"] = body["description"]
    if "eventId"     in body: data["event_id"]    = body["eventId"]
    if "meetingId"   in body: data["meeting_id"]  = body["meetingId"]
    if "startDate"   in body: data["start_date"]  = _parse_date(body["startDate"])
    if "dueDate"     in body: data["due_date"]     = _parse_date(body["dueDate"])
    if "priority"    in body: data["priority"]    = body["priority"]
    if "status"      in body: data["status"]      = body["status"]
    if "notes"       in body: data["notes"]       = body["notes"]

    result, err = update_action_plan(plan_id, data)
    if err == "action plan not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("action plan updated", data=result)


@bp.route("/<int:plan_id>", methods=["DELETE"])
@require_permission("meeting.manage")
def admin_delete(plan_id):
    err = delete_action_plan(plan_id)
    if err:
        return res(err, code=404)
    return res("action plan deleted")


# ── Admin: Assignees ───────────────────────────────────────────────────────

@bp.route("/<int:plan_id>/assignees", methods=["POST"])
@require_permission("meeting.manage")
def admin_add_assignees(plan_id):
    body = request.get_json(silent=True) or {}
    user_ids = body.get("userIds", [])
    if not user_ids:
        return res("userIds is required", code=422)

    verify_jwt_in_request()
    assigned_by = int(get_jwt_identity())

    result, err = add_assignees(plan_id, user_ids, assigned_by)
    if err == "action plan not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("assignees added", data=result)


@bp.route("/<int:plan_id>/assignees/<int:user_id>", methods=["DELETE"])
@require_permission("meeting.manage")
def admin_remove_assignee(plan_id, user_id):
    err = remove_assignee(plan_id, user_id)
    if err:
        return res(err, code=404)
    return res("assignee removed")


# ── Member: my action plans ────────────────────────────────────────────────

@bp.route("/me", methods=["GET"])
def member_list():
    user_id, _ = _auth()
    return res(data=list_my_action_plans(
        user_id=user_id,
        status=request.args.get("status"),
        priority=request.args.get("priority"),
        event_id=request.args.get("eventId", type=int),
        search=request.args.get("search"),
        page=request.args.get("page", 1, type=int),
        per_page=request.args.get("perPage", 20, type=int),
    ))
