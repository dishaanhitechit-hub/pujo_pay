import enum

from ..extensions import db


class CommitteeRoleEnum(str, enum.Enum):
    """Assignable committee positions. Order here is the display/seniority order."""
    chairman         = "chairman"
    president        = "president"
    vice_president   = "vice_president"
    secretary        = "secretary"
    junior_secretary = "junior_secretary"
    treasurer        = "treasurer"
    accountant       = "accountant"
    advisory_member  = "advisory_member"
    member           = "member"


# Seniority / display order (lower = more senior)
COMMITTEE_ROLE_ORDER = {r.value: i for i, r in enumerate(CommitteeRoleEnum)}


class ClubYear(db.Model):
    """A club term (free-text label like '2025-26'). One marked current per org."""
    __tablename__ = "club_years"
    __table_args__ = (
        db.UniqueConstraint("org_id", "label", name="uq_club_year_org_label"),
    )

    id         = db.Column(db.Integer, primary_key=True)
    org_id     = db.Column(db.Integer, db.ForeignKey("organisations.id"), nullable=True, index=True)
    label      = db.Column(db.String(50), nullable=False)
    is_current = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "label":     self.label,
            "isCurrent": self.is_current,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class YearRoleAssignment(db.Model):
    """A member's committee role for a club year."""
    __tablename__ = "year_role_assignments"
    __table_args__ = (
        db.UniqueConstraint("club_year_id", "user_id", name="uq_year_role_year_user"),
    )

    id           = db.Column(db.Integer, primary_key=True)
    org_id       = db.Column(db.Integer, db.ForeignKey("organisations.id"), nullable=True, index=True)
    club_year_id = db.Column(db.Integer, db.ForeignKey("club_years.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role         = db.Column(db.Enum(CommitteeRoleEnum, native_enum=False), nullable=False)
    is_public    = db.Column(db.Boolean, nullable=False, default=True)
    created_at   = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self) -> dict:
        role = self.role.value if isinstance(self.role, CommitteeRoleEnum) else self.role
        return {
            "id":         self.id,
            "clubYearId": self.club_year_id,
            "userId":     self.user_id,
            "role":       role,
            "isPublic":   self.is_public,
            "user": {
                "id":    self.user.id,
                "name":  self.user.name,
                "phone": self.user.phone,
            } if self.user else None,
        }


class CommitteeOrdering(db.Model):
    """Manual display order for committee members, per scope (club year or event).

    Covers ALL org members (not only those with a role) so admins can arrange the
    whole list. One row per (scope, scope_id, user). Lower sort_order shows first.
    """
    __tablename__ = "committee_orderings"
    __table_args__ = (
        db.UniqueConstraint("scope", "scope_id", "user_id", name="uq_committee_order_scope_user"),
    )

    id         = db.Column(db.Integer, primary_key=True)
    org_id     = db.Column(db.Integer, db.ForeignKey("organisations.id"), nullable=True, index=True)
    scope      = db.Column(db.String(10), nullable=False)   # 'year' | 'event'
    scope_id   = db.Column(db.Integer, nullable=False, index=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class EventRoleAssignment(db.Model):
    """A member's committee role for a specific event (can_collect lives here)."""
    __tablename__ = "event_role_assignments"
    __table_args__ = (
        db.UniqueConstraint("event_id", "user_id", name="uq_event_role_event_user"),
    )

    id          = db.Column(db.Integer, primary_key=True)
    org_id      = db.Column(db.Integer, db.ForeignKey("organisations.id"), nullable=True, index=True)
    event_id    = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role        = db.Column(db.Enum(CommitteeRoleEnum, native_enum=False), nullable=False)
    can_collect = db.Column(db.Boolean, nullable=False, default=False)
    # Cashier capability for this event: grants the old treasurer/cashier powers
    # (view/approve payments, manage expenses & handovers) scoped to THIS event only.
    can_cashier = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    is_public   = db.Column(db.Boolean, nullable=False, default=True)
    created_at  = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self) -> dict:
        role = self.role.value if isinstance(self.role, CommitteeRoleEnum) else self.role
        return {
            "id":         self.id,
            "eventId":    self.event_id,
            "userId":     self.user_id,
            "role":       role,
            "canCollect": self.can_collect,
            "canCashier": self.can_cashier,
            "isPublic":   self.is_public,
            "user": {
                "id":    self.user.id,
                "name":  self.user.name,
                "phone": self.user.phone,
            } if self.user else None,
        }
