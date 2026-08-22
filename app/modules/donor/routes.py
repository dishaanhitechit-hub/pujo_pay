from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, request

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import get_donor_list, get_donor_detail

bp = Blueprint("donor", __name__)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        d = Decimal(value)
        return d if d >= 0 else None
    except InvalidOperation:
        return None


@bp.route("/", methods=["GET"])
@require_permission("dashboard.view")
def list_donors():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("perPage", 20, type=int), 100)
    search = request.args.get("search", "").strip() or None
    donor_type = request.args.get("donorType", "").strip() or None
    date_from = _parse_date(request.args.get("dateFrom"))
    date_to = _parse_date(request.args.get("dateTo"))
    min_amount = _parse_decimal(request.args.get("minAmount"))
    max_amount = _parse_decimal(request.args.get("maxAmount"))

    return res(data=get_donor_list(
        page=page,
        per_page=per_page,
        search=search,
        donor_type=donor_type,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
    ))


@bp.route("/<int:donor_id>", methods=["GET"])
@require_permission("dashboard.view")
def donor_detail(donor_id):
    result = get_donor_detail(donor_id)
    if not result:
        return res("donor not found", code=404)
    return res(data=result)
