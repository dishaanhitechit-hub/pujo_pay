import io
import base64
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from urllib.parse import urlencode

import qrcode
from qrcode.image.pil import PilImage

from ...extensions import db
from ...models.payment import Payment, StatusEnum
from ...models.pledge import Pledge, PledgeStatusEnum

QR_WINDOW_MINUTES = 10


# ── QR generation ──────────────────────────────────────────────────────────

def generate_upi_qr_base64(upi_id: str, org_name: str, amount: str) -> str:
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
    if payment.payment_page_opened_at is None:
        payment.payment_page_opened_at = datetime.now(timezone.utc)
        db.session.commit()
    expiry = payment.payment_page_opened_at.replace(tzinfo=timezone.utc) + timedelta(minutes=QR_WINDOW_MINUTES)
    return int(expiry.timestamp())


# ── Pledge sync ────────────────────────────────────────────────────────────

def _sync_pledge(payment: Payment) -> None:
    """Recalculate pledge paid_amount and flip status to complete if fully paid."""
    if not payment.pledge_id:
        return
    pledge = Pledge.query.get(payment.pledge_id)
    if not pledge:
        return

    confirmed_total = db.session.query(
        db.func.coalesce(db.func.sum(Payment.amount), 0)
    ).filter(
        Payment.pledge_id == pledge.id,
        Payment.status == StatusEnum.confirmed,
    ).scalar()

    pledge.paid_amount = Decimal(str(confirmed_total))
    if pledge.paid_amount >= Decimal(str(pledge.total_amount)):
        pledge.status = PledgeStatusEnum.complete


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
    _sync_pledge(payment)
    db.session.commit()
    return True, "confirmed"


def confirm_cash_payment(payment: Payment) -> tuple[bool, str]:
    if payment.status != StatusEnum.pending:
        return False, "payment already processed"

    payment.status = StatusEnum.confirmed
    payment.confirmed_at = datetime.now(timezone.utc)
    payment.assign_receipt_no()
    _sync_pledge(payment)
    db.session.commit()
    return True, "confirmed"


def confirm_cheque_payment(
    payment: Payment,
    cheque_number: str | None,
    bank_name: str | None,
    cheque_date: str | None,
) -> tuple[bool, str]:
    if payment.status != StatusEnum.pending:
        return False, "payment already processed"

    from datetime import date
    parsed_date = None
    if cheque_date:
        try:
            parsed_date = date.fromisoformat(cheque_date)
        except ValueError:
            pass

    payment.cheque_number = cheque_number or None
    payment.bank_name = bank_name or None
    payment.cheque_date = parsed_date
    payment.status = StatusEnum.confirmed
    payment.confirmed_at = datetime.now(timezone.utc)
    payment.assign_receipt_no()
    _sync_pledge(payment)
    db.session.commit()
    return True, "confirmed"


def cancel_payment(payment: Payment) -> tuple[bool, str]:
    if payment.status in (StatusEnum.confirmed, StatusEnum.expired, StatusEnum.cancelled):
        return False, f"cannot cancel — payment is already {payment.status.value}"
    payment.status = StatusEnum.cancelled
    payment.cancelled_at = datetime.now(timezone.utc)
    db.session.commit()
    return True, "cancelled"
