from flask import Blueprint, send_file, abort

from .service import get_by_receipt_no, pdf_path_valid

bp = Blueprint("receipt", __name__)


@bp.route("/receipt/<receipt_no>", methods=["GET"])
def serve_pdf(receipt_no):
    payment = get_by_receipt_no(receipt_no.upper())
    if not payment:
        abort(404)
    if not pdf_path_valid(payment):
        abort(404)
    return send_file(
        payment.receipt_pdf_path,
        mimetype="application/pdf",
        download_name=f"{receipt_no}.pdf",
        as_attachment=False,
    )
