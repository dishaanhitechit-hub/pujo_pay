from flask import Blueprint, render_template, request, redirect, url_for, abort, make_response, jsonify

from ...models.payment import Payment
from ...models.app_config import AppConfig
from ...utils.pay_token import valid_action_token, valid_receipt_token
from ...services.whatsapp_service import send_whatsapp_text, build_receipt_message
from .service import (
    generate_upi_qr_base64,
    open_qr_page,
    confirm_upi_payment,
    confirm_cash_payment,
    confirm_cheque_payment,
    cancel_payment,
)

bp = Blueprint("qr", __name__)


# ── Link signing ───────────────────────────────────────────────────────────
# Every /pay page needs the signed `t` token issued by the authenticated API.
# The token is checked before the DB lookup so unsigned requests can't probe IDs.

def _token() -> str | None:
    return request.args.get("t") or request.form.get("t")


def _require(payment_id: int, is_valid) -> Payment:
    if not is_valid(_token(), payment_id):
        abort(make_response(render_template(
            "pay/error.html", message="This payment link is invalid or has expired.",
        ), 403))
    return Payment.query.get_or_404(payment_id)


def _receipt_redirect(payment_id: int):
    return redirect(url_for("qr.receipt_page", payment_id=payment_id, t=_token()))


# ── UPI QR page ────────────────────────────────────────────────────────────

@bp.route("/qr/<int:payment_id>", methods=["GET"])
def qr_page(payment_id):
    payment = _require(payment_id, valid_action_token)

    if payment.status.value in ("completed", "confirmed"):
        return _receipt_redirect(payment_id)
    if payment.status.value in ("cancelled", "expired"):
        return render_template("pay/error.html",
                               message=f"This payment has already been {payment.status.value}.")

    event_org_id = payment.event.org_id if payment.event else None
    upi_id = AppConfig.get("upi_id", org_id=event_org_id)
    if not upi_id:
        return render_template("pay/error.html",
                               message="UPI ID not configured. Ask admin to set it via POST /api/admin/config.")

    org_name = AppConfig.get("org_name", org_id=event_org_id, default="Pujo Committee")
    expiry_ts = open_qr_page(payment)
    qr_b64 = generate_upi_qr_base64(upi_id, org_name, str(payment.amount))

    return render_template("pay/qr.html",
                           payment=payment,
                           collector=payment.collector,
                           qr_b64=qr_b64,
                           expiry_ts=expiry_ts,
                           t=_token())


@bp.route("/qr/<int:payment_id>/confirm", methods=["POST"])
def qr_confirm(payment_id):
    payment = _require(payment_id, valid_action_token)
    utr = (request.form.get("utr_number") or "").strip() or None

    ok, msg = confirm_upi_payment(payment, utr)
    if not ok:
        event_org_id = payment.event.org_id if payment.event else None
        upi_id = AppConfig.get("upi_id", org_id=event_org_id, default="")
        org_name = AppConfig.get("org_name", org_id=event_org_id, default="Pujo Committee")
        expiry_ts = (
            int(payment.payment_page_opened_at.timestamp()) + 600
            if payment.payment_page_opened_at else 0
        )
        return render_template("pay/qr.html",
                               payment=payment,
                               collector=payment.collector,
                               qr_b64=generate_upi_qr_base64(upi_id, org_name, str(payment.amount)),
                               expiry_ts=expiry_ts,
                               flash_error=msg,
                               t=_token())

    return _receipt_redirect(payment_id)


@bp.route("/qr/<int:payment_id>/cancel", methods=["POST"])
def qr_cancel(payment_id):
    payment = _require(payment_id, valid_action_token)
    cancel_payment(payment)
    return render_template("pay/cancelled.html", payment=payment)


# ── Cash confirm page ──────────────────────────────────────────────────────

@bp.route("/cash/<int:payment_id>", methods=["GET"])
def cash_page(payment_id):
    payment = _require(payment_id, valid_action_token)

    if payment.status.value in ("completed", "confirmed"):
        return _receipt_redirect(payment_id)
    if payment.status.value in ("cancelled", "expired"):
        return render_template("pay/error.html",
                               message=f"This payment has already been {payment.status.value}.")

    return render_template("pay/cash.html", payment=payment, collector=payment.collector, t=_token())


@bp.route("/cash/<int:payment_id>/confirm", methods=["POST"])
def cash_confirm(payment_id):
    payment = _require(payment_id, valid_action_token)
    ok, msg = confirm_cash_payment(payment)
    if not ok:
        return render_template("pay/cash.html",
                               payment=payment,
                               collector=payment.collector,
                               flash_error=msg,
                               t=_token())
    return _receipt_redirect(payment_id)


@bp.route("/cash/<int:payment_id>/cancel", methods=["POST"])
def cash_cancel(payment_id):
    payment = _require(payment_id, valid_action_token)
    cancel_payment(payment)
    return render_template("pay/cancelled.html", payment=payment)


# ── Cheque confirm page ────────────────────────────────────────────────────

@bp.route("/cheque/<int:payment_id>", methods=["GET"])
def cheque_page(payment_id):
    payment = _require(payment_id, valid_action_token)

    if payment.status.value in ("completed", "confirmed"):
        return _receipt_redirect(payment_id)
    if payment.status.value in ("cancelled", "expired"):
        return render_template("pay/error.html",
                               message=f"This payment has already been {payment.status.value}.")

    return render_template("pay/cheque.html", payment=payment, collector=payment.collector, t=_token())


@bp.route("/cheque/<int:payment_id>/confirm", methods=["POST"])
def cheque_confirm(payment_id):
    payment = _require(payment_id, valid_action_token)
    cheque_number = (request.form.get("cheque_number") or "").strip() or None
    bank_name = (request.form.get("bank_name") or "").strip() or None
    cheque_date = (request.form.get("cheque_date") or "").strip() or None

    ok, msg = confirm_cheque_payment(payment, cheque_number, bank_name, cheque_date)
    if not ok:
        return render_template("pay/cheque.html",
                               payment=payment,
                               collector=payment.collector,
                               flash_error=msg,
                               t=_token())
    return _receipt_redirect(payment_id)


@bp.route("/cheque/<int:payment_id>/cancel", methods=["POST"])
def cheque_cancel(payment_id):
    payment = _require(payment_id, valid_action_token)
    cancel_payment(payment)
    return render_template("pay/cancelled.html", payment=payment)


# ── HTML receipt page ──────────────────────────────────────────────────────
# ?from=dashboard       → admin/manager: Back to Dashboard button, no auto-redirect
# ?from=my-collections  → collector: Back to My Collections button, no auto-redirect
# (no param)            → post-payment collector flow: auto-redirects to /collect after 30s

@bp.route("/receipt/<int:payment_id>", methods=["GET"])
def receipt_page(payment_id):
    payment = _require(payment_id, valid_receipt_token)
    if payment.status.value not in ("completed", "confirmed"):
        return render_template("pay/error.html",
                               message=f"This payment was {payment.status.value} and has no receipt.")
    source = request.args.get("from")
    if source == "dashboard":
        return render_template("pay/receipt_dashboard.html", payment=payment)
    if source == "my-collections":
        return render_template("pay/receipt_my_collections.html", payment=payment)
    return render_template("pay/receipt.html", payment=payment)


@bp.route("/receipt/<int:payment_id>/send-whatsapp", methods=["POST"])
def receipt_send_whatsapp(payment_id):
    """Send receipt via WhatsApp. Authenticated via signed receipt token in body."""
    from flask import current_app
    from ...models.organisation import Organisation

    token = (request.get_json(silent=True) or {}).get("t", "")
    if not valid_receipt_token(token, payment_id):
        return jsonify({"ok": False, "error": "Invalid or expired token"}), 403

    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({"ok": False, "error": "Payment not found"}), 404

    phone = (request.get_json(silent=True) or {}).get("phone") or (
        payment.donor.phone if payment.donor else None
    )
    if not phone:
        return jsonify({"ok": False, "error": "No phone number available"}), 400

    collector_user = payment.collector
    org_name = "Organisation"
    if collector_user and collector_user.org_id:
        org = Organisation.query.get(collector_user.org_id)
        if org:
            org_name = org.name

    site_url = current_app.config.get("SITE_URL") or request.host_url.rstrip("/")
    message = build_receipt_message(payment, org_name, site_url)
    ok, detail = send_whatsapp_text(phone, message)

    if ok:
        return jsonify({"ok": True, "messageId": detail, "phone": phone})
    return jsonify({"ok": False, "error": detail}), 502
