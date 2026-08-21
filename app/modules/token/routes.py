from flask import Blueprint, request, render_template
from flask_jwt_extended import get_jwt_identity, get_jwt
from marshmallow import ValidationError

from ...middleware.permissions import require_permission
from ...utils.helpers import res
from .service import (
    generate_schema, bulk_schema,
    generate_token, generate_bulk,
    get_token, get_token_list, get_batch, void_token,
    get_token_config_dict, set_token_config, reset_token_counter,
    make_qr_b64,
)

bp = Blueprint("token", __name__)


# ── Admin: token config ────────────────────────────────────────────────────

@bp.route("/api/admin/token-config", methods=["GET"])
@require_permission("users.manage")
def token_config_get():
    return res(data={"config": get_token_config_dict()})


@bp.route("/api/admin/token-config", methods=["POST"])
@require_permission("users.manage")
def token_config_set():
    body = request.get_json(silent=True) or {}
    if not body:
        return res("request body is empty", code=400)
    updated = set_token_config(body)
    return res("token config updated", data=updated)


@bp.route("/api/admin/token-config/reset", methods=["POST"])
@require_permission("users.manage")
def token_counter_reset():
    if get_jwt().get("role") != "admin":
        return res("only admin can reset the token counter", code=403)
    start = reset_token_counter()
    return res("token counter reset", data={"nextTokenStartsAt": start})


# ── Generate ───────────────────────────────────────────────────────────────

@bp.route("/api/token/generate", methods=["POST"])
@require_permission("token.generate")
def generate():
    body = request.get_json(silent=True) or {}
    try:
        data = generate_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    user_id = int(get_jwt_identity())
    token = generate_token(data, user_id)
    return res("token generated", data=token.to_dict(), code=201)


@bp.route("/api/token/bulk", methods=["POST"])
@require_permission("token.bulk")
def bulk():
    body = request.get_json(silent=True) or {}
    try:
        data = bulk_schema.load(body)
    except ValidationError as e:
        return res("validation failed", data=e.messages, code=422)

    user_id = int(get_jwt_identity())
    tokens, batch_id = generate_bulk(data["count"], user_id)
    return res("bulk tokens generated", data={
        "batchId": batch_id,
        "count": len(tokens),
        "tokens": [t.to_dict() for t in tokens],
        "printUrl": f"/token/print/bulk/{batch_id}",
    }, code=201)


# ── List & detail ──────────────────────────────────────────────────────────

@bp.route("/api/token/list", methods=["GET"])
@require_permission("token.generate")
def token_list():
    page = int(request.args.get("page", 1))
    batch_id = request.args.get("batchId")
    pagination = get_token_list(page=page, per_page=50, batch_id=batch_id or None)
    return res(data={
        "tokens": [t.to_dict() for t in pagination.items],
        "total": pagination.total,
        "page": page,
        "pages": pagination.pages,
    })


@bp.route("/api/token/<token_no>", methods=["GET"])
@require_permission("token.generate")
def token_detail(token_no):
    token = get_token(token_no.upper())
    if not token:
        return res("token not found", code=404)
    return res(data=token.to_dict())


@bp.route("/api/token/<token_no>/void", methods=["POST"])
@require_permission("users.manage")
def token_void(token_no):
    token = get_token(token_no.upper())
    if not token:
        return res("token not found", code=404)
    token = void_token(token)
    return res("token voided", data=token.to_dict())


# ── Public QR verification page ────────────────────────────────────────────

@bp.route("/token/<token_no>", methods=["GET"])
def token_view(token_no):
    token = get_token(token_no.upper())
    return render_template("token/view.html", token=token, token_no=token_no.upper())


# ── Print pages (no auth — URL contains the token_no / batch_id) ──────────

@bp.route("/token/print/bulk/<batch_id>", methods=["GET"])
def token_print_bulk(batch_id):
    tokens = get_batch(batch_id)
    if not tokens:
        return res("batch not found", code=404)
    base_url = request.host_url.rstrip("/")
    qr_map = {t.token_no: make_qr_b64(f"{base_url}/token/{t.token_no}") for t in tokens}
    return render_template("token/print.html", tokens=tokens, qr_map=qr_map, is_bulk=True)


@bp.route("/token/print/<token_no>", methods=["GET"])
def token_print(token_no):
    token = get_token(token_no.upper())
    if not token:
        return res("token not found", code=404)
    base_url = request.host_url.rstrip("/")
    qr_map = {token.token_no: make_qr_b64(f"{base_url}/token/{token.token_no}")}
    return render_template("token/print.html", tokens=[token], qr_map=qr_map, is_bulk=False)
