from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from marshmallow import ValidationError

from ...middleware.permissions import require_super_admin
from ...utils.helpers import res
from .service import (
    create_provision_schema,
    create_provision,
    list_provisions,
    get_provision,
    confirm_payment_and_activate,
    resend_credentials,
)

bp = Blueprint("super_admin", __name__)


@bp.route("/orgs", methods=["POST"])
@require_super_admin()
def create_org_provision():
    """Register a new organisation (pending payment)."""
    body = request.get_json(silent=True) or {}
    try:
        data = create_provision_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    prov = create_provision(data, created_by=int(get_jwt_identity()))
    return res("organisation provision created", data=prov.to_dict(), code=201)


@bp.route("/orgs", methods=["GET"])
@require_super_admin()
def list_org_provisions():
    """List all organisation provisions."""
    provisions = list_provisions()
    return res(data=[p.to_dict() for p in provisions])


@bp.route("/orgs/<int:provision_id>", methods=["GET"])
@require_super_admin()
def get_org_provision(provision_id: int):
    prov = get_provision(provision_id)
    if not prov:
        return res("provision not found", code=404)
    return res(data=prov.to_dict())


@bp.route("/orgs/<int:provision_id>/confirm-payment", methods=["POST"])
@require_super_admin()
def confirm_payment(provision_id: int):
    """Confirm payment → create org + admin → send credentials email."""
    prov = get_provision(provision_id)
    if not prov:
        return res("provision not found", code=404)

    result, extra, _ = confirm_payment_and_activate(prov)
    if result is None:
        return res(extra, code=409)

    return res(
        "payment confirmed — organisation activated and credentials sent via email",
        data=result.to_dict(),
    )


@bp.route("/orgs/<int:provision_id>/resend-credentials", methods=["POST"])
@require_super_admin()
def resend_org_credentials(provision_id: int):
    """Regenerate credentials and resend the welcome email."""
    prov = get_provision(provision_id)
    if not prov:
        return res("provision not found", code=404)

    ok, msg = resend_credentials(prov)
    if not ok:
        return res(msg, code=409)
    return res(msg)
