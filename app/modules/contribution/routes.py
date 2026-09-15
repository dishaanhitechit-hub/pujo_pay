import os
import traceback
from flask import Blueprint, request, send_file, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity

from ...utils.helpers import res
from ...middleware.permissions import require_permission
from .service import (
    get_payment_info,
    submit_contribution,
    list_my_contributions,
    get_my_stats,
    admin_list_contributions,
    admin_review_contribution,
    get_screenshot_path,
    admin_stats,
)

bp = Blueprint("contribution", __name__)


def _auth():
    """Verify JWT and return (user_id, role)."""
    verify_jwt_in_request()
    claims = get_jwt()
    return int(get_jwt_identity()), claims.get("role", "")


# ── Payment info (any authenticated user) ────────────────────────────────

@bp.route("/payment-info", methods=["GET"])
def payment_info():
    _auth()
    return res(data=get_payment_info())


# ── Member: submit ────────────────────────────────────────────────────────

@bp.route("/", methods=["POST"])
def submit():
    user_id, role = _auth()
    if role == "admin":
        return res("admin accounts cannot submit contributions", code=403)

    file    = request.files.get("screenshot")
    mime    = file.mimetype if file and file.filename else None
    fileobj = file if file and file.filename else None

    data = request.form

    try:
        result, err = submit_contribution(
            user_id=user_id,
            amount=data.get("amount"),
            payment_method=data.get("paymentMethod"),
            payment_date=data.get("paymentDate"),
            payment_time=data.get("paymentTime") or None,
            note=data.get("note") or None,
            event_id=int(data["eventId"]) if data.get("eventId") else None,
            fileobj=fileobj,
            mime_type=mime,
            media_root=current_app.config["MEDIA_STORAGE_PATH"],
        )
    except Exception as exc:
        current_app.logger.error("submit_contribution crashed: %s", traceback.format_exc())
        return res(f"Unexpected error: {exc}", code=500)

    if err:
        return res(err, code=400)
    return res("contribution submitted — pending approval", data=result, code=201)


# ── Member: my list ───────────────────────────────────────────────────────

@bp.route("/me", methods=["GET"])
def my_list():
    user_id, _ = _auth()
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("perPage", 10, type=int)
    return res(data=list_my_contributions(user_id, page, per_page))


# ── Member: my stats ─────────────────────────────────────────────────────

@bp.route("/me/stats", methods=["GET"])
def my_stats():
    user_id, _ = _auth()
    return res(data=get_my_stats(user_id))


# ── Screenshot (owner or admin) ───────────────────────────────────────────

@bp.route("/screenshot/<int:contribution_id>", methods=["GET"])
def screenshot(contribution_id: int):
    user_id, role = _auth()
    is_admin = role == "admin"

    rel_path, err = get_screenshot_path(contribution_id, user_id, is_admin)
    if err == "forbidden":
        return res("forbidden", code=403)
    if err:
        return res(err, code=404)

    media_root = current_app.config["MEDIA_STORAGE_PATH"]
    abs_path = os.path.realpath(os.path.join(media_root, rel_path))
    real_root = os.path.realpath(media_root)

    if not abs_path.startswith(real_root + os.sep) or not os.path.isfile(abs_path):
        return res("file not found", code=404)

    return send_file(abs_path)


# ── Admin: list all ───────────────────────────────────────────────────────

@bp.route("/admin", methods=["GET"])
@require_permission("contribution.manage")
def admin_list():
    return res(data=admin_list_contributions(
        status=request.args.get("status"),
        user_id=request.args.get("userId", type=int),
        event_id=request.args.get("eventId", type=int),
        page=request.args.get("page", 1, type=int),
        per_page=request.args.get("perPage", 20, type=int),
    ))


# ── Admin: approve / reject ───────────────────────────────────────────────

@bp.route("/admin/<int:contribution_id>/review", methods=["PATCH"])
@require_permission("contribution.manage")
def admin_review(contribution_id: int):
    body = request.get_json(silent=True) or {}
    action     = body.get("action")     # "approve" | "reject"
    admin_note = body.get("adminNote")

    verify_jwt_in_request()
    reviewer_id = int(get_jwt_identity())

    result, err = admin_review_contribution(contribution_id, action, reviewer_id, admin_note)
    if err:
        return res(err, code=400 if "not found" not in err else 404)
    return res(f"contribution {action}d", data=result)


# ── Admin: aggregate stats ────────────────────────────────────────────────

@bp.route("/admin/stats", methods=["GET"])
@require_permission("contribution.manage")
def admin_aggregate():
    return res(data=admin_stats())
