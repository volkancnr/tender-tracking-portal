# Live VPS Usage Note

This GitHub-ready version reads credentials from environment variables.

For your existing VPS, either create `/home/loji/portal/.env` or define variables inside the systemd service.

Example `.env` on the server:

```env
APP_PAGE_TITLE=Loji Pharma İhale Takip Paneli
APP_BRAND_TITLE=Loji Pharma İhale Takip Paneli
APP_BRAND_SUBTITLE=Loji Pharma Sağlık A.Ş.
APP_SIDEBAR_TITLE=Loji Pharma
APP_SYSTEM_NAME=Loji Pharma İhale Takip Sistemi

DB_HOST=localhost
DB_PORT=3306
DB_NAME=loji_portal_v2
DB_USER=loji_user
DB_PASSWORD=YOUR_REAL_PASSWORD

PARTICIPANT_COMPANY_OPTIONS=Ak Hayat,Loji Pharma,Medikoset,Global IVD
PRODUCT_GROUP_OPTIONS=Ortho IA,Ortho CC,Ortho Kan Gruplama,Hologic,Sysmex Flow,Others
```

Do not commit this real `.env` file to GitHub.
