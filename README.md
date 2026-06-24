# Tender Tracking Portal

A Streamlit-based internal tender tracking and reporting panel.

## Features

- Tender registration and status tracking
- Salesperson assignment and task follow-up
- Follow-up, objection, won/lost tender workflows
- Partial result tracking by product group
- Device and expense tracking
- Private job tracking
- Mail notification support through database SMTP settings
- Sales analytics and tender result dashboards
- Deleted tender archive and reason classification

## Tech Stack

- Python
- Streamlit
- MySQL
- SQLAlchemy
- Pandas
- Plotly

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create your environment file:

```bash
cp .env.example .env
```

Edit `.env` with your own database credentials.

Run locally:

```bash
streamlit run app.py
```

## Environment Variables

```env
APP_PAGE_TITLE=Tender Tracking Portal
APP_BRAND_TITLE=Tender Tracking Portal
APP_BRAND_SUBTITLE=Internal Tender Management
APP_SIDEBAR_TITLE=Tender Portal
APP_SYSTEM_NAME=Tender Tracking System

DB_HOST=localhost
DB_PORT=3306
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password

PARTICIPANT_COMPANY_OPTIONS=Company A,Company B,Company C,Company D
PRODUCT_GROUP_OPTIONS=Product Group A,Product Group B,Product Group C,Product Group D,Other
```

## Security Notes

Do not commit production secrets or business data.

Never commit:

- Real database credentials
- SMTP credentials
- SQL dumps or backups
- Production user data
- Tender prices, contract values, customer/institution data
- Internal company names, if the repository is public

If a secret was committed accidentally, rotate it immediately and remove it from Git history.
