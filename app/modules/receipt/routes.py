from flask import Blueprint, render_template, abort

from .service import get_by_receipt_no

bp = Blueprint("receipt", __name__)


@bp.route("/receipt/<receipt_no>", methods=["GET"])
def serve_receipt(receipt_no):
    payment = get_by_receipt_no(receipt_no.upper())
    if not payment:
        abort(404)
    return render_template("pay/receipt.html", payment=payment)
