from flask import Blueprint, render_template, request, redirect, url_for, abort

from ...models.payment import Payment
from ...models.app_config import AppConfig
from .service import (
    generate_upi_qr_base64,
    open_qr_page,
    confirm_upi_payment,
    confirm_cash_payment,
    cancel_payment,
)

bp = Blueprint("qr", __name__)


# ── UPI QR page ────────────────────────────────────────────────────────────

@bp.route("/qr/<int:payment_id>", methods=["GET"])
def qr_page(payment_id):
    payment = Payment.query.get_or_404(payment_id)

    if payment.status.value == "confirmed":
        return redirect(url_for("qr.receipt_page", payment_id=payment_id))
    if payment.status.value in ("cancelled", "expired"):
        return render_template("pay/error.html",
                               message=f"This payment has already been {payment.status.value}.")

    upi_id = AppConfig.get("upi_id")
    if not upi_id:
        return render_template("pay/error.html",
                               message="UPI ID not configured. Ask admin to set it via POST /api/admin/config.")

    org_name = AppConfig.get("org_name", "Pujo Committee")
    expiry_ts = open_qr_page(payment)
    qr_b64 = generate_upi_qr_base64(upi_id, org_name, str(payment.amount))

    return render_template("pay/qr.html",
                           payment=payment,
                           collector=payment.collector,
                           qr_b64=qr_b64,
                           expiry_ts=expiry_ts)


@bp.route("/qr/<int:payment_id>/confirm", methods=["POST"])
def qr_confirm(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    utr = (request.form.get("utr_number") or "").strip() or None

    ok, msg = confirm_upi_payment(payment, utr)
    if not ok:
        upi_id = AppConfig.get("upi_id", "")
        org_name = AppConfig.get("org_name", "Pujo Committee")
        expiry_ts = (
            int(payment.payment_page_opened_at.timestamp()) + 600
            if payment.payment_page_opened_at else 0
        )
        return render_template("pay/qr.html",
                               payment=payment,
                               collector=payment.collector,
                               qr_b64=generate_upi_qr_base64(upi_id, org_name, str(payment.amount)),
                               expiry_ts=expiry_ts,
                               flash_error=msg)

    return redirect(url_for("qr.receipt_page", payment_id=payment_id))


@bp.route("/qr/<int:payment_id>/cancel", methods=["POST"])
def qr_cancel(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    cancel_payment(payment)
    return render_template("pay/cancelled.html", payment=payment)


# ── Cash confirm page ──────────────────────────────────────────────────────

@bp.route("/cash/<int:payment_id>", methods=["GET"])
def cash_page(payment_id):
    payment = Payment.query.get_or_404(payment_id)

    if payment.status.value == "confirmed":
        return redirect(url_for("qr.receipt_page", payment_id=payment_id))
    if payment.status.value in ("cancelled", "expired"):
        return render_template("pay/error.html",
                               message=f"This payment has already been {payment.status.value}.")

    return render_template("pay/cash.html", payment=payment, collector=payment.collector)


@bp.route("/cash/<int:payment_id>/confirm", methods=["POST"])
def cash_confirm(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    ok, msg = confirm_cash_payment(payment)
    if not ok:
        return render_template("pay/cash.html",
                               payment=payment,
                               collector=payment.collector,
                               flash_error=msg)
    return redirect(url_for("qr.receipt_page", payment_id=payment_id))


@bp.route("/cash/<int:payment_id>/cancel", methods=["POST"])
def cash_cancel(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    cancel_payment(payment)
    return render_template("pay/cancelled.html", payment=payment)


# ── HTML receipt page ──────────────────────────────────────────────────────
# ?from=dashboard  → shows Back to Dashboard button, no auto-redirect
# (no param)       → collector mode: auto-redirects to /collect after 30s

@bp.route("/receipt/<int:payment_id>", methods=["GET"])
def receipt_page(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if request.args.get("from") == "dashboard":
        return render_template("pay/receipt_dashboard.html", payment=payment)
    return render_template("pay/receipt.html", payment=payment)
