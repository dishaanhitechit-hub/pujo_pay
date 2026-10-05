from datetime import date
from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, get_jwt

from ...middleware.permissions import require_collect_capable, require_permission
from ...middleware.tenant import get_current_org_id
from ...utils.helpers import res
from .service import (
    get_collector_summary, get_handover_receivers, create_handover,
    list_handovers, accept_handover, reject_handover,
)

bp = Blueprint("handover", __name__)


def _is_admin() -> bool:
    claims = get_jwt()
    return claims.get("role") in ("admin", "super_admin")


# ── Collector side ───────────────────────────────────────────────

@bp.route("/my-summary", methods=["GET"])
@require_collect_capable()
def my_summary():
    return res(data=get_collector_summary(get_current_org_id(), int(get_jwt_identity())))


@bp.route("/mine", methods=["GET"])
@require_collect_capable()
def mine():
    return res(data=list_handovers(
        get_current_org_id(),
        collector_id=int(get_jwt_identity()),
        status=request.args.get("status") or None,
        event_id=request.args.get("eventId", type=int),
    ))


@bp.route("/receivers", methods=["GET"])
@require_collect_capable()
def receivers():
    """List users who can receive a handover (admin, cashier, treasurer)."""
    return res(data=get_handover_receivers(get_current_org_id()))


@bp.route("/", methods=["POST"])
@require_collect_capable()
def create():
    body = request.get_json(silent=True) or {}
    event_id = body.get("eventId")
    amount = body.get("amount")
    if not event_id or amount is None:
        return res("eventId and amount are required", code=400)
    hd = body.get("handoverDate")
    try:
        hd_date = date.fromisoformat(hd) if hd else date.today()
    except ValueError:
        return res("invalid handoverDate", code=400)
    result, err = create_handover(
        get_current_org_id(), int(get_jwt_identity()), event_id, amount,
        hd_date, body.get("note"), handover_to_id=body.get("handoverToId"),
    )
    if err:
        code = 404 if "not found" in err else 400
        return res(err, code=code)
    return res("handover submitted", data=result, code=201)


# ── Treasurer / admin side ────────────────────────────────────────

@bp.route("/", methods=["GET"])
@require_permission("handover.manage")
def index():
    user_id = int(get_jwt_identity())
    admin = _is_admin()
    return res(data=list_handovers(
        get_current_org_id(),
        status=request.args.get("status") or None,
        event_id=request.args.get("eventId", type=int),
        recipient_id=user_id,
        is_admin=admin,
    ))


@bp.route("/<int:handover_id>/accept", methods=["POST"])
@require_permission("handover.manage")
def accept(handover_id):
    result, err = accept_handover(
        get_current_org_id(), handover_id, int(get_jwt_identity()), is_admin=_is_admin()
    )
    if err:
        code = 404 if "not found" in err else 400
        return res(err, code=code)
    return res("handover accepted", data=result)


@bp.route("/<int:handover_id>/reject", methods=["POST"])
@require_permission("handover.manage")
def reject(handover_id):
    body = request.get_json(silent=True) or {}
    result, err = reject_handover(
        get_current_org_id(), handover_id, int(get_jwt_identity()),
        body.get("reason"), is_admin=_is_admin()
    )
    if err:
        code = 404 if "not found" in err else 400
        return res(err, code=code)
    return res("handover rejected", data=result)
