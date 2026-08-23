import os
import uuid

from flask import current_app

from ...extensions import db
from ...models.event import Event
from ...models.media_file import MediaFile, MediaCategoryEnum


# ── MIME allow-list (images only; no PDFs, no documents) ──────────────────

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

def _media_root() -> str:
    return current_app.config["MEDIA_STORAGE_PATH"]


def _safe_abs_path(relative: str, root: str) -> str | None:
    """
    Return the absolute path only if it resolves strictly within root.
    Returns None on path-traversal attempts.
    """
    real_root = os.path.realpath(root)
    abs_path = os.path.realpath(os.path.join(root, relative))
    # Must start with root + separator to prevent matching /srv/pujo/media-other
    if abs_path.startswith(real_root + os.sep) or abs_path == real_root:
        return abs_path
    return None


def _save_file(fileobj, rel_dir: str, ext: str, root: str) -> tuple[str, str, int]:
    """
    Save fileobj into root/rel_dir/ using a UUID filename.
    Returns (relative_path, filename, file_size_bytes).
    rel_dir must already be validated to be within root (caller's responsibility).
    """
    filename = uuid.uuid4().hex + ext
    rel_path = rel_dir.rstrip("/") + "/" + filename

    abs_path = _safe_abs_path(rel_path, root)
    if abs_path is None:
        raise ValueError("computed path escapes media root")

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    fileobj.save(abs_path)
    file_size = os.path.getsize(abs_path)
    return rel_path, filename, file_size


def _delete_file(rel_path: str, root: str) -> None:
    """Remove a file from the filesystem. Silently ignores missing files."""
    if not rel_path:
        return
    abs_path = _safe_abs_path(rel_path, root)
    if abs_path and os.path.isfile(abs_path):
        os.remove(abs_path)


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

    root = _media_root()
    rel_dir = f"events/{event_id}/cover"

    # Delete old cover file + DB record if one exists
    if event.cover_image_path:
        old = MediaFile.query.filter_by(
            event_id=event_id, category=MediaCategoryEnum.event_cover
        ).first()
        if old:
            _delete_file(old.path, root)
            db.session.delete(old)

    ext = _ext_for_mime(mime_type)
    try:
        rel_path, filename, file_size = _save_file(fileobj, rel_dir, ext, root)
    except Exception as exc:
        return None, f"file save failed: {exc}"

    media = MediaFile(
        path=rel_path,
        event_id=event_id,
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
    event.cover_image_path = rel_path
    db.session.commit()
    return media.to_dict(), None


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

    root = _media_root()
    rel_dir = f"events/{event_id}/gallery"

    # sort_order = count of existing gallery items
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
    return media.to_dict(), None


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

    root = _media_root()
    rel_dir = "committee"

    # Delete old photo file + DB record if one exists
    if member.photo_path:
        old = MediaFile.query.filter_by(
            path=member.photo_path, category=MediaCategoryEnum.committee
        ).first()
        if old:
            _delete_file(old.path, root)
            db.session.delete(old)

    ext = _ext_for_mime(mime_type)
    try:
        rel_path, filename, file_size = _save_file(fileobj, rel_dir, ext, root)
    except Exception as exc:
        return None, f"file save failed: {exc}"

    media = MediaFile(
        path=rel_path,
        event_id=member.event_id,
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
    member.photo_path = rel_path
    db.session.commit()
    return media.to_dict(), None


# ── Generic delete ─────────────────────────────────────────────────────────

def delete_media(media_id: int) -> str | None:
    media = MediaFile.query.get(media_id)
    if not media:
        return "media not found"

    root = _media_root()
    _delete_file(media.path, root)

    # Clear back-references so model fields don't point at a deleted file
    if media.category == MediaCategoryEnum.event_cover and media.event_id:
        event = Event.query.get(media.event_id)
        if event and event.cover_image_path == media.path:
            event.cover_image_path = None

    if media.category == MediaCategoryEnum.committee:
        from ...models.committee_member import CommitteeMember
        member = CommitteeMember.query.filter_by(photo_path=media.path).first()
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


# ── Gallery list (used by event service) ──────────────────────────────────

def get_event_gallery(event_id: int) -> list[dict]:
    items = (
        MediaFile.query
        .filter_by(event_id=event_id, category=MediaCategoryEnum.event_gallery)
        .order_by(MediaFile.sort_order)
        .all()
    )
    return [m.to_dict() for m in items]


# ── Serve helper ───────────────────────────────────────────────────────────

def resolve_media_path(relative: str) -> str | None:
    """
    Resolve a relative media path to an absolute filesystem path.
    Returns None if the path is outside MEDIA_STORAGE_PATH or does not exist.
    """
    root = _media_root()
    abs_path = _safe_abs_path(relative, root)
    if abs_path and os.path.isfile(abs_path):
        return abs_path
    return None
