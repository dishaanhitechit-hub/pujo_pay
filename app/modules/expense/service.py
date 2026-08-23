from datetime import datetime
from decimal import Decimal

from marshmallow import Schema, fields, validate
from sqlalchemy import func

from ...extensions import db
from ...models.expense import Expense
from ...models.payment import MethodEnum


def _fmt(value) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateExpenseSchema(Schema):
    event_id           = fields.Int(required=True, data_key="eventId")
    budget_category_id = fields.Int(load_default=None, allow_none=True, data_key="budgetCategoryId")
    purpose            = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    mode               = fields.Str(required=True, validate=validate.OneOf(["cash", "upi", "cheque"]))
    amount             = fields.Decimal(required=True, places=2)
    expense_date       = fields.Date(required=True, data_key="expenseDate")
    notes              = fields.Str(load_default=None, allow_none=True)


class UpdateExpenseSchema(Schema):
    budget_category_id = fields.Int(allow_none=True, data_key="budgetCategoryId")
    purpose            = fields.Str(validate=validate.Length(min=1, max=200))
    mode               = fields.Str(validate=validate.OneOf(["cash", "upi", "cheque"]))
    amount             = fields.Decimal(places=2)
    expense_date       = fields.Date(data_key="expenseDate")
    notes              = fields.Str(allow_none=True)


create_expense_schema = CreateExpenseSchema()
update_expense_schema = UpdateExpenseSchema()


# ── Global summary ─────────────────────────────────────────────────────────────

def get_expense_summary(
    event_id: int | None = None,
    budget_category_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Aggregate summary respecting current filters (event + category + date)."""
    base = Expense.query

    if event_id:
        base = base.filter(Expense.event_id == event_id)
    if budget_category_id is not None:
        if budget_category_id == 0:
            base = base.filter(Expense.budget_category_id.is_(None))
        else:
            base = base.filter(Expense.budget_category_id == budget_category_id)
    if date_from:
        try:
            base = base.filter(Expense.expense_date >= datetime.strptime(date_from, "%Y-%m-%d").date())
        except ValueError:
            pass
    if date_to:
        try:
            base = base.filter(Expense.expense_date <= datetime.strptime(date_to, "%Y-%m-%d").date())
        except ValueError:
            pass

    total = Decimal(str(base.with_entities(func.coalesce(func.sum(Expense.amount), 0)).scalar()))
    count = base.count()

    mode_rows = (
        db.session.query(
            Expense.mode,
            func.coalesce(func.sum(Expense.amount), 0).label("total"),
            func.count(Expense.id).label("cnt"),
        )
        .filter(*_base_filters(event_id, budget_category_id, date_from, date_to))
        .group_by(Expense.mode)
        .all()
    )

    return {
        "totalExpenses": _fmt(total),
        "expenseCount":  count,
        "modeBreakdown": [
            {
                "mode":  row.mode.value if hasattr(row.mode, "value") else row.mode,
                "total": _fmt(row.total),
                "count": int(row.cnt),
            }
            for row in mode_rows
        ],
    }


def _base_filters(event_id, budget_category_id, date_from, date_to) -> list:
    filters = []
    if event_id:
        filters.append(Expense.event_id == event_id)
    if budget_category_id is not None:
        if budget_category_id == 0:
            filters.append(Expense.budget_category_id.is_(None))
        else:
            filters.append(Expense.budget_category_id == budget_category_id)
    if date_from:
        try:
            filters.append(Expense.expense_date >= datetime.strptime(date_from, "%Y-%m-%d").date())
        except ValueError:
            pass
    if date_to:
        try:
            filters.append(Expense.expense_date <= datetime.strptime(date_to, "%Y-%m-%d").date())
        except ValueError:
            pass
    return filters


# ── List ───────────────────────────────────────────────────────────────────────

def get_expenses(
    event_id: int | None = None,
    budget_category_id: int | None = None,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
    mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_amount: str | None = None,
    max_amount: str | None = None,
) -> dict:
    query = Expense.query

    if event_id:
        query = query.filter(Expense.event_id == event_id)

    if budget_category_id is not None:
        if budget_category_id == 0:
            query = query.filter(Expense.budget_category_id.is_(None))
        else:
            query = query.filter(Expense.budget_category_id == budget_category_id)

    if search:
        like = f"%{search}%"
        query = query.filter(Expense.purpose.ilike(like) | Expense.notes.ilike(like))

    if mode in ("cash", "upi", "cheque"):
        query = query.filter(Expense.mode == MethodEnum(mode))

    if date_from:
        try:
            query = query.filter(Expense.expense_date >= datetime.strptime(date_from, "%Y-%m-%d").date())
        except ValueError:
            pass

    if date_to:
        try:
            query = query.filter(Expense.expense_date <= datetime.strptime(date_to, "%Y-%m-%d").date())
        except ValueError:
            pass

    if min_amount:
        try:
            query = query.filter(Expense.amount >= Decimal(str(min_amount)))
        except Exception:
            pass

    if max_amount:
        try:
            query = query.filter(Expense.amount <= Decimal(str(max_amount)))
        except Exception:
            pass

    query = query.order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)

    return {
        "expenses": [e.to_dict() for e in pagination.items],
        "page":    pagination.page,
        "perPage": pagination.per_page,
        "total":   pagination.total,
        "pages":   pagination.pages,
    }


# ── CRUD ───────────────────────────────────────────────────────────────────────

def create_expense(data: dict, created_by: int) -> Expense:
    expense = Expense(
        event_id           = data["event_id"],
        budget_category_id = data.get("budget_category_id"),
        purpose            = data["purpose"].strip(),
        mode               = MethodEnum(data["mode"]),
        amount             = data["amount"],
        expense_date       = data["expense_date"],
        notes              = data.get("notes") or None,
        created_by         = created_by,
    )
    db.session.add(expense)
    db.session.commit()
    return expense


def update_expense(expense_id: int, data: dict) -> tuple:
    expense = Expense.query.get(expense_id)
    if not expense:
        return None, "expense not found"

    if "budget_category_id" in data:
        expense.budget_category_id = data["budget_category_id"]
    if "purpose" in data:
        expense.purpose = data["purpose"].strip()
    if "mode" in data:
        expense.mode = MethodEnum(data["mode"])
    if "amount" in data:
        expense.amount = data["amount"]
    if "expense_date" in data:
        expense.expense_date = data["expense_date"]
    if "notes" in data:
        expense.notes = data.get("notes") or None

    db.session.commit()
    return expense, None


def delete_expense(expense_id: int) -> bool:
    expense = Expense.query.get(expense_id)
    if not expense:
        return False
    db.session.delete(expense)
    db.session.commit()
    return True


# ── Per-event total (used by dashboard) ───────────────────────────────────────

def get_expense_totals_for_events(event_ids: list[int]) -> dict[int, Decimal]:
    """Single query: {event_id: total_expenses}."""
    if not event_ids:
        return {}
    rows = (
        db.session.query(
            Expense.event_id,
            func.coalesce(func.sum(Expense.amount), 0).label("total"),
        )
        .filter(Expense.event_id.in_(event_ids))
        .group_by(Expense.event_id)
        .all()
    )
    return {row.event_id: Decimal(str(row.total)) for row in rows}


def get_event_expense_total(event_id: int) -> Decimal:
    total = (
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(Expense.event_id == event_id)
        .scalar()
    )
    return Decimal(str(total))
