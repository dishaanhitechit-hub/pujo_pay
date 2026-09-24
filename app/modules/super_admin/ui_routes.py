from flask import Blueprint, render_template

ui_bp = Blueprint("super_admin_ui", __name__)


@ui_bp.route("/super-admin")
def super_admin_dashboard():
    return render_template("super_admin/dashboard.html")
