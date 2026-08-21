import io
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
    return True, "confirmed"


def cancel_payment(payment: Payment) -> tuple[bool, str]:
    if payment.status in (StatusEnum.confirmed, StatusEnum.expired, StatusEnum.cancelled):
        return False, f"cannot cancel — payment is already {payment.status.value}"
    payment.status = StatusEnum.cancelled
    payment.cancelled_at = datetime.now(timezone.utc)
    db.session.commit()
    return True, "cancelled"


def confirm_cash_payment(payment: Payment) -> tuple[bool, str]:
    if payment.status != StatusEnum.pending:
        return False, "payment already processed"

    payment.status = StatusEnum.confirmed
    payment.confirmed_at = datetime.now(timezone.utc)
    payment.assign_receipt_no()
    db.session.commit()
    return True, "confirmed"
