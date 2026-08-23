from flask import Blueprint, request, jsonify

from ...utils.helpers import res
from ...models.app_config import AppConfig
from .service import (
    list_public_events,
    get_public_event_by_slug,
    get_featured_event,
    list_public_announcements,
    list_public_committee,
)

bp = Blueprint("public", __name__)


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
    return res(data=list_public_announcements(event_id=event_id))


@bp.route("/committee", methods=["GET"])
def committee():
    event_id = request.args.get("eventId", type=int)
    return res(data=list_public_committee(event_id=event_id))


@bp.route("/events", methods=["GET"])
def events():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("perPage", default=12, type=int)
    return res(data=list_public_events(page=page, per_page=per_page))


@bp.route("/events/<slug>", methods=["GET"])
def event_detail(slug: str):
    result = get_public_event_by_slug(slug)
    if not result:
        return res("event not found", code=404)
    return res(data=result)


@bp.route("/featured-event", methods=["GET"])
def featured_event():
    result = get_featured_event()
    # Return JSON null (not []) when no featured event is set.
    return jsonify({"message": "", "data": result}), 200
