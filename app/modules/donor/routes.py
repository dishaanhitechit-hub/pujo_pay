from flask import Blueprint, request

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import get_donor_list, get_donor_detail

bp = Blueprint("donor", __name__)


@bp.route("/", methods=["GET"])
@require_permission("dashboard.view")
def list_donors():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("perPage", 20, type=int), 100)
    search = request.args.get("search", "").strip() or None
    donor_type = request.args.get("donorType", "").strip() or None

    return res(data=get_donor_list(
        page=page,
        per_page=per_page,
        search=search,
        donor_type=donor_type,
    ))


@bp.route("/<int:donor_id>", methods=["GET"])
@require_permission("dashboard.view")
def donor_detail(donor_id):
    result = get_donor_detail(donor_id)
    if not result:
        return res("donor not found", code=404)
    return res(data=result)
