from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, get_jwt
from marshmallow import ValidationError

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import initiate_schema, initiate_payment, get_payment, get_payment_by_receipt_no

bp = Blueprint("payment", __name__)


@bp.route("/initiate", methods=["POST"])
@require_permission("payment.initiate")
def initiate():
    body = request.get_json(silent=True) or {}
    try:
        data = initiate_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    if get_jwt().get("role") == "admin":
        return res("admin accounts cannot collect payments", code=403)

    collector_id = int(get_jwt_identity())
    payment, err = initiate_payment(data, collector_id)
    if err:
        return res(err, code=400)

    method = payment.method.value
    if method == "upi":
        next_url = f"/pay/qr/{payment.id}"
    elif method == "cheque":
        next_url = f"/pay/cheque/{payment.id}"
    else:
        next_url = f"/pay/cash/{payment.id}"

    return res("payment initiated", data={
        "paymentId": payment.id,
        "method": method,
        "amount": str(payment.amount),
        "donorName": payment.donor.name,
        "status": payment.status.value,
        "pledgeId": payment.pledge_id,
        "eventId": payment.event_id,
        "nextUrl": next_url,
    }, code=201)


@bp.route("/receipt/<int:payment_id>", methods=["GET"])
@require_permission("payment.view_receipt")
def receipt(payment_id):
    payment = get_payment(payment_id)
    if not payment:
        return res("payment not found", code=404)
    if payment.status.value == "pending":
        return res("payment not confirmed yet", code=400)
    return res(data=payment.to_dict())


@bp.route("/by-receipt/<receipt_no>", methods=["GET"])
@require_permission("payment.view_receipt")
def by_receipt_no(receipt_no):
    payment = get_payment_by_receipt_no(receipt_no)
    if not payment:
        return res("receipt not found", code=404)
    return res(data=payment.to_dict())
