# Development of a Data-Driven Sales Prediction and Analysis Platform Using Data Warehousing and Data Mining

This is a final-year DWDM capstone project built with Python, Flask, MySQL, HTML, CSS, JavaScript, Pandas, Scikit-learn, and Matplotlib. It uses `Sample - Superstore.csv` to demonstrate data collection, cleaning, ETL, data warehousing, OLAP-style analytics, data mining, and real-time predictive analytics.

## Features

- Login and register system with first-user admin role
- MySQL data warehouse for users, sales records, model metrics, and prediction history
- ETL pipeline from `Sample - Superstore.csv`
- Dashboard with monthly sales, profit, region, category, and top product charts
- Real-time sales prediction from quantity, discount, and profit
- Linear Regression, Decision Tree Regressor, and Random Forest Regressor
- Accuracy comparison with Chart.js and Matplotlib reports
- CSV exports for sales records, prediction history, and analytics summary
- Admin/user management

## Project Structure

```text
SalesPredictionCapstone/
|-- app.py
|-- model.py
|-- database.py
|-- requirements.txt
|-- database_schema.sql
|-- README.md
|-- PROJECT_DOCUMENTATION.md
|-- Sample - Superstore.csv
|-- templates/
|   |-- login.html
|   |-- register.html
|   |-- dashboard.html
|   |-- prediction.html
|   |-- reports.html
|-- static/
|   |-- style.css
|   |-- charts.js
|   |-- images/
|-- models/
```

## Setup Instructions

1. Install Python 3.10 or newer.
2. Install MySQL Server or start MySQL from XAMPP/WAMP.
3. Open this folder in VS Code:

```powershell
cd C:\Users\harth\Downloads\agri-fintech\SalesPredictionCapstone
code .
```

4. Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\activate
```

5. Install dependencies:

```powershell
pip install -r requirements.txt
```

6. Optional: copy `.env.example` to `.env` and update your MySQL credentials:

```powershell
copy .env.example .env
```

Default values are:

```text
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=sales_prediction_dw
```

7. Run the Flask app:

```powershell
python app.py
```

8. Open the application:

```text
http://127.0.0.1:5000
```

9. Register the first account. It automatically becomes the admin account.

## What Happens on First Run

When the first page loads, the system automatically:

1. Creates the MySQL database and tables.
2. Reads `Sample - Superstore.csv`.
3. Cleans the dataset using Pandas.
4. Loads records into the `sales_records` warehouse table.
5. Trains Linear Regression, Decision Tree, and Random Forest models.
6. Saves trained models in the `models/` folder.
7. Generates Matplotlib report images in `static/images/`.

## Manual Database Setup

If automatic database creation is disabled in your MySQL setup, run:

```powershell
mysql -u root -p < database_schema.sql
```

Then run:

```powershell
python app.py
```

## VS Code Execution Guide

1. Open VS Code.
2. Select `File > Open Folder`.
3. Choose `SalesPredictionCapstone`.
4. Open the VS Code terminal.
5. Run:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

6. Visit `http://127.0.0.1:5000`.

## Login Notes

- The first registered user is assigned `admin`.
- Later registered users are assigned `user`.
- Admins can update roles and delete other users from the dashboard.

## Prediction Input

The prediction page accepts:

- Quantity
- Discount
- Profit
- Model selection

It returns the predicted sales value instantly and stores the record in MySQL.
