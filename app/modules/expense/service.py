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
    purpose      = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    mode         = fields.Str(required=True, validate=validate.OneOf(["cash", "upi", "cheque"]))
    amount       = fields.Decimal(required=True, places=2)
    expense_date = fields.Date(required=True, data_key="expenseDate")
    notes        = fields.Str(load_default=None, allow_none=True)


class UpdateExpenseSchema(Schema):
    purpose      = fields.Str(validate=validate.Length(min=1, max=200))
    mode         = fields.Str(validate=validate.OneOf(["cash", "upi", "cheque"]))
    amount       = fields.Decimal(places=2)
    expense_date = fields.Date(data_key="expenseDate")
    notes        = fields.Str(allow_none=True)


create_expense_schema = CreateExpenseSchema()
update_expense_schema = UpdateExpenseSchema()


# ── Aggregation helper ─────────────────────────────────────────────────────────

def get_expense_totals_for_event(event_id: int) -> Decimal:
    """Return total expense amount for an event (used by dashboard overview)."""
    total = db.session.query(
        func.coalesce(func.sum(Expense.amount), 0)
    ).filter(Expense.event_id == event_id).scalar()
    return Decimal(str(total))


def get_event_expense_summary(event_id: int) -> dict:
    """Whole-event expense summary (unaffected by list pagination/filters)."""
    from ...models.event import Event as EventModel

    event = EventModel.query.get(event_id)
    budget = Decimal(str(event.budget)) if event and event.budget is not None else None

    total = get_expense_totals_for_event(event_id)
    count = Expense.query.filter_by(event_id=event_id).count()

    mode_rows = (
        db.session.query(
            Expense.mode,
            func.coalesce(func.sum(Expense.amount), 0).label("total"),
            func.count(Expense.id).label("cnt"),
        )
        .filter(Expense.event_id == event_id)
        .group_by(Expense.mode)
        .all()
    )

    over_budget_amount = (total - budget) if budget is not None and total > budget else None

    return {
        "totalExpenses":    _fmt(total),
        "expenseCount":     count,
        "modeBreakdown":    [
            {
                "mode":  row.mode.value if hasattr(row.mode, "value") else row.mode,
                "total": _fmt(row.total),
                "count": int(row.cnt),
            }
            for row in mode_rows
        ],
        "budget":           _fmt(budget) if budget is not None else None,
        "budgetNotes":      event.budget_notes if event else None,
        "budgetRemaining":  _fmt(budget - total) if budget is not None else None,
        "overBudget":       (total > budget) if budget is not None else False,
        "overBudgetAmount": _fmt(over_budget_amount) if over_budget_amount is not None else None,
    }


# ── CRUD operations ────────────────────────────────────────────────────────────

def get_expenses(
    event_id: int,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
    mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_amount: str | None = None,
    max_amount: str | None = None,
) -> dict:
    query = Expense.query.filter_by(event_id=event_id)

    if search:
        like = f"%{search}%"
        query = query.filter(Expense.purpose.ilike(like) | Expense.notes.ilike(like))

    if mode in ("cash", "upi", "cheque"):
        query = query.filter(Expense.mode == MethodEnum(mode))

    if date_from:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d").date()
            query = query.filter(Expense.expense_date >= df)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").date()
            query = query.filter(Expense.expense_date <= dt)
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


def create_expense(event_id: int, data: dict, created_by: int) -> Expense:
    expense = Expense(
        event_id=event_id,
        purpose=data["purpose"].strip(),
        mode=MethodEnum(data["mode"]),
        amount=data["amount"],
        expense_date=data["expense_date"],
        notes=data.get("notes") or None,
        created_by=created_by,
    )
    db.session.add(expense)
    db.session.commit()
    return expense


def update_expense(expense_id: int, event_id: int, data: dict) -> tuple:
    expense = Expense.query.filter_by(id=expense_id, event_id=event_id).first()
    if not expense:
        return None, "expense not found"

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


def delete_expense(expense_id: int, event_id: int) -> bool:
    expense = Expense.query.filter_by(id=expense_id, event_id=event_id).first()
    if not expense:
        return False
    db.session.delete(expense)
    db.session.commit()
    return True
