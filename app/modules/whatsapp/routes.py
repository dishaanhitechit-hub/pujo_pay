from flask import Blueprint, request

from ...extensions import db
from ...models.payment import Payment, COMPLETED_STATUSES
from ...models.token import Token
from ...models.user import User
from ...models.organisation import Organisation
from ...models.event import Event
from ...models.circular import Circular
from ...middleware.permissions import require_permission
from ...middleware.tenant import get_current_org_id
from ...utils.helpers import res
from ...services.whatsapp_service import (
    send_whatsapp_text,
    send_whatsapp_image,
    build_receipt_message,
    build_token_message,
    build_membership_card_message,
    build_event_notification_message,
    build_circular_message,
)

bp = Blueprint("whatsapp", __name__)


def _get_org_name(org_id: int) -> str:
    org = Organisation.query.get(org_id)
    return org.name if org else "Organisation"


@bp.route("/api/whatsapp/send-receipt/<int:payment_id>", methods=["POST"])
@require_permission("payment.view_receipt")
def send_receipt(payment_id: int):
    """Manually send a payment receipt to the donor's WhatsApp number."""
    org_id = get_current_org_id()

    # Scope payment to this org via collector
    payment = Payment.query.get(payment_id)
    if not payment:
        return res("payment not found", code=404)
    collector = User.query.get(payment.collector_id)
    if not collector or collector.org_id != org_id:
        return res("payment not found", code=404)

    if payment.status not in COMPLETED_STATUSES:
        return res("payment is not yet completed", code=400)

    # Determine phone — body can override donor's stored phone
    body = request.get_json(silent=True) or {}
    phone = body.get("phone") or (payment.donor.phone if payment.donor else None)
    if not phone:
        return res("no phone number available for this donor", code=400)

    base_url = request.host_url.rstrip("/")
    message = build_receipt_message(payment, _get_org_name(org_id), base_url)
    ok, detail = send_whatsapp_text(phone, message)

    if ok:
        payment.whatsapp_sent = True
        db.session.commit()
        return res("WhatsApp receipt sent", data={"messageId": detail, "phone": phone})

    return res(f"WhatsApp send failed: {detail}", code=502)


@bp.route("/api/whatsapp/send-token/<token_no>", methods=["POST"])
@require_permission("token.generate")
def send_token(token_no: str):
    """Manually send a membership card / token to a WhatsApp number."""
    org_id = get_current_org_id()

    # Scope token to this org via generating user
    token = (
        Token.query
        .join(User, Token.generated_by_id == User.id)
        .filter(Token.token_no == token_no, User.org_id == org_id)
        .first()
    )
    if not token:
        return res("token not found", code=404)

    body = request.get_json(silent=True) or {}
    phone = (body.get("phone") or "").strip()
    if not phone:
        return res("phone number is required", code=400)

    base_url = request.host_url.rstrip("/")
    message = build_token_message(token, base_url)
    ok, detail = send_whatsapp_text(phone, message)

    if ok:
        return res("WhatsApp token sent", data={"messageId": detail, "phone": phone})

    return res(f"WhatsApp send failed: {detail}", code=502)


def _user_phone(user) -> str | None:
    """Prefer whatsapp_no; fall back to phone."""
    return (user.whatsapp_no or "").strip() or (user.phone or "").strip() or None


def _bulk_send(users: list, message: str) -> dict:
    sent, failed, errors = 0, 0, []
    for u in users:
        phone = _user_phone(u)
        if not phone:
            failed += 1
            errors.append({"userId": u.id, "name": u.name, "error": "no phone"})
            continue
        ok, detail = send_whatsapp_text(phone, message)
        if ok:
            sent += 1
        else:
            failed += 1
            errors.append({"userId": u.id, "name": u.name, "error": detail})
    return {"sent": sent, "failed": failed, "errors": errors}


@bp.route("/api/whatsapp/send-membership-card/<int:user_id>", methods=["POST"])
@require_permission("users.manage")
def send_membership_card(user_id: int):
    """Receive a base64 card PNG from the frontend and send it via WhatsApp."""
    import os, base64
    from flask import current_app

    org_id = get_current_org_id()
    user = User.query.filter_by(id=user_id, org_id=org_id).first()
    if not user:
        return res("user not found", code=404)

    phone = _user_phone(user)
    if not phone:
        return res("no WhatsApp / phone number for this member", code=400)

    org = Organisation.query.get(org_id)
    org_name = org.name if org else "Organisation"
    org_slug = org.slug if org else str(org_id)

    body = request.get_json(silent=True) or {}
    image_b64 = body.get("imageBase64", "")
    if not image_b64:
        return res("imageBase64 is required", code=400)

    # Strip data URI prefix if present
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    storage_base = current_app.config.get("STORAGE_BASE", "/srv/pujo-backend")
    save_dir = os.path.join(storage_base, org_slug, "media", "cards")
    os.makedirs(save_dir, exist_ok=True)

    safe_id = (user.member_id or str(user.id)).replace("/", "_").replace(" ", "_")
    filename = f"card_{safe_id}.png"
    card_path = os.path.join(save_dir, filename)

    try:
        with open(card_path, "wb") as f:
            f.write(base64.b64decode(image_b64))
    except Exception as exc:
        return res(f"Failed to save card image: {exc}", code=500)

    site_url = current_app.config.get("SITE_URL") or request.host_url.rstrip("/")
    image_url = f"{site_url}/media/{org_slug}/cards/{filename}"
    caption = f"🙏 {org_name} — Membership Card\n{user.name}"
    ok, detail = send_whatsapp_image(phone, image_url, caption)

    if ok:
        return res("membership card sent", data={"messageId": detail, "phone": phone})
    return res(f"WhatsApp send failed: {detail}", code=502)


@bp.route("/api/whatsapp/notify-event/<int:event_id>", methods=["POST"])
@require_permission("event.manage")
def notify_event(event_id: int):
    """Send event notification to selected or all org members."""
    org_id = get_current_org_id()
    event = Event.query.filter_by(id=event_id, org_id=org_id).first()
    if not event:
        return res("event not found", code=404)

    body = request.get_json(silent=True) or {}
    send_all = body.get("all", False)
    user_ids = body.get("userIds") or []

    if send_all:
        users = User.query.filter_by(org_id=org_id, is_active=True).all()
    elif user_ids:
        users = User.query.filter(
            User.org_id == org_id,
            User.id.in_(user_ids),
            User.is_active == True,
        ).all()
    else:
        return res("provide userIds list or set all=true", code=400)

    org_name = _get_org_name(org_id)
    message = build_event_notification_message(event, org_name)
    result = _bulk_send(users, message)
    return res("event notification sent", data=result)


@bp.route("/api/whatsapp/notify-circular/<int:circular_id>", methods=["POST"])
@require_permission("content.manage")
def notify_circular(circular_id: int):
    """Send a circular to selected or all org members via WhatsApp."""
    org_id = get_current_org_id()
    circular = (
        Circular.query
        .join(User, Circular.created_by == User.id)
        .filter(Circular.id == circular_id, User.org_id == org_id)
        .first()
    )
    if not circular:
        return res("circular not found", code=404)

    body = request.get_json(silent=True) or {}
    send_all = body.get("all", False)
    user_ids = body.get("userIds") or []

    if send_all:
        users = User.query.filter_by(org_id=org_id, is_active=True).all()
    elif user_ids:
        users = User.query.filter(
            User.org_id == org_id,
            User.id.in_(user_ids),
            User.is_active == True,
        ).all()
    else:
        return res("provide userIds list or set all=true", code=400)

    org_name = _get_org_name(org_id)
    message = build_circular_message(circular, org_name)
    result = _bulk_send(users, message)
    return res("circular notification sent", data=result)
