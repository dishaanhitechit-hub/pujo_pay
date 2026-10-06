from sqlalchemy import func
from sqlalchemy.orm import joinedload
from ...extensions import db
from ...models.event import Event, EventStatusEnum
from ...models.announcement import Announcement
from ...models.committee_member import CommitteeMember
from ...models.media_file import MediaFile, MediaCategoryEnum
from ...models.donor import Donor


# ── URL helpers ────────────────────────────────────────────────────────────

def _media_url(path: str | None) -> str | None:
    """Convert relative media storage path to a public URL path."""
    if not path:
        return None
    return f"/media/{path}"


# ── Public-safe serializers ─────────────────────────────────────────────────

def _public_event_dict(
    event: Event,
    include_days: bool = False,
    include_gallery: bool = False,
) -> dict:
    d = {
        "id":            event.id,
        "name":          event.name,
        "slug":          event.slug,
        "description":   event.description,
        "startDate":     event.start_date.isoformat() if event.start_date else None,
        "endDate":       event.end_date.isoformat() if event.end_date else None,
        "location":      event.location,
        "year":          event.year,
        "isFeatured":    event.is_featured,
        "coverImageUrl": _media_url(event.cover_image_path),
    }
    if include_days:
        d["days"] = [day.to_dict() for day in event.days]
    if include_gallery:
        gallery = (
            MediaFile.query
            .filter_by(event_id=event.id, category=MediaCategoryEnum.event_gallery)
            .order_by(MediaFile.sort_order)
            .all()
        )
        d["gallery"] = [
            {
                "id":        m.id,
                "url":       _media_url(m.path),
                "altText":   m.alt_text,
                "sortOrder": m.sort_order,
                "mimeType":  m.mime_type,
            }
            for m in gallery
        ]
    return d


def _public_announcement_dict(ann: Announcement) -> dict:
    return {
        "id":          ann.id,
        "title":       ann.title,
        "body":        ann.body,
        "event":       {
            "id":   ann.event.id,
            "name": ann.event.name,
            "slug": ann.event.slug,
        } if ann.event else None,
        "publishedAt": ann.published_at.isoformat() if ann.published_at else None,
    }


def _public_committee_dict(member: CommitteeMember) -> dict:
    return {
        "id":        member.id,
        "name":      member.name,
        "roleTitle": member.role_title,
        "photoUrl":  _media_url(member.photo_path),
        "sortOrder": member.sort_order,
    }


_ROLE_LABELS = {
    "chairman":        "Chairman",
    "president":       "President",
    "vice_president":  "Vice President",
    "secretary":       "Secretary",
    "junior_secretary":"Junior Secretary",
    "treasurer":       "Treasurer",
    "accountant":      "Accountant",
    "advisory_member": "Advisory Member",
    "member":          "Member",
}


def _year_role_dict(assignment) -> dict:
    from ...models.committee_role import COMMITTEE_ROLE_ORDER
    role = assignment.role.value if hasattr(assignment.role, "value") else assignment.role
    return {
        "id":        assignment.id,
        "name":      assignment.user.name if assignment.user else "",
        "roleTitle": _ROLE_LABELS.get(role, role.replace("_", " ").title()),
        "photoUrl":  None,
        "sortOrder": COMMITTEE_ROLE_ORDER.get(role, 999),
    }


def _event_role_dict(assignment) -> dict:
    from ...models.committee_role import COMMITTEE_ROLE_ORDER
    role = assignment.role.value if hasattr(assignment.role, "value") else assignment.role
    return {
        "id":        assignment.id,
        "name":      assignment.user.name if assignment.user else "",
        "roleTitle": _ROLE_LABELS.get(role, role.replace("_", " ").title()),
        "photoUrl":  None,
        "sortOrder": COMMITTEE_ROLE_ORDER.get(role, 999),
    }


# ── Query functions ────────────────────────────────────────────────────────

def list_public_events(org_id: int | None = None, page: int = 1, per_page: int = 12, include_days: bool = False) -> dict:
    per_page = min(per_page, 50)
    query = (
        Event.query
        .filter_by(status=EventStatusEnum.published, org_id=org_id)
        .order_by(Event.is_featured.desc(), Event.start_date.desc(), Event.created_at.desc())
    )
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return {
        "events": [_public_event_dict(e, include_days=include_days) for e in pagination.items],
        "page":    pagination.page,
        "perPage": pagination.per_page,
        "total":   pagination.total,
        "pages":   pagination.pages,
    }


def get_public_event_by_slug(slug: str, org_id: int | None = None) -> dict | None:
    event = Event.query.filter_by(
        slug=slug, status=EventStatusEnum.published, org_id=org_id
    ).first()
    if not event:
        return None
    return _public_event_dict(event, include_days=True, include_gallery=True)


def get_featured_event(org_id: int | None = None) -> dict | None:
    event = Event.query.filter_by(
        status=EventStatusEnum.published, is_featured=True, org_id=org_id
    ).first()
    if not event:
        return None
    return _public_event_dict(event, include_days=True, include_gallery=True)


def list_public_announcements(org_id: int | None = None, event_id: int | None = None) -> list[dict]:
    query = (
        Announcement.query
        .filter_by(is_published=True, org_id=org_id)
        .options(joinedload(Announcement.event))
    )
    if event_id:
        query = query.filter_by(event_id=event_id)
    items = query.order_by(Announcement.published_at.desc()).all()
    return [_public_announcement_dict(a) for a in items]


def list_public_committee(org_id: int | None = None, event_id: int | None = None) -> list[dict]:
    """Return committee members for the public Our Team page.

    Checks the YearRoleAssignment system: current year first, then any year
    with public assignments (most recent), then falls back to the legacy table.
    """
    from ...models.committee_role import ClubYear, YearRoleAssignment, COMMITTEE_ROLE_ORDER, CommitteeOrdering

    def _order_map(scope_id):
        rows = CommitteeOrdering.query.filter_by(org_id=org_id, scope="year", scope_id=scope_id).all()
        return {r.user_id: r.sort_order for r in rows}

    def _sorted_assignments(assigns, scope_id):
        omap = _order_map(scope_id)
        assigns.sort(key=lambda a: (
            omap.get(a.user_id, 10 ** 6),
            COMMITTEE_ROLE_ORDER.get(a.role.value if hasattr(a.role, "value") else a.role, 999),
        ))
        return [_year_role_dict(a) for a in assigns]

    # 1. Try current year
    current_year = ClubYear.query.filter_by(org_id=org_id, is_current=True).first()
    if current_year:
        assignments = (
            YearRoleAssignment.query
            .filter_by(club_year_id=current_year.id, is_public=True)
            .options(joinedload(YearRoleAssignment.user))
            .all()
        )
        if assignments:
            return _sorted_assignments(assignments, current_year.id)

    # 2. Any year with public assignments (most recently created first)
    all_years = (
        ClubYear.query
        .filter_by(org_id=org_id)
        .order_by(ClubYear.id.desc())
        .all()
    )
    for year in all_years:
        if current_year and year.id == current_year.id:
            continue  # already checked above
        assignments = (
            YearRoleAssignment.query
            .filter_by(club_year_id=year.id, is_public=True)
            .options(joinedload(YearRoleAssignment.user))
            .all()
        )
        if assignments:
            return _sorted_assignments(assignments, year.id)

    # 3. Fall back to legacy CommitteeMember table
    query = CommitteeMember.query.filter_by(is_active=True, org_id=org_id)
    if event_id:
        query = query.filter_by(event_id=event_id)
    items = query.order_by(CommitteeMember.sort_order, CommitteeMember.name).all()
    return [_public_committee_dict(m) for m in items]


def list_full_committee(org_id: int | None = None) -> dict:
    """Return year-based and event-based public committees separately.

    Used by the public Our Team page to show distinct sections per year/event.
    """
    from ...models.committee_role import (
        ClubYear, YearRoleAssignment, EventRoleAssignment, COMMITTEE_ROLE_ORDER, CommitteeOrdering,
    )

    def _order_map(scope, scope_id):
        rows = CommitteeOrdering.query.filter_by(org_id=org_id, scope=scope, scope_id=scope_id).all()
        return {r.user_id: r.sort_order for r in rows}

    def _sort_key(omap):
        def key(a):
            role = a.role.value if hasattr(a.role, "value") else a.role
            return (omap.get(a.user_id, 10 ** 6), COMMITTEE_ROLE_ORDER.get(role, 999))
        return key

    # ── Year committee ─────────────────────────────────────────────────────
    year_committee = None
    all_years = (
        ClubYear.query
        .filter_by(org_id=org_id)
        .order_by(ClubYear.is_current.desc(), ClubYear.id.desc())
        .all()
    )
    for year in all_years:
        assigns = (
            YearRoleAssignment.query
            .filter_by(club_year_id=year.id, is_public=True)
            .options(joinedload(YearRoleAssignment.user))
            .all()
        )
        if assigns:
            assigns.sort(key=_sort_key(_order_map("year", year.id)))
            year_committee = {
                "yearId":    year.id,
                "yearLabel": year.label,
                "members":   [_year_role_dict(a) for a in assigns],
            }
            break

    # ── Event committees ──────────────────────────────────────────────────
    events = (
        Event.query
        .filter_by(status=EventStatusEnum.published, org_id=org_id)
        .order_by(Event.start_date.desc().nullslast(), Event.id.desc())
        .all()
    )
    event_committees = []
    for event in events:
        assigns = (
            EventRoleAssignment.query
            .filter_by(event_id=event.id, is_public=True)
            .options(joinedload(EventRoleAssignment.user))
            .all()
        )
        if assigns:
            assigns.sort(key=_sort_key(_order_map("event", event.id)))
            event_committees.append({
                "eventId":   event.id,
                "eventName": event.name,
                "eventYear": event.year,
                "members":   [_event_role_dict(a) for a in assigns],
            })

    # ── Legacy fallback (if nothing from new system) ─────────────────────
    legacy_members = []
    if not year_committee and not event_committees:
        items = (
            CommitteeMember.query
            .filter_by(is_active=True, org_id=org_id)
            .order_by(CommitteeMember.sort_order, CommitteeMember.name)
            .all()
        )
        legacy_members = [_public_committee_dict(m) for m in items]

    return {
        "yearCommittee":   year_committee,
        "eventCommittees": event_committees,
        "legacyMembers":   legacy_members,
    }


def list_all_gallery_images(org_id: int | None = None) -> dict:
    """Return gallery images from all published events, featured event first."""
    events = (
        Event.query
        .filter_by(status=EventStatusEnum.published, org_id=org_id)
        .order_by(Event.is_featured.desc(), Event.start_date.desc(), Event.created_at.desc())
        .all()
    )
    images = []
    for event in events:
        gallery = (
            MediaFile.query
            .filter_by(event_id=event.id, category=MediaCategoryEnum.event_gallery)
            .order_by(MediaFile.sort_order)
            .all()
        )
        for m in gallery:
            images.append({
                "id":        m.id,
                "url":       _media_url(m.path),
                "altText":   m.alt_text,
                "sortOrder": m.sort_order,
                "mimeType":  m.mime_type,
                "event": {
                    "id":         event.id,
                    "name":       event.name,
                    "slug":       event.slug,
                    "isFeatured": event.is_featured,
                },
            })
    return {"images": images, "total": len(images)}


def get_public_stats(org_id: int | None = None) -> dict:
    """Lightweight stats for the public community section."""
    donor_q = db.session.query(func.count(Donor.id))
    if org_id is not None:
        donor_q = donor_q.filter(Donor.org_id == org_id)
    donor_count = donor_q.scalar() or 0

    event_q = (
        db.session.query(func.min(Event.year))
        .filter(Event.status == EventStatusEnum.published, Event.year.isnot(None))
    )
    if org_id is not None:
        event_q = event_q.filter(Event.org_id == org_id)
    oldest_year = event_q.scalar()

    return {
        "donorCount": donor_count,
        "oldestYear": oldest_year,
    }
