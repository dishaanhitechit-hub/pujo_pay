from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ...middleware.permissions import require_permission
from ...middleware.tenant import get_current_org_id
from ...utils.helpers import res
from .service import (
    list_club_years, create_club_year, set_current_year,
    list_year_assignments, set_year_assignment, clear_year_assignment,
    list_event_assignments, set_event_assignment, clear_event_assignment,
    reorder_year_assignments, reorder_event_assignments,
    get_my_roles, VALID_ROLES,
    list_committee_years, list_year_committee, list_committee_events, list_event_committee,
)

bp = Blueprint("roles", __name__)

# Role assignment is a committee/content concern — gate behind content.manage.
PERM = "content.manage"


@bp.route("/roles", methods=["GET"])
@require_permission(PERM)
def roles_list():
    return res(data={"roles": VALID_ROLES})


@bp.route("/my-roles", methods=["GET"])
@jwt_required()
def my_roles():
    return res(data=get_my_roles(get_current_org_id(), int(get_jwt_identity())))


# ── Member read-only committee view (no phone numbers) ───────────────────────

@bp.route("/committee/years", methods=["GET"])
@jwt_required()
def committee_years():
    return res(data=list_committee_years(get_current_org_id()))


@bp.route("/committee/years/<int:year_id>", methods=["GET"])
@jwt_required()
def committee_year(year_id):
    data, err = list_year_committee(get_current_org_id(), year_id)
    if err:
        return res(err, code=404)
    return res(data=data)


@bp.route("/committee/events", methods=["GET"])
@jwt_required()
def committee_events():
    return res(data=list_committee_events(get_current_org_id()))


@bp.route("/committee/events/<int:event_id>", methods=["GET"])
@jwt_required()
def committee_event(event_id):
    data, err = list_event_committee(get_current_org_id(), event_id)
    if err:
        return res(err, code=404)
    return res(data=data)


@bp.route("/my-profile", methods=["GET"])
@jwt_required()
def my_profile():
    """Bundled profile extras — committee roles + contribution stats in one round trip."""
    from ..contribution.service import get_my_stats
    user_id = int(get_jwt_identity())
    return res(data={
        "roles": get_my_roles(get_current_org_id(), user_id),
        "contributionStats": get_my_stats(user_id),
    })


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


@bp.route("/years/<int:year_id>/assignments/order", methods=["PUT"])
@require_permission(PERM)
def year_assignments_reorder(year_id):
    body = request.get_json(silent=True) or {}
    user_ids = body.get("userIds")
    if not isinstance(user_ids, list):
        return res("userIds (array) is required", code=400)
    ok, err = reorder_year_assignments(get_current_org_id(), year_id, user_ids)
    if err:
        return res(err, code=404)
    return res("order updated")


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


@bp.route("/events/<int:event_id>/assignments/order", methods=["PUT"])
@require_permission(PERM)
def event_assignments_reorder(event_id):
    body = request.get_json(silent=True) or {}
    user_ids = body.get("userIds")
    if not isinstance(user_ids, list):
        return res("userIds (array) is required", code=400)
    ok, err = reorder_event_assignments(get_current_org_id(), event_id, user_ids)
    if err:
        return res(err, code=404)
    return res("order updated")


@bp.route("/events/<int:event_id>/assignments/<int:user_id>", methods=["DELETE"])
@require_permission(PERM)
def event_assignment_clear(event_id, user_id):
    ok, err = clear_event_assignment(get_current_org_id(), event_id, user_id)
    if err:
        return res(err, code=404)
    return res("assignment cleared")
