import io
from flask import Blueprint, request, jsonify, send_file, abort, make_response

from ...utils.helpers import res
from ...models.app_config import AppConfig
from ...models.organisation import Organisation
from .service import (
    list_public_events,
    get_public_event_by_slug,
    get_featured_event,
    list_public_announcements,
    list_public_committee,
    list_full_committee,
    list_all_gallery_images,
    get_public_stats,
)

bp = Blueprint("public", __name__)


def _resolve_org_id() -> int | None:
    slug = request.args.get("orgSlug", "").strip()
    if not slug:
        return None
    org = Organisation.query.filter_by(slug=slug, is_active=True).first()
    if not org:
        # Fail loudly: falling back to org_id=None silently served an empty site for a mistyped slug.
        abort(make_response(res(f"organisation '{slug}' not found or inactive")[0], 404))
    return org.id


def _cfg(key: str, org_id: int | None) -> str | None:
    return AppConfig.get(key, org_id=org_id)


@bp.route("/site-config", methods=["GET"])
def site_config():
    org_id = _resolve_org_id()
    data = {
        "upiId":  _cfg("upi_id", org_id),
        "orgName": _cfg("org_name", org_id),
        "contact": {
            "phone":    _cfg("contact.phone", org_id),
            "email":    _cfg("contact.email", org_id),
            "whatsapp": _cfg("contact.whatsapp", org_id),
            "address":  _cfg("contact.address", org_id),
        },
        "support": {
            "title":           _cfg("support.title", org_id),
            "description":     _cfg("support.description", org_id),
            "whatsappMessage": _cfg("support.whatsapp_message", org_id),
        },
        "social": {
            "facebook":  _cfg("social.facebook", org_id),
            "instagram": _cfg("social.instagram", org_id),
            "youtube":   _cfg("social.youtube", org_id),
        },
        "club": {
            "nameVernacular":  _cfg("club.name_vernacular", org_id),
            "nameEn":          _cfg("club.name_en", org_id),
            "tagline":         _cfg("club.tagline", org_id),
            "description":     _cfg("club.description", org_id),
            "city":            _cfg("club.city", org_id),
            "state":           _cfg("club.state", org_id),
            "foundingYear":    _cfg("club.founding_year", org_id),
            "logoUrl":         _cfg("club.logo_url", org_id),
            "heroImageUrl":    _cfg("club.hero_image_url", org_id),
            "aboutText":       _cfg("club.about_text", org_id),
            "siteUrl":         _cfg("club.site_url", org_id),
            "metaDescription": _cfg("club.meta_description", org_id),
            "ogImageUrl":      _cfg("club.og_image_url", org_id),
        },
    }
    return res(data=data)


@bp.route("/announcements", methods=["GET"])
def announcements():
    event_id = request.args.get("eventId", type=int)
    return res(data=list_public_announcements(org_id=_resolve_org_id(), event_id=event_id))


@bp.route("/committee", methods=["GET"])
def committee():
    event_id = request.args.get("eventId", type=int)
    return res(data=list_public_committee(org_id=_resolve_org_id(), event_id=event_id))


@bp.route("/committee/full", methods=["GET"])
def committee_full():
    return res(data=list_full_committee(org_id=_resolve_org_id()))


@bp.route("/events", methods=["GET"])
def events():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("perPage", default=12, type=int)
    include_days = request.args.get("includeDays", default="false").lower() == "true"
    return res(data=list_public_events(org_id=_resolve_org_id(), page=page, per_page=per_page, include_days=include_days))


@bp.route("/events/<slug>", methods=["GET"])
def event_detail(slug: str):
    result = get_public_event_by_slug(slug, org_id=_resolve_org_id())
    if not result:
        return res("event not found", code=404)
    return res(data=result)


@bp.route("/featured-event", methods=["GET"])
def featured_event():
    result = get_featured_event(org_id=_resolve_org_id())
    return jsonify({"message": "", "data": result}), 200


@bp.route("/gallery", methods=["GET"])
def gallery():
    return res(data=list_all_gallery_images(org_id=_resolve_org_id()))


@bp.route("/stats", methods=["GET"])
def stats():
    return res(data=get_public_stats(org_id=_resolve_org_id()))


@bp.route("/platform-upi", methods=["GET"])
def platform_upi():
    upi_id = AppConfig.get("platform.registration_upi_id")
    return res(data={"upiId": upi_id})


@bp.route("/platform-upi-qr", methods=["GET"])
def platform_upi_qr():
    upi_id = AppConfig.get("platform.registration_upi_id")
    if not upi_id:
        return res("payment UPI not configured", code=404)
    import qrcode
    upi_url = f"upi://pay?pa={upi_id}&pn=PujoPay+Platform&tn=Organisation+Registration"
    img = qrcode.make(upi_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@bp.route("/org-request", methods=["POST"])
def org_request():
    from marshmallow import ValidationError
    from ...modules.super_admin.service import create_provision_schema, create_provision
    body = request.get_json(silent=True) or {}
    try:
        data = create_provision_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)
    prov = create_provision(data, created_by=None)
    return res(
        "request submitted — we will send your credentials once payment is confirmed",
        data=prov.to_dict(),
        code=201,
    )
