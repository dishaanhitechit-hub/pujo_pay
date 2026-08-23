from sqlalchemy import func
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
# These never expose: filesystem paths, createdBy, internal DB metadata,
# collection_enabled, or any admin-only fields.

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
        "phone":     member.phone,
        "photoUrl":  _media_url(member.photo_path),
        "sortOrder": member.sort_order,
    }


# ── Query functions ────────────────────────────────────────────────────────

def list_public_events(page: int = 1, per_page: int = 12, include_days: bool = False) -> dict:
    per_page = min(per_page, 50)
    query = (
        Event.query
        .filter_by(status=EventStatusEnum.published)
        .order_by(Event.start_date.desc(), Event.created_at.desc())
    )
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return {
        "events": [_public_event_dict(e, include_days=include_days) for e in pagination.items],
        "page":    pagination.page,
        "perPage": pagination.per_page,
        "total":   pagination.total,
        "pages":   pagination.pages,
    }


def get_public_event_by_slug(slug: str) -> dict | None:
    event = Event.query.filter_by(
        slug=slug, status=EventStatusEnum.published
    ).first()
    if not event:
        return None
    return _public_event_dict(event, include_days=True, include_gallery=True)


def get_featured_event() -> dict | None:
    event = Event.query.filter_by(
        status=EventStatusEnum.published, is_featured=True
    ).first()
    if not event:
        return None
    return _public_event_dict(event, include_days=True, include_gallery=True)


def list_public_announcements(event_id: int | None = None) -> list[dict]:
    query = Announcement.query.filter_by(is_published=True)
    if event_id:
        query = query.filter_by(event_id=event_id)
    items = query.order_by(Announcement.published_at.desc()).all()
    return [_public_announcement_dict(a) for a in items]


def list_public_committee(event_id: int | None = None) -> list[dict]:
    query = CommitteeMember.query.filter_by(is_active=True)
    if event_id:
        query = query.filter_by(event_id=event_id)
    items = query.order_by(CommitteeMember.sort_order, CommitteeMember.name).all()
    return [_public_committee_dict(m) for m in items]


def list_all_gallery_images() -> dict:
    """Return gallery images from all published events, featured event first."""
    events = (
        Event.query
        .filter_by(status=EventStatusEnum.published)
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


def get_public_stats() -> dict:
    """
    Lightweight stats for the public community section.
    All queries are simple aggregates — no table scans.
    """
    donor_count = db.session.query(func.count(Donor.id)).scalar() or 0

    oldest_year = (
        db.session.query(func.min(Event.year))
        .filter(Event.status == EventStatusEnum.published, Event.year.isnot(None))
        .scalar()
    )

    return {
        "donorCount":  donor_count,
        "oldestYear":  oldest_year,   # None if no published events have a year set
    }
