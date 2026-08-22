import enum

from ..extensions import db


class MediaCategoryEnum(str, enum.Enum):
    event_cover   = "event_cover"
    event_gallery = "event_gallery"
    committee     = "committee"
    announcement  = "announcement"
    public        = "public"


class MediaFile(db.Model):
    __tablename__ = "media_files"

    id                = db.Column(db.Integer, primary_key=True)
    # Relative path within MEDIA_STORAGE_PATH, e.g. "events/3/gallery/abc123.jpg"
    # Used directly as the URL path segment: GET /media/<path>
    path              = db.Column(db.String(600), nullable=False)
    event_id          = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="SET NULL"), nullable=True)
    category          = db.Column(
        db.Enum(MediaCategoryEnum, native_enum=False), nullable=False
    )
    filename          = db.Column(db.String(200), nullable=False)   # generated UUID filename
    original_filename = db.Column(db.String(500))                   # original upload name (metadata)
    mime_type         = db.Column(db.String(100), nullable=False)
    file_size         = db.Column(db.Integer, nullable=False)       # bytes
    alt_text          = db.Column(db.String(300))
    sort_order        = db.Column(db.Integer, nullable=False, default=0)
    uploaded_by       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_at       = db.Column(db.DateTime, server_default=db.func.now())

    event    = db.relationship("Event", foreign_keys=[event_id])
    uploader = db.relationship("User", foreign_keys=[uploaded_by])

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "path":             self.path,
            "event":            {"id": self.event.id, "name": self.event.name} if self.event else None,
            "category":         self.category.value,
            "filename":         self.filename,
            "originalFilename": self.original_filename,
            "mimeType":         self.mime_type,
            "fileSize":         self.file_size,
            "altText":          self.alt_text,
            "sortOrder":        self.sort_order,
            "uploadedBy":       {"id": self.uploader.id, "name": self.uploader.name} if self.uploader else None,
            "uploadedAt":       self.uploaded_at.isoformat() if self.uploaded_at else None,
        }
