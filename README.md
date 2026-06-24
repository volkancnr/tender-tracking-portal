# Tender Tracking Portal

A Streamlit-based internal tender tracking and reporting panel.

## Features


- Tender registration and status tracking  
- Salesperson assignment and task follow-up  
- Role-based team access and authorization management  
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

## Sample İmages

<img width="1708" height="806" alt="image" src="https://github.com/user-attachments/assets/9788ab97-a5eb-4989-bb78-f4a037fe3913" />

Admin Menu:

<img width="2546" height="1268" alt="image" src="https://github.com/user-attachments/assets/fb77d021-eda0-4c3c-80ef-6c94f090ebe1" />

<img width="2535" height="1197" alt="image" src="https://github.com/user-attachments/assets/bb15bbb2-bae9-4a36-9ae6-544925e689ea" />

<img width="2535" height="1217" alt="image" src="https://github.com/user-attachments/assets/7f438932-a543-44ae-99f4-057e970ef849" />

<img width="2520" height="1188" alt="image" src="https://github.com/user-attachments/assets/c268d428-30a5-4f81-a012-e2af57c26ab5" />

<img width="2470" height="1187" alt="image" src="https://github.com/user-attachments/assets/85b2ab84-2c40-4e04-a974-cb08577585d8" />

<img width="2552" height="1190" alt="image" src="https://github.com/user-attachments/assets/23874102-b68a-4463-8d39-658bb1f1b71f" />

<img width="2530" height="1142" alt="image" src="https://github.com/user-attachments/assets/4b3a17cd-8c8f-4d0d-8a4b-62782d8aca9b" />

<img width="2167" height="1142" alt="image" src="https://github.com/user-attachments/assets/3e844402-49ce-482e-9417-93a530b454ac" />

<img width="2378" height="1097" alt="image" src="https://github.com/user-attachments/assets/96547bfb-c506-41c7-9a19-4cef4d42b6bb" />

<img width="2476" height="1172" alt="image" src="https://github.com/user-attachments/assets/9b480ed9-e2f2-4c41-b57c-19171ec7695b" />

<img width="2538" height="1221" alt="image" src="https://github.com/user-attachments/assets/b136fee0-c9d2-4047-b16b-bc581fcf458a" />

<img width="2502" height="1192" alt="image" src="https://github.com/user-attachments/assets/763fba2d-68c5-44e4-94c9-1a8dea81e3c6" />

Tender regulations:

<img width="1385" height="1263" alt="image" src="https://github.com/user-attachments/assets/17b9eb0f-ce1e-441f-baf3-f72bcf18c1bd" />

<img width="1338" height="1230" alt="image" src="https://github.com/user-attachments/assets/bdc76a0f-b0a9-4b27-964e-c254e6d18efe" />

<img width="1293" height="1231" alt="image" src="https://github.com/user-attachments/assets/ce883308-e8e7-46d0-9986-e0d15bd02bf1" />
