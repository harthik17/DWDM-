"""
Database helper module for the Sales Prediction Capstone project.

This file centralizes all database operations used by the Flask application,
ETL process, analytics reports, prediction history, and admin screens.
Supports MySQL and automatically falls back to SQLite if MySQL is unavailable.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import mysql.connector
import pandas as pd
from dotenv import load_dotenv


load_dotenv()

DATABASE_NAME = os.getenv("MYSQL_DATABASE", "sales_prediction_dw")

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
}

_USE_SQLITE = None

def use_sqlite():
    global _USE_SQLITE
    if _USE_SQLITE is None:
        try:
            # Quick check if MySQL port is open to avoid long timeouts
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect((MYSQL_CONFIG["host"], MYSQL_CONFIG["port"]))
            s.close()
            # Port is open, test connection
            conn = mysql.connector.connect(**MYSQL_CONFIG)
            conn.close()
            _USE_SQLITE = False
        except Exception:
            _USE_SQLITE = True
            print("MySQL connection failed/unavailable. Using SQLite fallback (sales_warehouse.db).")
    return _USE_SQLITE


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class SQLiteCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, sql, params=None):
        sql = sql.replace("%s", "?")
        if params is not None:
            return self.cursor.execute(sql, params)
        return self.cursor.execute(sql)

    def executemany(self, sql, seq_of_parameters):
        sql = sql.replace("%s", "?")
        return self.cursor.executemany(sql, seq_of_parameters)

    def __getattr__(self, name):
        return getattr(self.cursor, name)


def create_database_if_needed():
    """Create the project database if it does not already exist."""
    if use_sqlite():
        return
    connection = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = connection.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DATABASE_NAME}`")
    cursor.close()
    connection.close()


def get_connection(dictionary=False):
    """Return a database connection for the project."""
    if use_sqlite():
        conn = sqlite3.connect("sales_warehouse.db")
        if dictionary:
            conn.row_factory = dict_factory
        return conn

    create_database_if_needed()
    return mysql.connector.connect(
        **MYSQL_CONFIG,
        database=DATABASE_NAME,
    )


@contextmanager
def get_cursor(dictionary=False, commit=False):
    """Open a cursor and close it safely after the operation."""
    connection = get_connection(dictionary=dictionary)
    if use_sqlite():
        raw_cursor = connection.cursor()
        cursor = SQLiteCursorWrapper(raw_cursor)
    else:
        cursor = connection.cursor(dictionary=dictionary)
    try:
        yield cursor
        if commit:
            connection.commit()
    finally:
        cursor.close()
        connection.close()


def init_database():
    """Create all tables required by the application."""
    create_database_if_needed()
    with get_cursor(commit=True) as cursor:
        if use_sqlite():
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name VARCHAR(120) NOT NULL,
                    email VARCHAR(160) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sales_records (
                    row_id INT PRIMARY KEY,
                    order_id VARCHAR(40),
                    order_date DATE,
                    ship_date DATE,
                    ship_mode VARCHAR(80),
                    customer_id VARCHAR(40),
                    customer_name VARCHAR(160),
                    segment VARCHAR(80),
                    country VARCHAR(80),
                    city VARCHAR(100),
                    state VARCHAR(100),
                    postal_code VARCHAR(30),
                    region VARCHAR(80),
                    product_id VARCHAR(80),
                    category VARCHAR(80),
                    sub_category VARCHAR(80),
                    product_name TEXT,
                    sales DECIMAL(14, 4),
                    quantity INT,
                    discount DECIMAL(8, 4),
                    profit DECIMAL(14, 4),
                    sales_year INT,
                    sales_month INT,
                    month_name VARCHAR(20),
                    quarter_name VARCHAR(10),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_date ON sales_records (order_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_region ON sales_records (region)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON sales_records (category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_id ON sales_records (product_id)")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS prediction_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    quantity INT NOT NULL,
                    discount DECIMAL(8, 4) NOT NULL,
                    profit DECIMAL(14, 4) NOT NULL,
                    model_name VARCHAR(80) NOT NULL,
                    predicted_sales DECIMAL(14, 4) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS model_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name VARCHAR(80) NOT NULL UNIQUE,
                    mae DECIMAL(14, 4) NOT NULL,
                    rmse DECIMAL(14, 4) NOT NULL,
                    r2_score DECIMAL(10, 6) NOT NULL,
                    accuracy_percentage DECIMAL(10, 4) NOT NULL,
                    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        else:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    full_name VARCHAR(120) NOT NULL,
                    email VARCHAR(160) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role ENUM('admin', 'user') NOT NULL DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sales_records (
                    row_id INT PRIMARY KEY,
                    order_id VARCHAR(40),
                    order_date DATE,
                    ship_date DATE,
                    ship_mode VARCHAR(80),
                    customer_id VARCHAR(40),
                    customer_name VARCHAR(160),
                    segment VARCHAR(80),
                    country VARCHAR(80),
                    city VARCHAR(100),
                    state VARCHAR(100),
                    postal_code VARCHAR(30),
                    region VARCHAR(80),
                    product_id VARCHAR(80),
                    category VARCHAR(80),
                    sub_category VARCHAR(80),
                    product_name TEXT,
                    sales DECIMAL(14, 4),
                    quantity INT,
                    discount DECIMAL(8, 4),
                    profit DECIMAL(14, 4),
                    sales_year INT,
                    sales_month INT,
                    month_name VARCHAR(20),
                    quarter_name VARCHAR(10),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_order_date (order_date),
                    INDEX idx_region (region),
                    INDEX idx_category (category),
                    INDEX idx_product_id (product_id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS prediction_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    quantity INT NOT NULL,
                    discount DECIMAL(8, 4) NOT NULL,
                    profit DECIMAL(14, 4) NOT NULL,
                    model_name VARCHAR(80) NOT NULL,
                    predicted_sales DECIMAL(14, 4) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS model_metrics (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    model_name VARCHAR(80) NOT NULL UNIQUE,
                    mae DECIMAL(14, 4) NOT NULL,
                    rmse DECIMAL(14, 4) NOT NULL,
                    r2_score DECIMAL(10, 6) NOT NULL,
                    accuracy_percentage DECIMAL(10, 4) NOT NULL,
                    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
                )
                """
            )


def get_user_count():
    with get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM users")
        return int(cursor.fetchone()[0])


def create_user(full_name, email, password_hash, role=None):
    """Create a new user. The first registered user becomes admin."""
    selected_role = role or ("admin" if get_user_count() == 0 else "user")
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO users (full_name, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            """,
            (full_name, email.lower().strip(), password_hash, selected_role),
        )
        return cursor.lastrowid, selected_role


def get_user_by_email(email):
    with get_cursor(dictionary=True) as cursor:
        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email.lower().strip(),),
        )
        return cursor.fetchone()


def get_user_by_id(user_id):
    with get_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()


def get_all_users():
    with get_cursor(dictionary=True) as cursor:
        cursor.execute(
            """
            SELECT id, full_name, email, role, created_at
            FROM users
            ORDER BY created_at DESC
            """
        )
        return cursor.fetchall()


def update_user_role(user_id, role):
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            "UPDATE users SET role = %s WHERE id = %s",
            (role, user_id),
        )


def delete_user(user_id):
    with get_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))


def get_sales_record_count():
    with get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM sales_records")
        return int(cursor.fetchone()[0])


def insert_sales_records(records, replace=False):
    """Insert cleaned Superstore records into the warehouse fact table."""
    if replace:
        with get_cursor(commit=True) as cursor:
            cursor.execute("DELETE FROM sales_records")

    if use_sqlite():
        query = """
            INSERT OR REPLACE INTO sales_records (
                row_id, order_id, order_date, ship_date, ship_mode, customer_id,
                customer_name, segment, country, city, state, postal_code, region,
                product_id, category, sub_category, product_name, sales, quantity,
                discount, profit, sales_year, sales_month, month_name, quarter_name
            )
            VALUES (
                :row_id, :order_id, :order_date, :ship_date,
                :ship_mode, :customer_id, :customer_name, :segment,
                :country, :city, :state, :postal_code, :region,
                :product_id, :category, :sub_category, :product_name,
                :sales, :quantity, :discount, :profit, :sales_year,
                :sales_month, :month_name, :quarter_name
            )
        """
        with get_cursor(commit=True) as cursor:
            cursor.executemany(query, records)
    else:
        query = """
            INSERT INTO sales_records (
                row_id, order_id, order_date, ship_date, ship_mode, customer_id,
                customer_name, segment, country, city, state, postal_code, region,
                product_id, category, sub_category, product_name, sales, quantity,
                discount, profit, sales_year, sales_month, month_name, quarter_name
            )
            VALUES (
                %(row_id)s, %(order_id)s, %(order_date)s, %(ship_date)s,
                %(ship_mode)s, %(customer_id)s, %(customer_name)s, %(segment)s,
                %(country)s, %(city)s, %(state)s, %(postal_code)s, %(region)s,
                %(product_id)s, %(category)s, %(sub_category)s, %(product_name)s,
                %(sales)s, %(quantity)s, %(discount)s, %(profit)s, %(sales_year)s,
                %(sales_month)s, %(month_name)s, %(quarter_name)s
            )
            ON DUPLICATE KEY UPDATE
                sales = VALUES(sales),
                quantity = VALUES(quantity),
                discount = VALUES(discount),
                profit = VALUES(profit),
                sales_year = VALUES(sales_year),
                sales_month = VALUES(sales_month),
                month_name = VALUES(month_name),
                quarter_name = VALUES(quarter_name)
        """
        with get_cursor(commit=True) as cursor:
            cursor.executemany(query, records)


def fetch_sales_dataframe():
    """Load warehouse data into a Pandas DataFrame for OLAP analysis."""
    with get_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM sales_records")
        rows = cursor.fetchall()
    return pd.DataFrame(rows)


def fetch_sales_records_for_export():
    with get_cursor(dictionary=True) as cursor:
        cursor.execute(
            """
            SELECT row_id, order_id, order_date, ship_date, ship_mode,
                   customer_id, customer_name, segment, country, city, state,
                   postal_code, region, product_id, category, sub_category,
                   product_name, sales, quantity, discount, profit,
                   sales_year, sales_month, month_name, quarter_name
            FROM sales_records
            ORDER BY row_id
            """
        )
        return cursor.fetchall()


def save_prediction(user_id, quantity, discount, profit, model_name, predicted_sales):
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO prediction_history (
                user_id, quantity, discount, profit, model_name, predicted_sales
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, quantity, discount, profit, model_name, predicted_sales),
        )


def fetch_prediction_history(user_id=None, include_all=False, limit=25):
    params = []
    where_clause = ""
    if user_id and not include_all:
        where_clause = "WHERE ph.user_id = %s"
        params.append(user_id)

    params.append(limit)
    with get_cursor(dictionary=True) as cursor:
        cursor.execute(
            f"""
            SELECT ph.id, ph.quantity, ph.discount, ph.profit, ph.model_name,
                   ph.predicted_sales, ph.created_at,
                   COALESCE(u.full_name, 'Deleted User') AS full_name,
                   COALESCE(u.email, '-') AS email
            FROM prediction_history ph
            LEFT JOIN users u ON ph.user_id = u.id
            {where_clause}
            ORDER BY ph.created_at DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return cursor.fetchall()


def fetch_prediction_history_for_export(user_id=None, include_all=False):
    params = []
    where_clause = ""
    if user_id and not include_all:
        where_clause = "WHERE ph.user_id = %s"
        params.append(user_id)

    with get_cursor(dictionary=True) as cursor:
        cursor.execute(
            f"""
            SELECT ph.id, COALESCE(u.full_name, 'Deleted User') AS full_name,
                   COALESCE(u.email, '-') AS email, ph.quantity, ph.discount,
                   ph.profit, ph.model_name, ph.predicted_sales, ph.created_at
            FROM prediction_history ph
            LEFT JOIN users u ON ph.user_id = u.id
            {where_clause}
            ORDER BY ph.created_at DESC
            """,
            tuple(params),
        )
        return cursor.fetchall()


def save_model_metrics(metrics):
    """Store regression evaluation results for dashboard comparison."""
    if use_sqlite():
        query = """
            INSERT OR REPLACE INTO model_metrics (
                model_name, mae, rmse, r2_score, accuracy_percentage, trained_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """
        rows = [
            (
                metric["model_name"],
                metric["mae"],
                metric["rmse"],
                metric["r2_score"],
                metric["accuracy_percentage"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            for metric in metrics
        ]
        with get_cursor(commit=True) as cursor:
            cursor.executemany(query, rows)
    else:
        query = """
            INSERT INTO model_metrics (
                model_name, mae, rmse, r2_score, accuracy_percentage, trained_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                mae = VALUES(mae),
                rmse = VALUES(rmse),
                r2_score = VALUES(r2_score),
                accuracy_percentage = VALUES(accuracy_percentage),
                trained_at = VALUES(trained_at)
        """
        rows = [
            (
                metric["model_name"],
                metric["mae"],
                metric["rmse"],
                metric["r2_score"],
                metric["accuracy_percentage"],
                datetime.now(),
            )
            for metric in metrics
        ]
        with get_cursor(commit=True) as cursor:
            cursor.executemany(query, rows)


def fetch_model_metrics():
    with get_cursor(dictionary=True) as cursor:
        cursor.execute(
            """
            SELECT model_name, mae, rmse, r2_score, accuracy_percentage,
                   trained_at
            FROM model_metrics
            ORDER BY accuracy_percentage DESC
            """
        )
        return cursor.fetchall()
