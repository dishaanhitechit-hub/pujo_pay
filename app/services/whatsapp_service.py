import re
import json
import logging
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from flask import current_app

logger = logging.getLogger(__name__)

_GRAPH_VERSION = "v21.0"


def _normalize_phone(phone: str) -> str | None:
    """Return E.164 digits without '+'. 10-digit numbers get Indian +91 prefix."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return "91" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "91" + digits[1:]
    if len(digits) >= 11:
        return digits
    return None


def send_whatsapp_text(to_phone: str, message: str) -> tuple[bool, str]:
    """Send a WhatsApp text message via Meta Cloud API.

    Returns (True, message_id) on success, (False, error_description) on failure.
    """
    token = current_app.config.get("WHATSAPP_TOKEN", "")
    phone_id = current_app.config.get("WHATSAPP_PHONE_NUMBER_ID", "")
    if not token or not phone_id:
        logger.warning("WhatsApp credentials not set — skipping send")
        return False, "WhatsApp credentials not configured"

    to = _normalize_phone(to_phone)
    if not to:
        return False, f"invalid phone number: {to_phone}"

    url = f"https://graph.facebook.com/{_GRAPH_VERSION}/{phone_id}/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message, "preview_url": False},
    }).encode()

    req = Request(url, data=payload, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })

    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            msg_id = data.get("messages", [{}])[0].get("id", "ok")
            logger.info("WhatsApp sent to %s, id=%s", to, msg_id)
            return True, msg_id
    except HTTPError as exc:
        try:
            err_body = json.loads(exc.read())
            err_msg = err_body.get("error", {}).get("message", str(exc))
        except Exception:
            err_msg = str(exc)
        logger.error("WhatsApp API error %s: %s", exc.code, err_msg)
        return False, err_msg
    except URLError as exc:
        logger.error("WhatsApp network error: %s", exc.reason)
        return False, str(exc.reason)
    except Exception as exc:
        logger.error("WhatsApp unexpected error: %s", exc)
        return False, str(exc)


def send_whatsapp_image(to_phone: str, image_url: str, caption: str = "") -> tuple[bool, str]:
    """Send a WhatsApp image message via a public URL."""
    token = current_app.config.get("WHATSAPP_TOKEN", "")
    phone_id = current_app.config.get("WHATSAPP_PHONE_NUMBER_ID", "")
    if not token or not phone_id:
        return False, "WhatsApp credentials not configured"

    to = _normalize_phone(to_phone)
    if not to:
        return False, f"invalid phone number: {to_phone}"

    url = f"https://graph.facebook.com/{_GRAPH_VERSION}/{phone_id}/messages"
    image_payload: dict = {"link": image_url}
    if caption:
        image_payload["caption"] = caption

    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": image_payload,
    }).encode()

    req = Request(url, data=payload, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })

    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            msg_id = data.get("messages", [{}])[0].get("id", "ok")
            logger.info("WhatsApp image sent to %s, id=%s", to, msg_id)
            return True, msg_id
    except HTTPError as exc:
        try:
            err_body = json.loads(exc.read())
            err_msg = err_body.get("error", {}).get("message", str(exc))
        except Exception:
            err_msg = str(exc)
        logger.error("WhatsApp image API error %s: %s", exc.code, err_msg)
        return False, err_msg
    except URLError as exc:
        logger.error("WhatsApp image network error: %s", exc.reason)
        return False, str(exc.reason)
    except Exception as exc:
        logger.error("WhatsApp image unexpected error: %s", exc)
        return False, str(exc)


def build_receipt_message(payment, org_name: str, base_url: str) -> str:
    donor = payment.donor.name if payment.donor else "Donor"
    method_label = {"cash": "Cash", "upi": "UPI/Online", "cheque": "Cheque"}.get(
        payment.method.value, payment.method.value
    )
    date_str = ""
    if payment.confirmed_at:
        date_str = payment.confirmed_at.strftime("%d %b %Y")
    elif payment.received_date:
        date_str = payment.received_date.strftime("%d %b %Y")

    lines = [
        f"🙏 *{org_name}*",
        "",
        f"Dear *{donor}*,",
        "Thank you for your generous contribution!",
        "",
        "📋 *Payment Receipt*",
        f"Receipt No: `{payment.receipt_no}`",
        f"Amount: ₹{payment.amount}",
        f"Method: {method_label}",
    ]
    if date_str:
        lines.append(f"Date: {date_str}")
    lines += ["", f"🔗 {base_url}/receipt/{payment.receipt_no}"]
    return "\n".join(lines)


def build_token_message(token, base_url: str) -> str:
    name = token.participant_name or "Participant"
    return "\n".join([
        f"🙏 *{token.org_name}*",
        "",
        f"Dear *{name}*,",
        "",
        "🎟️ *Your Entry Token*",
        f"Token No: *{token.token_no}*",
        f"Type: {token.type.value.title()}",
        "",
        "Verify your token:",
        f"🔗 {base_url}/token/{token.token_no}",
    ])


def build_membership_card_message(user, org_name: str) -> str:
    since = ""
    if user.member_since:
        since = f"\nMember Since: {user.member_since.strftime('%d %b %Y')}"
    category = f"\nCategory: {user.member_category.replace('_', ' ').title()}" if user.member_category else ""
    member_id = f"\nMember ID: *{user.member_id}*" if user.member_id else ""
    return "\n".join([
        f"🙏 *{org_name}*",
        "",
        f"Dear *{user.name}*,",
        "",
        "🪪 *Your Membership Card*",
        f"Name: {user.name}" + member_id + category + since,
        "",
        "Thank you for being a valued member of our organisation!",
        "Shubho Pujo! 🎉",
    ])


def build_event_notification_message(event, org_name: str) -> str:
    lines = [
        f"🙏 *{org_name}*",
        "",
        "📣 *Event Notification*",
        f"*{event.name}*",
    ]
    if event.start_date:
        date_str = event.start_date.strftime("%d %b %Y")
        if event.end_date and event.end_date != event.start_date:
            date_str += f" – {event.end_date.strftime('%d %b %Y')}"
        lines.append(f"📅 {date_str}")
    if event.location:
        lines.append(f"📍 {event.location}")
    if event.description:
        lines += ["", event.description[:300]]
    lines += ["", "Shubho Pujo! 🎉"]
    return "\n".join(lines)


def build_circular_message(circular, org_name: str) -> str:
    ref = f" (Ref: {circular.circular_no})" if circular.circular_no else ""
    return "\n".join([
        f"🙏 *{org_name}*",
        "",
        f"📄 *Circular: {circular.title}*{ref}",
        "",
        circular.body[:1000],
    ])
