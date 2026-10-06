import re
from decimal import Decimal
from datetime import datetime, timezone, date

from marshmallow import Schema, fields, validate, validates, ValidationError
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models.donor import Donor
from ...models.event import Event, EventStatusEnum
from ...models.payment import Payment, MethodEnum, StatusEnum, COMPLETED_STATUSES
from ...models.user import User, RoleEnum
from ...models.contribution_slip import ContributionSlip, SlipStatusEnum, DonorKindEnum


# ── Schemas ────────────────────────────────────────────────────────────────

class CreateSlipSchema(Schema):
    event_id      = fields.Int(required=True, data_key="eventId")
    donor_kind    = fields.Str(required=True, data_key="donorKind",
                               validate=validate.OneOf(["member", "other"]))
    member_user_id = fields.Int(load_default=None, data_key="memberUserId")
    donor_name    = fields.Str(load_default=None, data_key="donorName", validate=validate.Length(max=120))
    donor_phone   = fields.Str(load_default=None, data_key="donorPhone", validate=validate.Length(max=20))
    donor_address = fields.Str(load_default=None, data_key="donorAddress")
    donor_notes   = fields.Str(load_default=None, data_key="donorNotes")
    donor_type    = fields.Str(load_default=None, data_key="donorType")
    total_amount  = fields.Decimal(required=True, places=2, as_string=False, data_key="totalAmount")
    notes         = fields.Str(load_default=None)

    @validates("total_amount")
    def _v_total(self, value):
        if value <= Decimal("0"):
            raise ValidationError("totalAmount must be greater than zero")


class ManualPaymentSchema(Schema):
    amount        = fields.Decimal(required=True, places=2, as_string=False)
    method        = fields.Str(required=True, validate=validate.OneOf(["cash", "upi", "cheque"]))
    received_date = fields.Date(load_default=None, data_key="receivedDate")
    utr_number    = fields.Str(load_default=None, data_key="utrNumber", validate=validate.Length(max=100))
    cheque_number = fields.Str(load_default=None, data_key="chequeNumber", validate=validate.Length(max=50))
    bank_name     = fields.Str(load_default=None, data_key="bankName", validate=validate.Length(max=100))
    cheque_date   = fields.Date(load_default=None, data_key="chequeDate")

    @validates("amount")
    def _v_amount(self, value):
        if value <= Decimal("0"):
            raise ValidationError("amount must be greater than zero")


create_slip_schema = CreateSlipSchema()
manual_payment_schema = ManualPaymentSchema()


# ── Slip number ──────────────────────────────────────────────────────────────

def _event_abbr(name: str) -> str:
    letters = re.sub(r"[^A-Za-z]", "", name or "").upper()
    return (letters[:3] or "SLP")


_SLIP_LOCK_NAMESPACE = 7301  # arbitrary; pairs with org_id for pg_advisory_xact_lock


def _next_slip_number(org_id: int | None, event: Event | None) -> str:
    """Next number for this prefix, counted across the whole org.

    Slip numbers are unique per org, and different events can share a prefix (same first three
    letters + year, or Bengali names which all fall back to "SLP"), so the sequence is per
    prefix, not per event. Concurrent creates in an org are serialised until the caller commits.
    """
    if db.session.get_bind().dialect.name == "postgresql":
        db.session.execute(
            db.text("SELECT pg_advisory_xact_lock(:ns, :org)"),
            {"ns": _SLIP_LOCK_NAMESPACE, "org": org_id or 0},
        )
    if event is None:
        head = f"GEN{datetime.now().year}-"
    else:
        head = f"{_event_abbr(event.name)}{event.year or datetime.now().year}-"
    rows = (
        db.session.query(ContributionSlip.slip_number)
        .filter(ContributionSlip.org_id == org_id, ContributionSlip.slip_number.like(f"{head}%"))
        .all()
    )
    max_n = 0
    for (num,) in rows:
        if num and num.startswith(head):
            tail = num[len(head):]
            if tail.isdigit():
                max_n = max(max_n, int(tail))
    return f"{head}{max_n + 1:04d}"


# ── Donor resolution ─────────────────────────────────────────────────────────

def _build_donor(data: dict, org_id: int | None) -> tuple[Donor | None, int | None, str | None]:
    """Returns (donor, member_user_id, error)."""
    kind = data["donor_kind"]
    if kind == "member":
        uid = data.get("member_user_id")
        member = User.query.filter_by(id=uid, org_id=org_id).first() if uid else None
        if not member or member.role in (RoleEnum.admin, RoleEnum.super_admin):
            return None, None, "member not found"
        donor = Donor(
            name=member.name, phone=member.phone, address=member.address,
            notes=data.get("donor_notes"), donor_type="Member", org_id=org_id,
        )
        return donor, member.id, None
    # other
    name = (data.get("donor_name") or "").strip()
    if not name:
        return None, None, "donor name is required"
    donor = Donor(
        name=name, phone=data.get("donor_phone"), address=data.get("donor_address"),
        notes=data.get("donor_notes"), donor_type=(data.get("donor_type") or "").strip() or None,
        org_id=org_id,
    )
    return donor, None, None


# ── Slip CRUD ────────────────────────────────────────────────────────────────

def create_slip(data: dict, collector_id: int, org_id: int) -> tuple[ContributionSlip | None, str | None]:
    event = Event.query.get(data["event_id"])
    if not event or event.org_id != org_id:
        return None, "event not found"
    if event.status != EventStatusEnum.published or not event.collection_enabled:
        return None, "event is not currently accepting collections"

    donor, member_user_id, err = _build_donor(data, org_id)
    if err:
        return None, err
    db.session.add(donor)
    db.session.flush()

    slip = ContributionSlip(
        org_id=org_id,
        event_id=event.id,
        collector_id=collector_id,
        slip_number=_next_slip_number(org_id, event),
        donor_kind=DonorKindEnum(data["donor_kind"]),
        donor_id=donor.id,
        member_user_id=member_user_id,
        total_amount=data["total_amount"],
        paid_amount=Decimal("0"),
        status=SlipStatusEnum.open,
        notes=data.get("notes"),
    )
    db.session.add(slip)
    db.session.commit()
    return slip, None


def list_members(org_id: int | None) -> list[dict]:
    """Org members (excluding admins) for the slip 'member' donor picker."""
    members = (
        User.query.filter(
            User.org_id == org_id,
            User.is_active.is_(True),
            User.role.notin_([RoleEnum.admin, RoleEnum.super_admin]),
        )
        .order_by(User.name.asc())
        .all()
    )
    return [{
        "id": m.id, "name": m.name, "phone": m.phone, "address": m.address,
        "memberId": m.member_id, "memberCategory": m.member_category,
    } for m in members]


def list_donor_types(org_id: int | None) -> list[str]:
    rows = (
        db.session.query(Donor.donor_type)
        .filter(Donor.org_id == org_id, Donor.donor_type.isnot(None), Donor.donor_type != "")
        .distinct()
        .all()
    )
    return sorted({r[0] for r in rows if r[0] and r[0] != "Member"})


def _slip_in_scope(slip_id, collector_id, can_view_all, org_id):
    q = ContributionSlip.query.filter_by(id=slip_id)
    if org_id is not None:
        q = q.filter(ContributionSlip.org_id == org_id)
    slip = q.first()
    if not slip:
        return None, "not_found"
    if not can_view_all and slip.collector_id != collector_id:
        return None, "forbidden"
    return slip, None


def get_slip(slip_id, viewer_id, can_view_all, org_id=None):
    slip, err = _slip_in_scope(slip_id, viewer_id, can_view_all, org_id)
    if err:
        return None, err
    return slip.to_dict(with_payments=True), None


def list_slips(org_id, collector_id=None, event_id=None, status=None, search=None,
               page=1, per_page=20):
    q = ContributionSlip.query.options(
        joinedload(ContributionSlip.donor),
        joinedload(ContributionSlip.collector),
        joinedload(ContributionSlip.event),
    ).filter(ContributionSlip.org_id == org_id)
    if collector_id is not None:
        q = q.filter(ContributionSlip.collector_id == collector_id)
    if event_id:
        q = q.filter(ContributionSlip.event_id == event_id)
    if status:
        q = q.filter(ContributionSlip.status == SlipStatusEnum(status))
    if search:
        like = f"%{search}%"
        q = q.join(Donor, ContributionSlip.donor_id == Donor.id).filter(
            db.or_(ContributionSlip.slip_number.ilike(like), Donor.name.ilike(like), Donor.phone.ilike(like))
        )
    q = q.order_by(ContributionSlip.created_at.desc())
    pagination = db.paginate(q, page=page, per_page=per_page, error_out=False)
    return {
        "slips": [s.to_dict() for s in pagination.items],
        "page": pagination.page, "perPage": pagination.per_page,
        "total": pagination.total, "pages": pagination.pages,
    }


def recalc_slip(slip: ContributionSlip) -> None:
    """Recompute paid_amount from completed payments; auto-close when fully paid."""
    total = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).filter(
        Payment.slip_id == slip.id, Payment.status.in_(COMPLETED_STATUSES),
    ).scalar()
    slip.paid_amount = Decimal(str(total))
    if slip.status != SlipStatusEnum.cancelled:
        if slip.paid_amount >= Decimal(str(slip.total_amount)):
            if slip.status != SlipStatusEnum.closed:
                slip.status = SlipStatusEnum.closed
                slip.closed_at = datetime.now(timezone.utc)
        else:
            slip.status = SlipStatusEnum.open
            slip.closed_at = None


def lock_slip_outstanding(slip_id: int) -> tuple[ContributionSlip | None, Decimal]:
    """Row-lock the slip until commit and return it with its live outstanding balance.

    Every path that completes a payment calls this first, so two payments on the same slip
    can't both pass the balance check at the same time and overpay it.
    """
    slip = (
        ContributionSlip.query.filter_by(id=slip_id)
        .populate_existing()
        .with_for_update()
        .first()
    )
    if slip is None:
        return None, Decimal("0")
    paid = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).filter(
        Payment.slip_id == slip_id, Payment.status.in_(COMPLETED_STATUSES),
    ).scalar()
    return slip, Decimal(str(slip.total_amount)) - Decimal(str(paid))


def add_manual_payment(slip_id, data, collector_id, can_view_all, org_id):
    slip, err = _slip_in_scope(slip_id, collector_id, can_view_all, org_id)
    if err:
        return None, err
    slip, outstanding = lock_slip_outstanding(slip.id)
    if slip.status == SlipStatusEnum.cancelled:
        return None, "slip is cancelled"
    amount = Decimal(str(data["amount"]))
    if amount > outstanding:
        return None, f"amount exceeds outstanding balance of ₹{outstanding}"

    p = Payment(
        slip_id=slip.id, donor_id=slip.donor_id, collector_id=collector_id,
        amount=amount, method=MethodEnum(data["method"]), status=StatusEnum.completed,
        event_id=slip.event_id, received_date=data.get("received_date") or date.today(),
        confirmed_at=datetime.now(timezone.utc),
        utr_number=data.get("utr_number"), cheque_number=data.get("cheque_number"),
        bank_name=data.get("bank_name"), cheque_date=data.get("cheque_date"),
    )
    p.assign_receipt_no()
    db.session.add(p)
    db.session.flush()
    recalc_slip(slip)
    db.session.commit()
    return p.to_dict(), None


def close_slip(slip_id, collector_id, can_view_all, org_id):
    slip, err = _slip_in_scope(slip_id, collector_id, can_view_all, org_id)
    if err:
        return None, err
    if slip.status == SlipStatusEnum.cancelled:
        return None, "slip is cancelled"
    slip.status = SlipStatusEnum.closed
    slip.closed_at = datetime.now(timezone.utc)
    db.session.commit()
    return slip.to_dict(), None


def reopen_slip(slip_id, collector_id, can_view_all, org_id):
    slip, err = _slip_in_scope(slip_id, collector_id, can_view_all, org_id)
    if err:
        return None, err
    if slip.status == SlipStatusEnum.cancelled:
        return None, "slip is cancelled"
    recalc_slip(slip)
    if slip.paid_amount < Decimal(str(slip.total_amount)):
        slip.status = SlipStatusEnum.open
        slip.closed_at = None
    db.session.commit()
    return slip.to_dict(), None


def cancel_slip(slip_id, collector_id, can_view_all, org_id):
    slip, err = _slip_in_scope(slip_id, collector_id, can_view_all, org_id)
    if err:
        return None, err
    slip.status = SlipStatusEnum.cancelled
    slip.closed_at = datetime.now(timezone.utc)
    db.session.commit()
    return slip.to_dict(), None
