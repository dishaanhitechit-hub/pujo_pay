import os
from ...models.payment import Payment


def get_by_receipt_no(receipt_no: str) -> Payment | None:
    return Payment.query.filter_by(receipt_no=receipt_no).first()


def pdf_path_valid(payment: Payment) -> bool:
    return bool(payment.receipt_pdf_path and os.path.exists(payment.receipt_pdf_path))
