import io
from flask import Blueprint, request, jsonify, send_file

from ...utils.helpers import res
from ...models.app_config import AppConfig
from ...models.organisation import Organisation
from .service import (
    list_public_events,
    get_public_event_by_slug,
    get_featured_event,
    list_public_announcements,
    list_public_committee,
    list_all_gallery_images,
    get_public_stats,
)

bp = Blueprint("public", __name__)


def _resolve_org_id() -> int | None:
    slug = request.args.get("orgSlug", "").strip()
    if not slug:
        return None
    org = Organisation.query.filter_by(slug=slug, is_active=True).first()
    return org.id if org else None


@bp.route("/site-config", methods=["GET"])
def site_config():
    data = {
        "upiId":  AppConfig.get("upi_id"),
        "orgName": AppConfig.get("org_name"),
        "contact": {
            "phone":    AppConfig.get("contact.phone"),
            "email":    AppConfig.get("contact.email"),
            "whatsapp": AppConfig.get("contact.whatsapp"),
            "address":  AppConfig.get("contact.address"),
        },
        "support": {
            "title":           AppConfig.get("support.title"),
            "description":     AppConfig.get("support.description"),
            "whatsappMessage": AppConfig.get("support.whatsapp_message"),
        },
        "social": {
            "facebook":  AppConfig.get("social.facebook"),
            "instagram": AppConfig.get("social.instagram"),
            "youtube":   AppConfig.get("social.youtube"),
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
    # Return JSON null (not []) when no featured event is set.
    return jsonify({"message": "", "data": result}), 200


@bp.route("/gallery", methods=["GET"])
def gallery():
    return res(data=list_all_gallery_images(org_id=_resolve_org_id()))


@bp.route("/stats", methods=["GET"])
def stats():
    return res(data=get_public_stats())


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
