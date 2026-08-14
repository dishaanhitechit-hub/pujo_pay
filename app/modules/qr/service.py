import io
import os
import re
import base64
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

import qrcode
from qrcode.image.pil import PilImage

from ...extensions import db
from ...models.payment import Payment, StatusEnum

QR_WINDOW_MINUTES = 10


# ── QR generation ──────────────────────────────────────────────────────────

def generate_upi_qr_base64(upi_id: str, org_name: str, amount: str) -> str:
    """Generate UPI QR in-memory with amount embedded. Returns base64 PNG string."""
    params = urlencode({"pa": upi_id, "pn": org_name, "am": amount, "cu": "INR"})
    upi_link = f"upi://pay?{params}"

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(upi_link)
    qr.make(fit=True)
    img = qr.make_image(image_factory=PilImage)

    buf = io.BytesIO()
    img.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


# ── QR page session ────────────────────────────────────────────────────────

def open_qr_page(payment: Payment) -> int:
    """Set payment_page_opened_at once on first load. Returns expiry Unix timestamp."""
    if payment.payment_page_opened_at is None:
        payment.payment_page_opened_at = datetime.now(timezone.utc)
        db.session.commit()
    expiry = payment.payment_page_opened_at.replace(tzinfo=timezone.utc) + timedelta(minutes=QR_WINDOW_MINUTES)
    return int(expiry.timestamp())


# ── Payment confirm ────────────────────────────────────────────────────────

def confirm_upi_payment(payment: Payment, utr_number: str | None) -> tuple[bool, str]:
    if payment.status != StatusEnum.pending:
        return False, "payment already processed"

    now = datetime.now(timezone.utc)
    opened_at = payment.payment_page_opened_at.replace(tzinfo=timezone.utc)
    if now - opened_at > timedelta(minutes=QR_WINDOW_MINUTES):
        payment.status = StatusEnum.expired
        db.session.commit()
        return False, "session expired"

    payment.utr_number = utr_number or None
    payment.status = StatusEnum.confirmed
    payment.confirmed_at = now
    payment.assign_receipt_no()
    db.session.commit()

    _save_pdf(payment)
    return True, "confirmed"


def confirm_cash_payment(payment: Payment) -> tuple[bool, str]:
    if payment.status != StatusEnum.pending:
        return False, "payment already processed"

    payment.status = StatusEnum.confirmed
    payment.confirmed_at = datetime.now(timezone.utc)
    payment.assign_receipt_no()
    db.session.commit()

    _save_pdf(payment)
    return True, "confirmed"


# ── PDF receipt ────────────────────────────────────────────────────────────

def _save_pdf(payment: Payment) -> None:
    """Render receipt HTML → PDF → save to disk. Silently skips on failure."""
    try:
        from flask import current_app, render_template
        from weasyprint import HTML

        pdf_base = current_app.config["PDF_STORAGE_PATH"]
        collector_dir = _safe_dirname(payment.collector.name)
        dir_path = os.path.join(pdf_base, collector_dir, payment.method.value)
        os.makedirs(dir_path, exist_ok=True)

        timestamp = payment.confirmed_at.strftime("%Y%m%d_%H%M%S")
        filename = f"{payment.receipt_no}_{timestamp}.pdf"
        file_path = os.path.join(dir_path, filename)

        html_string = render_template("pay/receipt.html", payment=payment)
        HTML(string=html_string).write_pdf(file_path)

        payment.receipt_pdf_path = file_path
        db.session.commit()
    except Exception:
        pass


def _safe_dirname(name: str) -> str:
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")
