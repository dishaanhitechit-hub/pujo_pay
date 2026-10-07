import os
import uuid

from flask import current_app

from ...extensions import db
from ...models.event import Event
from ...models.media_file import MediaFile, MediaCategoryEnum


# ── MIME allow-list (images only) ─────────────────────────────────────────

ALLOWED_MIMES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png":  ".png",
    "image/webp": ".webp",
    "image/gif":  ".gif",
}


def allowed_mime(mime_type: str) -> bool:
    return mime_type in ALLOWED_MIMES


def _ext_for_mime(mime_type: str) -> str:
    return ALLOWED_MIMES.get(mime_type, ".bin")


# ── Path helpers ───────────────────────────────────────────────────────────

def _storage_base() -> str:
    return current_app.config["STORAGE_BASE"]


def _org_media_root(org_slug: str) -> str:
    """Absolute path to an org's media folder: {base}/{org_slug}/media"""
    return os.path.join(_storage_base(), org_slug, "media")


def _org_pdf_root(org_slug: str) -> str:
    """Absolute path to an org's PDF folder: {base}/{org_slug}/pdf"""
    return os.path.join(_storage_base(), org_slug, "pdf")


def _get_org_slug(org_id: int) -> str:
    from ...models.organisation import Organisation
    org = Organisation.query.get(org_id)
    if not org:
        raise ValueError(f"org {org_id} not found")
    return org.slug


def _safe_abs_path(relative: str, root: str) -> str | None:
    real_root = os.path.realpath(root)
    abs_path  = os.path.realpath(os.path.join(root, relative))
    if abs_path.startswith(real_root + os.sep) or abs_path == real_root:
        return abs_path
    return None


def _save_file(fileobj, rel_dir: str, ext: str, root: str) -> tuple[str, str, int]:
    """
    Save fileobj into {root}/{rel_dir}/ with a UUID filename.
    Returns (relative_path, filename, file_size_bytes).
    """
    filename = uuid.uuid4().hex + ext
    rel_path = rel_dir.rstrip("/") + "/" + filename

    abs_path = _safe_abs_path(rel_path, root)
    if abs_path is None:
        raise ValueError("computed path escapes storage root")

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    fileobj.save(abs_path)
    file_size = os.path.getsize(abs_path)
    return rel_path, filename, file_size


def _delete_file(org_slug: str, rel_path: str) -> None:
    """Remove a file. rel_path is relative to the org's media root."""
    if not rel_path or not org_slug:
        return
    root = _org_media_root(org_slug)
    abs_path = _safe_abs_path(rel_path, root)
    if abs_path and os.path.isfile(abs_path):
        os.remove(abs_path)


def _url_path(org_slug: str, rel_path: str) -> str:
    """URL path served by the /media endpoint: /media/{org_slug}/{rel_path}"""
    return f"/media/{org_slug}/{rel_path}"


# ── Event cover ────────────────────────────────────────────────────────────

def upload_event_cover(
    event_id: int, fileobj, mime_type: str, original_filename: str,
    alt_text: str | None, uploaded_by: int,
) -> tuple[dict | None, str | None]:
    event = Event.query.get(event_id)
    if not event:
        return None, "event not found"

    if not allowed_mime(mime_type):
        return None, f"unsupported file type '{mime_type}' — allowed: {list(ALLOWED_MIMES)}"

    org_slug = _get_org_slug(event.org_id)
    root     = _org_media_root(org_slug)
    rel_dir  = f"events/{event_id}/cover"

    # Delete old cover
    if event.cover_image_path:
        old = MediaFile.query.filter_by(
            event_id=event_id, category=MediaCategoryEnum.event_cover
        ).first()
        if old:
            _delete_file(org_slug, old.path)
            db.session.delete(old)

    ext = _ext_for_mime(mime_type)
    try:
        rel_path, filename, file_size = _save_file(fileobj, rel_dir, ext, root)
    except Exception as exc:
        return None, f"file save failed: {exc}"

    media = MediaFile(
        path=rel_path,
        event_id=event_id,
        org_id=event.org_id,
        category=MediaCategoryEnum.event_cover,
        filename=filename,
        original_filename=original_filename or None,
        mime_type=mime_type,
        file_size=file_size,
        alt_text=alt_text or None,
        sort_order=0,
        uploaded_by=uploaded_by,
    )
    db.session.add(media)
    event.cover_image_path = _url_path(org_slug, rel_path)
    db.session.commit()
    result = media.to_dict()
    result["url"] = _url_path(org_slug, rel_path)
    return result, None


# ── Event gallery ──────────────────────────────────────────────────────────

def upload_event_gallery(
    event_id: int, fileobj, mime_type: str, original_filename: str,
    alt_text: str | None, uploaded_by: int,
) -> tuple[dict | None, str | None]:
    event = Event.query.get(event_id)
    if not event:
        return None, "event not found"

    if not allowed_mime(mime_type):
        return None, f"unsupported file type '{mime_type}' — allowed: {list(ALLOWED_MIMES)}"

    org_slug   = _get_org_slug(event.org_id)
    root       = _org_media_root(org_slug)
    rel_dir    = f"events/{event_id}/gallery"
    sort_order = MediaFile.query.filter_by(
        event_id=event_id, category=MediaCategoryEnum.event_gallery
    ).count()

    ext = _ext_for_mime(mime_type)
    try:
        rel_path, filename, file_size = _save_file(fileobj, rel_dir, ext, root)
    except Exception as exc:
        return None, f"file save failed: {exc}"

    media = MediaFile(
        path=rel_path,
        event_id=event_id,
        org_id=event.org_id,
        category=MediaCategoryEnum.event_gallery,
        filename=filename,
        original_filename=original_filename or None,
        mime_type=mime_type,
        file_size=file_size,
        alt_text=alt_text or None,
        sort_order=sort_order,
        uploaded_by=uploaded_by,
    )
    db.session.add(media)
    db.session.commit()
    result = media.to_dict()
    result["url"] = _url_path(org_slug, rel_path)
    return result, None


# ── Committee photo ────────────────────────────────────────────────────────

def upload_committee_photo(
    member_id: int, fileobj, mime_type: str, original_filename: str,
    alt_text: str | None, uploaded_by: int,
) -> tuple[dict | None, str | None]:
    from ...models.committee_member import CommitteeMember

    member = CommitteeMember.query.get(member_id)
    if not member:
        return None, "committee member not found"

    if not allowed_mime(mime_type):
        return None, f"unsupported file type '{mime_type}' — allowed: {list(ALLOWED_MIMES)}"

    org_slug = _get_org_slug(member.org_id)
    root     = _org_media_root(org_slug)
    rel_dir  = "committee"

    if member.photo_path:
        old = MediaFile.query.filter_by(
            path=member.photo_path, category=MediaCategoryEnum.committee
        ).first()
        if old:
            _delete_file(org_slug, old.path)
            db.session.delete(old)

    ext = _ext_for_mime(mime_type)
    try:
        rel_path, filename, file_size = _save_file(fileobj, rel_dir, ext, root)
    except Exception as exc:
        return None, f"file save failed: {exc}"

    media = MediaFile(
        path=rel_path,
        event_id=member.event_id,
        org_id=member.org_id,
        category=MediaCategoryEnum.committee,
        filename=filename,
        original_filename=original_filename or None,
        mime_type=mime_type,
        file_size=file_size,
        alt_text=alt_text or None,
        sort_order=0,
        uploaded_by=uploaded_by,
    )
    db.session.add(media)
    member.photo_path = _url_path(org_slug, rel_path)
    db.session.commit()
    result = media.to_dict()
    result["url"] = _url_path(org_slug, rel_path)
    return result, None


# ── Admin config images ────────────────────────────────────────────────────

def upload_config_media(
    org_id: int, fileobj, mime_type: str, original_filename: str,
    uploaded_by: int,
) -> tuple[dict | None, str | None]:
    if not allowed_mime(mime_type):
        return None, f"unsupported file type '{mime_type}' — allowed: {list(ALLOWED_MIMES)}"

    org_slug = _get_org_slug(org_id)
    root     = _org_media_root(org_slug)
    rel_dir  = "config"
    ext      = _ext_for_mime(mime_type)

    try:
        rel_path, filename, file_size = _save_file(fileobj, rel_dir, ext, root)
    except Exception as exc:
        return None, f"file save failed: {exc}"

    media = MediaFile(
        path=rel_path,
        org_id=org_id,
        category=MediaCategoryEnum.public,
        filename=filename,
        original_filename=original_filename or None,
        mime_type=mime_type,
        file_size=file_size,
        alt_text=None,
        sort_order=0,
        uploaded_by=uploaded_by,
    )
    db.session.add(media)
    db.session.commit()
    url = _url_path(org_slug, rel_path)
    return {"url": url, "id": media.id}, None


# ── Generic delete ─────────────────────────────────────────────────────────

def delete_media(media_id: int) -> str | None:
    media = MediaFile.query.get(media_id)
    if not media:
        return "media not found"

    if media.org_id:
        try:
            org_slug = _get_org_slug(media.org_id)
            _delete_file(org_slug, media.path)
        except ValueError:
            pass

    if media.category == MediaCategoryEnum.event_cover and media.event_id:
        event = Event.query.get(media.event_id)
        if event and event.cover_image_path and media.path in event.cover_image_path:
            event.cover_image_path = None

    if media.category == MediaCategoryEnum.committee:
        from ...models.committee_member import CommitteeMember
        member = CommitteeMember.query.filter_by(photo_path=media.path).first()
        if not member:
            # photo_path may now store the full URL
            try:
                org_slug = _get_org_slug(media.org_id)
                full_url = _url_path(org_slug, media.path)
                member = CommitteeMember.query.filter_by(photo_path=full_url).first()
            except ValueError:
                pass
        if member:
            member.photo_path = None

    db.session.delete(media)
    db.session.commit()
    return None


# ── Gallery reorder ────────────────────────────────────────────────────────

def reorder_event_gallery(event_id: int, ordered_ids: list[int]) -> str | None:
    items = {m.id: m for m in MediaFile.query.filter(
        MediaFile.id.in_(ordered_ids),
        MediaFile.event_id == event_id,
        MediaFile.category == MediaCategoryEnum.event_gallery,
    ).all()}

    if len(items) != len(ordered_ids):
        return "some gallery items not found"

    for i, media_id in enumerate(ordered_ids):
        items[media_id].sort_order = i

    db.session.commit()
    return None


# ── Gallery list ───────────────────────────────────────────────────────────

def get_event_gallery(event_id: int) -> list[dict]:
    items = (
        MediaFile.query
        .filter_by(event_id=event_id, category=MediaCategoryEnum.event_gallery)
        .order_by(MediaFile.sort_order)
        .all()
    )
    results = []
    for m in items:
        d = m.to_dict()
        if m.org_id:
            try:
                d["url"] = _url_path(_get_org_slug(m.org_id), m.path)
            except ValueError:
                d["url"] = f"/media/{m.path}"
        results.append(d)
    return results


# ── Serve helper ───────────────────────────────────────────────────────────

def resolve_media_path(filepath: str) -> str | None:
    """
    Map a URL path to a filesystem path.
    filepath format: {org_slug}/{rel_path}  e.g. satadal-kolaghat/events/3/cover/abc.jpg
    Resolves to: {STORAGE_BASE}/{org_slug}/media/{rel_path}
    """
    parts = filepath.split("/", 1)
    if len(parts) != 2:
        return None
    org_slug, rel_path = parts[0], parts[1]
    root     = _org_media_root(org_slug)
    abs_path = _safe_abs_path(rel_path, root)
    if abs_path and os.path.isfile(abs_path):
        return abs_path
    return None
