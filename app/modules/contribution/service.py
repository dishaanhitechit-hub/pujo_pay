"""
Self-contribution service.

All queries use joinedload to eliminate N+1. Member queries are always
scoped to the requesting user; admin queries load across all users.
"""
import os
import uuid
from datetime import datetime, date

from sqlalchemy import exists, func, literal_column, select, union_all
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models.self_contribution import SelfContribution, ContributionStatusEnum, PaymentMethodEnum
from ...models.event import Event
from ...models.app_config import AppConfig
from ...utils.pay_token import make_receipt_token


def _not_self_contribution_slip():
    """Filter for "collected from member" queries: skip slips auto-created for a self-contribution.

    Those payments already appear as the "self" entry once approved; counting them again as
    "collected" doubled member totals.
    """
    from ...models.contribution_slip import ContributionSlip
    return ~exists().where(SelfContribution.slip_id == ContributionSlip.id)


# ── Payment info (UPI / bank) ───────────────────────────────────────────────────────

def get_payment_info(org_id: int | None = None) -> dict:
    """Return configured payment details for the contribution form."""
    return {
        "upi": {
            "id":    AppConfig.get("contribution.upi_id", org_id=org_id),
            "qrUrl": _qr_url(AppConfig.get("contribution.upi_qr_path", org_id=org_id)),
        },
        "bank": {
            "bankName":      AppConfig.get("contribution.bank_name", org_id=org_id),
            "accountName":   AppConfig.get("contribution.account_name", org_id=org_id),
            "accountNumber": AppConfig.get("contribution.account_number", org_id=org_id),
            "ifsc":          AppConfig.get("contribution.ifsc", org_id=org_id),
            "branch":        AppConfig.get("contribution.bank_branch", org_id=org_id),
        },
    }


def _qr_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"/media/{path}"


# ── Screenshot helpers ───────────────────────────────────────────────────────────────────

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


# ── Member: submit ──────────────────────────────────────────────────────────────────────

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
    org_id: int | None = None,
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
    event_obj = None
    if event_id:
        event_obj = Event.query.get(event_id)
        if not event_obj:
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

    # Auto-create a contribution slip + pending payment for all submissions (event or general)
    slip_number = None
    if org_id is not None:
        from ..slip.service import _next_slip_number
        from ...models.contribution_slip import ContributionSlip, DonorKindEnum, SlipStatusEnum
        from ...models.donor import Donor
        from ...models.payment import Payment, MethodEnum, StatusEnum
        from ...models.user import User

        # Same as member slips made by collectors: the member is recorded as the donor, so the
        # payment shows up (and is searchable) in payment lists and donor counts.
        member = User.query.get(user_id)
        donor = Donor(
            name=member.name, phone=member.phone, address=member.address,
            donor_type="Member", org_id=org_id,
        )
        db.session.add(donor)
        db.session.flush()

        slip = ContributionSlip(
            org_id=org_id,
            event_id=event_obj.id if event_obj else None,
            collector_id=user_id,
            slip_number=_next_slip_number(org_id, event_obj),
            donor_kind=DonorKindEnum.member,
            donor_id=donor.id,
            member_user_id=user_id,
            total_amount=amt,
            paid_amount=0,
            status=SlipStatusEnum.open,
            notes=note.strip() if note else None,
        )
        db.session.add(slip)
        db.session.flush()

        # Map contribution payment method to slip payment MethodEnum
        _method_map = {"upi": MethodEnum.upi, "cash": MethodEnum.cash, "bank_transfer": MethodEnum.upi}
        payment_method_enum = _method_map.get(payment_method, MethodEnum.cash)
        pending_payment = Payment(
            slip_id=slip.id,
            donor_id=slip.donor_id,
            collector_id=user_id,
            amount=amt,
            method=payment_method_enum,
            status=StatusEnum.pending,
            event_id=event_obj.id if event_obj else None,
            received_date=pdate,
        )
        db.session.add(pending_payment)

        # Link slip back to the self-contribution
        contrib.slip_id = slip.id
        db.session.commit()
        slip_number = slip.slip_number

    # Reload with relationships for response
    contrib = (
        SelfContribution.query
        .options(
            joinedload(SelfContribution.user),
            joinedload(SelfContribution.event),
            joinedload(SelfContribution.slip),
        )
        .get(contrib.id)
    )
    result = contrib.to_dict(include_screenshot_url=True)
    if slip_number:
        result["slipNumber"] = slip_number
    return result, None


# ── Member: my list ──────────────────────────────────────────────────────────────────────

def _collected_entries_for_member(user_id: int) -> list[dict]:
    """Contributions collected from this member via slips (donor = member)."""
    from ...models.payment import Payment, COMPLETED_STATUSES
    from ...models.contribution_slip import ContributionSlip

    rows = (
        db.session.query(Payment, ContributionSlip)
        .join(ContributionSlip, Payment.slip_id == ContributionSlip.id)
        .options(joinedload(Payment.collector), joinedload(Payment.event))
        .filter(
            ContributionSlip.member_user_id == user_id,
            Payment.status.in_(COMPLETED_STATUSES),
            _not_self_contribution_slip(),
        )
        .all()
    )
    entries = []
    for p, slip in rows:
        entries.append({
            "id":            p.id,
            "source":        "collected",
            "amount":        float(p.amount),
            "paymentMethod": p.method.value if p.method else None,
            "paymentDate":   (p.received_date.isoformat() if p.received_date
                              else (p.created_at.date().isoformat() if p.created_at else None)),
            "status":        "received",
            "note":          None,
            "hasScreenshot": False,
            "slipNumber":    slip.slip_number,
            "receiptNo":     p.receipt_no,
            "event":         {"id": p.event.id, "name": p.event.name} if p.event else None,
            "collector":     {"id": p.collector.id, "name": p.collector.name} if p.collector else None,
            "createdAt":     p.created_at.isoformat() if p.created_at else None,
        })
    return entries


def list_my_contributions(user_id: int, page: int = 1, per_page: int = 10) -> dict:
    per_page = min(per_page, 200)

    self_items = [
        {**c.to_dict(include_screenshot_url=True), "source": "self"}
        for c in (
            SelfContribution.query
            .filter_by(user_id=user_id)
            .options(
                joinedload(SelfContribution.event),
                joinedload(SelfContribution.reviewer),
                joinedload(SelfContribution.slip),
            )
            .all()
        )
    ]
    collected_items = _collected_entries_for_member(user_id)

    merged = self_items + collected_items
    merged.sort(key=lambda x: x.get("createdAt") or "", reverse=True)

    total = len(merged)
    start = (page - 1) * per_page
    items = merged[start:start + per_page]
    return {
        "contributions": items,
        "page":    page,
        "pages":   max(1, (total + per_page - 1) // per_page),
        "total":   total,
        "perPage": per_page,
    }


# ── Member: my stats ────────────────────────────────────────────────────────────────────────

def get_my_stats(user_id: int) -> dict:
    from ...models.payment import Payment, COMPLETED_STATUSES
    from ...models.contribution_slip import ContributionSlip

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

    # Contributions collected from this member via slips (already received money).
    collected = (
        db.session.query(
            func.coalesce(func.sum(Payment.amount), 0).label("total"),
            func.count(Payment.id).label("count"),
        )
        .join(ContributionSlip, Payment.slip_id == ContributionSlip.id)
        .filter(
            ContributionSlip.member_user_id == user_id,
            Payment.status.in_(COMPLETED_STATUSES),
            _not_self_contribution_slip(),
        )
        .one()
    )

    self_approved = float(row.total)
    collected_total = float(collected.total)
    return {
        "totalApproved":  self_approved + collected_total,   # total received (self-approved + collected)
        "approvedCount":  int(row.count) + int(collected.count),
        "pendingCount":   pending_count,
        "selfApproved":   self_approved,
        "collectedTotal": collected_total,
        "collectedCount": int(collected.count),
    }


# ── Admin: list all ──────────────────────────────────────────────────────────────────────

def admin_list_contributions(
    status: str | None = None,
    user_id: int | None = None,
    event_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
    org_id: int | None = None,
) -> dict:
    """Member contributions for admins/finance — self-reported PLUS amounts collected from
    members via slips (donor = member). Collected entries are read-only ('received').

    Both sources are merged, sorted and paginated in SQL; only the current page is loaded.
    """
    from ...models.user import User
    from ...models.payment import Payment, COMPLETED_STATUSES
    from ...models.contribution_slip import ContributionSlip
    per_page = min(per_page, 100)
    like = f"%{search.strip()}%" if search else None

    # ── self-reported ──
    self_sel = (
        select(
            literal_column("'self'").label("source"),
            SelfContribution.id.label("id"),
            SelfContribution.created_at.label("created_at"),
        )
        .select_from(SelfContribution)
        .join(User, SelfContribution.user_id == User.id)
    )
    if org_id is not None:
        self_sel = self_sel.where(User.org_id == org_id)
    if status:
        try:
            self_sel = self_sel.where(SelfContribution.status == ContributionStatusEnum(status))
        except ValueError:
            pass
    if user_id:
        self_sel = self_sel.where(SelfContribution.user_id == user_id)
    if event_id:
        self_sel = self_sel.where(SelfContribution.event_id == event_id)
    if like:
        self_sel = self_sel.where(db.or_(User.name.ilike(like), SelfContribution.note.ilike(like)))
    parts = [self_sel]

    # ── collected from members via slips (not pending/rejected buckets) ──
    if status in (None, "", "approved"):
        coll_sel = (
            select(
                literal_column("'collected'").label("source"),
                Payment.id.label("id"),
                Payment.created_at.label("created_at"),
            )
            .select_from(Payment)
            .join(ContributionSlip, Payment.slip_id == ContributionSlip.id)
            .join(User, ContributionSlip.member_user_id == User.id)
            .where(Payment.status.in_(COMPLETED_STATUSES), _not_self_contribution_slip())
        )
        if org_id is not None:
            coll_sel = coll_sel.where(ContributionSlip.org_id == org_id)
        if event_id:
            coll_sel = coll_sel.where(Payment.event_id == event_id)
        if user_id:
            coll_sel = coll_sel.where(ContributionSlip.member_user_id == user_id)
        if like:
            coll_sel = coll_sel.where(User.name.ilike(like))
        parts.append(coll_sel)

    merged = (union_all(*parts) if len(parts) > 1 else parts[0]).subquery()
    total = db.session.scalar(select(func.count()).select_from(merged)) or 0
    page_rows = db.session.execute(
        select(merged.c.source, merged.c.id)
        .order_by(merged.c.created_at.desc().nulls_last(), merged.c.source, merged.c.id.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
    ).all()

    # Load full rows for this page only.
    self_ids = [row_id for source, row_id in page_rows if source == "self"]
    coll_ids = [row_id for source, row_id in page_rows if source == "collected"]
    by_source: dict[str, dict[int, dict]] = {"self": {}, "collected": {}}
    if self_ids:
        for c in (
            SelfContribution.query
            .filter(SelfContribution.id.in_(self_ids))
            .options(
                joinedload(SelfContribution.user),
                joinedload(SelfContribution.event),
                joinedload(SelfContribution.reviewer),
                joinedload(SelfContribution.slip),
            )
        ):
            by_source["self"][c.id] = {**c.to_dict(include_screenshot_url=True), "source": "self"}
    if coll_ids:
        rows = (
            db.session.query(Payment, ContributionSlip, User)
            .join(ContributionSlip, Payment.slip_id == ContributionSlip.id)
            .join(User, ContributionSlip.member_user_id == User.id)
            .options(joinedload(Payment.collector), joinedload(Payment.event))
            .filter(Payment.id.in_(coll_ids))
        )
        for p, slip, member in rows:
            by_source["collected"][p.id] = {
                "id": p.id, "source": "collected", "status": "received",
                "amount": float(p.amount),
                "paymentMethod": p.method.value if p.method else None,
                "paymentDate": (p.received_date.isoformat() if p.received_date
                                else (p.created_at.date().isoformat() if p.created_at else None)),
                "hasScreenshot": False, "note": None,
                "user": {"id": member.id, "name": member.name},
                "event": {"id": p.event.id, "name": p.event.name} if p.event else None,
                "slipNumber": slip.slip_number, "receiptNo": p.receipt_no,
                "receiptToken": make_receipt_token(p.id),
                "collector": {"id": p.collector.id, "name": p.collector.name} if p.collector else None,
                "createdAt": p.created_at.isoformat() if p.created_at else None,
            }

    return {
        "contributions": [
            by_source[source][row_id] for source, row_id in page_rows if row_id in by_source[source]
        ],
        "page":    page,
        "pages":   max(1, (total + per_page - 1) // per_page),
        "total":   total,
        "perPage": per_page,
    }


# ── Admin: approve / reject ─────────────────────────────────────────────────────────────────

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

    # Complete or cancel the linked slip payment
    if contrib.slip_id:
        from ...models.payment import Payment, StatusEnum
        from ...models.contribution_slip import ContributionSlip, SlipStatusEnum
        from ..slip.service import recalc_slip
        pending = (
            Payment.query
            .filter_by(slip_id=contrib.slip_id, status=StatusEnum.pending)
            .first()
        )
        from datetime import timezone
        if action == "approve":
            if pending:
                pending.status = StatusEnum.completed
                pending.assign_receipt_no()
                pending.confirmed_at = datetime.now(timezone.utc)
                db.session.flush()
                recalc_slip(pending.slip)
        else:
            # The slip exists only for this contribution — cancel it too, or its unpaid
            # amount keeps counting as "pending" in dashboards and budget totals.
            if pending:
                pending.status = StatusEnum.cancelled
                pending.cancelled_at = datetime.now(timezone.utc)
            slip = ContributionSlip.query.get(contrib.slip_id)
            if slip:
                slip.status = SlipStatusEnum.cancelled
                slip.closed_at = datetime.now(timezone.utc)

    db.session.commit()
    return contrib.to_dict(include_screenshot_url=True), None


# ── Admin: screenshot path lookup ─────────────────────────────────────────────────────────────

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


# ── Admin: aggregate stats ────────────────────────────────────────────────────────────────────

def admin_stats(org_id: int | None = None) -> dict:
    from ...models.user import User
    q = db.session.query(
        SelfContribution.status,
        func.count(SelfContribution.id).label("cnt"),
        func.coalesce(func.sum(SelfContribution.amount), 0).label("total"),
    )
    if org_id is not None:
        q = q.join(User, SelfContribution.user_id == User.id).filter(User.org_id == org_id)
    rows = q.group_by(SelfContribution.status).all()
    stats = {s.value: {"count": 0, "total": 0.0} for s in ContributionStatusEnum}
    for row in rows:
        key = row.status.value if hasattr(row.status, "value") else row.status
        stats[key] = {"count": row.cnt, "total": float(row.total)}
    return stats
