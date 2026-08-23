import uuid
from datetime import timedelta
from flask import (
    Blueprint, render_template, request,
    make_response, jsonify, Response,
)

_IST = timedelta(hours=5, minutes=30)

from .service import (
    get_or_create_today_session,
    reset_session,
    get_session_by_token,
    get_today_sessions,
    submit_attendance,
    generate_qr_png,
    get_today_records,
)

bp = Blueprint("test_feature", __name__)


@bp.app_template_filter("to_ist")
def _to_ist(dt, fmt="%d %b %Y, %I:%M %p"):
    if not dt:
        return "—"
    return (dt + _IST).strftime(fmt)

_COOKIE = "atd_dev"
_COOKIE_AGE = 30 * 24 * 3600  # 30 days


# ── Attendance (attendee-facing) ────────────────────────────────────────────

@bp.route("/attend", methods=["GET"])
def attend_form():
    token = request.args.get("token", "").strip()
    if not token:
        return render_template("test_feature/already.html", reason="invalid_link"), 400

    session = get_session_by_token(token)
    if not session:
        return render_template("test_feature/already.html", reason="expired"), 400

    existing_fp = request.cookies.get(_COOKIE)
    new_fp = existing_fp or uuid.uuid4().hex

    resp = make_response(render_template("test_feature/attend.html", token=token, session=session))
    if not existing_fp:
        resp.set_cookie(_COOKIE, new_fp, max_age=_COOKIE_AGE, httponly=True, samesite="Lax")
    return resp


@bp.route("/attend", methods=["POST"])
def attend_submit():
    token   = request.form.get("token", "").strip()
    name    = (request.form.get("name") or "").strip()
    phone   = (request.form.get("phone") or "").strip()
    address = (request.form.get("address") or "").strip() or None

    if not token or not name or not phone:
        return render_template("test_feature/already.html", reason="invalid_data"), 400

    session = get_session_by_token(token)
    if not session:
        return render_template("test_feature/already.html", reason="expired"), 400

    device_fp = request.cookies.get(_COOKIE)
    record, err = submit_attendance(session, name, phone, address, device_fp, request.remote_addr)
    if err:
        return render_template("test_feature/already.html", reason=err), 409

    return render_template("test_feature/success.html", record=record, session=session)


# ── Admin (control panel) ───────────────────────────────────────────────────

@bp.route("/admin", methods=["GET"])
def admin():
    session = get_or_create_today_session()
    sessions = get_today_sessions()
    return render_template("test_feature/admin.html", session=session, sessions=sessions)


@bp.route("/admin/qr-image", methods=["GET"])
def admin_qr_image():
    session = get_or_create_today_session()
    base_url = request.host_url.rstrip("/")
    attend_url = f"{base_url}/test/attend?token={session.qr_token}"
    png = generate_qr_png(attend_url)
    return Response(png, mimetype="image/png",
                    headers={"Cache-Control": "no-store"})


@bp.route("/admin/reset", methods=["POST"])
def admin_reset():
    new_session = reset_session()
    return jsonify({"ok": True, "session": new_session.to_dict()})


@bp.route("/admin/records", methods=["GET"])
def admin_records():
    return jsonify({"records": get_today_records()})
