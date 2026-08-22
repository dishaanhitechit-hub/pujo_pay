from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import get_summary, get_payments

bp = Blueprint("collector", __name__)


@bp.route("/summary", methods=["GET"])
@require_permission("collector.view_own")
def summary():
    collector_id = int(get_jwt_identity())
    data = get_summary(collector_id)
    return res(data=data)


@bp.route("/payments", methods=["GET"])
@require_permission("collector.view_own")
def payments():
    collector_id = int(get_jwt_identity())

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("perPage", 20, type=int), 100)
    method = request.args.get("method")
    date = request.args.get("date")
    donor_type = request.args.get("donorType")

    data = get_payments(
        collector_id=collector_id,
        page=page,
        per_page=per_page,
        method=method,
        date=date,
        donor_type=donor_type,
    )
    return res(data=data)
