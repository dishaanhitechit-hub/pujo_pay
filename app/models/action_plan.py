import enum
from ..extensions import db


class ActionPlanPriorityEnum(str, enum.Enum):
    low    = "low"
    medium = "medium"
    high   = "high"
    urgent = "urgent"


class ActionPlanStatusEnum(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed   = "completed"
    on_hold     = "on_hold"
    cancelled   = "cancelled"


class ActionPlan(db.Model):
    __tablename__ = "action_plans"

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_id    = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=True, index=True)
    meeting_id  = db.Column(db.Integer, db.ForeignKey("meetings.id"), nullable=True, index=True)
    start_date  = db.Column(db.Date, nullable=True)
    due_date    = db.Column(db.Date, nullable=True)
    priority    = db.Column(
        db.Enum(ActionPlanPriorityEnum, native_enum=False, create_constraint=False),
        nullable=False,
        default=ActionPlanPriorityEnum.medium,
    )
    status = db.Column(
        db.Enum(ActionPlanStatusEnum, native_enum=False, create_constraint=False),
        nullable=False,
        default=ActionPlanStatusEnum.not_started,
    )
    notes      = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    event    = db.relationship("Event", foreign_keys=[event_id])
    meeting  = db.relationship("Meeting", foreign_keys=[meeting_id])
    creator  = db.relationship("User", foreign_keys=[created_by])
    assignees = db.relationship(
        "ActionPlanAssignee",
        back_populates="action_plan",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_assignees: bool = True) -> dict:
        d = {
            "id":          self.id,
            "title":       self.title,
            "description": self.description,
            "event":   {"id": self.event.id,   "name": self.event.name}    if self.event   else None,
            "meeting": {"id": self.meeting.id, "title": self.meeting.title} if self.meeting else None,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "dueDate":   self.due_date.isoformat()   if self.due_date   else None,
            "priority": self.priority.value if self.priority else None,
            "status":   self.status.value   if self.status   else None,
            "notes":     self.notes,
            "createdBy": {"id": self.creator.id, "name": self.creator.name} if self.creator else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_assignees:
            d["assignees"] = [a.to_dict() for a in self.assignees]
        return d


class ActionPlanAssignee(db.Model):
    __tablename__ = "action_plan_assignees"

    id             = db.Column(db.Integer, primary_key=True)
    action_plan_id = db.Column(db.Integer, db.ForeignKey("action_plans.id"), nullable=False, index=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_at    = db.Column(db.DateTime, server_default=db.func.now())
    assigned_by    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("action_plan_id", "user_id", name="uq_action_plan_assignee"),
    )

    action_plan = db.relationship("ActionPlan", back_populates="assignees")
    user        = db.relationship("User", foreign_keys=[user_id])
    assigner    = db.relationship("User", foreign_keys=[assigned_by])

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "actionPlanId": self.action_plan_id,
            "user": {
                "id":   self.user.id,
                "name": self.user.name,
                "role": self.user.role.value if self.user and self.user.role else None,
            } if self.user else None,
            "assignedAt": self.assigned_at.isoformat() if self.assigned_at else None,
            "assignedBy": {
                "id": self.assigner.id, "name": self.assigner.name,
            } if self.assigner else None,
        }
