"""
Self-contribution service.

All queries use joinedload to eliminate N+1. Member queries are always
scoped to the requesting user; admin queries load across all users.
"""
import os
import uuid
from datetime import datetime, date

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models.self_contribution import SelfContribution, ContributionStatusEnum, PaymentMethodEnum
from ...models.event import Event
from ...models.app_config import AppConfig


# ── Payment info (UPI / bank) ──────────────────────────────────────────────

def get_payment_info() -> dict:
    """Return configured payment details for the contribution form."""
    return {
        "upi": {
            "id":    AppConfig.get("contribution.upi_id"),
            "qrUrl": _qr_url(AppConfig.get("contribution.upi_qr_path")),
        },
        "bank": {
            "bankName":      AppConfig.get("contribution.bank_name"),
            "accountName":   AppConfig.get("contribution.account_name"),
            "accountNumber": AppConfig.get("contribution.account_number"),
            "ifsc":          AppConfig.get("contribution.ifsc"),
            "branch":        AppConfig.get("contribution.bank_branch"),
        },
    }


def _qr_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"/media/{path}"


# ── Screenshot helpers ─────────────────────────────────────────────────────

ALLOWED_SCREENSHOT_MIMES = {"image/jpeg", "image/png", "image/webp"}
_MIME_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _save_screenshot(fileobj, mime_type: str, media_root: str) -> tuple[str, str | None]:
    """Save screenshot to contributions/ subfolder. Returns (rel_path, error)."""
    if mime_type not in ALLOWED_SCREENSHOT_MIMES:
        return "", f"unsupported file type '{mime_type}' — allowed: jpeg, png, webp"

    fileobj.seek(0, os.SEEK_END)
    size = fileobj.tell()
    fileobj.seek(0)
    if size > 10 * 1024 * 1024:
        return "", "file too large — maximum 10 MB allowed"

    ext = _MIME_EXT[mime_type]
    filename = uuid.uuid4().hex + ext
    rel_path = f"contributions/{filename}"
    abs_dir = os.path.join(media_root, "contributions")
    os.makedirs(abs_dir, exist_ok=True)

    abs_path = os.path.join(abs_dir, filename)
    real_root = os.path.realpath(media_root)
    if not os.path.realpath(abs_path).startswith(real_root + os.sep):
        return "", "path traversal detected"

    fileobj.save(abs_path)
    return rel_path, None


def _delete_screenshot(rel_path: str | None, media_root: str) -> None:
    if not rel_path:
        return
    abs_path = os.path.join(media_root, rel_path)
    if os.path.isfile(abs_path):
        os.remove(abs_path)


# ── Member: submit ─────────────────────────────────────────────────────────

def submit_contribution(
    user_id: int,
    amount: float,
    payment_method: str,
    payment_date: str,
    payment_time: str | None,
    note: str | None,
    event_id: int | None,
    fileobj,
    mime_type: str | None,
    media_root: str,
) -> tuple[dict | None, str | None]:
    # Validate method
    try:
        method = PaymentMethodEnum(payment_method)
    except ValueError:
        return None, f"invalid payment_method '{payment_method}'"

    # Validate amount
    try:
        amt = float(amount)
        if amt <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return None, "amount must be a positive number"

    # Validate date
    try:
        pdate = date.fromisoformat(payment_date)
    except (TypeError, ValueError):
        return None, "payment_date must be YYYY-MM-DD"

    # Validate event if provided
    if event_id:
        if not Event.query.get(event_id):
            return None, "event not found"

    # Save screenshot if provided
    screenshot_path = None
    if fileobj and mime_type:
        screenshot_path, err = _save_screenshot(fileobj, mime_type, media_root)
        if err:
            return None, err

    contrib = SelfContribution(
        user_id=user_id,
        event_id=event_id or None,
        amount=amt,
        payment_method=method,
        payment_date=pdate,
        payment_time=payment_time.strip() if payment_time else None,
        note=note.strip() if note else None,
        screenshot_path=screenshot_path or None,
        status=ContributionStatusEnum.pending,
    )
    db.session.add(contrib)
    db.session.commit()

    # Reload with relationships for response
    contrib = (
        SelfContribution.query
        .options(joinedload(SelfContribution.user), joinedload(SelfContribution.event))
        .get(contrib.id)
    )
    return contrib.to_dict(include_screenshot_url=True), None


# ── Member: my list ────────────────────────────────────────────────────────

def list_my_contributions(user_id: int, page: int = 1, per_page: int = 10) -> dict:
    per_page = min(per_page, 50)
    query = (
        SelfContribution.query
        .filter_by(user_id=user_id)
        .options(joinedload(SelfContribution.event), joinedload(SelfContribution.reviewer))
        .order_by(SelfContribution.created_at.desc())
    )
    pag = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return {
        "contributions": [c.to_dict(include_screenshot_url=True) for c in pag.items],
        "page":    pag.page,
        "pages":   pag.pages,
        "total":   pag.total,
        "perPage": pag.per_page,
    }


# ── Member: my stats ──────────────────────────────────────────────────────

def get_my_stats(user_id: int) -> dict:
    row = (
        db.session.query(
            func.coalesce(func.sum(SelfContribution.amount), 0).label("total"),
            func.count(SelfContribution.id).label("count"),
        )
        .filter(
            SelfContribution.user_id == user_id,
            SelfContribution.status == ContributionStatusEnum.approved,
        )
        .one()
    )
    pending_count = (
        SelfContribution.query
        .filter_by(user_id=user_id, status=ContributionStatusEnum.pending)
        .count()
    )
    return {
        "totalApproved":  float(row.total),
        "approvedCount":  row.count,
        "pendingCount":   pending_count,
    }


# ── Admin: list all ────────────────────────────────────────────────────────

def admin_list_contributions(
    status: str | None = None,
    user_id: int | None = None,
    event_id: int | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    per_page = min(per_page, 100)
    query = (
        SelfContribution.query
        .options(
            joinedload(SelfContribution.user),
            joinedload(SelfContribution.event),
            joinedload(SelfContribution.reviewer),
        )
        .order_by(SelfContribution.created_at.desc())
    )
    if status:
        try:
            query = query.filter_by(status=ContributionStatusEnum(status))
        except ValueError:
            pass
    if user_id:
        query = query.filter_by(user_id=user_id)
    if event_id:
        query = query.filter_by(event_id=event_id)

    pag = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return {
        "contributions": [c.to_dict(include_screenshot_url=True) for c in pag.items],
        "page":    pag.page,
        "pages":   pag.pages,
        "total":   pag.total,
        "perPage": pag.per_page,
    }


# ── Admin: approve / reject ────────────────────────────────────────────────

def admin_review_contribution(
    contribution_id: int,
    action: str,           # "approve" or "reject"
    reviewer_id: int,
    admin_note: str | None = None,
) -> tuple[dict | None, str | None]:
    contrib = (
        SelfContribution.query
        .options(
            joinedload(SelfContribution.user),
            joinedload(SelfContribution.event),
            joinedload(SelfContribution.reviewer),
        )
        .get(contribution_id)
    )
    if not contrib:
        return None, "contribution not found"
    if contrib.status != ContributionStatusEnum.pending:
        return None, f"contribution is already {contrib.status.value}"

    if action == "approve":
        contrib.status = ContributionStatusEnum.approved
    elif action == "reject":
        if not admin_note or not admin_note.strip():
            return None, "admin_note is required when rejecting"
        contrib.status = ContributionStatusEnum.rejected
    else:
        return None, "action must be 'approve' or 'reject'"

    contrib.admin_note  = admin_note.strip() if admin_note else None
    contrib.reviewed_by = reviewer_id
    contrib.reviewed_at = datetime.utcnow()
    db.session.commit()
    return contrib.to_dict(include_screenshot_url=True), None


# ── Admin: screenshot path lookup ─────────────────────────────────────────

def get_screenshot_path(contribution_id: int, requesting_user_id: int, is_admin: bool) -> tuple[str | None, str | None]:
    """Return (absolute_path, error). Only owner or admin may access."""
    contrib = SelfContribution.query.get(contribution_id)
    if not contrib:
        return None, "not found"
    if not is_admin and contrib.user_id != requesting_user_id:
        return None, "forbidden"
    if not contrib.screenshot_path:
        return None, "no screenshot"
    return contrib.screenshot_path, None


# ── Admin: aggregate stats ─────────────────────────────────────────────────

def admin_stats() -> dict:
    rows = (
        db.session.query(
            SelfContribution.status,
            func.count(SelfContribution.id).label("cnt"),
            func.coalesce(func.sum(SelfContribution.amount), 0).label("total"),
        )
        .group_by(SelfContribution.status)
        .all()
    )
    stats = {s.value: {"count": 0, "total": 0.0} for s in ContributionStatusEnum}
    for row in rows:
        key = row.status.value if hasattr(row.status, "value") else row.status
        stats[key] = {"count": row.cnt, "total": float(row.total)}
    return stats
