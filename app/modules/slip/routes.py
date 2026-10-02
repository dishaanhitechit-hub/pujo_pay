from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from ...middleware.permissions import require_collect_capable, current_user_has_permission
from ...middleware.tenant import get_current_org_id
from ...utils.helpers import res
from flask_jwt_extended import get_jwt
from .service import (
    create_slip_schema, manual_payment_schema,
    create_slip, list_slips, get_slip, add_manual_payment,
    close_slip, reopen_slip, cancel_slip, list_donor_types, list_members,
)

bp = Blueprint("slip", __name__)


def _can_view_all() -> bool:
    return current_user_has_permission("payment.view_receipt")


@bp.route("/", methods=["POST"])
@require_collect_capable()
def create():
    body = request.get_json(silent=True) or {}
    try:
        data = create_slip_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)
    slip, err = create_slip(data, int(get_jwt_identity()), org_id=get_current_org_id())
    if err:
        return res(err, code=400)
    return res("slip created", data=slip.to_dict(with_payments=True), code=201)


@bp.route("/", methods=["GET"])
@jwt_required()
def index():
    org_id = get_current_org_id()
    viewer_id = int(get_jwt_identity())
    collector_id = None if _can_view_all() else viewer_id
    # a collector viewing their own; "mine" param forces own view for admins too
    if request.args.get("mine") == "true":
        collector_id = viewer_id
    return res(data=list_slips(
        org_id,
        collector_id=collector_id,
        event_id=request.args.get("eventId", type=int),
        status=request.args.get("status") or None,
        search=request.args.get("search") or None,
        page=request.args.get("page", default=1, type=int),
        per_page=min(request.args.get("perPage", default=20, type=int), 100),
    ))


@bp.route("/donor-types", methods=["GET"])
@require_collect_capable()
def donor_types():
    return res(data={"donorTypes": list_donor_types(get_current_org_id())})


@bp.route("/members", methods=["GET"])
@require_collect_capable()
def members():
    return res(data=list_members(get_current_org_id()))


@bp.route("/<int:slip_id>", methods=["GET"])
@jwt_required()
def detail(slip_id):
    data, err = get_slip(slip_id, int(get_jwt_identity()), _can_view_all(), org_id=get_current_org_id())
    if err == "not_found":
        return res("slip not found", code=404)
    if err == "forbidden":
        return res("forbidden", code=403)
    return res(data=data)


@bp.route("/<int:slip_id>/payments", methods=["POST"])
@require_collect_capable()
def add_payment(slip_id):
    body = request.get_json(silent=True) or {}
    try:
        data = manual_payment_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)
    result, err = add_manual_payment(slip_id, data, int(get_jwt_identity()), _can_view_all(), get_current_org_id())
    if err == "not_found":
        return res("slip not found", code=404)
    if err == "forbidden":
        return res("forbidden", code=403)
    if err:
        return res(err, code=400)
    return res("payment recorded", data=result, code=201)


@bp.route("/<int:slip_id>/close", methods=["POST"])
@require_collect_capable()
def close(slip_id):
    data, err = close_slip(slip_id, int(get_jwt_identity()), _can_view_all(), get_current_org_id())
    if err == "not_found":
        return res("slip not found", code=404)
    if err == "forbidden":
        return res("forbidden", code=403)
    if err:
        return res(err, code=400)
    return res("slip closed", data=data)


@bp.route("/<int:slip_id>/reopen", methods=["POST"])
@require_collect_capable()
def reopen(slip_id):
    data, err = reopen_slip(slip_id, int(get_jwt_identity()), _can_view_all(), get_current_org_id())
    if err == "not_found":
        return res("slip not found", code=404)
    if err == "forbidden":
        return res("forbidden", code=403)
    if err:
        return res(err, code=400)
    return res("slip reopened", data=data)


@bp.route("/<int:slip_id>/cancel", methods=["POST"])
@require_collect_capable()
def cancel(slip_id):
    data, err = cancel_slip(slip_id, int(get_jwt_identity()), _can_view_all(), get_current_org_id())
    if err == "not_found":
        return res("slip not found", code=404)
    if err == "forbidden":
        return res("forbidden", code=403)
    return res("slip cancelled", data=data)
