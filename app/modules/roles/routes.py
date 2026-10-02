from flask import Blueprint, request

from ...middleware.permissions import require_permission
from ...middleware.tenant import get_current_org_id
from ...utils.helpers import res
from .service import (
    list_club_years, create_club_year, set_current_year,
    list_year_assignments, set_year_assignment, clear_year_assignment,
    list_event_assignments, set_event_assignment, clear_event_assignment,
    VALID_ROLES,
)

bp = Blueprint("roles", __name__)

# Role assignment is a committee/content concern — gate behind content.manage.
PERM = "content.manage"


@bp.route("/roles", methods=["GET"])
@require_permission(PERM)
def roles_list():
    return res(data={"roles": VALID_ROLES})


# ── Club years ───────────────────────────────────────────────────────────────

@bp.route("/years", methods=["GET"])
@require_permission(PERM)
def years_list():
    return res(data=list_club_years(get_current_org_id()))


@bp.route("/years", methods=["POST"])
@require_permission(PERM)
def years_create():
    body = request.get_json(silent=True) or {}
    year, err = create_club_year(get_current_org_id(), body.get("label", ""))
    if err:
        return res(err, code=400)
    return res("year created", data=year, code=201)


@bp.route("/years/<int:year_id>/current", methods=["POST"])
@require_permission(PERM)
def years_set_current(year_id):
    year, err = set_current_year(get_current_org_id(), year_id)
    if err:
        return res(err, code=404)
    return res("current year updated", data=year)


@bp.route("/years/<int:year_id>/assignments", methods=["GET"])
@require_permission(PERM)
def year_assignments_list(year_id):
    data, err = list_year_assignments(get_current_org_id(), year_id)
    if err:
        return res(err, code=404)
    return res(data=data)


@bp.route("/years/<int:year_id>/assignments", methods=["PUT"])
@require_permission(PERM)
def year_assignment_set(year_id):
    body = request.get_json(silent=True) or {}
    user_id = body.get("userId")
    role = body.get("role")
    if user_id is None or role is None:
        return res("userId and role are required", code=400)
    data, err = set_year_assignment(
        get_current_org_id(), year_id, user_id, role, body.get("isPublic", True),
    )
    if err:
        code = 404 if "not found" in err else 400
        return res(err, code=code)
    return res("assignment saved", data=data)


@bp.route("/years/<int:year_id>/assignments/<int:user_id>", methods=["DELETE"])
@require_permission(PERM)
def year_assignment_clear(year_id, user_id):
    ok, err = clear_year_assignment(get_current_org_id(), year_id, user_id)
    if err:
        return res(err, code=404)
    return res("assignment cleared")


# ── Event role assignments ───────────────────────────────────────────────────

@bp.route("/events/<int:event_id>/assignments", methods=["GET"])
@require_permission(PERM)
def event_assignments_list(event_id):
    data, err = list_event_assignments(get_current_org_id(), event_id)
    if err:
        return res(err, code=404)
    return res(data=data)


@bp.route("/events/<int:event_id>/assignments", methods=["PUT"])
@require_permission(PERM)
def event_assignment_set(event_id):
    body = request.get_json(silent=True) or {}
    user_id = body.get("userId")
    role = body.get("role")
    if user_id is None or role is None:
        return res("userId and role are required", code=400)
    data, err = set_event_assignment(
        get_current_org_id(), event_id, user_id, role,
        body.get("canCollect", False), body.get("isPublic", True),
    )
    if err:
        code = 404 if "not found" in err else 400
        return res(err, code=code)
    return res("assignment saved", data=data)


@bp.route("/events/<int:event_id>/assignments/<int:user_id>", methods=["DELETE"])
@require_permission(PERM)
def event_assignment_clear(event_id, user_id):
    ok, err = clear_event_assignment(get_current_org_id(), event_id, user_id)
    if err:
        return res(err, code=404)
    return res("assignment cleared")
