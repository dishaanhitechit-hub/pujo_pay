from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, get_jwt
from marshmallow import ValidationError

from ...middleware.permissions import require_permission, has_permission
from ...utils.helpers import res
from .service import (
    create_pledge_schema, pay_installment_schema,
    create_pledge, pay_installment, get_pledge, get_pledge_list, cancel_pledge,
)

bp = Blueprint("pledge", __name__)


@bp.route("/", methods=["POST"])
@require_permission("payment.initiate")
def create():
    if get_jwt().get("role") == "admin":
        return res("admin accounts cannot create pledges", code=403)

    body = request.get_json(silent=True) or {}
    try:
        data = create_pledge_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    collector_id = int(get_jwt_identity())
    pledge = create_pledge(data, collector_id)
    return res("pledge created", data=pledge.to_dict(), code=201)


@bp.route("/<int:pledge_id>/pay", methods=["POST"])
@require_permission("payment.initiate")
def pay(pledge_id):
    if get_jwt().get("role") == "admin":
        return res("admin accounts cannot collect payments", code=403)

    body = request.get_json(silent=True) or {}
    try:
        data = pay_installment_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    collector_id = int(get_jwt_identity())
    payment, err = pay_installment(pledge_id, data, collector_id)
    if err == "forbidden":
        return res("access denied: this pledge belongs to another collector", code=403)
    if err:
        return res(err, code=400)

    method = payment.method.value
    if method == "upi":
        next_url = f"/pay/qr/{payment.id}"
    elif method == "cheque":
        next_url = f"/pay/cheque/{payment.id}"
    else:
        next_url = f"/pay/cash/{payment.id}"

    return res("installment payment initiated", data={
        "paymentId": payment.id,
        "pledgeId": pledge_id,
        "method": method,
        "amount": str(payment.amount),
        "status": payment.status.value,
        "nextUrl": next_url,
    }, code=201)


@bp.route("/", methods=["GET"])
@require_permission("payment.view_receipt")
def list_pledges():
    claims = get_jwt()
    role = claims.get("role")
    viewer_id = int(get_jwt_identity())
    can_view_all = has_permission(role, "dashboard.view")

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("perPage", 20, type=int), 100)
    status = request.args.get("status", "").strip() or None
    # collectorId filter is only honoured for users who can see all pledges
    collector_id = request.args.get("collectorId", type=int) if can_view_all else None

    return res(data=get_pledge_list(
        page=page,
        per_page=per_page,
        status=status,
        viewer_id=viewer_id,
        can_view_all=can_view_all,
        collector_id=collector_id,
    ))


@bp.route("/<int:pledge_id>", methods=["GET"])
@require_permission("payment.view_receipt")
def detail(pledge_id):
    claims = get_jwt()
    role = claims.get("role")
    viewer_id = int(get_jwt_identity())
    can_view_all = has_permission(role, "dashboard.view")

    result, err = get_pledge(pledge_id, viewer_id=viewer_id, can_view_all=can_view_all)
    if err == "not_found":
        return res("pledge not found", code=404)
    if err == "forbidden":
        return res("access denied: this pledge belongs to another collector", code=403)
    return res(data=result)


@bp.route("/<int:pledge_id>/cancel", methods=["POST"])
@require_permission("users.manage")
def cancel(pledge_id):
    pledge, err = cancel_pledge(pledge_id)
    if err:
        return res(err, code=400)
    return res("pledge cancelled", data=pledge.to_dict())
