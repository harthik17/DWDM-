CREATE DATABASE IF NOT EXISTS sales_prediction_dw;
USE sales_prediction_dw;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(160) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'user') NOT NULL DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
);

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
);

CREATE TABLE IF NOT EXISTS model_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(80) NOT NULL UNIQUE,
    mae DECIMAL(14, 4) NOT NULL,
    rmse DECIMAL(14, 4) NOT NULL,
    r2_score DECIMAL(10, 6) NOT NULL,
    accuracy_percentage DECIMAL(10, 4) NOT NULL,
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);
