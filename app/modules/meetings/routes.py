from datetime import date as date_type

from flask import Blueprint, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity

from ...utils.helpers import res
from ...middleware.permissions import require_permission
from .service import (
    list_meetings, create_meeting, get_meeting_admin, update_meeting, delete_meeting,
    list_invitees, add_invitees, remove_invitee,
    list_member_meetings, get_meeting_member,
    list_agenda, create_agenda_item, update_agenda_item, delete_agenda_item,
    list_discussions, create_discussion, update_discussion, delete_discussion,
    get_attendance_status, mark_attendance, list_attendance,
)

bp = Blueprint("meetings", __name__)


def _auth():
    """Verify JWT and return (user_id, role)."""
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


# ── Admin: Meetings CRUD ───────────────────────────────────────────────────

@bp.route("/", methods=["GET"])
@require_permission("meeting.manage")
def admin_list():
    return res(data=list_meetings(
        status=request.args.get("status"),
        event_id=request.args.get("eventId", type=int),
        page=request.args.get("page", 1, type=int),
        per_page=request.args.get("perPage", 20, type=int),
    ))


@bp.route("/", methods=["POST"])
@require_permission("meeting.manage")
def admin_create():
    body = request.get_json(silent=True) or {}
    _, _ = _auth()  # already verified by decorator

    required = {"title", "date", "startTime", "endTime"}
    missing = required - body.keys()
    if missing:
        return res(f"missing fields: {', '.join(sorted(missing))}", code=422)

    parsed_date = _parse_date(body.get("date"))
    if not parsed_date:
        return res("invalid date format — use YYYY-MM-DD", code=422)

    verify_jwt_in_request()
    created_by = int(get_jwt_identity())

    data = {
        "title":        body.get("title", ""),
        "description":  body.get("description"),
        "date":         parsed_date,
        "start_time":   body.get("startTime", ""),
        "end_time":     body.get("endTime", ""),
        "venue":        body.get("venue"),
        "meeting_type": body.get("meetingType", "general"),
        "status":       body.get("status", "draft"),
        "event_id":     body.get("eventId"),
    }

    result, err = create_meeting(data, created_by)
    if err:
        return res(err, code=400)
    return res("meeting created", data=result, code=201)


@bp.route("/<int:meeting_id>", methods=["GET"])
@require_permission("meeting.manage")
def admin_detail(meeting_id):
    result = get_meeting_admin(meeting_id)
    if not result:
        return res("meeting not found", code=404)
    return res(data=result)


@bp.route("/<int:meeting_id>", methods=["PATCH"])
@require_permission("meeting.manage")
def admin_update(meeting_id):
    body = request.get_json(silent=True) or {}
    data = {}
    if "title"       in body: data["title"]        = body["title"]
    if "description" in body: data["description"]  = body["description"]
    if "date"        in body:
        parsed = _parse_date(body["date"])
        if not parsed:
            return res("invalid date format — use YYYY-MM-DD", code=422)
        data["date"] = parsed
    if "startTime"   in body: data["start_time"]   = body["startTime"]
    if "endTime"     in body: data["end_time"]      = body["endTime"]
    if "venue"       in body: data["venue"]         = body["venue"]
    if "meetingType" in body: data["meeting_type"]  = body["meetingType"]
    if "status"      in body: data["status"]        = body["status"]
    if "eventId"     in body: data["event_id"]      = body["eventId"]

    result, err = update_meeting(meeting_id, data)
    if err == "meeting not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("meeting updated", data=result)


@bp.route("/<int:meeting_id>", methods=["DELETE"])
@require_permission("meeting.manage")
def admin_delete(meeting_id):
    err = delete_meeting(meeting_id)
    if err:
        return res(err, code=404)
    return res("meeting deleted")


# ── Admin: Invitees ────────────────────────────────────────────────────────

@bp.route("/<int:meeting_id>/invitees", methods=["GET"])
@require_permission("meeting.manage")
def admin_invitees_list(meeting_id):
    result = list_invitees(meeting_id)
    if result is None:
        return res("meeting not found", code=404)
    return res(data=result)


@bp.route("/<int:meeting_id>/invitees", methods=["POST"])
@require_permission("meeting.manage")
def admin_invitees_add(meeting_id):
    body = request.get_json(silent=True) or {}
    payload = {
        "user_ids":   body.get("userIds", []),
        "roles":      body.get("roles", []),
        "invite_all": body.get("inviteAll", False),
    }
    result, err = add_invitees(meeting_id, payload)
    if err == "meeting not found":
        return res(err, code=404)
    if err:
        return res(err, code=400)
    return res("invitees added", data=result)


@bp.route("/<int:meeting_id>/invitees/<int:user_id>", methods=["DELETE"])
@require_permission("meeting.manage")
def admin_invitee_remove(meeting_id, user_id):
    err = remove_invitee(meeting_id, user_id)
    if err:
        return res(err, code=404)
    return res("invitee removed")


# ── Admin: Attendance (view) ───────────────────────────────────────────────

@bp.route("/<int:meeting_id>/attendance", methods=["GET"])
@require_permission("meeting.manage")
def admin_attendance_list(meeting_id):
    result = list_attendance(meeting_id)
    if result is None:
        return res("meeting not found", code=404)
    return res(data=result)


# ── Admin: Agenda ──────────────────────────────────────────────────────────

@bp.route("/<int:meeting_id>/agenda", methods=["GET"])
@require_permission("meeting.manage")
def admin_agenda_list(meeting_id):
    result = list_agenda(meeting_id)
    if result is None:
        return res("meeting not found", code=404)
    return res(data=result)


@bp.route("/<int:meeting_id>/agenda", methods=["POST"])
@require_permission("meeting.manage")
def admin_agenda_create(meeting_id):
    body = request.get_json(silent=True) or {}
    if not body.get("title"):
        return res("title is required", code=422)
    data = {
        "title":       body["title"],
        "description": body.get("description"),
        "sort_order":  body.get("sortOrder", 0),
        "owner_id":    body.get("ownerId"),
        "status":      body.get("status", "open"),
    }
    result, err = create_agenda_item(meeting_id, data)
    if err:
        return res(err, code=400 if "found" not in err else 404)
    return res("agenda item created", data=result, code=201)


@bp.route("/agenda/<int:item_id>", methods=["PATCH"])
@require_permission("meeting.manage")
def admin_agenda_update(item_id):
    body = request.get_json(silent=True) or {}
    data = {}
    if "title"       in body: data["title"]       = body["title"]
    if "description" in body: data["description"] = body["description"]
    if "sortOrder"   in body: data["sort_order"]  = body["sortOrder"]
    if "ownerId"     in body: data["owner_id"]    = body["ownerId"]
    if "status"      in body: data["status"]      = body["status"]
    result, err = update_agenda_item(item_id, data)
    if err:
        return res(err, code=404)
    return res("agenda item updated", data=result)


@bp.route("/agenda/<int:item_id>", methods=["DELETE"])
@require_permission("meeting.manage")
def admin_agenda_delete(item_id):
    err = delete_agenda_item(item_id)
    if err:
        return res(err, code=404)
    return res("agenda item deleted")


# ── Admin: Discussions ─────────────────────────────────────────────────────

@bp.route("/<int:meeting_id>/discussions", methods=["GET"])
@require_permission("meeting.manage")
def admin_discussions_list(meeting_id):
    result = list_discussions(meeting_id, member_only=False)
    if result is None:
        return res("meeting not found", code=404)
    return res(data=result)


@bp.route("/<int:meeting_id>/discussions", methods=["POST"])
@require_permission("meeting.manage")
def admin_discussions_create(meeting_id):
    body = request.get_json(silent=True) or {}
    if not body.get("content"):
        return res("content is required", code=422)

    verify_jwt_in_request()
    created_by = int(get_jwt_identity())

    data = {
        "content":               body["content"],
        "agenda_item_id":        body.get("agendaItemId"),
        "is_visible_to_members": body.get("isVisibleToMembers", True),
    }
    result, err = create_discussion(meeting_id, data, created_by)
    if err:
        return res(err, code=400 if "found" not in err else 404)
    return res("discussion created", data=result, code=201)


@bp.route("/discussions/<int:disc_id>", methods=["PATCH"])
@require_permission("meeting.manage")
def admin_discussions_update(disc_id):
    body = request.get_json(silent=True) or {}
    data = {}
    if "content"             in body: data["content"]               = body["content"]
    if "isVisibleToMembers"  in body: data["is_visible_to_members"] = body["isVisibleToMembers"]
    if "agendaItemId"        in body: data["agenda_item_id"]        = body["agendaItemId"]
    result, err = update_discussion(disc_id, data)
    if err:
        return res(err, code=404)
    return res("discussion updated", data=result)


@bp.route("/discussions/<int:disc_id>", methods=["DELETE"])
@require_permission("meeting.manage")
def admin_discussions_delete(disc_id):
    err = delete_discussion(disc_id)
    if err:
        return res(err, code=404)
    return res("discussion deleted")


# ── Member: Meetings ───────────────────────────────────────────────────────

@bp.route("/me", methods=["GET"])
def member_list():
    user_id, _ = _auth()
    return res(data=list_member_meetings(user_id))


@bp.route("/me/<int:meeting_id>", methods=["GET"])
def member_detail(meeting_id):
    user_id, _ = _auth()
    result = get_meeting_member(meeting_id, user_id)
    if not result:
        return res("meeting not found or you are not invited", code=404)
    return res(data=result)


# ── Member: Agenda (read-only) ─────────────────────────────────────────────

@bp.route("/me/<int:meeting_id>/agenda", methods=["GET"])
def member_agenda(meeting_id):
    user_id, _ = _auth()
    if not get_meeting_member(meeting_id, user_id):
        return res("meeting not found or you are not invited", code=404)
    result = list_agenda(meeting_id)
    if result is None:
        return res("meeting not found", code=404)
    return res(data=result)


# ── Member: Discussions (read-only, visible only) ──────────────────────────

@bp.route("/me/<int:meeting_id>/discussions", methods=["GET"])
def member_discussions(meeting_id):
    user_id, _ = _auth()
    if not get_meeting_member(meeting_id, user_id):
        return res("meeting not found or you are not invited", code=404)
    result = list_discussions(meeting_id, member_only=True)
    if result is None:
        return res("meeting not found", code=404)
    return res(data=result)


# ── Member: Attendance ─────────────────────────────────────────────────────

@bp.route("/me/<int:meeting_id>/attendance/status", methods=["GET"])
def member_attendance_status(meeting_id):
    user_id, _ = _auth()
    result = get_attendance_status(meeting_id, user_id)
    if not result:
        return res("meeting not found", code=404)
    return res(data=result)


@bp.route("/me/<int:meeting_id>/attendance", methods=["POST"])
def member_mark_attendance(meeting_id):
    user_id, _ = _auth()
    body = request.get_json(silent=True) or {}
    device_token = body.get("deviceToken") or None

    result, err = mark_attendance(meeting_id, user_id, device_token)
    if err:
        code = 409 if "different user" in err else 403 if "not invited" in err else 400
        return res(err, code=code)
    return res("attendance marked", data=result)
