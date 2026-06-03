"""
DWDM and machine learning services for the Sales Prediction Capstone project.

The functions in this module cover:
1. Data collection from CSV
2. Data cleaning
3. ETL into MySQL warehouse
4. OLAP-style analytics
5. Data mining model training
6. Real-time predictive analytics
"""

from pathlib import Path
import json
import re

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor

from database import (
    fetch_model_metrics,
    fetch_sales_dataframe,
    get_sales_record_count,
    init_database,
    insert_sales_records,
    save_model_metrics,
)


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "Sample - Superstore.csv"
MODEL_DIR = BASE_DIR / "models"
STATIC_IMAGE_DIR = BASE_DIR / "static" / "images"
BEST_MODEL_PATH = MODEL_DIR / "best_sales_model.pkl"
METADATA_PATH = MODEL_DIR / "model_metadata.json"


MODEL_FACTORIES = {
    "Linear Regression": LinearRegression,
    "Decision Tree Regressor": lambda: DecisionTreeRegressor(
        random_state=42,
        max_depth=8,
    ),
    "Random Forest Regressor": lambda: RandomForestRegressor(
        n_estimators=120,
        random_state=42,
        max_depth=12,
    ),
}


def clean_column_name(name):
    """Convert CSV column names such as 'Order Date' into 'order_date'."""
    cleaned = name.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    return cleaned.strip("_")


def load_and_clean_csv(csv_path=CSV_PATH):
    """Read and clean the Superstore CSV file using Pandas."""
    df = pd.read_csv(csv_path, encoding="latin1")
    df.columns = [clean_column_name(column) for column in df.columns]

    required_columns = {
        "row_id",
        "order_id",
        "order_date",
        "ship_date",
        "region",
        "category",
        "sub_category",
        "product_name",
        "sales",
        "quantity",
        "discount",
        "profit",
    }
    missing = required_columns.difference(df.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"CSV file is missing required columns: {missing_text}")

    df = df.drop_duplicates(subset=["row_id"]).copy()
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["ship_date"] = pd.to_datetime(df["ship_date"], errors="coerce")

    numeric_columns = ["sales", "quantity", "discount", "profit"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    categorical_columns = [
        "order_id",
        "ship_mode",
        "customer_id",
        "customer_name",
        "segment",
        "country",
        "city",
        "state",
        "postal_code",
        "region",
        "product_id",
        "category",
        "sub_category",
        "product_name",
    ]
    for column in categorical_columns:
        if column not in df.columns:
            df[column] = "Unknown"
        df[column] = df[column].fillna("Unknown").astype(str).str.strip()

    df["sales_year"] = df["order_date"].dt.year.fillna(0).astype(int)
    df["sales_month"] = df["order_date"].dt.month.fillna(0).astype(int)
    df["month_name"] = df["order_date"].dt.month_name().fillna("Unknown")
    df["quarter_name"] = "Q" + df["order_date"].dt.quarter.fillna(0).astype(int).astype(str)
    df.loc[df["quarter_name"] == "Q0", "quarter_name"] = "Unknown"
    return df


def _to_date(value):
    if pd.isna(value):
        return None
    return value.date()


def etl_to_datawarehouse(replace=False):
    """Execute the ETL process and load records into the MySQL warehouse."""
    init_database()
    if get_sales_record_count() > 0 and not replace:
        return {"loaded": False, "message": "Warehouse already contains sales records."}

    df = load_and_clean_csv()
    records = []
    for _, row in df.iterrows():
        records.append(
            {
                "row_id": int(row["row_id"]),
                "order_id": row["order_id"],
                "order_date": _to_date(row["order_date"]),
                "ship_date": _to_date(row["ship_date"]),
                "ship_mode": row["ship_mode"],
                "customer_id": row["customer_id"],
                "customer_name": row["customer_name"],
                "segment": row["segment"],
                "country": row["country"],
                "city": row["city"],
                "state": row["state"],
                "postal_code": row["postal_code"],
                "region": row["region"],
                "product_id": row["product_id"],
                "category": row["category"],
                "sub_category": row["sub_category"],
                "product_name": row["product_name"],
                "sales": float(row["sales"]),
                "quantity": int(row["quantity"]),
                "discount": float(row["discount"]),
                "profit": float(row["profit"]),
                "sales_year": int(row["sales_year"]),
                "sales_month": int(row["sales_month"]),
                "month_name": row["month_name"],
                "quarter_name": row["quarter_name"],
            }
        )

    insert_sales_records(records, replace=replace)
    return {"loaded": True, "message": f"Loaded {len(records)} records into MySQL warehouse."}


def _normalize_numeric_columns(df):
    for column in ["sales", "quantity", "discount", "profit"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
    return df


def get_training_dataframe():
    """Prefer the MySQL warehouse, then fall back to the CSV dataset."""
    try:
        if get_sales_record_count() > 0:
            df = fetch_sales_dataframe()
            if not df.empty:
                return _normalize_numeric_columns(df)
    except Exception:
        pass
    return load_and_clean_csv()


def train_models():
    """Train and compare Linear Regression, Decision Tree, and Random Forest."""
    MODEL_DIR.mkdir(exist_ok=True)
    df = get_training_dataframe()
    df = _normalize_numeric_columns(df)

    features = df[["quantity", "discount", "profit"]]
    target = df["sales"]

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.2,
        random_state=42,
    )

    metrics = []
    best_model = None
    best_score = float("-inf")
    best_model_name = None

    for model_name, factory in MODEL_FACTORIES.items():
        model = factory()
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)

        mae = mean_absolute_error(y_test, predictions)
        rmse = mean_squared_error(y_test, predictions) ** 0.5
        r2 = r2_score(y_test, predictions)
        accuracy_percentage = max(0, min(100, r2 * 100))

        model_file = MODEL_DIR / f"{clean_column_name(model_name)}.pkl"
        joblib.dump(model, model_file)

        metrics.append(
            {
                "model_name": model_name,
                "mae": round(float(mae), 4),
                "rmse": round(float(rmse), 4),
                "r2_score": round(float(r2), 6),
                "accuracy_percentage": round(float(accuracy_percentage), 4),
            }
        )

        if r2 > best_score:
            best_score = r2
            best_model = model
            best_model_name = model_name

    joblib.dump(best_model, BEST_MODEL_PATH)
    METADATA_PATH.write_text(
        json.dumps(
            {
                "best_model_name": best_model_name,
                "features": ["quantity", "discount", "profit"],
                "target": "sales",
                "metrics": metrics,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    try:
        save_model_metrics(metrics)
    except Exception:
        pass

    return metrics


def get_model_metrics():
    """Fetch model metrics from MySQL, training models if needed."""
    try:
        metrics = fetch_model_metrics()
        if metrics:
            return metrics
    except Exception:
        pass
    return train_models()


def _load_model_by_name(model_name):
    if model_name:
        model_file = MODEL_DIR / f"{clean_column_name(model_name)}.pkl"
        if model_file.exists():
            return joblib.load(model_file), model_name

    if not BEST_MODEL_PATH.exists():
        train_models()

    selected_name = "Best Model"
    if METADATA_PATH.exists():
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        selected_name = metadata.get("best_model_name", selected_name)
    return joblib.load(BEST_MODEL_PATH), selected_name


def predict_sales(quantity, discount, profit, model_name=None):
    """Predict sales for a real-time user input."""
    model, selected_model_name = _load_model_by_name(model_name)
    input_frame = pd.DataFrame(
        [
            {
                "quantity": int(quantity),
                "discount": float(discount),
                "profit": float(profit),
            }
        ]
    )
    prediction = float(model.predict(input_frame)[0])
    return round(max(0, prediction), 2), selected_model_name


def _get_analysis_dataframe():
    df = get_training_dataframe()
    df = _normalize_numeric_columns(df)
    if "order_date" in df.columns:
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    if "sales_year" not in df.columns or "sales_month" not in df.columns:
        df["sales_year"] = df["order_date"].dt.year.fillna(0).astype(int)
        df["sales_month"] = df["order_date"].dt.month.fillna(0).astype(int)
    df["year_month"] = df["order_date"].dt.to_period("M").astype(str)
    df.loc[df["year_month"] == "NaT", "year_month"] = "Unknown"
    return df


def build_analytics_payload():
    """Create OLAP-style aggregations used by the dashboard charts."""
    df = _get_analysis_dataframe()

    monthly = (
        df[df["year_month"] != "Unknown"]
        .groupby("year_month", as_index=False)
        .agg({"sales": "sum", "profit": "sum"})
        .sort_values("year_month")
    )

    region_sales = (
        df.groupby("region", as_index=False)["sales"].sum().sort_values("sales", ascending=False)
    )
    category_sales = (
        df.groupby("category", as_index=False)
        .agg({"sales": "sum", "profit": "sum"})
        .sort_values("sales", ascending=False)
    )
    top_products = (
        df.groupby("product_name", as_index=False)["sales"]
        .sum()
        .sort_values("sales", ascending=False)
        .head(10)
    )

    total_sales = float(df["sales"].sum())
    total_profit = float(df["profit"].sum())
    total_orders = int(df["order_id"].nunique()) if "order_id" in df.columns else int(len(df))
    average_order_value = round(total_sales / total_orders, 2) if total_orders else 0

    return {
        "kpis": {
            "total_sales": round(total_sales, 2),
            "total_profit": round(total_profit, 2),
            "total_orders": total_orders,
            "average_order_value": average_order_value,
            "record_count": int(len(df)),
        },
        "monthly_sales": {
            "labels": monthly["year_month"].tolist(),
            "values": [round(float(value), 2) for value in monthly["sales"]],
        },
        "monthly_profit": {
            "labels": monthly["year_month"].tolist(),
            "values": [round(float(value), 2) for value in monthly["profit"]],
        },
        "region_sales": {
            "labels": region_sales["region"].tolist(),
            "values": [round(float(value), 2) for value in region_sales["sales"]],
        },
        "category_performance": {
            "labels": category_sales["category"].tolist(),
            "sales": [round(float(value), 2) for value in category_sales["sales"]],
            "profit": [round(float(value), 2) for value in category_sales["profit"]],
        },
        "top_products": {
            "labels": top_products["product_name"].tolist(),
            "values": [round(float(value), 2) for value in top_products["sales"]],
        },
    }


def generate_report_images():
    """Create Matplotlib report images for the reports section."""
    STATIC_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    metrics = get_model_metrics()
    df = _get_analysis_dataframe()

    metrics_df = pd.DataFrame(metrics)
    if not metrics_df.empty:
        plt.figure(figsize=(8, 4.8))
        plt.bar(
            metrics_df["model_name"],
            pd.to_numeric(metrics_df["accuracy_percentage"], errors="coerce"),
            color=["#3b82f6", "#14b8a6", "#f97316"],
        )
        plt.title("Model Accuracy Comparison")
        plt.ylabel("Accuracy Percentage")
        plt.xticks(rotation=12, ha="right")
        plt.tight_layout()
        plt.savefig(STATIC_IMAGE_DIR / "model_comparison.png", dpi=140)
        plt.close()

    monthly = (
        df[df["year_month"] != "Unknown"]
        .groupby("year_month", as_index=False)
        .agg({"sales": "sum", "profit": "sum"})
        .sort_values("year_month")
    )
    if not monthly.empty:
        plt.figure(figsize=(10, 4.8))
        plt.plot(monthly["year_month"], monthly["sales"], marker="o", label="Sales")
        plt.plot(monthly["year_month"], monthly["profit"], marker="s", label="Profit")
        plt.title("Monthly Sales and Profit Trend")
        plt.ylabel("Amount")
        plt.xticks(rotation=45, ha="right")
        plt.legend()
        plt.tight_layout()
        plt.savefig(STATIC_IMAGE_DIR / "monthly_sales_report.png", dpi=140)
        plt.close()

    category_profit = (
        df.groupby("category", as_index=False)["profit"]
        .sum()
        .sort_values("profit", ascending=False)
    )
    if not category_profit.empty:
        plt.figure(figsize=(7, 4.8))
        plt.bar(category_profit["category"], category_profit["profit"], color="#0f766e")
        plt.title("Profit by Category")
        plt.ylabel("Profit")
        plt.tight_layout()
        plt.savefig(STATIC_IMAGE_DIR / "category_profit_report.png", dpi=140)
        plt.close()
