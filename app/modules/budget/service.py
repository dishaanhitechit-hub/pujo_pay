from decimal import Decimal

from marshmallow import Schema, fields, validate
from sqlalchemy import func

from ...extensions import db
from ...models.budget_category import BudgetCategory


def _fmt(value) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateBudgetCategorySchema(Schema):
    event_id       = fields.Int(required=True, data_key="eventId")
    title          = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    planned_amount = fields.Decimal(required=True, places=2, data_key="plannedAmount")
    notes          = fields.Str(load_default=None, allow_none=True)
    sort_order     = fields.Int(load_default=0, data_key="sortOrder")


class UpdateBudgetCategorySchema(Schema):
    title          = fields.Str(validate=validate.Length(min=1, max=200))
    planned_amount = fields.Decimal(places=2, data_key="plannedAmount")
    notes          = fields.Str(allow_none=True)
    sort_order     = fields.Int(data_key="sortOrder")


class ReorderSchema(Schema):
    ids = fields.List(fields.Int(), required=True)


create_budget_category_schema = CreateBudgetCategorySchema()
update_budget_category_schema = UpdateBudgetCategorySchema()
reorder_schema                = ReorderSchema()


# ── Queries ────────────────────────────────────────────────────────────────────

def get_categories(
    event_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    query = BudgetCategory.query

    if event_id:
        query = query.filter_by(event_id=event_id)

    if search:
        like = f"%{search}%"
        query = query.filter(BudgetCategory.title.ilike(like))

    query = query.order_by(BudgetCategory.event_id, BudgetCategory.sort_order, BudgetCategory.id)
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)

    return {
        "categories": [c.to_dict() for c in pagination.items],
        "page":    pagination.page,
        "perPage": pagination.per_page,
        "total":   pagination.total,
        "pages":   pagination.pages,
    }


def get_budget_report(event_id: int) -> dict:
    """Budget vs actual for every category in an event — single aggregation pass."""
    from ...models.expense import Expense

    categories = (
        BudgetCategory.query
        .filter_by(event_id=event_id)
        .order_by(BudgetCategory.sort_order, BudgetCategory.id)
        .all()
    )

    # One grouped query: actual expenses by budget_category_id for this event
    expense_rows = (
        db.session.query(
            Expense.budget_category_id,
            func.coalesce(func.sum(Expense.amount), 0).label("total"),
            func.count(Expense.id).label("cnt"),
        )
        .filter(Expense.event_id == event_id)
        .group_by(Expense.budget_category_id)
        .all()
    )

    exp_map: dict[int | None, dict] = {
        row.budget_category_id: {"total": Decimal(str(row.total)), "count": int(row.cnt)}
        for row in expense_rows
    }

    unallocated = exp_map.get(None, {"total": Decimal("0"), "count": 0})

    total_planned = Decimal("0")
    total_allocated_actual = Decimal("0")
    category_rows = []

    for cat in categories:
        actual = exp_map.get(cat.id, {"total": Decimal("0"), "count": 0})
        planned = Decimal(str(cat.planned_amount))
        remaining = planned - actual["total"]
        total_planned += planned
        total_allocated_actual += actual["total"]
        util = round(float(actual["total"] / planned * 100), 1) if planned > 0 else 0.0
        category_rows.append({
            "id":              cat.id,
            "title":           cat.title,
            "sortOrder":       cat.sort_order,
            "plannedAmount":   _fmt(planned),
            "actualExpenses":  _fmt(actual["total"]),
            "expenseCount":    actual["count"],
            "remaining":       _fmt(remaining),
            "overBudget":      remaining < 0,
            "utilizationPct":  util,
        })

    total_actual = total_allocated_actual + unallocated["total"]
    total_remaining = total_planned - total_actual
    total_util = round(float(total_actual / total_planned * 100), 1) if total_planned > 0 else 0.0

    return {
        "categories":   category_rows,
        "unallocated": {
            "actualExpenses": _fmt(unallocated["total"]),
            "expenseCount":   unallocated["count"],
        },
        "totals": {
            "totalPlanned":   _fmt(total_planned),
            "totalActual":    _fmt(total_actual),
            "remaining":      _fmt(total_remaining),
            "overBudget":     total_actual > total_planned,
            "utilizationPct": total_util,
        },
    }


# ── CRUD ───────────────────────────────────────────────────────────────────────

def create_category(data: dict, created_by: int) -> BudgetCategory:
    # Append after existing categories for this event
    max_sort = (
        db.session.query(func.coalesce(func.max(BudgetCategory.sort_order), -1))
        .filter_by(event_id=data["event_id"])
        .scalar()
    )
    cat = BudgetCategory(
        event_id       = data["event_id"],
        title          = data["title"].strip(),
        planned_amount = data["planned_amount"],
        notes          = data.get("notes") or None,
        sort_order     = data.get("sort_order") if data.get("sort_order") is not None else int(max_sort) + 1,
        created_by     = created_by,
    )
    db.session.add(cat)
    db.session.commit()
    return cat


def update_category(cat_id: int, data: dict) -> tuple:
    cat = BudgetCategory.query.get(cat_id)
    if not cat:
        return None, "budget category not found"
    if "title" in data:
        cat.title = data["title"].strip()
    if "planned_amount" in data:
        cat.planned_amount = data["planned_amount"]
    if "notes" in data:
        cat.notes = data.get("notes") or None
    if "sort_order" in data:
        cat.sort_order = data["sort_order"]
    db.session.commit()
    return cat, None


def delete_category(cat_id: int) -> bool:
    cat = BudgetCategory.query.get(cat_id)
    if not cat:
        return False
    db.session.delete(cat)
    db.session.commit()
    return True


def reorder_categories(event_id: int, ids: list[int]) -> bool:
    """Assign sequential sort_order values to the given ids (must all belong to event)."""
    cats = BudgetCategory.query.filter(
        BudgetCategory.id.in_(ids),
        BudgetCategory.event_id == event_id,
    ).all()
    if len(cats) != len(ids):
        return False
    cat_map = {c.id: c for c in cats}
    for pos, cat_id in enumerate(ids):
        if cat_id in cat_map:
            cat_map[cat_id].sort_order = pos
    db.session.commit()
    return True
