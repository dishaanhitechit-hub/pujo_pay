"""
Action Plans service.
"""
from datetime import date as date_type

from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models.action_plan import ActionPlan, ActionPlanAssignee, ActionPlanPriorityEnum, ActionPlanStatusEnum
from ...models.user import User


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_plan(plan_id: int) -> ActionPlan | None:
    return (
        ActionPlan.query
        .options(
            joinedload(ActionPlan.creator),
            joinedload(ActionPlan.event),
            joinedload(ActionPlan.meeting),
            joinedload(ActionPlan.assignees).joinedload(ActionPlanAssignee.user),
            joinedload(ActionPlan.assignees).joinedload(ActionPlanAssignee.assigner),
        )
        .get(plan_id)
    )


# ── Admin: Action Plan CRUD ────────────────────────────────────────────────

def list_action_plans(
    status: str | None = None,
    priority: str | None = None,
    event_id: int | None = None,
    meeting_id: int | None = None,
    assignee_id: int | None = None,
    search: str | None = None,
    due_date_from: str | None = None,
    due_date_to: str | None = None,
    page: int = 1,
    per_page: int = 20,
    org_id: int | None = None,
) -> dict:
    q = ActionPlan.query.options(
        joinedload(ActionPlan.creator),
        joinedload(ActionPlan.event),
        joinedload(ActionPlan.meeting),
        joinedload(ActionPlan.assignees).joinedload(ActionPlanAssignee.user),
    )
    if org_id is not None:
        q = q.join(User, ActionPlan.created_by == User.id).filter(User.org_id == org_id)

    if status:    q = q.filter(ActionPlan.status   == status)
    if priority:  q = q.filter(ActionPlan.priority == priority)
    if event_id:  q = q.filter(ActionPlan.event_id == event_id)
    if meeting_id: q = q.filter(ActionPlan.meeting_id == meeting_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(ActionPlan.title.ilike(like))
    if due_date_from:
        try:
            q = q.filter(ActionPlan.due_date >= date_type.fromisoformat(due_date_from))
        except ValueError:
            pass
    if due_date_to:
        try:
            q = q.filter(ActionPlan.due_date <= date_type.fromisoformat(due_date_to))
        except ValueError:
            pass
    if assignee_id:
        q = q.join(ActionPlanAssignee, ActionPlan.id == ActionPlanAssignee.action_plan_id)\
             .filter(ActionPlanAssignee.user_id == assignee_id)

    q = q.order_by(ActionPlan.due_date.asc().nulls_last(), ActionPlan.created_at.desc())
    total = q.count()
    plans = q.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "actionPlans": [p.to_dict() for p in plans],
        "page":        page,
        "perPage":     per_page,
        "total":       total,
        "pages":       max(1, -(-total // per_page)),
    }


def create_action_plan(data: dict, created_by: int) -> tuple[dict | None, str | None]:
    from ...models.event import Event
    from ...models.meeting import Meeting

    if data.get("event_id") and not Event.query.get(data["event_id"]):
        return None, "event not found"
    if data.get("meeting_id") and not Meeting.query.get(data["meeting_id"]):
        return None, "meeting not found"

    plan = ActionPlan(
        title=data["title"].strip(),
        description=(data.get("description") or "").strip() or None,
        event_id=data.get("event_id"),
        meeting_id=data.get("meeting_id"),
        start_date=data.get("start_date"),
        due_date=data.get("due_date"),
        priority=ActionPlanPriorityEnum(data.get("priority", "medium")),
        status=ActionPlanStatusEnum(data.get("status", "not_started")),
        notes=(data.get("notes") or "").strip() or None,
        created_by=created_by,
    )
    db.session.add(plan)
    db.session.commit()
    return _load_plan(plan.id).to_dict(), None


def get_action_plan(plan_id: int) -> dict | None:
    p = _load_plan(plan_id)
    return p.to_dict() if p else None


def update_action_plan(plan_id: int, data: dict) -> tuple[dict | None, str | None]:
    from ...models.event import Event
    from ...models.meeting import Meeting

    plan = ActionPlan.query.get(plan_id)
    if not plan:
        return None, "action plan not found"

    if "title"       in data: plan.title       = data["title"].strip()
    if "description" in data: plan.description = (data["description"] or "").strip() or None
    if "start_date"  in data: plan.start_date  = data["start_date"]
    if "due_date"    in data: plan.due_date     = data["due_date"]
    if "priority"    in data: plan.priority     = ActionPlanPriorityEnum(data["priority"])
    if "status"      in data: plan.status       = ActionPlanStatusEnum(data["status"])
    if "notes"       in data: plan.notes        = (data["notes"] or "").strip() or None
    if "event_id" in data:
        if data["event_id"] and not Event.query.get(data["event_id"]):
            return None, "event not found"
        plan.event_id = data["event_id"]
    if "meeting_id" in data:
        if data["meeting_id"] and not Meeting.query.get(data["meeting_id"]):
            return None, "meeting not found"
        plan.meeting_id = data["meeting_id"]

    db.session.commit()
    return _load_plan(plan_id).to_dict(), None


def delete_action_plan(plan_id: int) -> str | None:
    plan = ActionPlan.query.get(plan_id)
    if not plan:
        return "action plan not found"
    db.session.delete(plan)
    db.session.commit()
    return None


# ── Admin: Assignees ───────────────────────────────────────────────────────

def add_assignees(plan_id: int, user_ids: list[int], assigned_by: int) -> tuple[dict | None, str | None]:
    plan = ActionPlan.query.get(plan_id)
    if not plan:
        return None, "action plan not found"

    existing_users = {u.id for u in User.query.filter(User.id.in_(user_ids)).all()}
    bad = set(user_ids) - existing_users
    if bad:
        return None, f"user ids not found: {sorted(bad)}"

    already = {a.user_id for a in ActionPlanAssignee.query.filter_by(action_plan_id=plan_id).all()}
    added = 0
    for uid in user_ids:
        if uid not in already:
            db.session.add(ActionPlanAssignee(
                action_plan_id=plan_id,
                user_id=uid,
                assigned_by=assigned_by,
            ))
            added += 1

    db.session.commit()
    return _load_plan(plan_id).to_dict(), None


def remove_assignee(plan_id: int, user_id: int) -> str | None:
    row = ActionPlanAssignee.query.filter_by(action_plan_id=plan_id, user_id=user_id).first()
    if not row:
        return "assignee not found"
    db.session.delete(row)
    db.session.commit()
    return None


# ── Member: my action plans ────────────────────────────────────────────────

def list_my_action_plans(
    user_id: int,
    status: str | None = None,
    priority: str | None = None,
    event_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    q = (
        ActionPlan.query
        .join(ActionPlanAssignee, ActionPlan.id == ActionPlanAssignee.action_plan_id)
        .filter(ActionPlanAssignee.user_id == user_id)
        .options(
            joinedload(ActionPlan.creator),
            joinedload(ActionPlan.event),
            joinedload(ActionPlan.meeting),
            joinedload(ActionPlan.assignees).joinedload(ActionPlanAssignee.user),
        )
    )

    if status:   q = q.filter(ActionPlan.status   == status)
    if priority: q = q.filter(ActionPlan.priority == priority)
    if event_id: q = q.filter(ActionPlan.event_id == event_id)
    if search:
        q = q.filter(ActionPlan.title.ilike(f"%{search.strip()}%"))

    q = q.order_by(ActionPlan.due_date.asc().nulls_last(), ActionPlan.created_at.desc())
    total = q.count()
    plans = q.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "actionPlans": [p.to_dict() for p in plans],
        "page":        page,
        "perPage":     per_page,
        "total":       total,
        "pages":       max(1, -(-total // per_page)),
    }
