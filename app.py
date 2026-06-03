"""
Flask backend for the DWDM Sales Prediction and Analysis Platform.

Run this file from VS Code or terminal:
    python app.py
"""

from functools import wraps
from io import StringIO
from decimal import Decimal

import pandas as pd
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
    create_user,
    delete_user,
    fetch_model_metrics,
    fetch_prediction_history,
    fetch_prediction_history_for_export,
    fetch_sales_records_for_export,
    get_all_users,
    get_user_by_email,
    get_user_by_id,
    init_database,
    save_prediction,
    update_user_role,
)
from model import (
    MODEL_FACTORIES,
    build_analytics_payload,
    etl_to_datawarehouse,
    generate_report_images,
    get_model_metrics,
    predict_sales,
    train_models,
)


app = Flask(__name__)
app.secret_key = "change-this-secret-key-for-production"
app.config["BOOTSTRAPPED"] = False
app.config["STARTUP_ERROR"] = None


def bootstrap_project():
    """Prepare database, ETL data warehouse, train models, and report images."""
    init_database()
    etl_to_datawarehouse(replace=False)
    train_models()
    generate_report_images()


@app.before_request
def ensure_project_ready():
    """Run setup once before the first real page request."""
    if request.endpoint == "static":
        return
    if not app.config["BOOTSTRAPPED"]:
        try:
            bootstrap_project()
            app.config["BOOTSTRAPPED"] = True
            app.config["STARTUP_ERROR"] = None
        except Exception as exc:
            app.config["STARTUP_ERROR"] = str(exc)


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


def login_required(view_function):
    @wraps(view_function)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)

    return wrapper


def admin_required(view_function):
    @wraps(view_function)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user["role"] != "admin":
            flash("Admin access is required for this action.", "danger")
            return redirect(url_for("dashboard"))
        return view_function(*args, **kwargs)

    return wrapper


def to_plain_value(value):
    """Make MySQL Decimal and date objects JSON/CSV friendly."""
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def normalize_rows(rows):
    return [{key: to_plain_value(value) for key, value in row.items()} for row in rows]


@app.context_processor
def inject_global_template_data():
    return {
        "logged_in_user": current_user() if session.get("user_id") else None,
        "startup_error": app.config.get("STARTUP_ERROR"),
        "model_names": list(MODEL_FACTORIES.keys()),
    }


@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if app.config.get("STARTUP_ERROR"):
            flash("Database setup failed. Check MySQL settings before registering.", "danger")
            return render_template("register.html")

        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")
        if get_user_by_email(email):
            flash("This email is already registered.", "warning")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        user_id, role = create_user(full_name, email, password_hash)
        session["user_id"] = user_id
        session["user_role"] = role
        flash(f"Registration successful. Your role is {role}.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if app.config.get("STARTUP_ERROR"):
            flash("Database setup failed. Check MySQL settings before logging in.", "danger")
            return render_template("login.html")

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_user_by_email(email)

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_role"] = user["role"]
            flash("Welcome back.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    analytics = build_analytics_payload()
    user = current_user()
    users = get_all_users() if user["role"] == "admin" else []
    history = fetch_prediction_history(
        user_id=user["id"],
        include_all=user["role"] == "admin",
        limit=10,
    )
    return render_template(
        "dashboard.html",
        analytics=analytics,
        users=users,
        prediction_history=history,
    )


@app.route("/prediction", methods=["GET", "POST"])
@login_required
def prediction():
    result = None
    user = current_user()

    if request.method == "POST":
        try:
            quantity = int(request.form.get("quantity", 0))
            discount = float(request.form.get("discount", 0))
            profit = float(request.form.get("profit", 0))
            model_name = request.form.get("model_name") or None
            predicted_sales, selected_model = predict_sales(
                quantity,
                discount,
                profit,
                model_name,
            )
            save_prediction(
                user["id"],
                quantity,
                discount,
                profit,
                selected_model,
                predicted_sales,
            )
            result = {
                "predicted_sales": predicted_sales,
                "model_name": selected_model,
            }
            flash("Prediction completed successfully.", "success")
        except Exception as exc:
            flash(f"Prediction failed: {exc}", "danger")

    history = fetch_prediction_history(user_id=user["id"], limit=15)
    return render_template(
        "prediction.html",
        result=result,
        prediction_history=history,
    )


@app.route("/reports")
@login_required
def reports():
    generate_report_images()
    metrics = get_model_metrics()
    analytics = build_analytics_payload()
    user = current_user()
    history = fetch_prediction_history(
        user_id=user["id"],
        include_all=user["role"] == "admin",
        limit=10,
    )
    return render_template(
        "reports.html",
        metrics=metrics,
        analytics=analytics,
        prediction_history=history,
    )


@app.route("/api/analytics")
@login_required
def api_analytics():
    return jsonify(build_analytics_payload())


@app.route("/api/model-metrics")
@login_required
def api_model_metrics():
    metrics = fetch_model_metrics() or get_model_metrics()
    return jsonify(normalize_rows(metrics))


@app.route("/api/predict", methods=["POST"])
@login_required
def api_predict():
    data = request.get_json(silent=True) or request.form
    quantity = int(data.get("quantity", 0))
    discount = float(data.get("discount", 0))
    profit = float(data.get("profit", 0))
    model_name = data.get("model_name") or None

    predicted_sales, selected_model = predict_sales(quantity, discount, profit, model_name)
    user = current_user()
    save_prediction(
        user["id"],
        quantity,
        discount,
        profit,
        selected_model,
        predicted_sales,
    )
    return jsonify(
        {
            "predicted_sales": predicted_sales,
            "model_name": selected_model,
            "quantity": quantity,
            "discount": discount,
            "profit": profit,
        }
    )


@app.route("/admin/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def admin_update_role(user_id):
    role = request.form.get("role")
    if role not in {"admin", "user"}:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("dashboard"))
    update_user_role(user_id, role)
    flash("User role updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_delete_user(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot delete your own account while logged in.", "warning")
        return redirect(url_for("dashboard"))
    delete_user(user_id)
    flash("User deleted.", "success")
    return redirect(url_for("dashboard"))


def dataframe_csv_response(rows, filename):
    normalized = normalize_rows(rows)
    csv_buffer = StringIO()
    pd.DataFrame(normalized).to_csv(csv_buffer, index=False)
    return Response(
        csv_buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/export/sales.csv")
@login_required
def export_sales_csv():
    rows = fetch_sales_records_for_export()
    return dataframe_csv_response(rows, "superstore_sales_records.csv")


@app.route("/export/predictions.csv")
@login_required
def export_predictions_csv():
    user = current_user()
    rows = fetch_prediction_history_for_export(
        user_id=user["id"],
        include_all=user["role"] == "admin",
    )
    return dataframe_csv_response(rows, "prediction_history.csv")


@app.route("/download/analytics-report")
@login_required
def download_analytics_report():
    analytics = build_analytics_payload()
    rows = [
        {"section": "KPI", "metric": key, "value": value}
        for key, value in analytics["kpis"].items()
    ]

    for label, value in zip(
        analytics["region_sales"]["labels"],
        analytics["region_sales"]["values"],
    ):
        rows.append({"section": "Region Sales", "metric": label, "value": value})

    for label, sales, profit in zip(
        analytics["category_performance"]["labels"],
        analytics["category_performance"]["sales"],
        analytics["category_performance"]["profit"],
    ):
        rows.append({"section": "Category Sales", "metric": label, "value": sales})
        rows.append({"section": "Category Profit", "metric": label, "value": profit})

    for label, value in zip(
        analytics["top_products"]["labels"],
        analytics["top_products"]["values"],
    ):
        rows.append({"section": "Top Products", "metric": label, "value": value})

    return dataframe_csv_response(rows, "analytics_summary_report.csv")


if __name__ == "__main__":
    app.run(debug=True)
