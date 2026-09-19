"""JSON attendance API for the mobile app.

The attendee-facing flow lives in `app/test_feature` and is intentionally public —
attendees scan a QR at the venue and fill in a web form without logging in.
These endpoints are the staff-facing counterpart and are permission-gated, because
attendance records carry attendee names, phone numbers and addresses.
"""

from flask import Blueprint, Response, request

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from ...test_feature.service import (
    generate_qr_png,
    get_history,
    get_or_create_today_session,
    get_today_records,
    get_today_sessions,
    reset_session,
)

bp = Blueprint("attendance_api", __name__)


def _attend_url(token: str) -> str:
    return f"{request.host_url.rstrip('/')}/test/attend?token={token}"


@bp.route("/session", methods=["GET"])
@require_permission("dashboard.view")
def current_session():
    """The active session for today, creating one if none exists yet."""
    session = get_or_create_today_session()
    data = session.to_dict()
    data["attendUrl"] = _attend_url(session.qr_token)
    return res(data=data)


@bp.route("/sessions", methods=["GET"])
@require_permission("dashboard.view")
def today_sessions():
    return res(data=[s.to_dict() for s in get_today_sessions()])


@bp.route("/session/qr.png", methods=["GET"])
@require_permission("dashboard.view")
def session_qr():
    """PNG of the join URL, for displaying at the venue."""
    session = get_or_create_today_session()
    png = generate_qr_png(_attend_url(session.qr_token))
    return Response(
        png,
        mimetype="image/png",
        headers={"Cache-Control": "no-store"},
    )


@bp.route("/session/reset", methods=["POST"])
@require_permission("event.manage")
def reset():
    """Close the active session and open a new one for the same day."""
    session = reset_session()
    data = session.to_dict()
    data["attendUrl"] = _attend_url(session.qr_token)
    return res("new attendance session started", data=data)


@bp.route("/records", methods=["GET"])
@require_permission("dashboard.view")
def records():
    return res(data=get_today_records())


@bp.route("/history", methods=["GET"])
@require_permission("dashboard.view")
def history():
    return res(data=get_history(
        date_from=request.args.get("dateFrom", "").strip() or None,
        date_to=request.args.get("dateTo", "").strip() or None,
        search=request.args.get("search", "").strip() or None,
    ))
