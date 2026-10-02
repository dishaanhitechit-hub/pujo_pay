import io
import base64
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from urllib.parse import urlencode

import qrcode
from qrcode.image.pil import PilImage

from ...extensions import db
from ...models.payment import Payment, StatusEnum, COMPLETED_STATUSES
from ...models.contribution_slip import ContributionSlip

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


# ── Slip sync ──────────────────────────────────────────────────────────────

def _sync_pledge(payment: Payment) -> None:
    """Recalculate the slip's paid_amount and auto-close it when fully paid."""
    if not payment.slip_id:
        return
    slip = ContributionSlip.query.get(payment.slip_id)
    if not slip:
        return
    from ..slip.service import recalc_slip
    recalc_slip(slip)


# ── Payment confirm ────────────────────────────────────────────────────────

def confirm_upi_payment(payment: Payment, utr_number: str | None) -> tuple[bool, str]:
    if payment.status != StatusEnum.pending:
        return False, "payment already processed"

    now = datetime.now(timezone.utc)
    # payment_page_opened_at is only set when the web QR page is visited.
    # Mobile app confirmations skip the expiry window check.
    if payment.payment_page_opened_at is not None:
        opened_at = payment.payment_page_opened_at.replace(tzinfo=timezone.utc)
        if now - opened_at > timedelta(minutes=QR_WINDOW_MINUTES):
            payment.status = StatusEnum.expired
            db.session.commit()
            return False, "session expired"

    payment.utr_number = utr_number or None
    payment.status = StatusEnum.completed
    payment.confirmed_at = now
    payment.assign_receipt_no()
    _sync_pledge(payment)
    db.session.commit()
    return True, "completed"


def confirm_cash_payment(payment: Payment) -> tuple[bool, str]:
    if payment.status != StatusEnum.pending:
        return False, "payment already processed"

    payment.status = StatusEnum.completed
    payment.confirmed_at = datetime.now(timezone.utc)
    payment.assign_receipt_no()
    _sync_pledge(payment)
    db.session.commit()
    return True, "completed"


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
    payment.status = StatusEnum.completed
    payment.confirmed_at = datetime.now(timezone.utc)
    payment.assign_receipt_no()
    _sync_pledge(payment)
    db.session.commit()
    return True, "completed"


def cancel_payment(payment: Payment) -> tuple[bool, str]:
    if payment.status in (*COMPLETED_STATUSES, StatusEnum.expired, StatusEnum.cancelled):
        return False, f"cannot cancel — payment is already {payment.status.value}"
    payment.status = StatusEnum.cancelled
    payment.cancelled_at = datetime.now(timezone.utc)
    db.session.commit()
    return True, "cancelled"
