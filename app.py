
import io
import html
import calendar
import smtplib
import urllib.parse
import re
import os
import unicodedata
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def env_list(name, default):
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return [x.strip() for x in raw.split(",") if x.strip()]


APP_PAGE_TITLE = os.getenv("APP_PAGE_TITLE", "Tender Tracking Portal")
APP_BRAND_TITLE = os.getenv("APP_BRAND_TITLE", APP_PAGE_TITLE)
APP_BRAND_SUBTITLE = os.getenv("APP_BRAND_SUBTITLE", "Internal Tender Management")
APP_SIDEBAR_TITLE = os.getenv("APP_SIDEBAR_TITLE", "Tender Portal")
APP_SYSTEM_NAME = os.getenv("APP_SYSTEM_NAME", APP_BRAND_TITLE)

st.set_page_config(page_title=APP_PAGE_TITLE, layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
</style>
""", unsafe_allow_html=True)


# =========================
# MySQL 
# =========================
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

SALES_STATUS_OPTIONS = [
    "Uyuyoruz",
    "Girmiyoruz",
    "Uymuyoruz",
    "İtiraz Verilecek",
    "İtiraz Verildi",
    "İtiraz Reddedildi",
    "Kurumla Görüşülecek",
    "Kurumla Görüşüldü",
]
ADMIN_STATUS_OPTIONS = ["Yeni Geldi"] + SALES_STATUS_OPTIONS + ["Kazanıldı", "Kaybedildi", "Kısmi Sonuçlandı"]

PRIVATE_JOB_STATUS_OPTIONS = [
    "Fiyat Teklifi Bekleniyor",
    "Fiyat Teklifi Değerlendiriliyor",
    "Teklif Onaylandı",
    "Teklif Onaylanmadı",
]

PARTICIPANT_COMPANY_OPTIONS = env_list(
    "PARTICIPANT_COMPANY_OPTIONS",
    ["Company A", "Company B", "Company C", "Company D"]
)



def get_engine():
    if not DB_NAME or not DB_USER:
        st.error("Veritabanı bağlantı bilgileri eksik. Lütfen DB_NAME, DB_USER ve DB_PASSWORD ortam değişkenlerini tanımlayın.")
        st.stop()
    password = urllib.parse.quote_plus(DB_PASSWORD)
    url = f"mysql+pymysql://{DB_USER}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


ENGINE = get_engine()


def now_str():
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def dt_to_panel(value, with_time=True):
    if value is None or str(value) in ["", "NaT", "None"]:
        return ""
    try:
        fmt = "%d.%m.%Y %H:%M" if with_time else "%d.%m.%Y"
        return pd.to_datetime(value).strftime(fmt)
    except Exception:
        return str(value)


def parse_tr_date(value):
    if isinstance(value, date):
        return value
    if value is None or str(value).strip() == "":
        return None
    s = str(value).strip()
    for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None


def parse_number(value):
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("₺", "").replace("$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        parts = s.split(".")
        if len(parts) > 2:
            s = "".join(parts)
    try:
        return float(s)
    except Exception:
        return None


def parse_int(value):
    s = str(value).strip()
    if not s:
        return None
    s = s.replace(".", "").replace(",", "").replace(" ", "")
    try:
        return int(float(s))
    except Exception:
        return None



def price_required_ok(value):
    return parse_tr_number(value) is not None and parse_tr_number(value) > 0


def format_money_tr(value):
    return format_tr_number(value)

def normalize_tr_number_text(value):
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    s = s.replace("₺", "").replace("$", "").replace("€", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        parts = s.split(".")
        if len(parts) > 2:
            s = "".join(parts)
    return s


def parse_tr_number(value):
    try:
        s = normalize_tr_number_text(value)
        if s == "":
            return None
        return float(s)
    except Exception:
        return None


def format_tr_number(value, decimals=2):
    try:
        if value is None or str(value).strip() == "":
            return ""
        v = float(value)
        txt = f"{v:,.{decimals}f}"
        return txt.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(value or "")


def tr_money_input(label, key, value="", required=False):
    default = ""
    parsed_default = parse_tr_number(value)
    if parsed_default is not None and parsed_default != 0:
        default = format_tr_number(parsed_default)
    raw = st.text_input(label, value=default, key=key, placeholder="Örn: 11.151.990,48")
    parsed = parse_tr_number(raw)
    if raw:
        if parsed is None:
            st.caption("Sayı biçimi geçersiz. Örnek: 11.151.990,48")
        else:
            st.caption(f"Görünen değer: {format_tr_number(parsed)}")
    elif required:
        st.caption("Bu alan zorunludur.")
    return raw





def format_tr_money_display(value):
    try:
        if value is None or str(value).strip() == "":
            return ""
        v = float(value)
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(value or "")


def format_tr_percent_display(value):
    try:
        if value is None or str(value).strip() == "":
            return ""
        v = float(value)
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(value or "")


def format_tr_int_display(value):
    try:
        if value is None or str(value).strip() == "":
            return ""
        v = int(float(value))
        return f"{v:,}".replace(",", ".")
    except Exception:
        return str(value or "")


def annual_value(total_price, duration_months):
    """12 aydan kısa işlerde yıllık getiri olarak direkt iş bedeli alınır.
    12 ay ve üzerindeyse yıllık karşılık = bedel / ay * 12.
    """
    try:
        price = float(total_price or 0)
        months = int(float(duration_months or 12))
        if months < 12:
            return price
        return (price / max(months, 1)) * 12
    except Exception:
        return 0


def split_multi_values_for_report(df, col_name):
    if df is None or df.empty or col_name not in df.columns:
        return df
    rows = []
    for _, row in df.iterrows():
        raw = str(row.get(col_name, "") or "")
        parts = [p.strip() for p in re.split(r"\s+\+\s+|[,/;]+", raw) if p.strip()]
        if not parts:
            parts = ["Belirtilmemiş"]
        for p in parts:
            new_row = row.copy()
            new_row[col_name] = p
            rows.append(new_row)
    return pd.DataFrame(rows)



def get_result_parts(tender_id):
    try:
        return fetch_df("""
            SELECT *
            FROM tender_result_parts
            WHERE ihale_id=:id
            ORDER BY FIELD(sonuc_durum, 'Kazanıldı', 'Kaybedildi'), sonuc_urun_grubu, id
        """, {"id": tender_id}).fillna("")
    except Exception:
        return pd.DataFrame()


def calc_result_yield(amount, months):
    amount = float(amount or 0)
    months = int(months or 12)
    if months < 12:
        return amount
    return amount / max(months, 1) * 12


def recompute_tender_result_status(tender_id):
    parts = get_result_parts(tender_id)
    if parts.empty:
        return
    statuses = set([str(x) for x in parts["sonuc_durum"].dropna().tolist()])
    if statuses == {"Kazanıldı"}:
        final_status = "Kazanıldı"
    elif statuses == {"Kaybedildi"}:
        final_status = "Kaybedildi"
    else:
        final_status = "Kısmi Sonuçlandı"

    won_total = 0
    won_yield = 0
    months = None
    start_date = None
    groups = []
    try:
        won_rows = parts[parts["sonuc_durum"] == "Kazanıldı"].copy()
        if not won_rows.empty:
            won_total = pd.to_numeric(won_rows["sozlesme_bedeli"], errors="coerce").fillna(0).sum()
            won_yield = pd.to_numeric(won_rows["yillik_getiri"], errors="coerce").fillna(0).sum()
            mvals = pd.to_numeric(won_rows["ihale_suresi_ay"], errors="coerce").dropna()
            months = int(mvals.iloc[0]) if not mvals.empty else None
            svals = [x for x in won_rows["sozlesme_baslangic_tarihi"].tolist() if str(x).strip()]
            start_date = svals[0] if svals else None
        groups = [str(x).strip() for x in parts["sonuc_urun_grubu"].tolist() if str(x).strip()]
    except Exception:
        pass

    execute("""
        UPDATE tenders
        SET durum=:durum,
            takip_ediliyor=0,
            aksiyon_alindi=1,
            sonuc_urun_grubu=:gruplar,
            yillik_getiri=:yillik_getiri,
            ihale_suresi_ay=COALESCE(:sure, ihale_suresi_ay),
            sozlesme_baslangic_tarihi=COALESCE(:baslangic, sozlesme_baslangic_tarihi),
            son_guncelleme=NOW(),
            son_guncelleyen=:user
        WHERE id=:id
    """, {
        "id": tender_id,
        "durum": final_status,
        "gruplar": ", ".join(dict.fromkeys(groups)),
        "yillik_getiri": won_yield,
        "sure": months,
        "baslangic": start_date,
        "user": st.session_state.user.get("ad_soyad", "")
    })


def result_part_label(row):
    return f"{int(row.get('id'))} | {row.get('sonuc_durum', '')} | {row.get('sonuc_urun_grubu', '')}"




def render_partial_results_admin(tender, tender_id):
    st.markdown("### Sonuç Girişi")
    st.caption("Kısmi teklif varsa her ürün grubu ayrı sonuçlandırılır. Kısmi teklif yoksa seçilen ürün grupları için tek toplam sonuç girilir.")

    parts = get_result_parts(tender_id)
    existing_by_group = {}
    if not parts.empty:
        for _, r in parts.iterrows():
            grp = str(r.get("sonuc_urun_grubu", "") or "").strip()
            if grp:
                existing_by_group[grp] = r.to_dict()

    if not parts.empty:
        show_cols = [
            "sonuc_durum", "sonuc_urun_grubu", "istirak_firma", "sozlesme_bedeli", "bizim_fiyat",
            "fiyat_farki", "fark_yuzdesi", "ihale_suresi_ay", "yillik_getiri",
            "test_rakami", "alan_firma", "kazanan_cihaz", "admin_notu"
        ]
        with st.expander("Kayıtlı sonuçları göster", expanded=True):
            render_html_table(
                format_result_display_df(parts[[c for c in show_cols if c in parts.columns]]),
                empty_message="Henüz sonuç girilmedi."
            )

    partial_default = len(existing_by_group) > 1
    is_partial_offer = st.checkbox(
        "Kısmi teklif mi?",
        value=partial_default,
        key=f"is_partial_offer_{tender_id}",
        help="İş kalemleri ayrı ayrı kazanılıp/kaybedilecekse işaretle. Tek toplam fiyatla sonuçlanacaksa boş bırak."
    )

    default_groups = []
    if existing_by_group:
        for g in existing_by_group.keys():
            for part in re.split(r"\s+\+\s+|[,/;]+", str(g)):
                p = part.strip()
                if p in result_product_options() and p not in default_groups:
                    default_groups.append(p)

    if not default_groups:
        for g in multi_default_from_text(tender.get("sonuc_urun_grubu", "") or tender.get("urun_grubu", "")):
            if g in result_product_options() and g not in default_groups:
                default_groups.append(g)

    selected_groups = st.multiselect(
        "Sonuçlandırılacak Ürün Grubu / Grupları",
        result_product_options(),
        default=default_groups,
        key=f"result_top_groups_{tender_id}",
        help="Kısmi teklif açıksa her grup ayrı kart olur. Kısmi teklif kapalıysa seçilen gruplar tek toplam sonuç olarak kaydedilir."
    )

    if not selected_groups:
        st.info("Önce en az bir ürün grubu seç.")
        return

    if not is_partial_offer:
        st.markdown("#### Toplam Sonuç Bilgisi")
        st.caption("Bu modda seçilen ürün grupları tek toplam fiyat olarak kaydedilir.")

        combined_group = " + ".join(selected_groups)
        existing = existing_by_group.get(combined_group, {})
        if not existing and len(existing_by_group) == 1:
            existing = list(existing_by_group.values())[0]

        status_options = ["Kazanıldı", "Kaybedildi"]
        default_status = existing.get("sonuc_durum", "Kazanıldı")
        status_index = status_options.index(default_status) if default_status in status_options else 0

        c_status, c_months, c_start = st.columns([1.2, 1, 1.4])
        total_status = c_status.selectbox(
            "Toplam Sonuç",
            status_options,
            index=status_index,
            key=f"total_status_{tender_id}"
        )

        existing_firma = str(existing.get("istirak_firma", "") or "")
        total_firma_index = PARTICIPANT_COMPANY_OPTIONS.index(existing_firma) if existing_firma in PARTICIPANT_COMPANY_OPTIONS else 0
        total_istirak_firma = st.selectbox(
            "İhaleye İştirak Eden Firma",
            PARTICIPANT_COMPANY_OPTIONS,
            index=total_firma_index,
            key=f"total_istirak_firma_{tender_id}"
        )

        months_default = int(float(existing.get("ihale_suresi_ay") or tender.get("ihale_suresi_ay") or 12))
        total_months = c_months.number_input(
            "İhale Süresi (Ay)",
            min_value=1,
            step=1,
            value=months_default,
            key=f"total_months_{tender_id}"
        )

        start_default = parse_tr_date(existing.get("sozlesme_baslangic_tarihi")) or parse_tr_date(tender.get("sozlesme_baslangic_tarihi"))
        start_known = c_start.checkbox(
            "Sözleşme başlangıcı belli",
            value=bool(start_default),
            key=f"total_start_known_{tender_id}"
        )
        total_start_date = None
        if start_known:
            total_start_date = st.date_input(
                "Sözleşme Başlangıç Tarihi",
                value=start_default or date.today(),
                format="DD.MM.YYYY",
                key=f"total_start_{tender_id}"
            )

        if total_status == "Kazanıldı":
            c1, c2, c3 = st.columns([1.2, 1, 1])
            with c1:
                total_price = tr_money_input(
                    "Toplam Sözleşme Bedeli",
                    key=f"total_won_price_{tender_id}",
                    value=existing.get("sozlesme_bedeli", ""),
                    required=True
                )
            with c2:
                total_test = st.text_input(
                    "Toplam Test Rakamı",
                    value=format_tr_int_display(existing.get("test_rakami", "")),
                    key=f"total_test_{tender_id}"
                )
            with c3:
                total_annual = calc_result_yield(parse_tr_number(total_price) or 0, int(total_months))
                st.metric("Getiri", format_tr_money_display(total_annual))

            c4, c5 = st.columns(2)
            total_birim_puan = c4.text_input(
                "Birim Puan",
                value=str(existing.get("birim_puan", "") or ""),
                key=f"total_birim_puan_{tender_id}"
            )
            total_birim_test = c5.text_input(
                "Birim Test Fiyatı",
                value=str(existing.get("birim_test_fiyati", "") or ""),
                key=f"total_birim_test_{tender_id}"
            )
            total_our_price = None
            total_diff = None
            total_pct = None
            total_company = ""
            total_device = ""

        else:
            c1, c2, c3 = st.columns([1.2, 1.2, 1])
            with c1:
                total_price = tr_money_input(
                    "Tahmini Kazanan Toplam Fiyat",
                    key=f"total_lost_win_price_{tender_id}",
                    value=existing.get("sozlesme_bedeli", ""),
                    required=True
                )
            with c2:
                total_our_price = tr_money_input(
                    "Bizim Toplam Fiyatımız",
                    key=f"total_lost_our_price_{tender_id}",
                    value=existing.get("bizim_fiyat", ""),
                    required=True
                )
            win_num = parse_tr_number(total_price) or 0
            our_num = parse_tr_number(total_our_price) or 0
            total_diff = our_num - win_num
            total_pct = percent_diff(our_num, win_num)
            with c3:
                st.metric("Fiyat Farkı", format_tr_money_display(total_diff), f"%{format_tr_percent_display(total_pct)}")

            c4, c5 = st.columns(2)
            total_company = c4.text_input(
                "Kazanan Firma",
                value=str(existing.get("alan_firma", "") or ""),
                key=f"total_company_{tender_id}"
            )
            total_device = c5.text_input(
                "Kazanan Cihaz",
                value=str(existing.get("kazanan_cihaz", "") or ""),
                key=f"total_device_{tender_id}"
            )
            total_test = ""
            total_birim_puan = ""
            total_birim_test = ""
            total_annual = None

        total_note = st.text_area(
            "Admin Notu",
            value=str(existing.get("admin_notu", "") or ""),
            key=f"total_note_{tender_id}"
        )

        save_total = st.button(
            "Toplam Sonucu Kaydet",
            type="primary",
            key=f"total_save_{tender_id}"
        )

        if save_total:
            if total_status == "Kazanıldı" and not price_required_ok(total_price):
                st.error("Toplam sözleşme bedeli zorunludur.")
                st.stop()
            if total_status == "Kaybedildi" and (not price_required_ok(total_price) or not price_required_ok(total_our_price)):
                st.error("Kaybedilen toplam sonuç için tahmini kazanan fiyat ve bizim fiyatımız zorunludur.")
                st.stop()

            execute("DELETE FROM tender_result_parts WHERE ihale_id=:id", {"id": tender_id})

            price_num = parse_tr_number(total_price) or 0
            our_price_num = parse_tr_number(total_our_price) if total_status == "Kaybedildi" else None
            diff_num = (our_price_num or 0) - price_num if total_status == "Kaybedildi" else None
            pct_num = percent_diff(our_price_num or 0, price_num) if total_status == "Kaybedildi" else None
            annual_num = calc_result_yield(price_num, int(total_months)) if total_status == "Kazanıldı" else None

            execute("""
                INSERT INTO tender_result_parts
                (ihale_id, sonuc_durum, sonuc_urun_grubu, istirak_firma, sozlesme_bedeli, bizim_fiyat,
                 fiyat_farki, fark_yuzdesi, test_rakami, birim_puan, birim_test_fiyati,
                 alan_firma, kazanan_cihaz, sozlesme_baslangic_tarihi, ihale_suresi_ay,
                 yillik_getiri, admin_notu)
                VALUES
                (:ihale_id, :sonuc_durum, :sonuc_urun_grubu, :istirak_firma, :sozlesme_bedeli, :bizim_fiyat,
                 :fiyat_farki, :fark_yuzdesi, :test_rakami, :birim_puan, :birim_test_fiyati,
                 :alan_firma, :kazanan_cihaz, :sozlesme_baslangic_tarihi, :ihale_suresi_ay,
                 :yillik_getiri, :admin_notu)
            """, {
                "ihale_id": tender_id,
                "sonuc_durum": total_status,
                "sonuc_urun_grubu": combined_group,
                "istirak_firma": total_istirak_firma,
                "sozlesme_bedeli": price_num,
                "bizim_fiyat": our_price_num,
                "fiyat_farki": diff_num,
                "fark_yuzdesi": pct_num,
                "test_rakami": parse_int(total_test) if total_status == "Kazanıldı" else None,
                "birim_puan": total_birim_puan,
                "birim_test_fiyati": total_birim_test,
                "alan_firma": total_company,
                "kazanan_cihaz": total_device,
                "sozlesme_baslangic_tarihi": total_start_date,
                "ihale_suresi_ay": int(total_months),
                "yillik_getiri": annual_num,
                "admin_notu": total_note,
            })

            recompute_tender_result_status(tender_id)
            clear_caches()
            log_action(tender_id, f"Toplam sonuç kaydedildi: {total_status} / {combined_group}")
            notify_volkan(tender_id, f"Toplam sonuç kaydedildi: {total_status} / {combined_group}")
            st.success("Toplam sonuç kaydedildi ve analize işlendi.")
            st.rerun()

        return

    collected = []
    st.markdown("#### Grup Bazlı Sonuç Kartları")

    for idx, grp in enumerate(selected_groups, start=1):
        existing = existing_by_group.get(grp, {})
        safe_grp = re.sub(r"[^A-Za-z0-9_]+", "_", grp)
        suffix = f"{tender_id}_{safe_grp}"

        st.markdown(
            f"""
            <div class="info-band" style="margin-top:18px; margin-bottom:8px;">
                <b>{idx}. {grp}</b> için sonuç bilgileri
            </div>
            """,
            unsafe_allow_html=True
        )

        status_options = ["Kazanıldı", "Kaybedildi"]
        default_status = existing.get("sonuc_durum", "Kazanıldı")
        status_index = status_options.index(default_status) if default_status in status_options else 0

        c_status, c_months, c_start = st.columns([1.2, 1, 1.4])
        part_status = c_status.selectbox(
            "Sonuç",
            status_options,
            index=status_index,
            key=f"partial_status_{suffix}"
        )

        existing_firma = str(existing.get("istirak_firma", "") or "")
        part_firma_index = PARTICIPANT_COMPANY_OPTIONS.index(existing_firma) if existing_firma in PARTICIPANT_COMPANY_OPTIONS else 0
        part_istirak_firma = st.selectbox(
            f"{grp} - İhaleye İştirak Eden Firma",
            PARTICIPANT_COMPANY_OPTIONS,
            index=part_firma_index,
            key=f"partial_istirak_firma_{suffix}"
        )

        months_default = int(float(existing.get("ihale_suresi_ay") or tender.get("ihale_suresi_ay") or 12))
        part_months = c_months.number_input(
            "İhale Süresi (Ay)",
            min_value=1,
            step=1,
            value=months_default,
            key=f"partial_months_{suffix}"
        )

        start_default = parse_tr_date(existing.get("sozlesme_baslangic_tarihi")) or parse_tr_date(tender.get("sozlesme_baslangic_tarihi"))
        start_known = c_start.checkbox(
            "Sözleşme başlangıcı belli",
            value=bool(start_default),
            key=f"partial_start_known_{suffix}"
        )
        part_start_date = None
        if start_known:
            part_start_date = st.date_input(
                f"{grp} - Sözleşme Başlangıç Tarihi",
                value=start_default or date.today(),
                format="DD.MM.YYYY",
                key=f"partial_start_{suffix}"
            )

        if part_status == "Kazanıldı":
            c1, c2, c3 = st.columns([1.2, 1, 1])
            with c1:
                part_price = tr_money_input(
                    f"{grp} - Sözleşme Bedeli",
                    key=f"partial_won_price_{suffix}",
                    value=existing.get("sozlesme_bedeli", ""),
                    required=True
                )
            with c2:
                part_test = st.text_input(
                    f"{grp} - Test Rakamı",
                    value=format_tr_int_display(existing.get("test_rakami", "")),
                    key=f"partial_test_{suffix}"
                )
            with c3:
                part_annual = calc_result_yield(parse_tr_number(part_price) or 0, int(part_months))
                st.metric("Getiri", format_tr_money_display(part_annual))

            c4, c5 = st.columns(2)
            part_birim_puan = c4.text_input(
                f"{grp} - Birim Puan",
                value=str(existing.get("birim_puan", "") or ""),
                key=f"partial_birim_puan_{suffix}"
            )
            part_birim_test = c5.text_input(
                f"{grp} - Birim Test Fiyatı",
                value=str(existing.get("birim_test_fiyati", "") or ""),
                key=f"partial_birim_test_{suffix}"
            )

            part_our_price = None
            part_diff = None
            part_pct = None
            part_company = ""
            part_device = ""

        else:
            c1, c2, c3 = st.columns([1.2, 1.2, 1])
            with c1:
                part_price = tr_money_input(
                    f"{grp} - Tahmini Kazanan Fiyat",
                    key=f"partial_lost_win_price_{suffix}",
                    value=existing.get("sozlesme_bedeli", ""),
                    required=True
                )
            with c2:
                part_our_price = tr_money_input(
                    f"{grp} - Bizim Fiyatımız",
                    key=f"partial_lost_our_price_{suffix}",
                    value=existing.get("bizim_fiyat", ""),
                    required=True
                )
            win_num = parse_tr_number(part_price) or 0
            our_num = parse_tr_number(part_our_price) or 0
            part_diff = our_num - win_num
            part_pct = percent_diff(our_num, win_num)
            with c3:
                st.metric("Fiyat Farkı", format_tr_money_display(part_diff), f"%{format_tr_percent_display(part_pct)}")

            c4, c5 = st.columns(2)
            part_company = c4.text_input(
                f"{grp} - Kazanan Firma",
                value=str(existing.get("alan_firma", "") or ""),
                key=f"partial_company_{suffix}"
            )
            part_device = c5.text_input(
                f"{grp} - Kazanan Cihaz",
                value=str(existing.get("kazanan_cihaz", "") or ""),
                key=f"partial_device_{suffix}"
            )

            part_test = ""
            part_birim_puan = ""
            part_birim_test = ""
            part_annual = None

        part_note = st.text_area(
            f"{grp} - Admin Notu",
            value=str(existing.get("admin_notu", "") or ""),
            key=f"partial_note_{suffix}"
        )

        collected.append({
            "grp": grp,
            "status": part_status,
            "istirak_firma": part_istirak_firma,
            "months": int(part_months),
            "start_date": part_start_date,
            "price_text": part_price,
            "our_price_text": part_our_price,
            "diff": part_diff,
            "pct": part_pct,
            "test": part_test,
            "birim_puan": part_birim_puan,
            "birim_test": part_birim_test,
            "company": part_company,
            "device": part_device,
            "annual": part_annual,
            "note": part_note,
        })

    st.markdown("---")
    del_unselected = st.checkbox(
        "Seçili olmayan eski ürün grubu sonuçlarını sil",
        value=False,
        key=f"partial_delete_unselected_{tender_id}",
        help="Eski kayıtlardan artık istemediğin grup varsa işaretle. Seçili olmayan kısmi sonuçlar silinir."
    )

    save_all = st.button(
        "Tüm Ürün Grubu Sonuçlarını Kaydet",
        type="primary",
        key=f"partial_save_all_{tender_id}"
    )

    if save_all:
        for item in collected:
            if item["status"] == "Kazanıldı" and not price_required_ok(item["price_text"]):
                st.error(f"{item['grp']} için sözleşme bedeli zorunludur.")
                st.stop()
            if item["status"] == "Kaybedildi" and (not price_required_ok(item["price_text"]) or not price_required_ok(item["our_price_text"])):
                st.error(f"{item['grp']} için tahmini kazanan fiyat ve bizim fiyatımız zorunludur.")
                st.stop()

        if del_unselected:
            safe_groups = [str(g) for g in selected_groups]
            placeholders = ", ".join([f":g{i}" for i in range(len(safe_groups))])
            params = {"id": tender_id}
            params.update({f"g{i}": g for i, g in enumerate(safe_groups)})
            execute(f"DELETE FROM tender_result_parts WHERE ihale_id=:id AND sonuc_urun_grubu NOT IN ({placeholders})", params)

        for item in collected:
            price_num = parse_tr_number(item["price_text"]) or 0
            our_price_num = parse_tr_number(item["our_price_text"]) if item["status"] == "Kaybedildi" else None
            diff_num = (our_price_num or 0) - price_num if item["status"] == "Kaybedildi" else None
            pct_num = percent_diff(our_price_num or 0, price_num) if item["status"] == "Kaybedildi" else None
            annual_num = calc_result_yield(price_num, int(item["months"])) if item["status"] == "Kazanıldı" else None

            params = {
                "ihale_id": tender_id,
                "sonuc_durum": item["status"],
                "sonuc_urun_grubu": item["grp"],
                "istirak_firma": item["istirak_firma"],
                "sozlesme_bedeli": price_num,
                "bizim_fiyat": our_price_num,
                "fiyat_farki": diff_num,
                "fark_yuzdesi": pct_num,
                "test_rakami": parse_int(item["test"]) if item["status"] == "Kazanıldı" else None,
                "birim_puan": item["birim_puan"],
                "birim_test_fiyati": item["birim_test"],
                "alan_firma": item["company"],
                "kazanan_cihaz": item["device"],
                "sozlesme_baslangic_tarihi": item["start_date"],
                "ihale_suresi_ay": int(item["months"]),
                "yillik_getiri": annual_num,
                "admin_notu": item["note"],
            }

            execute("""
                INSERT INTO tender_result_parts
                (ihale_id, sonuc_durum, sonuc_urun_grubu, istirak_firma, sozlesme_bedeli, bizim_fiyat,
                 fiyat_farki, fark_yuzdesi, test_rakami, birim_puan, birim_test_fiyati,
                 alan_firma, kazanan_cihaz, sozlesme_baslangic_tarihi, ihale_suresi_ay,
                 yillik_getiri, admin_notu)
                VALUES
                (:ihale_id, :sonuc_durum, :sonuc_urun_grubu, :istirak_firma, :sozlesme_bedeli, :bizim_fiyat,
                 :fiyat_farki, :fark_yuzdesi, :test_rakami, :birim_puan, :birim_test_fiyati,
                 :alan_firma, :kazanan_cihaz, :sozlesme_baslangic_tarihi, :ihale_suresi_ay,
                 :yillik_getiri, :admin_notu)
                ON DUPLICATE KEY UPDATE
                    sonuc_durum=VALUES(sonuc_durum),
                    istirak_firma=VALUES(istirak_firma),
                    sozlesme_bedeli=VALUES(sozlesme_bedeli),
                    bizim_fiyat=VALUES(bizim_fiyat),
                    fiyat_farki=VALUES(fiyat_farki),
                    fark_yuzdesi=VALUES(fark_yuzdesi),
                    test_rakami=VALUES(test_rakami),
                    birim_puan=VALUES(birim_puan),
                    birim_test_fiyati=VALUES(birim_test_fiyati),
                    alan_firma=VALUES(alan_firma),
                    kazanan_cihaz=VALUES(kazanan_cihaz),
                    sozlesme_baslangic_tarihi=VALUES(sozlesme_baslangic_tarihi),
                    ihale_suresi_ay=VALUES(ihale_suresi_ay),
                    yillik_getiri=VALUES(yillik_getiri),
                    admin_notu=VALUES(admin_notu),
                    updated_at=NOW()
            """, params)

        recompute_tender_result_status(tender_id)
        clear_caches()
        log_action(tender_id, f"Ürün grubu bazlı sonuçlar kaydedildi: {', '.join(selected_groups)}")
        notify_volkan(tender_id, f"Ürün grubu bazlı sonuçlar kaydedildi: {', '.join(selected_groups)}")
        st.success("Tüm ürün grubu sonuçları kaydedildi ve analize işlendi.")
        st.rerun()



def result_product_options():
    return env_list(
        "PRODUCT_GROUP_OPTIONS",
        ["Product Group A", "Product Group B", "Product Group C", "Product Group D", "Other"]
    )


def format_result_display_df(df):
    if df is None or df.empty:
        return df
    df = df.copy()

    money_cols = [
        "sozlesme_bedeli", "Sözleşme Bedeli",
        "birim_puan", "Birim Puan",
        "birim_test_fiyati", "Birim Test Fiyatı", "Birim Test",
        "yillik_getiri", "Yıllık Getiri",
        "ihale_yillik_getiri", "İhale Yıllık Getiri",
        "onay_fiyati", "Onay Fiyatı",
        "ozel_is_fiyat_toplam", "Özel İş Fiyat Toplamı",
        "ozel_is_yillik_getiri", "Özel İş Yıllık Getiri",
        "bizim_fiyat", "Bizim Fiyatımız",
        "fiyat_farki", "Fiyat Farkı",
    ]
    int_cols = [
        "test_rakami", "Test Rakamı",
        "test_sayisi", "Test Sayısı",
        "cihaz_adedi", "Cihaz Adedi",
        "satir_adedi", "Kayıt Satırı",
        "ihale_adedi", "İhale Adedi",
        "mevcut_ihale_adedi", "Mevcut İhale Adedi",
        "aktif_sistemdeki_ihale_adedi", "Sistemdeki İhale",
        "silinen_ihale_adedi", "Silinen / Girilemeyen İhale",
        "toplam_verilen_ihale", "Toplam Verilen İhale",
        "kazanilan_ihale", "Kazanılan İhale",
        "kaybedilen_ihale", "Kaybedilen İhale",
        "ihale_sonuc_adedi", "Sonuçlanan Kalem",
        "ozel_is_adedi", "Özel İş Adedi",
        "alinan_ozel_is", "Alınan Özel İş",
        "alinan_ozel_is_adedi", "Alınan Özel İş Adedi",
        "ihale_suresi_ay", "İhale Süresi (Ay)",
        "Adet", "adet", "Kayıt Adedi",
    ]

    percent_cols = [
        "fark_yuzdesi", "Fark %",
        "kazanma_orani", "Kazanma Oranı %",
        "oran", "Oran %",
    ]

    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].apply(format_tr_money_display)
    for col in percent_cols:
        if col in df.columns:
            df[col] = df[col].apply(format_tr_percent_display)
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].apply(format_tr_int_display)

    # Tabloya kaçan diğer küsuratlı sayıları da 2 ondalığa sabitle.
    skip_numeric_cols = {
        "id", "ID", "ikn", "İKN", "yil", "Yıl", "ihale_tarihi", "İhale Tarihi",
        "kayit_tarihi", "Ekleme Tarihi", "son_guncelleme", "Son Güncelleme",
        "kazanma_tarihi", "Kazanma Tarihi", "kaybetme_tarihi", "Kaybetme Tarihi",
        "sozlesme_baslangic_tarihi", "Sözleşme Başlangıç Tarihi",
    }
    formatted_cols = set(money_cols + percent_cols + int_cols)
    for col in list(df.columns):
        if col in formatted_cols or col in skip_numeric_cols:
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.notna().any():
            non_empty = df[col].astype(str).str.strip().ne("")
            numeric_ratio = numeric.notna().sum() / max(int(non_empty.sum()), 1)
            if numeric_ratio >= 0.8 and (numeric.dropna() % 1 != 0).any():
                df[col] = numeric.apply(format_tr_number)

    rename_map = {
        "ihale_tarihi": "İhale Tarihi",
        "ikn": "İKN",
        "kurum": "Kurum",
        "urun_grubu": "Ürün Grubu",
        "durum": "Durum",
        "ilgili_kisi": "İlgili Kişi",
        "sozlesme_bedeli": "Sözleşme Bedeli",
        "test_rakami": "Test Rakamı",
        "sonuc_urun_grubu": "Sonuç Ürün Grubu",
        "istirak_firma": "İştirak Eden Firma",
        "birim_puan": "Birim Puan",
        "birim_test_fiyati": "Birim Test Fiyatı",
        "kazanma_tarihi": "Kazanma Tarihi",
        "kaybetme_tarihi": "Kaybetme Tarihi",
        "alan_firma": "Alan Firma",
        "kazanan_cihaz": "Kazanan Cihaz",
        "bizim_fiyat": "Bizim Fiyatımız",
        "fiyat_farki": "Fiyat Farkı",
        "fark_yuzdesi": "Fark %",
        "admin_notu": "Admin Notu",
        "yillik_getiri": "Yıllık Getiri",
        "ihale_yillik_getiri": "İhale Yıllık Getiri",
        "sozlesme_baslangic_tarihi": "Sözleşme Başlangıç Tarihi",
        "ihale_suresi_ay": "İhale Süresi (Ay)",
        "onay_fiyati": "Onay Fiyatı",
        "ozel_is_fiyat_toplam": "Özel İş Fiyat Toplamı",
        "ozel_is_yillik_getiri": "Özel İş Yıllık Getiri",
        "ihale_adedi": "İhale Adedi",
        "mevcut_ihale_adedi": "Mevcut İhale Adedi",
        "kazanilan_ihale": "Kazanılan İhale",
        "kaybedilen_ihale": "Kaybedilen İhale",
        "ozel_is_adedi": "Özel İş Adedi",
        "alinan_ozel_is": "Alınan Özel İş",
    }
    return df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})



def get_result_record(table_name, tender_id):
    try:
        df = fetch_df(f"SELECT * FROM {table_name} WHERE ihale_id=:id LIMIT 1", {"id": tender_id}).fillna("")
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception:
        pass
    return {}


def multi_default_from_text(value):
    raw = str(value or "")
    opts = result_product_options()
    vals = []
    for part in re.split(r"[,/;]+", raw):
        p = part.strip()
        if p and p in opts and p not in vals:
            vals.append(p)
    return vals


def percent_diff(our_price, winner_price):
    try:
        our = float(our_price or 0)
        win = float(winner_price or 0)
        if win <= 0:
            return 0
        return ((our - win) / win) * 100
    except Exception:
        return 0

def only_digits(value):
    return "".join(ch for ch in str(value) if ch.isdigit())


def format_tr_thousands(value):
    digits = only_digits(value)
    if not digits:
        return ""
    return f"{int(digits):,}".replace(",", ".")


def number_input_with_preview(label, key):
    raw = st.text_input(label, key=key)
    formatted = format_tr_thousands(raw)
    if formatted:
        st.caption(f"Anlık görünüm: **{formatted}**")
    return formatted if formatted else raw


def assigned_people_list(value):
    raw = str(value or "").replace(";", ",").replace("/", ",")
    return [x.strip() for x in raw.split(",") if x.strip()]


def assigned_people_text(values):
    if isinstance(values, str):
        return values
    return ", ".join([str(x).strip() for x in values if str(x).strip()])


def is_admin():
    return st.session_state.get("user", {}).get("rol") == "admin"


def current_user_can_edit(tender):
    if is_admin():
        return True
    assigned = [x.lower() for x in assigned_people_list(tender.get("ilgili_kisi", ""))]
    return st.session_state.user.get("ad_soyad", "").strip().lower() in assigned


# =========================
# SQL yardımcıları
# =========================
def fetch_df(sql, params=None):
    with ENGINE.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def execute(sql, params=None):
    with ENGINE.begin() as conn:
        conn.execute(text(sql), params or {})


def execute_many(sql, rows):
    with ENGINE.begin() as conn:
        conn.execute(text(sql), rows)


@st.cache_data(ttl=300, show_spinner=False)
def get_sales_users_cached():
    df = fetch_df("""
        SELECT id, kullanici_adi, ad_soyad, email
        FROM users
        WHERE rol='satis' AND aktif=1
        ORDER BY ad_soyad
    """)
    return df.fillna("").astype(str)


def clear_caches():
    get_sales_users_cached.clear()


def get_counts_live():
    """
    Sayaçlar cache kullanmadan direkt MySQL'den okunur.
    Kısmi sonuçlar tender_result_parts üzerinden sayılır.
    """
    try:
        df = fetch_df("""
            SELECT
              (SELECT COUNT(*) FROM tenders WHERE takip_ediliyor=0 AND durum NOT IN ('Kazanıldı','Kaybedildi','Kısmi Sonuçlandı')) AS listede,
              (SELECT COUNT(*) FROM tenders WHERE takip_ediliyor=1 AND durum NOT IN ('Kazanıldı','Kaybedildi','Kısmi Sonuçlandı')) AS takipte,
              (SELECT COUNT(*) FROM tenders WHERE durum LIKE '%İtiraz%') AS itiraz,
              (SELECT COUNT(DISTINCT ihale_id) FROM tender_result_parts WHERE sonuc_durum='Kazanıldı') AS kazanilan,
              (SELECT COUNT(DISTINCT ihale_id) FROM tender_result_parts WHERE sonuc_durum='Kaybedildi') AS kaybedilen
        """)
    except Exception:
        df = fetch_df("""
            SELECT
              SUM(CASE WHEN takip_ediliyor=0 AND durum NOT IN ('Kazanıldı','Kaybedildi','Kısmi Sonuçlandı') THEN 1 ELSE 0 END) AS listede,
              SUM(CASE WHEN takip_ediliyor=1 AND durum NOT IN ('Kazanıldı','Kaybedildi','Kısmi Sonuçlandı') THEN 1 ELSE 0 END) AS takipte,
              SUM(CASE WHEN durum LIKE '%İtiraz%' THEN 1 ELSE 0 END) AS itiraz,
              SUM(CASE WHEN durum='Kazanıldı' THEN 1 ELSE 0 END) AS kazanilan,
              SUM(CASE WHEN durum='Kaybedildi' THEN 1 ELSE 0 END) AS kaybedilen
            FROM tenders
        """)
    if df.empty:
        return {"listede": 0, "takipte": 0, "itiraz": 0, "kazanilan": 0, "kaybedilen": 0}
    r = df.iloc[0].fillna(0).to_dict()
    return {k: int(r.get(k, 0) or 0) for k in ["listede", "takipte", "itiraz", "kazanilan", "kaybedilen"]}


def get_counts_cached():
    # Eski isimle çağrı kalırsa da canlı sayacı kullansın.
    return get_counts_live()


def get_tender(tender_id):
    df = fetch_df("SELECT * FROM tenders WHERE id=:id LIMIT 1", {"id": tender_id})
    if df.empty:
        return None
    row = df.fillna("").iloc[0].to_dict()
    row["ihale_tarihi"] = dt_to_panel(row.get("ihale_tarihi"), with_time=False)
    row["kayit_tarihi"] = dt_to_panel(row.get("kayit_tarihi"))
    row["son_guncelleme"] = dt_to_panel(row.get("son_guncelleme"))
    row["itiraz_verilecek_tarihi"] = dt_to_panel(row.get("itiraz_verilecek_tarihi"))
    row["takip_ediliyor"] = "Evet" if str(row.get("takip_ediliyor")) in ["1", "1.0", "True", "true"] else "Hayır"
    row["aksiyon_alindi"] = "Evet" if str(row.get("aksiyon_alindi")) in ["1", "1.0", "True", "true"] else "Hayır"
    return {k: "" if v is None else str(v) for k, v in row.items()}


def log_action(ihale_id, islem):
    execute("""
        INSERT INTO logs (ihale_id, kullanici, islem, tarih)
        VALUES (:ihale_id, :kullanici, :islem, NOW())
    """, {
        "ihale_id": ihale_id,
        "kullanici": st.session_state.user.get("ad_soyad", ""),
        "islem": islem
    })


def mark_action(ihale_id):
    execute("""
        UPDATE tenders
        SET aksiyon_alindi=1,
            son_guncelleme=NOW(),
            son_guncelleyen=:user
        WHERE id=:id
    """, {"id": ihale_id, "user": st.session_state.user.get("ad_soyad", "")})


def set_objection_watch(ihale_id, status):
    if str(status).strip() != "İtiraz Verilecek":
        return
    execute("""
        UPDATE tenders
        SET itiraz_verilecek_tarihi = COALESCE(itiraz_verilecek_tarihi, NOW())
        WHERE id=:id
    """, {"id": ihale_id})




# =========================
# Silinen İhaleler Arşivi
# =========================
def ensure_deleted_tender_schema():
    sqls = [
        """
        CREATE TABLE IF NOT EXISTS deleted_tenders (
            id INT NOT NULL AUTO_INCREMENT,
            original_id INT DEFAULT NULL,
            kayit_tarihi DATETIME DEFAULT NULL,
            ihale_tarihi DATE DEFAULT NULL,
            ikn VARCHAR(100) DEFAULT NULL,
            kurum VARCHAR(255) DEFAULT NULL,
            urun_grubu VARCHAR(255) DEFAULT NULL,
            durum VARCHAR(100) DEFAULT NULL,
            ilgili_kisi VARCHAR(255) DEFAULT NULL,
            aciklama TEXT DEFAULT NULL,
            son_guncelleme DATETIME DEFAULT NULL,
            son_guncelleyen VARCHAR(255) DEFAULT NULL,
            silen_kisi VARCHAR(255) DEFAULT NULL,
            silinme_tarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
            silme_notu TEXT DEFAULT NULL,
            cihaz_sayisi INT DEFAULT 0,
            masraf_sayisi INT DEFAULT 0,
            yorum_sayisi INT DEFAULT 0,
            cihaz_ozet TEXT DEFAULT NULL,
            masraf_ozet TEXT DEFAULT NULL,
            yorum_ozet TEXT DEFAULT NULL,
            PRIMARY KEY (id),
            KEY idx_deleted_original_id (original_id),
            KEY idx_deleted_durum (durum),
            KEY idx_deleted_silinme_tarihi (silinme_tarihi),
            KEY idx_deleted_ilgili_kisi (ilgili_kisi)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_turkish_ci
        """,
        "ALTER TABLE deleted_tenders ADD COLUMN original_id INT DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN kayit_tarihi DATETIME DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN ihale_tarihi DATE DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN ikn VARCHAR(100) DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN kurum VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN urun_grubu VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN durum VARCHAR(100) DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN ilgili_kisi VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN aciklama TEXT DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN son_guncelleme DATETIME DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN son_guncelleyen VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN silen_kisi VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN silinme_tarihi DATETIME DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE deleted_tenders ADD COLUMN silme_notu TEXT DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN cihaz_sayisi INT DEFAULT 0",
        "ALTER TABLE deleted_tenders ADD COLUMN masraf_sayisi INT DEFAULT 0",
        "ALTER TABLE deleted_tenders ADD COLUMN yorum_sayisi INT DEFAULT 0",
        "ALTER TABLE deleted_tenders ADD COLUMN cihaz_ozet TEXT DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN masraf_ozet TEXT DEFAULT NULL",
        "ALTER TABLE deleted_tenders ADD COLUMN yorum_ozet TEXT DEFAULT NULL",
    ]
    for q in sqls:
        try:
            execute(q)
        except Exception:
            pass


def _count_child_rows(table_name, tender_id):
    try:
        df = fetch_df(f"SELECT COUNT(*) AS adet FROM {table_name} WHERE ihale_id=:id", {"id": tender_id})
        if df.empty:
            return 0
        return int(df.iloc[0].get("adet") or 0)
    except Exception:
        return 0


def _child_summary(table_name, tender_id, fields, limit=8):
    try:
        df = fetch_df(f"SELECT * FROM {table_name} WHERE ihale_id=:id ORDER BY id DESC LIMIT {int(limit)}", {"id": tender_id}).fillna("")
        if df.empty:
            return ""
        rows = []
        for _, r in df.iterrows():
            bits = []
            for f in fields:
                if f in df.columns and str(r.get(f, "")).strip():
                    bits.append(str(r.get(f, "")).strip())
            if bits:
                rows.append(" / ".join(bits))
        return " | ".join(rows)
    except Exception:
        return ""


def archive_tender_before_delete(tender_id, silme_notu="Admin tarafından silindi"):
    ensure_deleted_tender_schema()
    tender_df = fetch_df("SELECT * FROM tenders WHERE id=:id LIMIT 1", {"id": tender_id}).fillna("")
    if tender_df.empty:
        return

    t = tender_df.iloc[0].to_dict()
    cihaz_sayisi = _count_child_rows("devices", tender_id)
    masraf_sayisi = _count_child_rows("expenses", tender_id)
    yorum_sayisi = _count_child_rows("comments", tender_id)

    cihaz_ozet = _child_summary("devices", tender_id, ["cihaz_adedi", "marka", "model", "kurulum_yapilacak_hastane_bilgisi"])
    masraf_ozet = _child_summary("expenses", tender_id, ["masraf_aciklamasi", "ihale_miktari", "temin_edilecek_firma"])
    yorum_ozet = _child_summary("comments", tender_id, ["kullanici", "yorum", "tarih"])

    execute("""
        INSERT INTO deleted_tenders
        (original_id, kayit_tarihi, ihale_tarihi, ikn, kurum, urun_grubu, durum,
         ilgili_kisi, aciklama, son_guncelleme, son_guncelleyen, silen_kisi,
         silinme_tarihi, silme_notu, cihaz_sayisi, masraf_sayisi, yorum_sayisi,
         cihaz_ozet, masraf_ozet, yorum_ozet)
        VALUES
        (:original_id, :kayit_tarihi, :ihale_tarihi, :ikn, :kurum, :urun_grubu, :durum,
         :ilgili_kisi, :aciklama, :son_guncelleme, :son_guncelleyen, :silen_kisi,
         NOW(), :silme_notu, :cihaz_sayisi, :masraf_sayisi, :yorum_sayisi,
         :cihaz_ozet, :masraf_ozet, :yorum_ozet)
    """, {
        "original_id": int(t.get("id") or tender_id),
        "kayit_tarihi": t.get("kayit_tarihi") or None,
        "ihale_tarihi": t.get("ihale_tarihi") or None,
        "ikn": t.get("ikn", ""),
        "kurum": t.get("kurum", ""),
        "urun_grubu": t.get("urun_grubu", ""),
        "durum": t.get("durum", ""),
        "ilgili_kisi": t.get("ilgili_kisi", ""),
        "aciklama": t.get("aciklama", ""),
        "son_guncelleme": t.get("son_guncelleme") or None,
        "son_guncelleyen": t.get("son_guncelleyen", ""),
        "silen_kisi": st.session_state.user.get("ad_soyad", ""),
        "silme_notu": silme_notu,
        "cihaz_sayisi": cihaz_sayisi,
        "masraf_sayisi": masraf_sayisi,
        "yorum_sayisi": yorum_sayisi,
        "cihaz_ozet": cihaz_ozet,
        "masraf_ozet": masraf_ozet,
        "yorum_ozet": yorum_ozet,
    })



def normalize_reason_text(value):
    """Silinen ihale neden sınıflandırması için Türkçe karakter ve yazım farklarını sadeleştirir."""
    text = "" if value is None else str(value)
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = (
        text
        .replace("ı", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )
    return text


def classify_deleted_reason_text(row):
    durum = normalize_reason_text(row.get("durum", ""))
    aciklama = normalize_reason_text(row.get("aciklama", ""))
    notu = normalize_reason_text(row.get("silme_notu", ""))

    # İleride farklı kolon adıyla gelirse de yakalasın.
    sonuc = normalize_reason_text(row.get("sonuc", ""))
    sonuc_durum = normalize_reason_text(row.get("sonuc_durum", ""))
    neden = normalize_reason_text(row.get("neden", ""))

    text_blob = " ".join([durum, aciklama, notu, sonuc, sonuc_durum, neden])

    # En üst öncelik: iptal. Durumda veya notta geçerse asla "açıklama yetersiz"e düşmez.
    iptal_kelimeleri = [
        "ihale iptal",
        "iptal edildi",
        "iptal oldu",
        "kurum iptal",
        "iptal"
    ]
    if any(k in text_blob for k in iptal_kelimeleri):
        return "İhale iptal edildi"

    if "girmiyoruz" in text_blob or "girmiyoruz" in durum:
        return "Girmiyoruz"

    if "uymuyor" in text_blob or "uygun degil" in text_blob or "uygun değil" in text_blob:
        return "Şartname / uygunluk problemi"

    if "itiraz" in text_blob and ("red" in text_blob or "redd" in text_blob or "kabul edilmedi" in text_blob):
        return "İtiraz reddi / kurum cevabı"

    if "gecik" in text_blob or "sure" in text_blob or "süre" in text_blob or "kacir" in text_blob or "kaçır" in text_blob:
        return "Süre / gecikme riski"

    if "fiyat" in text_blob or "pahali" in text_blob or "pahalı" in text_blob or "rekabet" in text_blob:
        return "Fiyat / rekabet baskısı"

    if "evrak" in text_blob or "belge" in text_blob or "uts" in text_blob or "üts" in text_blob:
        return "Evrak / belge eksikliği"

    if "cihaz" in text_blob or "marka" in text_blob or "model" in text_blob:
        return "Cihaz / marka uyumu"

    return "Açıklama yetersiz / manuel inceleme"


def deleted_tenders_ai_comment(df):
    if df is None or df.empty:
        return "Silinen ihale kaydı yok. Giremediğimiz ihalelerin nedenlerini analiz etmek için silme sırasında açıklama tutulması gerekir."

    temp = df.copy()
    temp["neden"] = temp.apply(classify_deleted_reason_text, axis=1)
    total = len(temp)
    top_reason = temp["neden"].value_counts().idxmax()
    top_count = int(temp["neden"].value_counts().iloc[0])

    notes = [
        f"Silinen {total} ihale arşivde tutuluyor. En sık neden '{top_reason}' başlığında toplanıyor ({top_count} kayıt)."
    ]

    if top_reason == "Şartname / uygunluk problemi":
        notes.append("Uygunluk kaynaklı kayıplar yüksekse, şartname ilk okuma aşamasında ürün grubu ve cihaz uyum kontrol listesi zorunlu hale getirilmeli.")
    elif top_reason == "İtiraz reddi / kurum cevabı":
        notes.append("İtiraz reddi yoğunlaşıyorsa, itiraz metinleri ve teknik kanıt setleri standartlaştırılmalı.")
    elif top_reason == "Süre / gecikme riski":
        notes.append("Süre/gecikme kaynaklı silinen işler için hatırlatma ve son tarih takibi sıklaştırılmalı.")
    elif top_reason == "Fiyat / rekabet baskısı":
        notes.append("Fiyat kaynaklı elenen işlerde rakip/ürün grubu karşılaştırması yapılmalı ve minimum kâr eşiği netleşmeli.")
    elif top_reason == "Açıklama yetersiz / manuel inceleme":
        notes.append("Açıklamalar yeterli değil. Silme öncesinde 'neden giremedik?' alanı mümkün olduğunca net doldurulmalı.")

    if "ilgili_kisi" in temp.columns:
        sales_counts = temp["ilgili_kisi"].fillna("").astype(str)
        sales_counts = sales_counts[sales_counts.str.strip() != ""]
        if not sales_counts.empty:
            notes.append(f"Silinen işlerin satışçı dağılımı ayrıca izlenmeli; en çok kayıt görünen kişi/grup: {sales_counts.value_counts().idxmax()}.")

    return " ".join(notes)


def get_child_df(table, tender_id):
    return fetch_df(f"SELECT * FROM {table} WHERE ihale_id=:id ORDER BY id DESC", {"id": tender_id}).fillna("").astype(str)


def rename_main_tender_columns(df):
    return df.rename(columns={
        "id": "ID",
        "kayit_tarihi": "Ekleme Tarihi",
        "ihale_tarihi": "İhale Tarihi",
        "ikn": "İKN",
        "kurum": "Kurum",
        "urun_grubu": "Ürün Grubu",
        "durum": "Durum",
        "ilgili_kisi": "İlgili Kişi",
        "son_guncelleme": "Son Güncelleme",
        "son_guncelleyen": "Güncelleyen",
        "aciklama": "Açıklama",
    })


def rename_devices_columns(df):
    return df.rename(columns={
        "cihaz_adedi": "Cihaz Adedi",
        "marka": "Marka",
        "model": "Model",
        "kurulum_yapilacak_hastane_bilgisi": "Kurulum Yapılacak Hastane Bilgisi",
    })


def rename_expenses_columns(df):
    return df.rename(columns={
        "cihaz_adedi": "Cihaz Adedi",
        "masraf_aciklamasi": "Masraf Açıklaması",
        "ihale_miktari": "İhale Miktarı",
        "temin_edilecek_firma": "Temin Edilecek Firma",
    })


def rename_comments_columns(df):
    return df.rename(columns={
        "kullanici": "Kullanıcı",
        "yorum": "Yorum",
        "tarih": "Tarih",
    })


# =========================
# Mail
# =========================
def get_mail_settings():
    df = fetch_df("SELECT * FROM mail_settings WHERE aktif=1 ORDER BY id LIMIT 1")
    if df.empty:
        return None
    return df.fillna("").iloc[0].to_dict()


def send_email_to(to_emails, subject, body):
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    to_emails = [x.strip() for x in to_emails if str(x).strip() and "@" in str(x)]
    if not to_emails:
        return False, "Alıcı mail yok."

    s = get_mail_settings()
    if not s:
        return False, "SMTP aktif değil."

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = s.get("from_email", "")
        msg["To"] = ", ".join(to_emails)
        with smtplib.SMTP(s.get("smtp_host", ""), int(s.get("smtp_port", 587)), timeout=15) as server:
            server.starttls()
            if s.get("smtp_user", ""):
                server.login(s.get("smtp_user", ""), s.get("smtp_password", ""))
            server.sendmail(s.get("from_email", ""), to_emails, msg.as_string())
        return True, "Mail gönderildi."
    except Exception as e:
        return False, str(e)


def user_email_by_name(name):
    df = fetch_df("SELECT email FROM users WHERE LOWER(TRIM(ad_soyad))=LOWER(TRIM(:name)) LIMIT 1", {"name": name})
    if df.empty:
        return ""
    return str(df.iloc[0].get("email", "") or "").strip()


def volkan_email():
    df = fetch_df("""
        SELECT email FROM users
        WHERE aktif=1 AND (LOWER(kullanici_adi) IN ('volky','volkan') OR LOWER(ad_soyad) IN ('volkan','volky'))
        LIMIT 1
    """)
    if df.empty:
        return ""
    return str(df.iloc[0].get("email", "") or "").strip()


def notify_volkan(ihale_id, action_text):
    email = volkan_email()
    if not email:
        return
    tender = get_tender(ihale_id) or {}
    subject = f"İhale güncellemesi: {tender.get('kurum','')} / {tender.get('ikn','')}"
    body = f"""Merhaba Volkan,

Bir ihalede güncelleme yapılmıştır.

İşlem: {action_text}
Kurum: {tender.get('kurum','')}
İKN: {tender.get('ikn','')}
İhale Tarihi: {tender.get('ihale_tarihi','')}
Durum: {tender.get('durum','')}
İlgili Kişi(ler): {tender.get('ilgili_kisi','')}
Son Güncelleme: {tender.get('son_guncelleme','')}

{APP_SYSTEM_NAME}
"""
    send_email_to(email, subject, body)


def send_assignment_mails(tender_id, names):
    tender = get_tender(tender_id) or {}
    results = []
    for name in names:
        email = user_email_by_name(name)
        if not email:
            results.append(f"{name}: mail yok")
            continue
        subject = f"Yeni ihale ataması: {tender.get('kurum','')} / {tender.get('ikn','')}"
        body = f"""Merhaba {name},

Size yeni bir ihale ataması yapılmıştır.

Kurum: {tender.get('kurum','')}
İKN: {tender.get('ikn','')}
İhale Tarihi: {tender.get('ihale_tarihi','')}
Ürün Grubu: {tender.get('urun_grubu','')}
Durum: {tender.get('durum','')}

Lütfen ihale takip panelinden kontrol sağlayınız.

{APP_SYSTEM_NAME}
"""
        ok, msg = send_email_to(email, subject, body)
        results.append(f"{name}: {msg}")
    return " | ".join(results)


# =========================
# Stil
# =========================
def inject_css():
    st.markdown("""
    <style>

    /* Streamlit üst siyah header / toolbar gizleme */
    

    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"],
    

    .block-container {
        padding-top: 1rem !important;
    }

    :root {
        --loji-primary:#157a96;
        --loji-primary-2:#27a7be;
        --loji-primary-soft:#dff3f8;
        --loji-dark:#103f55;
        --loji-dark-2:#1d5c74;
        --loji-border:#c6dfea;
        --loji-text:#173f52;
        --loji-muted:#618290;
        --loji-card:#f7fcfe;
        --loji-input:#ffffff;
    }

    .stApp, [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #edf8fc 0%, #e4f3f8 42%, #eefaf8 100%) !important;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d4761 0%, #13607d 45%, #1b8aa0 100%) !important;
        border-right: 1px solid rgba(255,255,255,.08);
    }

    [data-testid="stSidebar"] * { color: #ffffff !important; }

    .block-container {
        max-width: 1450px;
        padding-top: 1rem;
        padding-bottom: 2rem;
    }

    .brand-banner {
        background: linear-gradient(135deg, rgba(255,255,255,.96) 0%, rgba(244,251,253,.98) 100%);
        border: 1px solid var(--loji-border);
        border-radius: 20px;
        padding: 18px 22px;
        margin-bottom: 1rem;
        box-shadow: 0 12px 30px rgba(12,70,98,.08);
    }

    .brand-title {
        font-size: 30px;
        font-weight: 900;
        color: #0c5671;
        margin: 0;
    }

    .brand-sub {
        color: #416c79;
        font-size: 14px;
        margin-top: 4px;
    }

    h1, h2, h3, h4, h5, h6 {
        color: var(--loji-dark) !important;
        font-weight: 800 !important;
    }

    p, label, .stMarkdown, .stCaption { color: var(--loji-text) !important; }
    .small-muted { color: #5e7f8b; font-size: 12px; }

    /* Buttons */
    .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
        border-radius: 12px !important;
        border: 1px solid #176d86 !important;
        background: linear-gradient(135deg, #1d8dad 0%, #39b4c4 100%) !important;
        color: white !important;
        font-weight: 700 !important;
        box-shadow: 0 6px 16px rgba(22,127,157,.18);
    }

    .stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {
        filter: brightness(1.03);
        transform: translateY(-1px);
    }

    /* Form labels */
    .stTextInput label, .stTextArea label, .stSelectbox label, .stDateInput label, .stNumberInput label {
        color: var(--loji-dark) !important;
        font-weight: 700 !important;
    }

    /* Inputs */
    .stTextInput input,
    .stTextArea textarea,
    .stDateInput input,
    .stNumberInput input,
    [data-baseweb="select"] > div {
        background: linear-gradient(180deg, #ffffff 0%, #f9fcfe 100%) !important;
        color: #163d50 !important;
        border: 1px solid #b7d6e3 !important;
        border-radius: 12px !important;
        box-shadow: inset 0 1px 2px rgba(17,76,102,.06), 0 2px 8px rgba(17,76,102,.04) !important;
    }

    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {
        color: #7c95a1 !important;
        opacity: 1 !important;
    }

    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stDateInput input:focus,
    .stNumberInput input:focus {
        border-color: #4ea5bb !important;
        box-shadow: 0 0 0 3px rgba(39,167,190,.12) !important;
    }

    [data-baseweb="select"] span,
    [data-baseweb="select"] input,
    [data-baseweb="select"] div {
        color: #163d50 !important;
    }

    /* Form and detail cards */
    [data-testid="stExpander"], div[data-testid="stForm"], .stForm {
        background: linear-gradient(180deg, #f8fcfe 0%, #edf7fb 100%) !important;
        border: 1px solid #c7dfea !important;
        border-radius: 18px !important;
        padding: 12px 14px !important;
        box-shadow: 0 10px 24px rgba(18,77,103,.07) !important;
    }

    [data-testid="stDialog"] > div {
        background: linear-gradient(180deg, #fbfeff 0%, #f1f9fc 100%) !important;
        border-radius: 22px !important;
        border: 1px solid #cfe3ec !important;
        box-shadow: 0 18px 42px rgba(18,77,103,.18) !important;
    }
    [data-testid="stDialog"] [data-testid="stVerticalBlock"],
    [data-testid="stDialog"] [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stDialog"] [data-testid="block-container"],
    [data-testid="stDialog"] section.main,
    [data-testid="stDialog"] .main {
        background: transparent !important;
    }
    [data-testid="stDialog"] {
        background: linear-gradient(180deg, #f7fcfe 0%, #edf7fb 100%) !important;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: rgba(255,255,255,.88);
        border: 1px solid #cfe3ec;
        padding: 14px 16px;
        border-radius: 18px;
        box-shadow: 0 10px 22px rgba(18,77,103,.07);
    }

    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {
        color: var(--loji-dark) !important;
    }

    /* Dataframe outer box */
    [data-testid="stDataFrame"] {
        background: linear-gradient(180deg, #ffffff 0%, #f8fcfe 100%) !important;
        border: 1px solid #cfe3ec !important;
        border-radius: 16px !important;
        padding: 6px !important;
        box-shadow: 0 8px 20px rgba(18,77,103,.06) !important;
    }

    /* Dataframe cells and headers */
    [data-testid="stDataFrame"] [role="columnheader"] {
        background: #e8f5fa !important;
        color: #0f4f68 !important;
        font-weight: 700 !important;
        border-color: #d4e6ee !important;
    }

    [data-testid="stDataFrame"] [role="gridcell"] {
        background: #fcfeff !important;
        color: #183f52 !important;
        border-color: #e0edf3 !important;
    }

    [data-testid="stDataFrame"] [role="row"]:nth-child(even) [role="gridcell"] {
        background: #f5fbfe !important;
    }
    .stAlert {
        background: linear-gradient(180deg, #eef8fc 0%, #e7f3f8 100%) !important;
        color: #184257 !important;
        border: 1px solid #c6dfea !important;
        border-radius: 14px !important;
    }
    .stAlert * {
        color: #184257 !important;
    }
    div[data-testid="stForm"] {
        background: linear-gradient(180deg, #f8fcfe 0%, #eef7fb 100%) !important;
    }

    hr { border-color: rgba(18,77,103,.12) !important; }

    /* give containers a softer consistent feel */
    [data-testid="stVerticalBlockBorderWrapper"]:has(> div [data-testid="stDataFrame"]) {
        background: transparent !important;
    }


    /* Açık renk özel HTML tablo: st.dataframe siyah temasını bypass eder */
    .loji-table-wrap {
        background: linear-gradient(180deg, #ffffff 0%, #f8fcfe 100%);
        border: 1px solid #cfe3ec;
        border-radius: 16px;
        overflow: auto;
        box-shadow: 0 8px 20px rgba(18,77,103,.06);
        margin: 10px 0 14px 0;
        max-height: 420px;
    }

    .loji-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
        color: #173f52;
        min-width: 980px;
    }

    .loji-table th {
        position: sticky;
        top: 0;
        z-index: 1;
        background: #e7f4f9;
        color: #0f4f68;
        text-align: left;
        padding: 11px 12px;
        border-right: 1px solid #d4e6ee;
        border-bottom: 1px solid #cfe3ec;
        font-weight: 800;
        white-space: nowrap;
    }

    .loji-table td {
        background: #fcfeff;
        color: #183f52;
        padding: 10px 12px;
        border-top: 1px solid #e0edf3;
        border-right: 1px solid #e0edf3;
        vertical-align: top;
        white-space: nowrap;
    }

    .loji-table tr:nth-child(even) td {
        background: #f5fbfe;
    }

    .loji-table tr:hover td {
        background: #eaf7fb;
    }

    .loji-empty {
        background: linear-gradient(180deg, #eef8fc 0%, #e7f3f8 100%);
        color: #184257;
        border: 1px solid #c6dfea;
        border-radius: 14px;
        padding: 12px 14px;
        margin: 10px 0 14px 0;
    }


    /* Modal / popup gövdesindeki siyah alanı tamamen açık tona zorla */
    div[role="dialog"],
    div[aria-modal="true"],
    [data-testid="stDialog"],
    [data-testid="stDialog"] > div,
    [data-testid="stDialog"] > div > div,
    [data-testid="stDialog"] section,
    [data-testid="stDialog"] [data-testid="stVerticalBlock"],
    [data-testid="stDialog"] [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stDialog"] [data-testid="stElementContainer"] {
        background: linear-gradient(180deg, #fbfeff 0%, #edf8fc 100%) !important;
        color: #143d52 !important;
    }

    div[role="dialog"] *:not(button):not(svg):not(path),
    div[aria-modal="true"] *:not(button):not(svg):not(path),
    [data-testid="stDialog"] *:not(button):not(svg):not(path) {
        color: #143d52 !important;
    }

    div[role="dialog"] h1,
    div[role="dialog"] h2,
    div[role="dialog"] h3,
    div[role="dialog"] h4,
    [data-testid="stDialog"] h1,
    [data-testid="stDialog"] h2,
    [data-testid="stDialog"] h3,
    [data-testid="stDialog"] h4 {
        color: #0d5871 !important;
    }

    div[role="dialog"] hr,
    [data-testid="stDialog"] hr {
        border-color: #c9e0ea !important;
    }

    div[role="dialog"] .stMarkdown,
    [data-testid="stDialog"] .stMarkdown {
        color: #143d52 !important;
    }

    div[role="dialog"] div[data-testid="stForm"],
    [data-testid="stDialog"] div[data-testid="stForm"] {
        background: linear-gradient(180deg, #ffffff 0%, #eef8fc 100%) !important;
        border: 1px solid #c6dfea !important;
        border-radius: 18px !important;
        box-shadow: 0 10px 24px rgba(18,77,103,.08) !important;
    }

    div[role="dialog"] .stAlert,
    [data-testid="stDialog"] .stAlert {
        background: linear-gradient(180deg, #eaf7fc 0%, #dff2f8 100%) !important;
        color: #143d52 !important;
        border: 1px solid #c6dfea !important;
        border-radius: 14px !important;
    }

    /* Popup kapatma X işareti görünür kalsın */
    div[role="dialog"] button[aria-label="Close"],
    [data-testid="stDialog"] button[aria-label="Close"] {
        background: #157a96 !important;
        color: #ffffff !important;
        border-radius: 999px !important;
    }


    /* Takvim kutucuk görünümü */
    .loji-calendar {
        display: grid;
        grid-template-columns: repeat(7, minmax(120px, 1fr));
        gap: 10px;
        margin-top: 14px;
    }

    .loji-cal-head {
        background: linear-gradient(135deg, #167f9d 0%, #2ea7b8 100%);
        color: white;
        border-radius: 12px;
        padding: 10px;
        text-align: center;
        font-weight: 800;
        box-shadow: 0 6px 16px rgba(22,127,157,.15);
    }

    .loji-cal-day {
        min-height: 128px;
        background: linear-gradient(180deg, #ffffff 0%, #f7fcfe 100%);
        border: 1px solid #cfe3ec;
        border-radius: 14px;
        padding: 10px;
        box-shadow: 0 8px 18px rgba(18,77,103,.06);
        overflow: hidden;
    }

    .loji-cal-day.empty {
        opacity: .45;
        background: #edf5f8;
    }

    .loji-cal-num {
        font-weight: 900;
        color: #0c5671;
        margin-bottom: 7px;
    }

    .loji-cal-item {
        background: #e8f6fa;
        border-left: 4px solid #167f9d;
        border-radius: 9px;
        padding: 6px 7px;
        margin-bottom: 6px;
        font-size: 12px;
        color: #143d52;
        line-height: 1.25;
    }

    .loji-cal-item strong {
        color: #0c5671;
    }

    .loji-cal-status {
        display: inline-block;
        margin-top: 3px;
        background: #d7eef5;
        color: #0d5871;
        border-radius: 999px;
        padding: 2px 6px;
        font-size: 11px;
        font-weight: 700;
    }

    @media (max-width: 768px) {
        .loji-calendar {
            grid-template-columns: 1fr;
        }
        .loji-cal-head {
            display: none;
        }
        .loji-cal-day.empty {
            display: none;
        }
    }

    @media (max-width: 768px) {
        .block-container { padding-left: .55rem !important; padding-right: .55rem !important; }
        .brand-title { font-size: 22px !important; }
        .brand-sub { font-size: 12px !important; }
        div[data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; min-width: 100% !important; }
        .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
            width: 100% !important; min-height: 44px !important;
        }
        [data-testid="stDialog"] { width: 96vw !important; max-width: 96vw !important; }
        input, textarea, select { font-size: 16px !important; }
    }
    }


    /* =========================
       V3.9.2 Mobil boşluk düzeltmesi
       ========================= */
    .loji-mobile-cards {
        display: none;
    }

    .loji-mobile-card {
        background: linear-gradient(180deg, #ffffff 0%, #f5fbfe 100%);
        border: 1px solid #cbe3ed;
        border-radius: 16px;
        padding: 13px 14px;
        margin: 10px 0;
        box-shadow: 0 8px 18px rgba(18,77,103,.07);
    }

    .loji-mobile-card-title {
        font-weight: 900;
        color: #0c5671;
        font-size: 15px;
        margin-bottom: 9px;
        line-height: 1.28;
    }

    .loji-mobile-row {
        display: grid;
        grid-template-columns: 38% 62%;
        gap: 8px;
        border-top: 1px solid #e1edf3;
        padding: 7px 0;
        color: #183f52;
        font-size: 13px;
        line-height: 1.32;
    }

    .loji-mobile-row:first-of-type {
        border-top: none;
    }

    .loji-mobile-label {
        color: #577b89;
        font-weight: 800;
    }

    .loji-mobile-value {
        color: #143d52;
        font-weight: 600;
        overflow-wrap: anywhere;
    }

    .mobile-hint {
        display: none;
        background: #dff3f8;
        border: 1px solid #b9dae6;
        color: #0f4f68;
        border-radius: 12px;
        padding: 9px 11px;
        margin: 8px 0 12px 0;
        font-size: 13px;
        font-weight: 700;
    }

    @media (max-width: 768px) {
        html, body, .stApp {
            overflow-x: hidden !important;
        }

        .block-container {
            padding-left: .65rem !important;
            padding-right: .65rem !important;
            padding-top: .65rem !important;
            max-width: 100% !important;
        }

        h1 {
            font-size: 1.55rem !important;
            line-height: 1.18 !important;
            margin-bottom: .55rem !important;
        }

        h2 {
            font-size: 1.28rem !important;
            line-height: 1.2 !important;
        }

        h3 {
            font-size: 1.08rem !important;
            line-height: 1.2 !important;
        }

        .mobile-hint {
            display: block !important;
        }

        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
            margin-bottom: .35rem !important;
        }

        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: .35rem !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] button {
            width: 100% !important;
            min-height: 46px !important;
            font-size: 15px !important;
            border-radius: 13px !important;
            padding: 10px 12px !important;
        }

        input, textarea, select {
            font-size: 16px !important;
        }

        .stTextInput input,
        .stTextArea textarea,
        .stDateInput input,
        .stNumberInput input,
        [data-baseweb="select"] > div {
            min-height: 44px !important;
            border-radius: 13px !important;
        }

        .loji-table-wrap {
            display: none !important;
        }

        .loji-mobile-cards {
            display: block !important;
        }

        [data-testid="stPlotlyChart"] {
            overflow-x: auto !important;
            border-radius: 14px !important;
        }

        div[role="dialog"] {
            width: 97vw !important;
            max-width: 97vw !important;
            margin: 0 auto !important;
        }

        div[role="dialog"] > div {
            max-height: 92vh !important;
            overflow-y: auto !important;
        }

        .loji-calendar {
            grid-template-columns: 1fr !important;
            gap: 8px !important;
        }

        .loji-cal-head,
        .loji-cal-day.empty {
            display: none !important;
        }

        .loji-cal-day {
            min-height: auto !important;
            padding: 11px !important;
        }

        .loji-cal-item {
            font-size: 12.5px !important;
        }
    }

    @media (min-width: 769px) {
        .loji-mobile-cards {
            display: none !important;
        }
    }

    




/* === Native Streamlit sidebar modu === */
/* Sidebar aç/kapat okuna dokunmuyoruz. Bu yüzden kapanınca tekrar açılabilir. */
/* Üst barın siyah görünümü Streamlit native kontrolden gelir; navigasyon stabilitesi için saklanmaz. */

</style>
    """, unsafe_allow_html=True)





def render_mobile_cards(df, title_cols=None, hidden_cols=None, max_rows=None):
    """Mobilde tabloları kart olarak gösterir. Masaüstünde CSS ile gizlenir ve boşluk bırakmaz."""
    if df is None or df.empty:
        return

    title_cols = title_cols or ["Kurum", "kurum", "İKN", "ikn", "Satışçı", "satisci", "Ürün Grubu", "urun_grubu"]
    hidden_cols = set(hidden_cols or [])
    show_df = df.copy()
    if max_rows:
        show_df = show_df.head(max_rows)

    cards = []
    for _, row in show_df.iterrows():
        title_bits = []
        for c in title_cols:
            if c in show_df.columns:
                v = row.get(c, "")
                if not pd.isna(v) and str(v).strip():
                    title_bits.append(str(v).strip())
            if len(title_bits) >= 2:
                break

        title = " | ".join(title_bits) if title_bits else "Kayıt"
        rows_html = []
        for c in show_df.columns:
            if c in hidden_cols:
                continue
            v = row.get(c, "")
            if pd.isna(v):
                v = ""
            v = str(v)
            if v.strip() == "":
                continue
            rows_html.append(
                '<div class="loji-mobile-row">'
                f'<div class="loji-mobile-label">{html.escape(str(c))}</div>'
                f'<div class="loji-mobile-value">{html.escape(v)}</div>'
                '</div>'
            )

        cards.append(
            '<div class="loji-mobile-card">'
            f'<div class="loji-mobile-card-title">{html.escape(title)}</div>'
            f'{"".join(rows_html)}'
            '</div>'
        )

    full_html = (
        '<div class="loji-mobile-cards">'
        '<div class="mobile-hint">İhaleler: </div>'
        f'{"".join(cards)}'
        '</div>'
    )
    st.markdown(full_html, unsafe_allow_html=True)



def render_html_table(df, empty_message="Kayıt yok.", max_rows=None):
    """Açık renk HTML tablo basar; mobilde kart görünümü, masaüstünde tablo görünümü verir."""
    df = format_result_display_df(df)
    if df is None or df.empty:
        st.markdown(f"<div class='loji-empty'>{html.escape(empty_message)}</div>", unsafe_allow_html=True)
        return

    show_df = df.copy()
    if max_rows:
        show_df = show_df.head(max_rows)

    # Mobil kart görünümü. Desktop'ta CSS display:none olduğu için boşluk bırakmaz.
    render_mobile_cards(show_df, max_rows=max_rows)

    # Masaüstü tablo görünümü.
    headers = "".join([f"<th>{html.escape(str(c))}</th>" for c in show_df.columns])
    rows = []
    for _, row in show_df.iterrows():
        cells = "".join([
            f"<td>{html.escape('' if pd.isna(v) else str(v))}</td>"
            for v in row.tolist()
        ])
        rows.append(f"<tr>{cells}</tr>")

    table = f"""
    <div class="loji-table-wrap">
      <table class="loji-table">
        <thead><tr>{headers}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """
    st.markdown(table, unsafe_allow_html=True)


def render_brand():
    title = html.escape(APP_BRAND_TITLE)
    subtitle = html.escape(APP_BRAND_SUBTITLE)
    st.markdown(f"""
    <div class="brand-banner">
      <div class="brand-title">{title}</div>
      <div class="brand-sub">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


# =========================
# Auth
# =========================
def login():
    render_brand()
    st.title("Giriş")
    st.caption("Kullanıcı bilgilerinle panele giriş yapabilirsin.")
    with st.form("login_form"):
        username = st.text_input("Kullanıcı adı")
        password = st.text_input("Şifre", type="password")
        ok = st.form_submit_button("Giriş Yap")
    if ok:
        df = fetch_df("""
            SELECT id, kullanici_adi, ad_soyad, rol, aktif, email
            FROM users
            WHERE kullanici_adi=:u AND sifre=:p AND aktif=1
            LIMIT 1
        """, {"u": username, "p": password})
        if df.empty:
            st.error("Kullanıcı adı veya şifre hatalı.")
        else:
            st.session_state.logged = True
            st.session_state.user = df.fillna("").iloc[0].to_dict()
            st.rerun()


def sidebar_nav():
    st.sidebar.markdown(f"## {APP_SIDEBAR_TITLE}")
    st.sidebar.caption(st.session_state.user.get("ad_soyad", ""))
    st.sidebar.caption("Admin" if is_admin() else "Satış")
    pages = ["İhale Listesi", "Takvim", "Takip Edilenler", "Kazanılanlar", "Kaybedilenler", "Özel İşler", "Alınan Özel İşler", "Satış Analizi"]
    if is_admin():
        pages += ["Silinen İhaleler", "Kullanıcılar", "Mail Ayarları"]
    page = st.sidebar.radio("Menü", pages)
    if st.sidebar.button("Çıkış"):
        st.session_state.clear()
        st.rerun()
    return page


# =========================
# Liste ve detay
# =========================
def status_pills():
    c = get_counts_live()
    cols = st.columns(5)
    cols[0].metric("Listede", c["listede"])
    cols[1].metric("Takipte", c["takipte"])
    cols[2].metric("İtiraz", c["itiraz"])
    cols[3].metric("Kazanılan", c["kazanilan"])
    cols[4].metric("Kaybedilen", c["kaybedilen"])


def query_tenders(kind="list", search="", limit=100):
    params = {"limit": int(limit)}

    if kind in ["won", "lost"]:
        status = "Kazanıldı" if kind == "won" else "Kaybedildi"
        params["status"] = status
        search_sql = ""
        if search:
            search_sql = "AND (t.kurum LIKE :s OR t.ikn LIKE :s OR t.urun_grubu LIKE :s OR t.ilgili_kisi LIKE :s OR p.sonuc_urun_grubu LIKE :s)"
            params["s"] = f"%{search}%"
        return fetch_df(f"""
            SELECT DISTINCT t.id, t.kayit_tarihi, t.ihale_tarihi, t.ikn, t.kurum, t.urun_grubu, t.durum,
                   t.ilgili_kisi, t.son_guncelleme, t.son_guncelleyen, t.aciklama
            FROM tenders t
            JOIN tender_result_parts p ON p.ihale_id=t.id AND p.sonuc_durum=:status
            WHERE 1=1 {search_sql}
            ORDER BY t.id DESC
            LIMIT :limit
        """, params).fillna("")

    where = []
    if kind == "list":
        where.append("takip_ediliyor=0")
        where.append("durum NOT IN ('Kazanıldı','Kaybedildi','Kısmi Sonuçlandı')")
    elif kind == "followed":
        where.append("takip_ediliyor=1")
        where.append("durum NOT IN ('Kazanıldı','Kaybedildi','Kısmi Sonuçlandı')")

    if search:
        where.append("(kurum LIKE :s OR ikn LIKE :s OR urun_grubu LIKE :s OR ilgili_kisi LIKE :s)")
        params["s"] = f"%{search}%"

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    return fetch_df(f"""
        SELECT id, kayit_tarihi, ihale_tarihi, ikn, kurum, urun_grubu, durum,
               ilgili_kisi, son_guncelleme, son_guncelleyen, aciklama
        FROM tenders
        {where_sql}
        ORDER BY id DESC
        LIMIT :limit
    """, params).fillna("")


def render_tender_list(kind, title):
    st.title(title)
    status_pills()
    search = st.text_input("Ara", placeholder="Kurum, İKN, ürün grubu veya kişi ara")
    df = query_tenders(kind=kind, search=search, limit=100)

    if df.empty:
        st.info("Kayıt yok.")
        return None

    view = df.copy()
    for col in ["kayit_tarihi", "son_guncelleme"]:
        if col in view.columns:
            view[col] = pd.to_datetime(view[col], errors="coerce").dt.strftime("%d.%m.%Y %H:%M").fillna("")
    if "ihale_tarihi" in view.columns:
        view["ihale_tarihi"] = pd.to_datetime(view["ihale_tarihi"], errors="coerce").dt.strftime("%d.%m.%Y").fillna("")

    view = rename_main_tender_columns(view)
    render_html_table(view, empty_message="Listelenecek ihale yok.", max_rows=100)

    options = [f"{int(r.id)} | {r.kurum} | {r.ikn} | {dt_to_panel(r.ihale_tarihi, False)}" for _, r in df.iterrows()]
    selected = st.selectbox("İşlem yapmak / detay görmek için ihale seç", [""] + options)
    if selected:
        return int(selected.split("|")[0].strip())
    return None


def admin_add_tender():
    sales = get_sales_users_cached()
    if sales.empty:
        st.warning("Önce satış kullanıcısı eklemelisin.")
        return

    with st.expander("➕ Yeni ihale ekle", expanded=False):
        with st.form("new_tender", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            ihale_tarihi = c1.date_input("İhale Tarihi", format="DD.MM.YYYY")
            ikn = c2.text_input("İKN")
            urun_grubu = c3.text_input("Ürün Grubu", placeholder="Örn: Kan G, Hepatit, IACC")
            kurum = st.text_input("Kurum / İhale adı")
            c4, c5, c6 = st.columns(3)
            durum = c4.selectbox("Durum", ADMIN_STATUS_OPTIONS)
            selected_sales = c5.multiselect("İlgili satışçı(lar)", sales["ad_soyad"].tolist())
            takip = c6.selectbox("Takip Edilenlere Al", ["Hayır", "Evet"])
            aciklama = st.text_area("Açıklama")
            save = st.form_submit_button("İhaleyi Kaydet")
        if save:
            if not selected_sales:
                st.warning("En az bir satışçı seçmelisin.")
                st.stop()
            
            with ENGINE.begin() as conn:
                res = conn.execute(text("""
                    INSERT INTO tenders
                    (ihale_tarihi, ikn, kurum, urun_grubu, durum, ilgili_kisi, takip_ediliyor,
                     aciklama, kayit_tarihi, aksiyon_alindi)
                    VALUES
                    (:ihale_tarihi, :ikn, :kurum, :urun_grubu, :durum, :ilgili_kisi, :takip,
                     :aciklama, NOW(), 0)
                """), {
                    "ihale_tarihi": ihale_tarihi,
                    "ikn": ikn,
                    "kurum": kurum,
                    "urun_grubu": urun_grubu,
                    "durum": durum,
                    "ilgili_kisi": assigned_people_text(selected_sales),
                    "takip": 1 if takip == "Evet" else 0,
                    "aciklama": aciklama
                })
                tender_id = res.lastrowid
            clear_caches()
            log_action(tender_id, "Yeni ihale eklendi")
            send_assignment_mails(tender_id, selected_sales)
            notify_volkan(tender_id, "Yeni ihale eklendi")
            st.success("İhale MySQL'e kaydedildi.")
            st.rerun()


@st.dialog("İhale İşlem Ekranı", width="large")
def details_dialog(tender_id):
    tender = get_tender(tender_id)
    if not tender:
        st.error("İhale bulunamadı.")
        return

    can_edit = current_user_can_edit(tender)

    st.markdown("### İhale Bilgileri")
    st.caption("Seçili ihalenin temel bilgileri aşağıda yer alır.")
    render_html_table(pd.DataFrame([{
        "Ekleme Tarihi": tender.get("kayit_tarihi", ""),
        "İhale Tarihi": tender.get("ihale_tarihi", ""),
        "İKN": tender.get("ikn", ""),
        "Kurum": tender.get("kurum", ""),
        "Ürün Grubu": tender.get("urun_grubu", ""),
        "Durum": tender.get("durum", ""),
        "İhale Süresi (Ay)": tender.get("ihale_suresi_ay", ""),
        "İhale Yıllık Getiri": format_money_tr(tender.get("yillik_getiri", "")),
        "Sözleşme Başlangıç": tender.get("sozlesme_baslangic_tarihi", ""),
        "İlgili Kişi": tender.get("ilgili_kisi", ""),
        "Son Güncelleme": tender.get("son_guncelleme", ""),
        "Güncelleyen": tender.get("son_guncelleyen", ""),
        "Açıklama": tender.get("aciklama", ""),
    }]), empty_message="İhale bilgisi yok.")


    if is_admin():
        with st.expander("Temel ihale bilgilerini düzenle", expanded=False):
            st.caption("Kurum adı, İKN, ihale tarihi, ürün grubu ve ilgili kişi bilgisini buradan düzeltebilirsin.")

            sales_df_edit = get_sales_users_cached()
            sales_options_edit = sales_df_edit["ad_soyad"].tolist() if not sales_df_edit.empty else []
            current_people_edit = assigned_people_list(tender.get("ilgili_kisi", ""))

            # Eski kayıtta pasif kullanıcı varsa listeden kaybolmasın.
            for person in current_people_edit:
                if person not in sales_options_edit:
                    sales_options_edit.append(person)

            default_people_edit = [p for p in current_people_edit if p in sales_options_edit]

            with st.form(f"main_tender_info_edit_{tender_id}"):
                c1, c2, c3 = st.columns([1, 1, 1.4])

                edit_ihale_tarihi = c1.date_input(
                    "İhale Tarihi",
                    value=parse_tr_date(tender.get("ihale_tarihi", "")) or date.today(),
                    format="DD.MM.YYYY",
                    key=f"edit_ihale_tarihi_{tender_id}"
                )

                edit_ikn = c2.text_input(
                    "İKN",
                    value=str(tender.get("ikn", "") or ""),
                    key=f"edit_ikn_{tender_id}"
                )

                edit_urun_grubu = c3.text_input(
                    "Ürün Grubu",
                    value=str(tender.get("urun_grubu", "") or ""),
                    key=f"edit_urun_grubu_{tender_id}"
                )

                edit_kurum = st.text_input(
                    "Kurum / İhale adı",
                    value=str(tender.get("kurum", "") or ""),
                    key=f"edit_kurum_{tender_id}"
                )

                edit_people = st.multiselect(
                    "İlgili kişi / kişiler",
                    options=sales_options_edit,
                    default=default_people_edit,
                    key=f"edit_ilgili_kisi_{tender_id}"
                )

                save_main_info = st.form_submit_button("Temel Bilgileri Güncelle")

            if save_main_info:
                if not str(edit_kurum).strip():
                    st.error("Kurum / ihale adı boş bırakılamaz.")
                    st.stop()

                old_summary = (
                    f"Kurum: {tender.get('kurum','')} | "
                    f"İKN: {tender.get('ikn','')} | "
                    f"Ürün Grubu: {tender.get('urun_grubu','')} | "
                    f"İhale Tarihi: {tender.get('ihale_tarihi','')} | "
                    f"İlgili Kişi: {tender.get('ilgili_kisi','')}"
                )

                new_people_text = assigned_people_text(edit_people)

                execute("""
                    UPDATE tenders
                    SET ihale_tarihi=:ihale_tarihi,
                        ikn=:ikn,
                        kurum=:kurum,
                        urun_grubu=:urun_grubu,
                        ilgili_kisi=:ilgili_kisi,
                        son_guncelleme=NOW(),
                        son_guncelleyen=:user
                    WHERE id=:id
                """, {
                    "id": tender_id,
                    "ihale_tarihi": edit_ihale_tarihi,
                    "ikn": edit_ikn,
                    "kurum": edit_kurum.strip(),
                    "urun_grubu": edit_urun_grubu,
                    "ilgili_kisi": new_people_text,
                    "user": st.session_state.user.get("ad_soyad", "")
                })

                new_summary = (
                    f"Kurum: {edit_kurum.strip()} | "
                    f"İKN: {edit_ikn} | "
                    f"Ürün Grubu: {edit_urun_grubu} | "
                    f"İhale Tarihi: {edit_ihale_tarihi.strftime('%d.%m.%Y')} | "
                    f"İlgili Kişi: {new_people_text}"
                )

                clear_caches()
                log_action(tender_id, f"Temel ihale bilgileri güncellendi. Eski: {old_summary} → Yeni: {new_summary}")
                st.success("Temel ihale bilgileri güncellendi.")
                st.rerun()


    if not can_edit:
        st.info("Bu ihaleyi görüntüleyebilirsin. İşlem yetkisi sadece atanan satışçı(lar) ve adminlerde vardır.")

    st.divider()
    st.markdown("### Durum / Açıklama")
    if can_edit:
        with st.form(f"status_{tender_id}"):
            opts = ADMIN_STATUS_OPTIONS if is_admin() else SALES_STATUS_OPTIONS
            idx = opts.index(tender["durum"]) if tender["durum"] in opts else 0
            new_status = st.selectbox("Durum", opts, index=idx)
            takip = tender.get("takip_ediliyor", "Hayır")
            if is_admin():
                takip = st.selectbox("Takip Edilenlere Al", ["Hayır", "Evet"], index=1 if takip == "Evet" else 0)
            ihale_suresi_ay_status = st.number_input(
                "İhale Süresi (Ay)",
                min_value=1,
                step=1,
                value=int(float(tender.get("ihale_suresi_ay") or 12)),
                key=f"status_contract_months_{tender_id}"
            )
            aciklama = st.text_area("Açıklama", value=tender.get("aciklama", ""))
            if st.form_submit_button("Durumu Kaydet"):
                set_objection_watch(tender_id, new_status)
                execute("""
                    UPDATE tenders
                    SET durum=:durum, takip_ediliyor=:takip, aciklama=:aciklama,
                        ihale_suresi_ay=:ihale_suresi_ay,
                        aksiyon_alindi=1, son_guncelleme=NOW(), son_guncelleyen=:user
                    WHERE id=:id
                """, {
                    "id": tender_id,
                    "durum": new_status,
                    "takip": 1 if takip == "Evet" else 0,
                    "aciklama": aciklama,
                    "ihale_suresi_ay": int(ihale_suresi_ay_status),
                    "user": st.session_state.user.get("ad_soyad", "")
                })
                clear_caches()
                log_action(tender_id, f"Durum güncellendi: {tender.get('durum','')} → {new_status}")
                notify_volkan(tender_id, f"Durum güncellendi: {tender.get('durum','')} → {new_status}")
                st.success("Durum kaydedildi.")
                st.rerun()

    st.divider()
    st.markdown("### Cihaz Bilgileri")
    devices = get_child_df("devices", tender_id)
    show_cols = ["cihaz_adedi", "marka", "model", "kurulum_yapilacak_hastane_bilgisi"]
    if not devices.empty:
        render_html_table(rename_devices_columns(devices[show_cols]), empty_message="Henüz cihaz bilgisi girilmemiş.")
        editable_sql_rows(
            "İhale Cihaz",
            devices,
            "devices",
            "id",
            {
                "cihaz_adedi": "Cihaz Adedi",
                "marka": "Marka",
                "model": "Model",
                "kurulum_yapilacak_hastane_bilgisi": "Kurulum Yapılacak Hastane Bilgisi",
            },
            numeric_fields=["cihaz_adedi"],
            text_area_fields=["kurulum_yapilacak_hastane_bilgisi"],
            log_func=log_tender_edit_row,
            parent_id=tender_id,
            update_log_text="İhale cihaz satırı güncellendi",
            delete_log_text="İhale cihaz satırı silindi"
        )
    else:
        st.info("Henüz cihaz bilgisi girilmemiş.")
    if can_edit:
        with st.form(f"device_{tender_id}", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([1, 2, 2, 4])
            adet = c1.number_input("Cihaz Adedi", min_value=1, step=1)
            marka = c2.text_input("Marka")
            model = c3.text_input("Model")
            yer = c4.text_input("Kurulum Yapılacak Hastane Bilgisi")
            if st.form_submit_button("Cihaz Satırı Ekle"):
                execute("""
                    INSERT INTO devices (ihale_id, cihaz_adedi, marka, model, kurulum_yapilacak_hastane_bilgisi)
                    VALUES (:ihale_id, :adet, :marka, :model, :yer)
                """, {"ihale_id": tender_id, "adet": int(adet), "marka": marka, "model": model, "yer": yer})
                mark_action(tender_id)
                log_action(tender_id, "Cihaz bilgisi eklendi")
                st.success("Cihaz eklendi.")
                st.rerun()

    st.divider()
    st.markdown("### Masraf Bilgileri")
    expenses = get_child_df("expenses", tender_id)
    show_cols = ["sira_no", "masraf_aciklamasi", "ihale_miktari", "temin_edilecek_firma"]
    if not expenses.empty:
        render_html_table(rename_expenses_columns(expenses[show_cols]), empty_message="Henüz masraf bilgisi girilmemiş.")
        editable_sql_rows(
            "İhale Masraf",
            expenses,
            "expenses",
            "id",
            {
                "sira_no": "Sıra No",
                "masraf_aciklamasi": "Masraf Açıklaması",
                "ihale_miktari": "İhale Miktarı",
                "temin_edilecek_firma": "Temin Edilecek Firma",
            },
            numeric_fields=["sira_no"],
            text_area_fields=["masraf_aciklamasi"],
            log_func=log_tender_edit_row,
            parent_id=tender_id,
            update_log_text="İhale masraf satırı güncellendi",
            delete_log_text="İhale masraf satırı silindi"
        )
    else:
        st.info("Henüz masraf bilgisi girilmemiş.")
    if can_edit:
        with st.form(f"expense_{tender_id}", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([1, 4, 2, 3])
            sira = c1.number_input("Sıra No", min_value=1, step=1)
            masraf = c2.text_input("Masraf Açıklaması")
            miktar = c3.text_input("İhale Miktarı")
            firma = c4.text_input("Temin Edilecek Firma")
            if st.form_submit_button("Masraf Satırı Ekle"):
                execute("""
                    INSERT INTO expenses (ihale_id, sira_no, masraf_aciklamasi, ihale_miktari, temin_edilecek_firma)
                    VALUES (:ihale_id, :sira, :masraf, :miktar, :firma)
                """, {"ihale_id": tender_id, "sira": int(sira), "masraf": masraf, "miktar": miktar, "firma": firma})
                mark_action(tender_id)
                log_action(tender_id, "Masraf bilgisi eklendi")
                st.success("Masraf eklendi.")
                st.rerun()

    st.divider()
    st.markdown("### Yorumlar")
    comments = get_child_df("comments", tender_id)
    if not comments.empty:
        render_html_table(rename_comments_columns(comments[["kullanici", "yorum", "tarih"]]), empty_message="Henüz yorum yok.")
    else:
        st.caption("Henüz yorum yok.")
    if can_edit:
        with st.form(f"comment_{tender_id}", clear_on_submit=True):
            yorum = st.text_area("Yorum yaz")
            if st.form_submit_button("Yorum Ekle") and yorum.strip():
                execute("""
                    INSERT INTO comments (ihale_id, kullanici, yorum, tarih)
                    VALUES (:ihale_id, :kullanici, :yorum, NOW())
                """, {"ihale_id": tender_id, "kullanici": st.session_state.user.get("ad_soyad", ""), "yorum": yorum})
                mark_action(tender_id)
                log_action(tender_id, "Yorum eklendi")
                st.success("Yorum eklendi.")
                st.rerun()


    if can_edit:
        st.divider()
        st.markdown("### Bilgileri Kaydet / Bildir")
        st.caption("Cihaz, masraf ve yorum satırlarını ekledikten sonra bu butona basınız.")

        if st.button("Bilgileri Kaydet", type="primary", key=f"finish_tender_update_{tender_id}"):
            cihaz_sayisi_df = fetch_df("SELECT COUNT(*) AS adet FROM devices WHERE ihale_id=:id", {"id": tender_id})
            masraf_sayisi_df = fetch_df("SELECT COUNT(*) AS adet FROM expenses WHERE ihale_id=:id", {"id": tender_id})
            yorum_sayisi_df = fetch_df("SELECT COUNT(*) AS adet FROM comments WHERE ihale_id=:id", {"id": tender_id})

            cihaz_sayisi = int(cihaz_sayisi_df.iloc[0]["adet"] or 0) if not cihaz_sayisi_df.empty else 0
            masraf_sayisi = int(masraf_sayisi_df.iloc[0]["adet"] or 0) if not masraf_sayisi_df.empty else 0
            yorum_sayisi = int(yorum_sayisi_df.iloc[0]["adet"] or 0) if not yorum_sayisi_df.empty else 0

            execute("""
                UPDATE tenders
                SET aksiyon_alindi=1,
                    son_guncelleme=NOW(),
                    son_guncelleyen=:user
                WHERE id=:id
            """, {
                "id": tender_id,
                "user": st.session_state.user.get("ad_soyad", "")
            })

            log_action(
                tender_id,
                f"Bilgiler kaydedildi. Cihaz: {cihaz_sayisi}, Masraf: {masraf_sayisi}, Yorum: {yorum_sayisi}"
            )
            notify_volkan(
                tender_id,
                f"Bilgiler kaydedildi. Cihaz: {cihaz_sayisi}, Masraf: {masraf_sayisi}, Yorum: {yorum_sayisi}"
            )
            clear_caches()
            st.success("Bilgiler kaydedildi Teşekkürler.")



    if is_admin():
        st.divider()
        st.markdown("### Admin İşlemleri")

        # Sonuç girişi en üstte: ürün grubu seçilir, her grup için ayrı kazanıldı/kaybedildi kartı açılır.
        render_partial_results_admin(tender, tender_id)

        st.divider()
        st.markdown("### Genel Admin Bilgileri")
        sales = get_sales_users_cached()

        with st.form(f"admin_general_{tender_id}", enter_to_submit=False):
            c1, c2, c3 = st.columns(3)
            current_assigned = [x for x in assigned_people_list(tender.get("ilgili_kisi", "")) if x in sales["ad_soyad"].tolist()]
            selected_sales = c1.multiselect("İlgili kişi / kişiler", sales["ad_soyad"].tolist(), default=current_assigned)
            takip_admin = c2.selectbox("Takip Edilenlere Al", ["Hayır", "Evet"], index=1 if tender.get("takip_ediliyor") == "Evet" else 0)
            current_date = parse_tr_date(tender.get("ihale_tarihi")) or date.today()
            new_date = c3.date_input("İhale Tarihi", value=current_date, format="DD.MM.YYYY")

            admin_note_general = st.text_area("Genel admin notu / açıklama", value=str(tender.get("aciklama", "") or ""))
            save_general = st.form_submit_button("Genel Bilgileri Kaydet")

        if save_general:
            if not selected_sales:
                st.warning("En az bir satışçı seçmelisin.")
                st.stop()

            new_assigned = assigned_people_text(selected_sales)
            old_set = set([x.lower() for x in assigned_people_list(tender.get("ilgili_kisi", ""))])
            new_added = [x for x in selected_sales if x.lower() not in old_set]

            execute("""
                UPDATE tenders
                SET ilgili_kisi=:ilgili,
                    ihale_tarihi=:ihale_tarihi,
                    takip_ediliyor=:takip,
                    aciklama=:aciklama,
                    son_guncelleme=NOW(),
                    son_guncelleyen=:user
                WHERE id=:id
            """, {
                "id": tender_id,
                "ilgili": new_assigned,
                "ihale_tarihi": new_date,
                "takip": 1 if takip_admin == "Evet" else 0,
                "aciklama": admin_note_general,
                "user": st.session_state.user.get("ad_soyad", "")
            })

            clear_caches()
            log_action(tender_id, "Genel admin bilgileri güncellendi")
            if new_added:
                send_assignment_mails(tender_id, new_added)
            notify_volkan(tender_id, "Genel admin bilgileri güncellendi")
            st.success("Genel admin bilgileri kaydedildi.")
            st.rerun()

        delete_reason = st.text_area(
            "Silme notu / giremediysek nedeni",
            value=str(tender.get("aciklama", "") or ""),
            key=f"delete_reason_{tender_id}",
            help="Silinen ihaleler arşivine bu açıklamayla kaydedilir. Otomatik analizinde neden giremediğimizi yorumlamak için kullanılır."
        )

        if st.button("İhaleyi Kaldır ve Silinenlere Aktar", key=f"delete_tender_{tender_id}"):
            archive_tender_before_delete(tender_id, delete_reason or "Admin tarafından kaldırıldı")

            # Bağlı kayıtlar temizlenir, ana ihale silinir.
            for table_name in ["tender_result_parts", "devices", "expenses", "comments", "logs"]:
                try:
                    execute(f"DELETE FROM {table_name} WHERE ihale_id=:id", {"id": tender_id})
                except Exception:
                    pass

            execute("DELETE FROM tenders WHERE id=:id", {"id": tender_id})
            clear_caches()
            st.success("İhale silindi ve Silinen İhaleler arşivine aktarıldı.")
            st.rerun()



# =========================
# Sayfalar
# =========================

def style_plotly(fig):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#f7fcfe",
        plot_bgcolor="#ffffff",
        font=dict(color="#173f52", size=13),
        title=dict(font=dict(color="#0c5671", size=18)),
        legend=dict(
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#d7e8ef",
            borderwidth=1,
            font=dict(color="#173f52", size=12),
        ),
        margin=dict(l=40, r=30, t=70, b=40),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#e4eef3",
        linecolor="#cfe0e8",
        tickfont=dict(color="#173f52"),
        title_font=dict(color="#0c5671"),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#e4eef3",
        linecolor="#cfe0e8",
        tickfont=dict(color="#173f52"),
        title_font=dict(color="#0c5671"),
    )
    return fig


def make_full_export_excel():
    output = io.BytesIO()
    tables = {
        "İhaleler": "SELECT * FROM tenders ORDER BY id DESC",
        "Cihaz Bilgileri": "SELECT * FROM devices ORDER BY id DESC",
        "Masraf Bilgileri": "SELECT * FROM expenses ORDER BY id DESC",
        "Yorumlar": "SELECT * FROM comments ORDER BY id DESC",
        "Kazanılan İhaleler": "SELECT * FROM won_tenders ORDER BY id DESC",
        "Kaybedilen İhaleler": "SELECT * FROM lost_tenders ORDER BY id DESC",
        "Kısmi Sonuçlar": "SELECT * FROM tender_result_parts ORDER BY id DESC",
        "Silinen İhaleler": "SELECT * FROM deleted_tenders ORDER BY id DESC",
        "İşlem Geçmişi": "SELECT * FROM logs ORDER BY id DESC",
        "Kullanıcılar": "SELECT id,kullanici_adi,ad_soyad,rol,aktif,email,created_at FROM users ORDER BY id",
        "Mail Uyarıları": "SELECT * FROM mail_warnings ORDER BY id DESC",
        "Mail Ayarları": "SELECT id,smtp_host,smtp_port,smtp_user,from_email,aktif FROM mail_settings ORDER BY id",
        "Özel İşler": "SELECT * FROM private_jobs ORDER BY id DESC",
        "Özel İş Cihazları": "SELECT * FROM private_job_devices ORDER BY id DESC",
        "Özel İş Testleri": "SELECT * FROM private_job_tests ORDER BY id DESC",
        "Özel İş Yorumları": "SELECT * FROM private_job_comments ORDER BY id DESC",
        "Özel İş Logları": "SELECT * FROM private_job_logs ORDER BY id DESC",
    }
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet, sql in tables.items():
            fetch_df(sql).to_excel(writer, sheet_name=sheet[:31], index=False)
    output.seek(0)
    return output.getvalue()


def render_export_button():
    if not is_admin():
        return
    if "export_bytes" not in st.session_state:
        st.session_state.export_bytes = None
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📦 Excel'i Hazırla", use_container_width=True):
            with st.spinner("Excel hazırlanıyor..."):
                st.session_state.export_bytes = make_full_export_excel()
            st.success("Excel hazır.")
    with c2:
        if st.session_state.export_bytes:
            st.download_button("📥 Excel'i İndir", st.session_state.export_bytes,
                               file_name=f"ihale_takip_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)



# =========================
# Özel İşler Modülü
# =========================
def log_private_job(job_id, islem):
    execute("""
        INSERT INTO private_job_logs (private_job_id, kullanici, islem, tarih)
        VALUES (:job_id, :kullanici, :islem, NOW())
    """, {"job_id": job_id, "kullanici": st.session_state.user.get("ad_soyad", ""), "islem": islem})


def get_private_job(job_id):
    df = fetch_df("SELECT * FROM private_jobs WHERE id=:id LIMIT 1", {"id": job_id})
    if df.empty:
        return None
    row = df.fillna("").iloc[0].to_dict()
    for c in ["kayit_tarihi", "son_guncelleme", "onay_tarihi"]:
        if row.get(c):
            row[c] = dt_to_panel(row.get(c))
    return {k: "" if v is None else str(v) for k, v in row.items()}


def notify_volkan_private_job(job_id, action_text):
    email = volkan_email()
    if not email:
        return
    job = get_private_job(job_id) or {}
    subject = f"Özel iş güncellemesi: {job.get('kurum_adi','')} / {job.get('urun_grubu','')}"
    body = f"""Merhaba Volkan,

Bir özel iş kaydında güncelleme yapılmıştır.

İşlem: {action_text}
Kurum: {job.get('kurum_adi','')}
Ürün Grubu: {job.get('urun_grubu','')}
İstenen Cihaz Miktarı: {job.get('istenen_cihaz_miktari','')}
Durum: {job.get('durum','')}
İlgili Kişi: {job.get('ilgili_kisi','')}
Onay Fiyatı: {job.get('onay_fiyati','')}
Son Güncelleme: {job.get('son_guncelleme','')}

{APP_SYSTEM_NAME}
"""
    send_email_to(email, subject, body)


def private_jobs_summary():
    df = fetch_df("""
        SELECT
          SUM(CASE WHEN alinan_is=0 THEN 1 ELSE 0 END) AS aktif,
          SUM(CASE WHEN alinan_is=1 THEN 1 ELSE 0 END) AS alinan,
          SUM(CASE WHEN durum='Fiyat Teklifi Bekleniyor' THEN 1 ELSE 0 END) AS bekleyen,
          SUM(CASE WHEN durum='Fiyat Teklifi Değerlendiriliyor' THEN 1 ELSE 0 END) AS degerlendirilen,
          SUM(CASE WHEN durum='Teklif Onaylanmadı' THEN 1 ELSE 0 END) AS onaylanmadi
        FROM private_jobs
    """)
    r = df.iloc[0].fillna(0).to_dict() if not df.empty else {}
    cols = st.columns(5)
    cols[0].metric("Aktif Özel İş", int(r.get("aktif", 0) or 0))
    cols[1].metric("Alınan Özel İş", int(r.get("alinan", 0) or 0))
    cols[2].metric("Teklif Bekleyen", int(r.get("bekleyen", 0) or 0))
    cols[3].metric("Değerlendirilen", int(r.get("degerlendirilen", 0) or 0))
    cols[4].metric("Onaylanmadı", int(r.get("onaylanmadi", 0) or 0))


def add_private_job():
    if "private_job_device_row_count" not in st.session_state:
        st.session_state.private_job_device_row_count = 1
    if "private_job_test_row_count" not in st.session_state:
        st.session_state.private_job_test_row_count = 1

    with st.expander("➕ Yeni özel iş ekle", expanded=False):
        st.caption("Özel iş açılırken cihaz, test ve iş süresi bilgilerini aynı anda girebilirsin.")

        with st.form("new_private_job", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            kurum = c1.text_input("Kurum Adı")
            urun = c2.text_input("Ürün Grubu")
            cihaz = c3.number_input("İstenen Cihaz Miktarı", min_value=0, step=1)
            is_suresi = c4.number_input("İş Süresi (Ay)", min_value=1, step=1, value=12)

            st.markdown("### Cihaz Bilgileri")
            st.caption("Sıra No yerine cihaz adedi girilir. Boş bırakılan cihaz satırları kaydedilmez.")
            device_rows = []
            for i in range(1, st.session_state.private_job_device_row_count + 1):
                d1, d2, d3, d4 = st.columns([0.9, 1.2, 1.2, 2.8])
                cihaz_adedi = d1.number_input("Cihaz Adedi", min_value=1, value=1, step=1, key=f"new_private_device_adedi_{i}")
                marka = d2.text_input("Marka", key=f"new_private_device_marka_{i}")
                model = d3.text_input("Model", key=f"new_private_device_model_{i}")
                hastane = d4.text_input("Kurulum Yapılacak Hastane Bilgisi", key=f"new_private_device_hastane_{i}")
                device_rows.append({
                    "cihaz_adedi": int(cihaz_adedi),
                    "marka": marka.strip(),
                    "model": model.strip(),
                    "hastane": hastane.strip()
                })

            st.markdown("### Test Parametreleri")
            st.caption("Boş bırakılan test satırları kaydedilmez.")
            test_rows = []
            for i in range(1, st.session_state.private_job_test_row_count + 1):
                t1, t2, t3 = st.columns([3, 1.4, 1.4])
                test_adi = t1.text_input("Test Adı", key=f"new_private_test_adi_{i}")
                toplam_test = t2.number_input("Toplam Test Miktarı", min_value=0, value=0, step=1, key=f"new_private_test_toplam_{i}")
                ihale_toplam = t3.number_input("İhale Toplam Test Sayısı", min_value=0, value=0, step=1, key=f"new_private_test_ihale_{i}")
                test_rows.append({
                    "test_adi": test_adi.strip(),
                    "toplam_test": int(toplam_test or 0),
                    "ihale_toplam": int(ihale_toplam or 0)
                })

            aciklama = st.text_area("Genel Açıklama / İlk Yorum")
            save = st.form_submit_button("Özel İşi Kaydet")

        st.markdown("#### Cihaz satırı")
        dc1, dc2, _ = st.columns([1, 1, 4])
        if dc1.button("+ Cihaz Satırı Ekle", key="btn_add_private_device_row"):
            st.session_state.private_job_device_row_count += 1
            st.rerun()
        if dc2.button("- Cihaz Satırı Sil", key="btn_remove_private_device_row"):
            st.session_state.private_job_device_row_count = max(1, st.session_state.private_job_device_row_count - 1)
            st.rerun()

        st.markdown("#### Test satırı")
        tc1, tc2, _ = st.columns([1, 1, 4])
        if tc1.button("+ Test Satırı Ekle", key="btn_add_private_test_row"):
            st.session_state.private_job_test_row_count += 1
            st.rerun()
        if tc2.button("- Test Satırı Sil", key="btn_remove_private_test_row"):
            st.session_state.private_job_test_row_count = max(1, st.session_state.private_job_test_row_count - 1)
            st.rerun()

        if save:
            if not kurum.strip():
                st.warning("Kurum adı zorunlu.")
                st.stop()

            device_rows = [r for r in device_rows if r["marka"] or r["model"] or r["hastane"]]
            test_rows = [r for r in test_rows if r["test_adi"] or r["toplam_test"] > 0 or r["ihale_toplam"] > 0]

            with ENGINE.begin() as conn:
                res = conn.execute(text("""
                    INSERT INTO private_jobs
                    (kurum_adi, urun_grubu, istenen_cihaz_miktari, is_suresi_ay, durum, ilgili_kisi, aciklama, kayit_tarihi)
                    VALUES (:kurum, :urun, :cihaz, :is_suresi, 'Fiyat Teklifi Bekleniyor', :kisi, :aciklama, NOW())
                """), {
                    "kurum": kurum,
                    "urun": urun,
                    "cihaz": int(cihaz or 0),
                    "is_suresi": int(is_suresi or 12),
                    "kisi": st.session_state.user.get("ad_soyad", ""),
                    "aciklama": aciklama
                })
                job_id = res.lastrowid

                for r in device_rows:
                    conn.execute(text("""
                        INSERT INTO private_job_devices
                        (private_job_id, cihaz_adedi, marka, model, kurulum_yapilacak_hastane_bilgisi)
                        VALUES (:job_id, :cihaz_adedi, :marka, :model, :hastane)
                    """), {
                        "job_id": job_id,
                        "cihaz_adedi": r["cihaz_adedi"],
                        "marka": r["marka"],
                        "model": r["model"],
                        "hastane": r["hastane"]
                    })

                for r in test_rows:
                    conn.execute(text("""
                        INSERT INTO private_job_tests
                        (private_job_id, test_parametresi, test_rakami, ihale_toplam_test_sayisi)
                        VALUES (:job_id, :test_adi, :toplam_test, :ihale_toplam)
                    """), {
                        "job_id": job_id,
                        "test_adi": r["test_adi"],
                        "toplam_test": r["toplam_test"],
                        "ihale_toplam": r["ihale_toplam"]
                    })

                if aciklama.strip():
                    conn.execute(text("""
                        INSERT INTO private_job_comments
                        (private_job_id, kullanici, yorum, tarih)
                        VALUES (:job_id, :kullanici, :yorum, NOW())
                    """), {
                        "job_id": job_id,
                        "kullanici": st.session_state.user.get("ad_soyad", ""),
                        "yorum": aciklama
                    })

            log_private_job(job_id, f"Yeni özel iş eklendi. İş süresi: {is_suresi} ay, cihaz satırı: {len(device_rows)}, test satırı: {len(test_rows)}")
            notify_volkan_private_job(job_id, f"Yeni özel iş eklendi. İş süresi: {is_suresi} ay, cihaz satırı: {len(device_rows)}, test satırı: {len(test_rows)}")
            st.success("Özel iş, iş süresi, cihaz bilgileri ve test parametreleri kaydedildi.")
            st.session_state.private_job_device_row_count = 1
            st.session_state.private_job_test_row_count = 1
            st.rerun()


def query_private_jobs(kind="active", search=""):
    params = {}
    where = []
    if kind == "active":
        where.append("alinan_is=0")
    elif kind == "won":
        where.append("alinan_is=1")
    if search:
        where.append("(kurum_adi LIKE :s OR urun_grubu LIKE :s OR ilgili_kisi LIKE :s)")
        params["s"] = f"%{search}%"
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    return fetch_df(f"""
        SELECT id, kayit_tarihi, kurum_adi, urun_grubu, istenen_cihaz_miktari, is_suresi_ay,
               durum, ilgili_kisi, son_guncelleme, son_guncelleyen, onay_fiyati, yillik_getiri, aciklama
        FROM private_jobs
        {where_sql}
        ORDER BY id DESC
        LIMIT 200
    """, params).fillna("")



def log_tender_edit_row(tender_id, islem):
    try:
        add_log(tender_id, islem)
    except Exception:
        try:
            execute("INSERT INTO logs (tender_id, kullanici, islem, tarih) VALUES (:id,:u,:islem,NOW())", {
                "id": tender_id,
                "u": st.session_state.user.get("ad_soyad", ""),
                "islem": islem
            })
        except Exception:
            pass


def editable_sql_rows(title, df, table_name, id_col, field_map, numeric_fields=None, text_area_fields=None, delete_log_text="Satır silindi", update_log_text="Satır güncellendi", log_func=None, parent_id=None):
    numeric_fields = numeric_fields or []
    text_area_fields = text_area_fields or []
    if df is None or df.empty:
        st.info(f"{title} kaydı yok.")
        return

    st.markdown(f"#### {title} Satır Düzenleme")
    for _, row in df.iterrows():
        row_id = int(row[id_col])
        with st.expander(f"{title} satırı #{row_id}", expanded=False):
            new_values = {}
            cols = st.columns(len(field_map))
            for idx, (db_col, label) in enumerate(field_map.items()):
                current = row.get(db_col, "")
                if db_col in numeric_fields:
                    try:
                        val = int(float(current or 0))
                    except Exception:
                        val = 0
                    new_values[db_col] = cols[idx].number_input(label, min_value=0, value=val, step=1, key=f"edit_{table_name}_{db_col}_{row_id}")
                elif db_col in text_area_fields:
                    new_values[db_col] = st.text_area(label, value=str(current or ""), key=f"edit_{table_name}_{db_col}_{row_id}")
                else:
                    new_values[db_col] = cols[idx].text_input(label, value=str(current or ""), key=f"edit_{table_name}_{db_col}_{row_id}")

            b1, b2, _ = st.columns([1, 1, 4])
            if b1.button("Satırı Güncelle", key=f"update_{table_name}_{row_id}"):
                set_sql = ", ".join([f"{c}=:{c}" for c in field_map.keys()])
                params = {**new_values, "id": row_id}
                execute(f"UPDATE {table_name} SET {set_sql} WHERE {id_col}=:id", params)
                if log_func and parent_id is not None:
                    log_func(parent_id, update_log_text)
                st.success("Satır güncellendi.")
                st.rerun()
            if b2.button("Satırı Sil", key=f"delete_{table_name}_{row_id}"):
                execute(f"DELETE FROM {table_name} WHERE {id_col}=:id", {"id": row_id})
                if log_func and parent_id is not None:
                    log_func(parent_id, delete_log_text)
                st.warning("Satır silindi.")
                st.rerun()



@st.dialog("Özel İş Detay", width="large")
def admin_edit_delete_private_job(job_id, job, key_suffix='detail'):

    counter_key = f"_admin_edit_private_render_counter_{job_id}_{key_suffix}"
    st.session_state[counter_key] = int(st.session_state.get(counter_key, 0)) + 1
    key_suffix = f"{key_suffix}_{st.session_state[counter_key]}"
    if not is_admin():
        return

    st.divider()
    st.markdown("### Admin: Özel İşi Düzenle / Sil")

    with st.form(f"admin_edit_private_job_fixed_{job_id}_{key_suffix}", enter_to_submit=False):
        c1, c2 = st.columns(2)

        kurum_adi = c1.text_input(
            "Kurum Adı",
            value=str(job.get("kurum_adi", "") or "")
        )

        urun_grubu = c2.text_input(
            "Ürün Grubu",
            value=str(job.get("urun_grubu", "") or "")
        )

        c3, c4 = st.columns(2)

        istenen_cihaz_miktari = c3.number_input(
            "İstenen Cihaz Miktarı",
            min_value=0,
            step=1,
            value=int(float(job.get("istenen_cihaz_miktari") or 0))
        )

        is_suresi_ay = c4.number_input(
            "İş Süresi (Ay)",
            min_value=1,
            step=1,
            value=int(float(job.get("is_suresi_ay") or 12))
        )

        durum_default = str(job.get("durum") or "Fiyat Teklifi Bekleniyor")

        if durum_default not in PRIVATE_JOB_STATUS_OPTIONS:
            durum_default = "Fiyat Teklifi Bekleniyor"

        durum = st.selectbox(
            "Durum",
            PRIVATE_JOB_STATUS_OPTIONS,
            index=PRIVATE_JOB_STATUS_OPTIONS.index(durum_default)
        )

        ilgili_kisi = st.text_input(
            "İlgili Kişi",
            value=str(job.get("ilgili_kisi", "") or "")
        )

        fiyat = tr_money_input(
            "Onay / Alınan İş Fiyatı",
            key=f"edit_private_price_fixed_{job_id}_{key_suffix}",
            value=job.get("onay_fiyati", ""),
            required=False
        )

        aciklama = st.text_area(
            "Açıklama",
            value=str(job.get("aciklama", "") or "")
        )

        admin_notu = st.text_area(
            "Admin Notu",
            value=str(job.get("admin_notu", "") or "")
        )

        alinan_islerde_kalsin = st.checkbox(
            "Alınan özel işler içinde görünsün",
            value=bool(int(job.get("alinan_is") or 0) == 1)
        )

        save_job = st.form_submit_button("Özel İşi Güncelle")

    if save_job:
        if alinan_islerde_kalsin and not price_required_ok(fiyat):
            st.error("Alınan iş olarak görünecekse fiyat girmek zorunludur.")
            st.stop()

        fiyat_num = parse_tr_number(fiyat) or 0

        yillik_getiri = None

        if alinan_islerde_kalsin:
            if int(is_suresi_ay or 12) < 12:
                yillik_getiri = fiyat_num
            else:
                yillik_getiri = fiyat_num / max(int(is_suresi_ay or 12), 1) * 12

        execute("""
            UPDATE private_jobs
            SET kurum_adi=:kurum_adi,
                urun_grubu=:urun_grubu,
                istenen_cihaz_miktari=:istenen_cihaz_miktari,
                is_suresi_ay=:is_suresi_ay,
                durum=:durum,
                ilgili_kisi=:ilgili_kisi,
                aciklama=:aciklama,
                admin_notu=:admin_notu,
                alinan_is=:alinan_is,
                onay_fiyati=:onay_fiyati,
                yillik_getiri=:yillik_getiri,
                son_guncelleme=NOW(),
                son_guncelleyen=:user
            WHERE id=:id
        """, {
            "id": job_id,
            "kurum_adi": kurum_adi.strip(),
            "urun_grubu": urun_grubu.strip(),
            "istenen_cihaz_miktari": int(istenen_cihaz_miktari or 0),
            "is_suresi_ay": int(is_suresi_ay or 12),
            "durum": durum,
            "ilgili_kisi": ilgili_kisi.strip(),
            "aciklama": aciklama,
            "admin_notu": admin_notu,
            "alinan_is": 1 if alinan_islerde_kalsin else 0,
            "onay_fiyati": fiyat_num if alinan_islerde_kalsin else None,
            "yillik_getiri": yillik_getiri,
            "user": st.session_state.user.get("ad_soyad", "")
        })

        log_private_job(job_id, "Özel iş admin tarafından güncellendi")
        notify_volkan_private_job(job_id, "Özel iş admin tarafından güncellendi")
        clear_caches()
        st.success("Özel iş güncellendi.")
        st.rerun()

    st.markdown("#### İşlemler")

    col_back, col_delete = st.columns(2)

    with col_back:
        if st.button("Alınan İşlerden Geri Al", key=f"back_private_fixed_{job_id}_{key_suffix}"):
            execute("""
                UPDATE private_jobs
                SET alinan_is=0,
                    durum='Fiyat Teklifi Değerlendiriliyor',
                    onay_fiyati=NULL,
                    yillik_getiri=NULL,
                    son_guncelleme=NOW(),
                    son_guncelleyen=:user
                WHERE id=:id
            """, {
                "id": job_id,
                "user": st.session_state.user.get("ad_soyad", "")
            })

            log_private_job(job_id, "Alınan özel işlerden geri alındı")
            notify_volkan_private_job(job_id, "Alınan özel işlerden geri alındı")
            clear_caches()
            st.success("İş alınan özel işler listesinden geri alındı.")
            st.rerun()

    with col_delete:
        delete_confirm = st.checkbox(
            "Bu özel işi tamamen silmeyi onaylıyorum",
            key=f"delete_private_confirm_fixed_{job_id}_{key_suffix}"
        )

        if st.button("Özel İşi Tamamen Sil", key=f"delete_private_fixed_{job_id}_{key_suffix}", type="secondary"):
            if not delete_confirm:
                st.warning("Silmek için önce onay kutusunu işaretle.")
                st.stop()

            execute("DELETE FROM private_job_devices WHERE private_job_id=:id", {"id": job_id})
            execute("DELETE FROM private_job_tests WHERE private_job_id=:id", {"id": job_id})
            execute("DELETE FROM private_job_comments WHERE private_job_id=:id", {"id": job_id})
            execute("DELETE FROM private_job_logs WHERE private_job_id=:id", {"id": job_id})
            execute("DELETE FROM private_jobs WHERE id=:id", {"id": job_id})

            clear_caches()
            st.success("Özel iş tamamen silindi.")
            st.rerun()
def private_job_dialog(job_id):
    

    job = get_private_job(job_id)
    if not job:
        st.error("Özel iş bulunamadı.")
        return

    st.markdown("### Özel İş Bilgileri")
    render_html_table(pd.DataFrame([{
        "Kayıt Tarihi": job.get("kayit_tarihi", ""),
        "Kurum": job.get("kurum_adi", ""),
        "Ürün Grubu": job.get("urun_grubu", ""),
        "Cihaz Miktarı": job.get("istenen_cihaz_miktari", ""),
        "İş Süresi (Ay)": job.get("is_suresi_ay", ""),
        "Durum": job.get("durum", ""),
        "İlgili Kişi": job.get("ilgili_kisi", ""),
        "Son Güncelleme": job.get("son_guncelleme", ""),
        "Güncelleyen": job.get("son_guncelleyen", ""),
        "Onay Fiyatı": format_money_tr(job.get("onay_fiyati", "")),
        "Yıllık Getiri": format_money_tr(job.get("yillik_getiri", "")),
        "Açıklama": job.get("aciklama", ""),
    }]), empty_message="Özel iş bilgisi yok.")

    st.divider()
    st.markdown("### Durum Güncelle")
    with st.form(f"private_status_{job_id}"):
        durum_idx = PRIVATE_JOB_STATUS_OPTIONS.index(job.get("durum")) if job.get("durum") in PRIVATE_JOB_STATUS_OPTIONS else 0
        durum = st.selectbox("Durum", PRIVATE_JOB_STATUS_OPTIONS, index=durum_idx)
        aciklama = st.text_area("Açıklama", value=job.get("aciklama", ""))
        save = st.form_submit_button("Durumu Kaydet")
    if save:
        execute("""
            UPDATE private_jobs
            SET durum=:durum, aciklama=:aciklama, son_guncelleme=NOW(), son_guncelleyen=:user
            WHERE id=:id
        """, {"id": job_id, "durum": durum, "aciklama": aciklama, "user": st.session_state.user.get("ad_soyad", "")})
        log_private_job(job_id, f"Durum güncellendi: {job.get('durum','')} → {durum}")
        notify_volkan_private_job(job_id, f"Durum güncellendi: {job.get('durum','')} → {durum}")
        st.success("Durum kaydedildi.")
        st.rerun()

    st.divider()
    st.markdown("### Cihaz Bilgileri")
    private_devices = fetch_df("""
        SELECT cihaz_adedi, marka, model, kurulum_yapilacak_hastane_bilgisi
        FROM private_job_devices
        WHERE private_job_id=:id
        ORDER BY sira_no, id
    """, {"id": job_id}).fillna("")
    if not private_devices.empty:
        render_html_table(private_devices.rename(columns={
            "cihaz_adedi": "Cihaz Adedi",
            "marka": "Marka",
            "model": "Model",
            "kurulum_yapilacak_hastane_bilgisi": "Kurulum Yapılacak Hastane Bilgisi",
        }))
    else:
        st.info("Henüz cihaz bilgisi girilmemiş.")

    with st.form(f"private_device_{job_id}", clear_on_submit=True):
        d1, d2, d3, d4 = st.columns([1, 2, 2, 4])
        sira_no = d1.number_input("Sıra No", min_value=1, step=1)
        marka = d2.text_input("Marka")
        model = d3.text_input("Model")
        kurulum = d4.text_input("Kurulum Yapılacak Hastane Bilgisi")
        add_device = st.form_submit_button("Cihaz Satırı Ekle")
    if add_device:
        execute("""
            INSERT INTO private_job_devices
            (private_job_id, cihaz_adedi, marka, model, kurulum_yapilacak_hastane_bilgisi)
            VALUES (:id, :sira_no, :marka, :model, :kurulum)
        """, {"id": job_id, "sira_no": int(sira_no or 1), "marka": marka, "model": model, "kurulum": kurulum})
        execute("UPDATE private_jobs SET son_guncelleme=NOW(), son_guncelleyen=:u WHERE id=:id",
                {"id": job_id, "u": st.session_state.user.get("ad_soyad", "")})
        log_private_job(job_id, "Cihaz bilgisi eklendi")
        st.success("Cihaz bilgisi eklendi.")
        st.rerun()

    st.divider()
    st.markdown("### Cihaz Bilgileri")
    pdevices = fetch_df("""
        SELECT id, cihaz_adedi, marka, model, kurulum_yapilacak_hastane_bilgisi
        FROM private_job_devices
        WHERE private_job_id=:id
        ORDER BY id DESC
    """, {"id": job_id}).fillna("")
    if not pdevices.empty:
        render_html_table(pdevices.rename(columns={
            "cihaz_adedi": "Cihaz Adedi",
            "marka": "Marka",
            "model": "Model",
            "kurulum_yapilacak_hastane_bilgisi": "Kurulum Yapılacak Hastane Bilgisi",
        })[["Cihaz Adedi", "Marka", "Model", "Kurulum Yapılacak Hastane Bilgisi"]])
        editable_sql_rows(
            "Cihaz",
            pdevices,
            "private_job_devices",
            "id",
            {
                "cihaz_adedi": "Cihaz Adedi",
                "marka": "Marka",
                "model": "Model",
                "kurulum_yapilacak_hastane_bilgisi": "Kurulum Yapılacak Hastane Bilgisi",
            },
            numeric_fields=["cihaz_adedi"],
            text_area_fields=["kurulum_yapilacak_hastane_bilgisi"],
            log_func=log_private_job,
            parent_id=job_id,
            update_log_text="Özel iş cihaz satırı güncellendi",
            delete_log_text="Özel iş cihaz satırı silindi"
        )
    else:
        st.info("Henüz cihaz bilgisi girilmemiş.")

    st.divider()
    st.markdown("### Test Parametreleri")
    tests = fetch_df("""
        SELECT test_parametresi, test_rakami, COALESCE(ihale_toplam_test_sayisi, 0) AS ihale_toplam_test_sayisi
        FROM private_job_tests
        WHERE private_job_id=:id
        ORDER BY id DESC
    """, {"id": job_id}).fillna("")
    if not tests.empty:
        render_html_table(tests.rename(columns={
            "test_parametresi": "Test Adı",
            "test_rakami": "Toplam Test Miktarı",
            "ihale_toplam_test_sayisi": "İhale Toplam Test Sayısı",
        }))
    else:
        st.info("Henüz test parametresi girilmemiş.")

    with st.form(f"private_test_{job_id}", clear_on_submit=True):
        t1, t2, t3 = st.columns([3, 1, 1])
        param = t1.text_input("Test Adı")
        toplam_miktar = t2.number_input("Toplam Test Miktarı", min_value=0, step=1)
        ihale_toplam = t3.number_input("İhale Toplam Test Sayısı", min_value=0, step=1)
        add = st.form_submit_button("Test Satırı Ekle")
    if add:
        if not param.strip():
            st.warning("Test adı boş olamaz.")
            st.stop()
        execute("""
            INSERT INTO private_job_tests (private_job_id, test_parametresi, test_rakami, ihale_toplam_test_sayisi)
            VALUES (:id, :param, :rakam, :ihale_toplam)
        """, {"id": job_id, "param": param, "rakam": int(toplam_miktar or 0), "ihale_toplam": int(ihale_toplam or 0)})
        execute("UPDATE private_jobs SET son_guncelleme=NOW(), son_guncelleyen=:u WHERE id=:id",
                {"id": job_id, "u": st.session_state.user.get("ad_soyad", "")})
        log_private_job(job_id, "Test satırı eklendi")
        st.success("Test satırı eklendi.")
        st.rerun()

    st.divider()
    st.markdown("### Yorumlar")
    comments = fetch_df("""
        SELECT kullanici, yorum, tarih
        FROM private_job_comments
        WHERE private_job_id=:id
        ORDER BY id DESC
    """, {"id": job_id}).fillna("")
    if not comments.empty:
        render_html_table(comments.rename(columns={"kullanici": "Kullanıcı", "yorum": "Yorum", "tarih": "Tarih"}))
    else:
        st.info("Henüz yorum yok.")

    with st.form(f"private_comment_{job_id}", clear_on_submit=True):
        yorum = st.text_area("Yorum")
        add_y = st.form_submit_button("Yorum Ekle")
    if add_y and yorum.strip():
        execute("""
            INSERT INTO private_job_comments (private_job_id, kullanici, yorum, tarih)
            VALUES (:id, :kullanici, :yorum, NOW())
        """, {"id": job_id, "kullanici": st.session_state.user.get("ad_soyad", ""), "yorum": yorum})
        execute("UPDATE private_jobs SET son_guncelleme=NOW(), son_guncelleyen=:u WHERE id=:id",
                {"id": job_id, "u": st.session_state.user.get("ad_soyad", "")})
        log_private_job(job_id, "Yorum eklendi")
        st.success("Yorum eklendi.")
        st.rerun()


    st.divider()
    st.markdown("### Bilgileri Kaydet / Bildir")
    st.caption("Cihaz, test ve yorum satırlarını ekledikten sonra bu butona basınız.")

    if st.button("Özel İş Bilgilerini Kaydet", type="primary", key=f"finish_private_update_{job_id}"):
        cihaz_sayisi_df = fetch_df("SELECT COUNT(*) AS adet FROM private_job_devices WHERE private_job_id=:id", {"id": job_id})
        test_sayisi_df = fetch_df("SELECT COUNT(*) AS adet FROM private_job_tests WHERE private_job_id=:id", {"id": job_id})
        yorum_sayisi_df = fetch_df("SELECT COUNT(*) AS adet FROM private_job_comments WHERE private_job_id=:id", {"id": job_id})

        cihaz_sayisi = int(cihaz_sayisi_df.iloc[0]["adet"] or 0) if not cihaz_sayisi_df.empty else 0
        test_sayisi = int(test_sayisi_df.iloc[0]["adet"] or 0) if not test_sayisi_df.empty else 0
        yorum_sayisi = int(yorum_sayisi_df.iloc[0]["adet"] or 0) if not yorum_sayisi_df.empty else 0

        execute("""
            UPDATE private_jobs
            SET son_guncelleme=NOW(),
                son_guncelleyen=:user
            WHERE id=:id
        """, {
            "id": job_id,
            "user": st.session_state.user.get("ad_soyad", "")
        })

        log_private_job(
            job_id,
            f"Bilgiler kaydedildi. Cihaz: {cihaz_sayisi}, Test: {test_sayisi}, Yorum: {yorum_sayisi}"
        )
        notify_volkan_private_job(
            job_id,
            f"Bilgiler kaydedildi. Cihaz: {cihaz_sayisi}, Test: {test_sayisi}, Yorum: {yorum_sayisi}"
        )
        clear_caches()
        st.success("Özel iş bilgileri kaydedildi Teşekkürler.")
    if is_admin():
        st.divider()
        st.markdown("### Admin: Alınan Özel İşe Aktar")
        with st.form(f"private_admin_{job_id}"):
            fiyat = tr_money_input("Onay / Alınan İş Fiyatı", key=f"private_price_{job_id}", value=job.get("onay_fiyati", ""), required=True)
            admin_notu = st.text_area("Admin Notu", value=job.get("admin_notu", ""))
            approve = st.form_submit_button("Alınan Özel İşlere Aktar")
        if approve:
            if not price_required_ok(fiyat):
                st.error("Alınan özel işlere aktarmak için fiyat girmek zorunludur.")
                st.stop()
            execute("""
                UPDATE private_jobs
                SET alinan_is=1, durum='Teklif Onaylandı', onay_fiyati=:fiyat, yillik_getiri=CASE WHEN COALESCE(is_suresi_ay, 12) < 12 THEN :fiyat ELSE (:fiyat / GREATEST(COALESCE(is_suresi_ay, 12), 1)) * 12 END, onay_tarihi=NOW(),
                    admin_notu=:notu, son_guncelleme=NOW(), son_guncelleyen=:user
                WHERE id=:id
            """, {"id": job_id, "fiyat": parse_tr_number(fiyat), "notu": admin_notu, "user": st.session_state.user.get("ad_soyad", "")})
            log_private_job(job_id, f"Alınan özel işe aktarıldı. Fiyat: {fiyat}")
            notify_volkan_private_job(job_id, f"Alınan özel işe aktarıldı. Fiyat: {fiyat}")
            st.success("Alınan özel işlere aktarıldı.")
            st.rerun()

def admin_edit_delete_private_job(job_id, job, key_suffix='detail'):
    if not is_admin():
        return

    st.divider()
    st.markdown("### Admin: Alınan Özel İşi Düzenle / Sil")

    with st.form(f"admin_edit_taken_private_job_{job_id}_{key_suffix}", enter_to_submit=False):
        c1, c2 = st.columns(2)
        kurum_adi = c1.text_input("Kurum Adı", value=str(job.get("kurum_adi", "") or ""))
        urun_grubu = c2.text_input("Ürün Grubu", value=str(job.get("urun_grubu", "") or ""))

        c3, c4, c5 = st.columns(3)
        istenen_cihaz_miktari = c3.number_input(
            "İstenen Cihaz Miktarı",
            min_value=0,
            step=1,
            value=int(float(job.get("istenen_cihaz_miktari") or 0))
        )
        is_suresi_ay = c4.number_input(
            "İş Süresi (Ay)",
            min_value=1,
            step=1,
            value=int(float(job.get("is_suresi_ay") or 12))
        )

        durum_default = job.get("durum") if job.get("durum") in PRIVATE_JOB_STATUS_OPTIONS else "Teklif Onaylandı"
        durum = c5.selectbox(
            "Durum",
            PRIVATE_JOB_STATUS_OPTIONS,
            index=PRIVATE_JOB_STATUS_OPTIONS.index(durum_default)
        )

        c6, c7 = st.columns(2)
        ilgili_kisi = c6.text_input("İlgili Kişi", value=str(job.get("ilgili_kisi", "") or ""))
        fiyat = tr_money_input(
            "Onay / Alınan İş Fiyatı",
            key=f"edit_taken_private_price_{job_id}_{key_suffix}",
            value=job.get("onay_fiyati", ""),
            required=True
        )

        aciklama = st.text_area("Açıklama", value=str(job.get("aciklama", "") or ""))
        admin_notu = st.text_area("Admin Notu", value=str(job.get("admin_notu", "") or ""))

        alinan_islerde_kalsin = st.checkbox(
            "Alınan özel işler içinde kalsın",
            value=bool(int(job.get("alinan_is") or 0) == 1)
        )

        save_taken_job = st.form_submit_button("Alınan Özel İşi Güncelle")

    if save_taken_job:
        if alinan_islerde_kalsin and not price_required_ok(fiyat):
            st.error("Alınan iş olarak kalacaksa fiyat girmek zorunludur.")
            st.stop()

        fiyat_num = parse_tr_number(fiyat) or 0
        yillik_getiri = fiyat_num if int(is_suresi_ay or 12) < 12 else (fiyat_num / max(int(is_suresi_ay or 12), 1)) * 12

        execute("""
            UPDATE private_jobs
            SET kurum_adi=:kurum_adi,
                urun_grubu=:urun_grubu,
                istenen_cihaz_miktari=:istenen_cihaz_miktari,
                is_suresi_ay=:is_suresi_ay,
                durum=:durum,
                ilgili_kisi=:ilgili_kisi,
                aciklama=:aciklama,
                admin_notu=:admin_notu,
                alinan_is=:alinan_is,
                onay_fiyati=:onay_fiyati,
                yillik_getiri=:yillik_getiri,
                son_guncelleme=NOW(),
                son_guncelleyen=:user
            WHERE id=:id
        """, {
            "id": job_id,
            "kurum_adi": kurum_adi,
            "urun_grubu": urun_grubu,
            "istenen_cihaz_miktari": int(istenen_cihaz_miktari or 0),
            "is_suresi_ay": int(is_suresi_ay or 12),
            "durum": durum,
            "ilgili_kisi": ilgili_kisi,
            "aciklama": aciklama,
            "admin_notu": admin_notu,
            "alinan_is": 1 if alinan_islerde_kalsin else 0,
            "onay_fiyati": fiyat_num if alinan_islerde_kalsin else None,
            "yillik_getiri": yillik_getiri if alinan_islerde_kalsin else None,
            "user": st.session_state.user.get("ad_soyad", "")
        })

        log_private_job(job_id, "Alınan özel iş admin tarafından güncellendi")
        notify_volkan_private_job(job_id, "Alınan özel iş admin tarafından güncellendi")
        clear_caches()
        st.success("Alınan özel iş güncellendi.")
        st.rerun()

    st.markdown("#### İşlemler")

    col_back, col_delete = st.columns(2)

    with col_back:
        if st.button("Alınan İşlerden Geri Al", key=f"back_taken_private_{job_id}_{key_suffix}"):
            execute("""
                UPDATE private_jobs
                SET alinan_is=0,
                    durum='Fiyat Teklifi Değerlendiriliyor',
                    onay_fiyati=NULL,
                    yillik_getiri=NULL,
                    son_guncelleme=NOW(),
                    son_guncelleyen=:user
                WHERE id=:id
            """, {
                "id": job_id,
                "user": st.session_state.user.get("ad_soyad", "")
            })

            log_private_job(job_id, "Alınan özel işlerden geri alındı")
            notify_volkan_private_job(job_id, "Alınan özel işlerden geri alındı")
            clear_caches()
            st.success("İş alınan özel işler listesinden geri alındı.")
            st.rerun()

    with col_delete:
        delete_confirm = st.checkbox(
            "Bu özel işi tamamen silmeyi onaylıyorum",
            key=f"delete_taken_private_confirm_{job_id}_{key_suffix}"
        )

        if st.button("Özel İşi Tamamen Sil", key=f"delete_taken_private_{job_id}_{key_suffix}", type="secondary"):
            if not delete_confirm:
                st.warning("Silmek için önce onay kutusunu işaretle.")
                st.stop()

            execute("DELETE FROM private_job_devices WHERE private_job_id=:id", {"id": job_id})
            execute("DELETE FROM private_job_tests WHERE private_job_id=:id", {"id": job_id})
            execute("DELETE FROM private_job_comments WHERE private_job_id=:id", {"id": job_id})
            execute("DELETE FROM private_job_logs WHERE private_job_id=:id", {"id": job_id})
            execute("DELETE FROM private_jobs WHERE id=:id", {"id": job_id})

            clear_caches()
            st.success("Özel iş tamamen silindi.")
            st.rerun()
def page_private_jobs():
    render_brand()
    render_export_button()
    st.title("Özel İşler")
    private_jobs_summary()
    add_private_job()

    search = st.text_input("Özel iş ara", placeholder="Kurum, ürün grubu veya kişi ara")
    df = query_private_jobs("active", search)
    if df.empty:
        st.info("Aktif özel iş kaydı yok.")
        return

    view = df.rename(columns={
        "id": "ID", "kayit_tarihi": "Kayıt Tarihi", "kurum_adi": "Kurum",
        "urun_grubu": "Ürün Grubu", "istenen_cihaz_miktari": "Cihaz Miktarı", "is_suresi_ay": "İş Süresi (Ay)",
        "durum": "Durum", "ilgili_kisi": "İlgili Kişi", "son_guncelleme": "Son Güncelleme",
        "son_guncelleyen": "Güncelleyen", "onay_fiyati": "Onay Fiyatı", "yillik_getiri": "Yıllık Getiri", "aciklama": "Açıklama"
    })
    render_html_table(view, empty_message="Aktif özel iş kaydı yok.")

    opts = [f"{int(r.id)} | {r.kurum_adi} | {r.urun_grubu} | {r.durum}" for _, r in df.iterrows()]
    selected = st.selectbox("İşlem yapmak / detay görmek için özel iş seç", [""] + opts)
    if selected:
        private_job_dialog(int(selected.split("|")[0].strip()))


def page_private_jobs_won():
    render_brand()
    render_export_button()
    st.title("Alınan Özel İşler")
    df = query_private_jobs("won", "")
    if df.empty:
        st.info("Alınan özel iş yok.")
        return

    df["onay_fiyati_num"] = pd.to_numeric(df["onay_fiyati"], errors="coerce").fillna(0)
    c1, c2 = st.columns(2)
    with c1:
        kurum_sum = df.groupby("kurum_adi", as_index=False)["onay_fiyati_num"].sum().sort_values("onay_fiyati_num", ascending=False).head(12)
        if kurum_sum["onay_fiyati_num"].sum() > 0:
            fig = px.bar(kurum_sum, x="kurum_adi", y="onay_fiyati_num",
                         title="Alınan Özel İşler - Kuruma Göre Fiyat",
                         labels={"kurum_adi": "Kurum", "onay_fiyati_num": "Fiyat"})
            fig = style_plotly(fig)
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        grup = df.groupby("urun_grubu", as_index=False).size().rename(columns={"size": "adet"}).sort_values("adet", ascending=False)
        if not grup.empty:
            fig = px.pie(grup, names="urun_grubu", values="adet", title="Alınan Özel İşler - Ürün Grubu Dağılımı")
            fig = style_plotly(fig)
            fig.update_traces(textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)

    view = df.rename(columns={
        "id": "ID", "kayit_tarihi": "Kayıt Tarihi", "kurum_adi": "Kurum",
        "urun_grubu": "Ürün Grubu", "istenen_cihaz_miktari": "Cihaz Miktarı", "is_suresi_ay": "İş Süresi (Ay)",
        "durum": "Durum", "ilgili_kisi": "İlgili Kişi", "son_guncelleme": "Son Güncelleme",
        "son_guncelleyen": "Güncelleyen", "onay_fiyati": "Onay Fiyatı", "yillik_getiri": "Yıllık Getiri", "aciklama": "Açıklama"
    })
    render_html_table(view, empty_message="Alınan özel iş yok.")
    opts = [f"{int(r.id)} | {r.kurum_adi} | {r.urun_grubu} | {format_money_tr(r.onay_fiyati)}" for _, r in df.iterrows()]
    

    if is_admin() and not df.empty:
        opts = []

        for _, r in df.iterrows():
            job_id = int(r.get("id") or 0)
            kurum = str(r.get("kurum_adi") or "")
            urun = str(r.get("urun_grubu") or "")
            fiyat = format_tr_money_display(r.get("onay_fiyati") or 0)

            opts.append(f"{job_id} | {kurum} | {urun} | {fiyat}")
        selected = st.selectbox(
            "Düzenlemek / silmek için alınan özel iş seç",
            [""] + opts,
            key="select_taken_private_job_won_admin_fixed"
        )

        if selected:
            selected_id = int(selected.split("|")[0].strip())

            selected_job_df = fetch_df("SELECT * FROM private_jobs WHERE id=:id", {"id": selected_id}).fillna("")
            if not selected_job_df.empty:
                selected_job = selected_job_df.iloc[0].to_dict()
                admin_edit_delete_private_job(
                    selected_id,
                    selected_job,
                    key_suffix=f"won_page_{selected_id}"
                )


def split_sales_people(value):
    if value is None:
        return []
    raw = str(value).strip()
    if not raw:
        return []
    parts = re.split(r"[,/;]+", raw)
    cleaned = []
    for p in parts:
        name = p.strip()
        if name and name not in cleaned:
            cleaned.append(name)
    return cleaned


def explode_sales_df(df, person_col="ilgili_kisi"):
    rows = []
    if df is None or df.empty:
        return pd.DataFrame()
    for _, row in df.iterrows():
        people = split_sales_people(row.get(person_col, ""))
        if not people:
            people = ["Atanmamış"]
        for person in people:
            item = row.to_dict()
            item[person_col] = person
            rows.append(item)
    return pd.DataFrame(rows)

def split_sales_names_for_analysis(df, person_col):
    rows = []
    if df is None or df.empty:
        return pd.DataFrame()
    for _, row in df.iterrows():
        raw = str(row.get(person_col, "") or "")
        names = []
        for part in re.split(r"[,/;]+", raw):
            name = part.strip()
            if name:
                names.append(name)
        if not names:
            names = ["Belirtilmemiş"]
        for name in names:
            new_row = row.copy()
            new_row[person_col] = name
            rows.append(new_row)
    return pd.DataFrame(rows)



def split_sales_names_for_analysis(df, person_col):
    rows = []
    if df is None or df.empty:
        return pd.DataFrame()
    for _, row in df.iterrows():
        raw = str(row.get(person_col, "") or "")
        names = []
        for part in re.split(r"[,/;]+", raw):
            name = part.strip()
            if name:
                names.append(name)
        if not names:
            names = ["Belirtilmemiş"]
        for name in names:
            new_row = row.copy()
            new_row[person_col] = name
            rows.append(new_row)
    return pd.DataFrame(rows)



def page_sales_analysis():
    render_brand()
    render_export_button()
    st.title("Satış Analizi")

    firma_options = ["Tüm Firmalar"] + PARTICIPANT_COMPANY_OPTIONS + ["Belirtilmemiş"]
    selected_firma = st.selectbox(
        "Analiz firması",
        firma_options,
        key="sales_analysis_firma_filter"
    )
    st.caption(
        "Firma filtresi sonuçlanan ihale kalemleri için uygulanır. "
        "Toplam verilen ihale hesabı aktif/sistemde duran ihaleler + silinen/girilemeyen ihaleler olarak hesaplanır."
    )

    active_tender_raw = fetch_df("""
        SELECT ilgili_kisi, durum, ihale_tarihi, kayit_tarihi
        FROM tenders
        WHERE takip_ediliyor=0
          AND durum NOT IN ('Kazanıldı', 'Kaybedildi', 'Kısmi Sonuçlandı')
    """).fillna("")

    all_tender_raw = fetch_df("""
        SELECT ilgili_kisi, durum, ihale_tarihi, kayit_tarihi
        FROM tenders
    """).fillna("")

    try:
        deleted_tender_raw = fetch_df("""
            SELECT ilgili_kisi, durum, ihale_tarihi, silinme_tarihi AS kayit_tarihi,
                   kurum, ikn, urun_grubu, aciklama, silme_notu
            FROM deleted_tenders
        """).fillna("")
    except Exception:
        deleted_tender_raw = pd.DataFrame()

    result_where = ""
    params = {}
    if selected_firma != "Tüm Firmalar":
        result_where = "AND COALESCE(NULLIF(TRIM(p.istirak_firma), ''), 'Belirtilmemiş') = :firma"
        params["firma"] = selected_firma

    result_raw = fetch_df(f"""
        SELECT t.ilgili_kisi, p.sonuc_durum AS durum, t.ihale_tarihi, t.kayit_tarihi,
               COALESCE(NULLIF(TRIM(p.istirak_firma), ''), 'Belirtilmemiş') AS istirak_firma,
               COALESCE(p.yillik_getiri, 0) AS yillik_getiri,
               COALESCE(p.sozlesme_bedeli, 0) AS sozlesme_bedeli,
               COALESCE(p.bizim_fiyat, 0) AS bizim_fiyat,
               COALESCE(p.fiyat_farki, 0) AS fiyat_farki,
               p.sonuc_urun_grubu
        FROM tender_result_parts p
        JOIN tenders t ON t.id=p.ihale_id
        WHERE 1=1 {result_where}
    """, params).fillna("")

    private_raw = fetch_df("""
        SELECT ilgili_kisi, alinan_is, COALESCE(onay_fiyati,0) AS onay_fiyati,
               COALESCE(yillik_getiri,0) AS yillik_getiri
        FROM private_jobs
    """).fillna("")

    active_split = split_sales_names_for_analysis(active_tender_raw, "ilgili_kisi")
    all_split = split_sales_names_for_analysis(all_tender_raw, "ilgili_kisi")
    deleted_split = (
        split_sales_names_for_analysis(deleted_tender_raw, "ilgili_kisi")
        if deleted_tender_raw is not None and not deleted_tender_raw.empty
        else pd.DataFrame()
    )
    result_split = split_sales_names_for_analysis(result_raw, "ilgili_kisi")
    private_split = split_sales_names_for_analysis(private_raw, "ilgili_kisi")

    active_tender_df = pd.DataFrame()
    if not active_split.empty:
        active_split["mevcut_ihale_adedi"] = 1
        active_tender_df = active_split.groupby("ilgili_kisi", as_index=False).agg({
            "mevcut_ihale_adedi": "sum",
        })

    current_all_tender_df = pd.DataFrame()
    if not all_split.empty:
        all_split["aktif_sistemdeki_ihale_adedi"] = 1
        current_all_tender_df = all_split.groupby("ilgili_kisi", as_index=False).agg({
            "aktif_sistemdeki_ihale_adedi": "sum",
        })

    deleted_tender_df = pd.DataFrame()
    if not deleted_split.empty:
        deleted_split["silinen_ihale_adedi"] = 1
        deleted_tender_df = deleted_split.groupby("ilgili_kisi", as_index=False).agg({
            "silinen_ihale_adedi": "sum",
        })

    total_tender_df = current_all_tender_df.copy()
    if total_tender_df.empty:
        total_tender_df = deleted_tender_df.copy()
    elif not deleted_tender_df.empty:
        total_tender_df = total_tender_df.merge(deleted_tender_df, on="ilgili_kisi", how="outer").fillna(0)

    if not total_tender_df.empty:
        if "aktif_sistemdeki_ihale_adedi" not in total_tender_df.columns:
            total_tender_df["aktif_sistemdeki_ihale_adedi"] = 0
        if "silinen_ihale_adedi" not in total_tender_df.columns:
            total_tender_df["silinen_ihale_adedi"] = 0
        total_tender_df["toplam_verilen_ihale"] = (
            pd.to_numeric(total_tender_df["aktif_sistemdeki_ihale_adedi"], errors="coerce").fillna(0)
            + pd.to_numeric(total_tender_df["silinen_ihale_adedi"], errors="coerce").fillna(0)
        )

    # Yıl bazında toplam verilen ihale: sistemde duran + silinen/girilemeyen.
    tender_year_source_parts = []
    if not all_split.empty:
        temp_all = all_split.copy()
        temp_all["kaynak"] = "Sistemdeki İhale"
        temp_all["ihale_adedi"] = 1
        tender_year_source_parts.append(temp_all)
    if not deleted_split.empty:
        temp_deleted = deleted_split.copy()
        temp_deleted["kaynak"] = "Silinen / Girilemeyen"
        temp_deleted["ihale_adedi"] = 1
        tender_year_source_parts.append(temp_deleted)

    tender_year_df = pd.DataFrame()
    if tender_year_source_parts:
        tender_year_source = pd.concat(tender_year_source_parts, ignore_index=True)
        tender_year_source["analiz_tarihi"] = pd.to_datetime(tender_year_source.get("ihale_tarihi"), errors="coerce")
        fallback_date = pd.to_datetime(tender_year_source.get("kayit_tarihi"), errors="coerce")
        tender_year_source["analiz_tarihi"] = tender_year_source["analiz_tarihi"].fillna(fallback_date)
        tender_year_source["yil"] = tender_year_source["analiz_tarihi"].dt.year.fillna(0).astype(int)
        tender_year_df = tender_year_source[tender_year_source["yil"] > 0].groupby(["yil", "ilgili_kisi"], as_index=False).agg({
            "ihale_adedi": "sum",
        })

    result_summary = pd.DataFrame()
    if not result_split.empty:
        result_split["ihale_sonuc_adedi"] = 1
        result_split["kazanilan_ihale"] = (result_split["durum"] == "Kazanıldı").astype(int)
        result_split["kaybedilen_ihale"] = (result_split["durum"] == "Kaybedildi").astype(int)
        result_split["sozlesme_bedeli"] = pd.to_numeric(result_split["sozlesme_bedeli"], errors="coerce").fillna(0)
        result_split["ihale_yillik_getiri"] = pd.to_numeric(result_split["yillik_getiri"], errors="coerce").fillna(0)
        result_split["fiyat_farki"] = pd.to_numeric(result_split["fiyat_farki"], errors="coerce").fillna(0)

        # Sözleşme bedeli yalnızca kazanılan kalemlerden toplansın.
        result_split["kazanilan_sozlesme_bedeli"] = result_split.apply(
            lambda r: float(r["sozlesme_bedeli"]) if r["durum"] == "Kazanıldı" else 0,
            axis=1
        )
        result_split["kazanilan_yillik_getiri"] = result_split.apply(
            lambda r: float(r["ihale_yillik_getiri"]) if r["durum"] == "Kazanıldı" else 0,
            axis=1
        )
        result_split["kaybedilen_fiyat_farki"] = result_split.apply(
            lambda r: float(r["fiyat_farki"]) if r["durum"] == "Kaybedildi" else 0,
            axis=1
        )

        result_summary = result_split.groupby("ilgili_kisi", as_index=False).agg({
            "ihale_sonuc_adedi": "sum",
            "kazanilan_ihale": "sum",
            "kaybedilen_ihale": "sum",
            "kazanilan_sozlesme_bedeli": "sum",
            "kazanilan_yillik_getiri": "sum",
            "kaybedilen_fiyat_farki": "sum",
        })
        result_summary["kazanma_orani"] = (
            result_summary["kazanilan_ihale"] / result_summary["ihale_sonuc_adedi"].replace(0, 1)
        ) * 100

    private_summary = pd.DataFrame()
    private_won_df = pd.DataFrame()
    if not private_split.empty:
        private_split["ozel_is_adedi"] = 1
        private_split["alinan_ozel_is"] = pd.to_numeric(private_split["alinan_is"], errors="coerce").fillna(0).astype(int)
        private_split["ozel_is_fiyat_toplam"] = pd.to_numeric(private_split["onay_fiyati"], errors="coerce").fillna(0)
        private_split["ozel_is_yillik_getiri"] = pd.to_numeric(private_split["yillik_getiri"], errors="coerce").fillna(0)

        private_summary = private_split.groupby("ilgili_kisi", as_index=False).agg({
            "ozel_is_adedi": "sum",
            "alinan_ozel_is": "sum",
            "ozel_is_fiyat_toplam": "sum",
            "ozel_is_yillik_getiri": "sum",
        })

        private_won_only = private_split[private_split["alinan_ozel_is"] == 1].copy()
        if not private_won_only.empty:
            private_won_only["alinan_ozel_is_adedi"] = 1
            private_won_df = private_won_only.groupby("ilgili_kisi", as_index=False).agg({
                "alinan_ozel_is_adedi": "sum",
                "ozel_is_yillik_getiri": "sum",
                "ozel_is_fiyat_toplam": "sum",
            })

    st.markdown("### Satışçı Toplam Verilen İhale Analizi")
    if not total_tender_df.empty:
        render_html_table(format_result_display_df(total_tender_df.rename(columns={
            "ilgili_kisi": "Satışçı",
            "aktif_sistemdeki_ihale_adedi": "Sistemdeki İhale",
            "silinen_ihale_adedi": "Silinen / Girilemeyen İhale",
            "toplam_verilen_ihale": "Toplam Verilen İhale",
        })), empty_message="Satışçı toplam ihale analizi yok.")
    else:
        st.info("Satışçı toplam ihale analizi yok.")

    st.markdown("### Firma Bazlı İhale Sonuç Analizi")
    if not result_summary.empty:
        render_html_table(format_result_display_df(result_summary.rename(columns={
            "ilgili_kisi": "Satışçı",
            "ihale_sonuc_adedi": "Sonuçlanan Kalem",
            "kazanilan_ihale": "Kazanılan Kalem",
            "kaybedilen_ihale": "Kaybedilen Kalem",
            "kazanilan_sozlesme_bedeli": "Sözleşme Bedeli",
            "kazanilan_yillik_getiri": "İhale Yıllık Getiri",
            "kaybedilen_fiyat_farki": "Fiyat Farkı",
            "kazanma_orani": "Kazanma Oranı %",
        })), empty_message="İhale satış analizi yok.")
    else:
        st.info("Seçili firma için sonuçlanmış ihale satış analizi yok.")

    st.markdown("### Mevcut İhale Listesi Satışçı Analizi")
    if not active_tender_df.empty:
        render_html_table(format_result_display_df(active_tender_df.rename(columns={
            "ilgili_kisi": "Satışçı",
            "mevcut_ihale_adedi": "Mevcut İhale Adedi",
        })), empty_message="Mevcut ihale satış analizi yok.")
    else:
        st.info("Mevcut ihale satış analizi yok.")

    st.markdown("### Özel İş Satış Analizi")
    if not private_summary.empty:
        render_html_table(format_result_display_df(private_summary.rename(columns={
            "ilgili_kisi": "Satışçı",
            "ozel_is_adedi": "Özel İş Adedi",
            "alinan_ozel_is": "Alınan Özel İş",
            "ozel_is_fiyat_toplam": "Özel İş Fiyat Toplamı",
            "ozel_is_yillik_getiri": "Özel İş Yıllık Getiri",
        })), empty_message="Özel iş satış analizi yok.")
    else:
        st.info("Özel iş satış analizi yok.")

    st.markdown("### Satışçı Kazanım Grafikleri")
    cg1, cg2 = st.columns(2)
    with cg1:
        if not result_summary.empty:
            count_long = result_summary[["ilgili_kisi", "kazanilan_ihale", "kaybedilen_ihale"]].melt(
                id_vars="ilgili_kisi",
                value_vars=["kazanilan_ihale", "kaybedilen_ihale"],
                var_name="Tip",
                value_name="Adet"
            )
            count_long["Tip"] = count_long["Tip"].replace({
                "kazanilan_ihale": "Kazanılan Kalem",
                "kaybedilen_ihale": "Kaybedilen Kalem",
            })
            fig = px.bar(
                count_long,
                x="ilgili_kisi",
                y="Adet",
                color="Tip",
                barmode="group",
                title="Satışçıya Göre Kazanılan / Kaybedilen Kalem Adedi",
                labels={"ilgili_kisi": "Satışçı"}
            )
            fig = style_plotly(fig)
            st.plotly_chart(fig, use_container_width=True)

    with cg2:
        if not result_summary.empty:
            fig = px.bar(
                result_summary.sort_values("kazanilan_yillik_getiri", ascending=False),
                x="ilgili_kisi",
                y="kazanilan_yillik_getiri",
                title="Satışçıya Göre Kazanılan İhale Yıllık Getirisi",
                labels={"ilgili_kisi": "Satışçı", "kazanilan_yillik_getiri": "Yıllık Getiri"}
            )
            fig = style_plotly(fig)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Yıl Bazında Satışçıya Verilen Toplam İhale Grafiği")
    if not tender_year_df.empty:
        fig = px.bar(
            tender_year_df,
            x="yil",
            y="ihale_adedi",
            color="ilgili_kisi",
            barmode="group",
            title="Yıl Bazında Satışçıya Verilen Toplam İhale Miktarı",
            labels={"yil": "Yıl", "ihale_adedi": "Toplam İhale", "ilgili_kisi": "Satışçı"}
        )
        fig = style_plotly(fig)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Yıl bazında ihale verisi yok.")

    st.markdown("### Özel İş Grafikleri")
    c1, c2 = st.columns(2)
    with c1:
        if not private_summary.empty:
            fig = px.bar(
                private_summary,
                x="ilgili_kisi",
                y="ozel_is_yillik_getiri",
                title="Satışçıya Göre Özel İş Getirisi",
                labels={"ilgili_kisi": "Satışçı", "ozel_is_yillik_getiri": "Özel İş Getirisi"}
            )
            fig = style_plotly(fig)
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        if not private_summary.empty:
            fig = px.bar(
                private_summary,
                x="ilgili_kisi",
                y="ozel_is_adedi",
                title="Satışçıya Göre Özel İş Adedi",
                labels={"ilgili_kisi": "Satışçı", "ozel_is_adedi": "Özel İş Adedi"}
            )
            fig = style_plotly(fig)
            st.plotly_chart(fig, use_container_width=True)



def page_deleted_tenders():
    render_brand()
    render_export_button()
    st.title("Silinen İhaleler")

    if not is_admin():
        st.warning("Bu sayfaya sadece admin erişebilir.")
        return

    ensure_deleted_tender_schema()

    df = fetch_df("""
        SELECT id, original_id, silinme_tarihi, silen_kisi, ihale_tarihi, ikn, kurum,
               urun_grubu, durum, ilgili_kisi, aciklama, silme_notu,
               cihaz_sayisi, masraf_sayisi, yorum_sayisi, cihaz_ozet, masraf_ozet, yorum_ozet
        FROM deleted_tenders
        ORDER BY id DESC
    """).fillna("")

    if df.empty:
        st.info("Henüz silinen ihale kaydı yok.")
        return

    df["neden"] = df.apply(classify_deleted_reason_text, axis=1)

    st.markdown("### Genel Özet")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Silinen İhale", len(df))
    c2.metric("Uymuyoruz", int(df["durum"].astype(str).str.contains("Uymuyoruz", case=False, na=False).sum()))
    c3.metric("İtiraz Reddedildi", int(df["durum"].astype(str).str.contains("İtiraz Reddedildi|Itiraz Reddedildi", case=False, na=False).sum()))
    c4.metric("İhale İptal Edildi", int((df["neden"] == "İhale iptal edildi").sum()))
    c5.metric("Cihaz/Masraf Girilmiş", int(((pd.to_numeric(df["cihaz_sayisi"], errors="coerce").fillna(0) + pd.to_numeric(df["masraf_sayisi"], errors="coerce").fillna(0)) > 0).sum()))

    st.info(deleted_tenders_ai_comment(df))

    c_chart1, c_chart2 = st.columns(2)
    with c_chart1:
        reason_df = df.groupby("neden", as_index=False).size().rename(columns={"size": "adet"}).sort_values("adet", ascending=False)
        fig = px.bar(reason_df, x="neden", y="adet", title="Silinen İhaleler - Neden Dağılımı", labels={"neden": "Neden", "adet": "Adet"})
        fig = style_plotly(fig)
        st.plotly_chart(fig, use_container_width=True)

    with c_chart2:
        status_df = df.groupby("durum", as_index=False).size().rename(columns={"size": "adet"}).sort_values("adet", ascending=False).head(10)
        fig = px.bar(status_df, x="durum", y="adet", title="Silinen İhaleler - Durum Dağılımı", labels={"durum": "Durum", "adet": "Adet"})
        fig = style_plotly(fig)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Satışçı / Ürün Grubu Kırılımı")
    split_df = split_sales_names_for_analysis(df, "ilgili_kisi")
    if not split_df.empty:
        s1, s2 = st.columns(2)
        with s1:
            sales_df = split_df.groupby("ilgili_kisi", as_index=False).size().rename(columns={"size": "silinen_ihale"}).sort_values("silinen_ihale", ascending=False)
            fig = px.bar(sales_df, x="ilgili_kisi", y="silinen_ihale", title="Satışçıya Göre Silinen İhale", labels={"ilgili_kisi": "Satışçı", "silinen_ihale": "Silinen İhale"})
            fig = style_plotly(fig)
            st.plotly_chart(fig, use_container_width=True)
        with s2:
            product_df = df.groupby("urun_grubu", as_index=False).size().rename(columns={"size": "silinen_ihale"}).sort_values("silinen_ihale", ascending=False).head(12)
            fig = px.bar(product_df, x="urun_grubu", y="silinen_ihale", title="Ürün Grubuna Göre Silinen İhale", labels={"urun_grubu": "Ürün Grubu", "silinen_ihale": "Silinen İhale"})
            fig = style_plotly(fig)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Silinen İhale Listesi")
    view = df.rename(columns={
        "id": "Arşiv ID",
        "original_id": "Eski ID",
        "silinme_tarihi": "Silinme Tarihi",
        "silen_kisi": "Silen Kişi",
        "ihale_tarihi": "İhale Tarihi",
        "ikn": "İKN",
        "kurum": "Kurum",
        "urun_grubu": "Ürün Grubu",
        "durum": "Silinmeden Önceki Durum",
        "ilgili_kisi": "İlgili Kişi",
        "aciklama": "Açıklama",
        "silme_notu": "Silme Notu",
        "neden": "Neden Sınıfı",
        "cihaz_sayisi": "Cihaz Satırı",
        "masraf_sayisi": "Masraf Satırı",
        "yorum_sayisi": "Yorum Satırı",
        "cihaz_ozet": "Cihaz Özeti",
        "masraf_ozet": "Masraf Özeti",
        "yorum_ozet": "Yorum Özeti",
    })
    render_html_table(format_result_display_df(view), empty_message="Silinen ihale kaydı yok.")


def page_tenders():
    render_brand()
    render_export_button()
    if is_admin():
        admin_add_tender()
    selected = render_tender_list("list", "İhale Listesi")
    if selected:
        details_dialog(selected)


def page_followed():
    render_brand()
    render_export_button()
    selected = render_tender_list("followed", "Takip Edilenler")
    if selected:
        details_dialog(selected)



def show_result_summary(kind):
    durum = "Kazanıldı" if kind == "won" else "Kaybedildi"
    firma_filter = st.session_state.get(f"result_report_firma_{kind}", "Tüm Firmalar")

    if kind == "won":
        preferred_cols = [
            "ihale_tarihi", "ikn", "kurum", "urun_grubu", "sonuc_durum", "ilgili_kisi",
            "istirak_firma", "sozlesme_bedeli", "ihale_suresi_ay", "yillik_getiri",
            "sozlesme_baslangic_tarihi", "test_rakami", "sonuc_urun_grubu",
            "birim_puan", "birim_test_fiyati", "updated_at", "admin_notu"
        ]
    else:
        preferred_cols = [
            "ihale_tarihi", "ikn", "kurum", "urun_grubu", "sonuc_durum", "ilgili_kisi",
            "istirak_firma", "sozlesme_bedeli", "bizim_fiyat", "fiyat_farki", "fark_yuzdesi",
            "ihale_suresi_ay", "sonuc_urun_grubu", "updated_at",
            "alan_firma", "kazanan_cihaz", "admin_notu"
        ]

    df = fetch_df("""
        SELECT t.ihale_tarihi, t.ikn, t.kurum, t.urun_grubu,
               p.sonuc_durum, t.ilgili_kisi,
               COALESCE(NULLIF(TRIM(p.istirak_firma), ''), 'Belirtilmemiş') AS istirak_firma,
               p.sozlesme_bedeli, p.bizim_fiyat, p.fiyat_farki, p.fark_yuzdesi,
               p.ihale_suresi_ay, p.yillik_getiri, p.sozlesme_baslangic_tarihi,
               p.test_rakami, p.sonuc_urun_grubu, p.birim_puan, p.birim_test_fiyati,
               p.updated_at, p.alan_firma, p.kazanan_cihaz, p.admin_notu
        FROM tender_result_parts p
        JOIN tenders t ON t.id=p.ihale_id
        WHERE p.sonuc_durum=:durum
        ORDER BY p.updated_at DESC, p.id DESC
    """, {"durum": durum}).fillna("")

    if not df.empty and firma_filter != "Tüm Firmalar":
        df = df[df["istirak_firma"] == firma_filter].copy()

    if not df.empty:
        st.markdown("### Sonuç ve Fiyat Bilgileri")
        df = df[[c for c in preferred_cols if c in df.columns]]
        render_html_table(format_result_display_df(df), empty_message="Sonuç kaydı yok.")


def page_won():
    render_brand()
    render_export_button()
    st.title("Kazanılanlar")
    render_result_charts("won")
    show_result_summary("won")
    selected = render_tender_list("won", "Kazanılan İhale Listesi")
    if selected:
        details_dialog(selected)


def page_lost():
    render_brand()
    render_export_button()
    st.title("Kaybedilenler")
    render_result_charts("lost")
    show_result_summary("lost")
    selected = render_tender_list("lost", "Kaybedilen İhale Listesi")
    if selected:
        details_dialog(selected)


def page_reports():
    return






def page_calendar():
    render_brand()
    render_export_button()
    st.title("İhale Takvimi")

    today = date.today()
    c1, c2 = st.columns(2)
    year = c1.number_input("Yıl", min_value=2020, max_value=2100, value=today.year, key="calendar_year")
    month = c2.selectbox(
        "Ay",
        list(range(1, 13)),
        index=today.month - 1,
        format_func=lambda x: f"{x} - {calendar.month_name[x]}",
        key="calendar_month"
    )

    df = fetch_df("""
        SELECT id, ihale_tarihi, ikn, kurum, urun_grubu, durum, ilgili_kisi
        FROM tenders
        WHERE ihale_tarihi IS NOT NULL
          AND YEAR(ihale_tarihi)=:y
          AND MONTH(ihale_tarihi)=:m
        ORDER BY ihale_tarihi, id DESC
    """, {"y": int(year), "m": int(month)}).fillna("")

    render_calendar_grid(df, year, month)

    with st.expander("Liste görünümü"):
        if df.empty:
            st.info("Bu ay ihale yok.")
        else:
            cal_view = df.rename(columns={
                "id": "ID",
                "ihale_tarihi": "İhale Tarihi",
                "ikn": "İKN",
                "kurum": "Kurum",
                "urun_grubu": "Ürün Grubu",
                "durum": "Durum",
                "ilgili_kisi": "İlgili Kişi"
            })
            render_html_table(cal_view, empty_message="Bu ay ihale yok.")


def render_calendar_grid(df, year, month):
    week_days = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(int(year), int(month))

    items_by_day = {}
    if df is not None and not df.empty:
        tmp = df.copy()
        tmp["ihale_tarihi_dt"] = pd.to_datetime(tmp["ihale_tarihi"], errors="coerce")
        for _, r in tmp.dropna(subset=["ihale_tarihi_dt"]).iterrows():
            d = int(r["ihale_tarihi_dt"].day)
            items_by_day.setdefault(d, []).append(r)

    parts = ["<div class='loji-calendar'>"]
    for wd in week_days:
        parts.append(f"<div class='loji-cal-head'>{wd}</div>")

    for week in weeks:
        for day in week:
            if day == 0:
                parts.append("<div class='loji-cal-day empty'></div>")
                continue

            parts.append("<div class='loji-cal-day'>")
            parts.append(f"<div class='loji-cal-num'>{day}</div>")

            day_items = items_by_day.get(day, [])
            if not day_items:
                parts.append("<div class='small-muted'>İhale yok</div>")
            else:
                for r in day_items[:4]:
                    kurum = html.escape(str(r.get("kurum", "")))
                    ikn = html.escape(str(r.get("ikn", "")))
                    grup = html.escape(str(r.get("urun_grubu", "")))
                    durum = html.escape(str(r.get("durum", "")))
                    kisi = html.escape(str(r.get("ilgili_kisi", "")))
                    parts.append(
                        f"<div class='loji-cal-item'>"
                        f"<strong>{kurum}</strong><br>"
                        f"İKN: {ikn}<br>"
                        f"{grup}<br>"
                        f"<span class='loji-cal-status'>{durum}</span><br>"
                        f"<span class='small-muted'>{kisi}</span>"
                        f"</div>"
                    )
                if len(day_items) > 4:
                    parts.append(f"<div class='small-muted'>+{len(day_items)-4} ihale daha</div>")
            parts.append("</div>")

    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)



def render_result_charts(kind):
    status = "Kazanıldı" if kind == "won" else "Kaybedildi"

    df = fetch_df("""
        SELECT t.id, t.kurum, t.urun_grubu, t.ilgili_kisi, t.ihale_tarihi,
               p.sonuc_durum, p.sonuc_urun_grubu,
               COALESCE(NULLIF(TRIM(p.istirak_firma), ''), 'Belirtilmemiş') AS istirak_firma,
               p.sozlesme_bedeli, p.bizim_fiyat, p.fiyat_farki, p.fark_yuzdesi,
               p.ihale_suresi_ay, p.yillik_getiri, p.sozlesme_baslangic_tarihi
        FROM tender_result_parts p
        JOIN tenders t ON t.id=p.ihale_id
        WHERE p.sonuc_durum=:status
    """, {"status": status}).fillna("")

    if df.empty:
        st.info("Grafik için veri yok.")
        return

    # Firma bazlı rapor filtresi
    df["istirak_firma"] = df["istirak_firma"].fillna("Belirtilmemiş").astype(str)
    extra_firmalar = sorted([x for x in df["istirak_firma"].unique().tolist() if x and x not in PARTICIPANT_COMPANY_OPTIONS and x != "Belirtilmemiş"])
    firma_options = ["Tüm Firmalar"] + PARTICIPANT_COMPANY_OPTIONS + extra_firmalar + ["Belirtilmemiş"]
    selected_firma = st.selectbox(
        "Rapor firması",
        firma_options,
        key=f"result_report_firma_{kind}"
    )
    # Streamlit widget state kendi güncellenir; burada manuel session_state ataması yapılmaz.

    if selected_firma != "Tüm Firmalar":
        df = df[df["istirak_firma"] == selected_firma].copy()

    if df.empty:
        st.info(f"{selected_firma} için {status.lower()} ihale sonucu yok.")
        return

    df["sozlesme_bedeli_num"] = pd.to_numeric(df.get("sozlesme_bedeli", 0), errors="coerce").fillna(0)
    df["yillik_getiri_num"] = pd.to_numeric(df.get("yillik_getiri", 0), errors="coerce").fillna(0)
    df["bizim_fiyat_num"] = pd.to_numeric(df.get("bizim_fiyat", 0), errors="coerce").fillna(0)
    df["fiyat_farki_num"] = pd.to_numeric(df.get("fiyat_farki", 0), errors="coerce").fillna(0)

    sonuc_chart_df = split_multi_values_for_report(df, "sonuc_urun_grubu") if "sonuc_urun_grubu" in df.columns else df

    def build_kurum_group_detail(source_df, value_col):
        detail_map = {}
        temp = source_df.copy()
        temp["kurum"] = temp["kurum"].fillna("").astype(str)
        temp["sonuc_urun_grubu"] = temp["sonuc_urun_grubu"].fillna("Belirtilmemiş").astype(str)
        temp[value_col] = pd.to_numeric(temp[value_col], errors="coerce").fillna(0)

        grouped = (
            temp.groupby(["kurum", "sonuc_urun_grubu"], as_index=False)[value_col]
            .sum()
            .sort_values(["kurum", value_col], ascending=[True, False])
        )

        for kurum, g in grouped.groupby("kurum"):
            lines = []
            for _, r in g.iterrows():
                grup = str(r["sonuc_urun_grubu"] or "Belirtilmemiş")
                tutar = format_tr_money_display(r[value_col])
                lines.append(f"{grup}: {tutar}")
            detail_map[kurum] = "<br>".join(lines) if lines else "Detay yok"
        return detail_map

    st.markdown("###  Özet Grafikleri")
    st.caption(f"Seçili firma: {selected_firma}")

    if kind == "won":
        c1, c2 = st.columns(2)
        with c1:
            kurum_sum = (
                df.groupby("kurum", as_index=False)["sozlesme_bedeli_num"]
                .sum()
                .sort_values("sozlesme_bedeli_num", ascending=False)
                .head(12)
            )
            if kurum_sum["sozlesme_bedeli_num"].sum() > 0:
                detail_map = build_kurum_group_detail(df, "sozlesme_bedeli_num")
                kurum_sum["detay"] = kurum_sum["kurum"].map(detail_map).fillna("Detay yok")
                kurum_sum["goster"] = kurum_sum["sozlesme_bedeli_num"].apply(format_tr_money_display)
                fig = px.bar(
                    kurum_sum,
                    x="kurum",
                    y="sozlesme_bedeli_num",
                    title="Kazanılan İhaleler - Kuruma Göre Sözleşme Bedeli",
                    labels={"kurum": "Kurum", "sozlesme_bedeli_num": "Sözleşme Bedeli"},
                    custom_data=["goster", "detay"],
                )
                fig.update_traces(
                    hovertemplate=(
                        "<b>Kurum:</b> %{x}<br>"
                        "<b>Toplam Sözleşme Bedeli:</b> %{customdata[0]}<br><br>"
                        "<b>Ürün Grubu Detayı</b><br>%{customdata[1]}<extra></extra>"
                    )
                )
                fig = style_plotly(fig)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sözleşme bedeli verisi yok.")

        with c2:
            yillik_sum = (
                df.groupby("kurum", as_index=False)["yillik_getiri_num"]
                .sum()
                .sort_values("yillik_getiri_num", ascending=False)
                .head(12)
            )
            if yillik_sum["yillik_getiri_num"].sum() > 0:
                detail_map = build_kurum_group_detail(df, "yillik_getiri_num")
                yillik_sum["detay"] = yillik_sum["kurum"].map(detail_map).fillna("Detay yok")
                yillik_sum["goster"] = yillik_sum["yillik_getiri_num"].apply(format_tr_money_display)
                fig = px.bar(
                    yillik_sum,
                    x="kurum",
                    y="yillik_getiri_num",
                    title="Kazanılan İhaleler - Kuruma Göre Getiri",
                    labels={"kurum": "Kurum", "yillik_getiri_num": "Getiri"},
                    custom_data=["goster", "detay"],
                )
                fig.update_traces(
                    hovertemplate=(
                        "<b>Kurum:</b> %{x}<br>"
                        "<b>Toplam Getiri:</b> %{customdata[0]}<br><br>"
                        "<b>Ürün Grubu Getiri Detayı</b><br>%{customdata[1]}<extra></extra>"
                    )
                )
                fig = style_plotly(fig)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Getiri verisi yok.")

    else:
        c1, c2 = st.columns(2)
        with c1:
            kurum_sum = (
                df.groupby("kurum", as_index=False)["sozlesme_bedeli_num"]
                .sum()
                .sort_values("sozlesme_bedeli_num", ascending=False)
                .head(12)
            )
            if kurum_sum["sozlesme_bedeli_num"].sum() > 0:
                detail_map = build_kurum_group_detail(df, "sozlesme_bedeli_num")
                kurum_sum["detay"] = kurum_sum["kurum"].map(detail_map).fillna("Detay yok")
                kurum_sum["goster"] = kurum_sum["sozlesme_bedeli_num"].apply(format_tr_money_display)
                fig = px.bar(
                    kurum_sum,
                    x="kurum",
                    y="sozlesme_bedeli_num",
                    title="Kaybedilen İhaleler - Tahmini Kazanan Fiyat",
                    labels={"kurum": "Kurum", "sozlesme_bedeli_num": "Tahmini Kazanan Fiyat"},
                    custom_data=["goster", "detay"],
                )
                fig.update_traces(
                    hovertemplate=(
                        "<b>Kurum:</b> %{x}<br>"
                        "<b>Tahmini Kazanan Fiyat:</b> %{customdata[0]}<br><br>"
                        "<b>Ürün Grubu Detayı</b><br>%{customdata[1]}<extra></extra>"
                    )
                )
                fig = style_plotly(fig)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Tahmini kazanan fiyat verisi yok.")

        with c2:
            fark_sum = (
                df.groupby("kurum", as_index=False)["fiyat_farki_num"]
                .sum()
                .sort_values("fiyat_farki_num", ascending=False)
                .head(12)
            )
            if fark_sum["fiyat_farki_num"].abs().sum() > 0:
                fark_sum["goster"] = fark_sum["fiyat_farki_num"].apply(format_tr_money_display)
                fig = px.bar(
                    fark_sum,
                    x="kurum",
                    y="fiyat_farki_num",
                    title="Kaybedilen İhaleler - Fiyat Farkı",
                    labels={"kurum": "Kurum", "fiyat_farki_num": "Bizim Fiyat - Kazanan Fiyat"},
                    custom_data=["goster"],
                )
                fig.update_traces(
                    hovertemplate=(
                        "<b>Kurum:</b> %{x}<br>"
                        "<b>Fiyat Farkı:</b> %{customdata[0]}<extra></extra>"
                    )
                )
                fig = style_plotly(fig)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Fiyat farkı verisi yok.")

    # Ürün grubu ve cihaz grafikleri için kurum filtresi
    st.markdown("### Kurum Filtresi")
    result_kurum_options = sorted([
        k for k in df["kurum"].fillna("Kurum belirtilmemiş").astype(str).unique().tolist()
        if str(k).strip()
    ])
    selected_result_kurumlar = st.multiselect(
        "Ürün grubu ve cihaz grafikleri için kurum seç",
        options=result_kurum_options,
        default=[],
        key=f"result_graph_kurum_filter_{kind}",
        help="Boş bırakılırsa tüm kurumlar grafiğe dahil edilir. Birden fazla kurum seçilebilir."
    )

    if selected_result_kurumlar:
        result_chart_base_df = df[df["kurum"].fillna("Kurum belirtilmemiş").astype(str).isin(selected_result_kurumlar)].copy()
        st.caption(f"Grafik kurum filtresi: {', '.join(selected_result_kurumlar)}")
    else:
        result_chart_base_df = df.copy()
        st.caption("Grafik kurum filtresi: Tüm kurumlar")

    if result_chart_base_df.empty:
        st.info("Seçili kurumlar için grafik verisi yok.")
        return

    filtered_sonuc_chart_df = (
        split_multi_values_for_report(result_chart_base_df, "sonuc_urun_grubu")
        if "sonuc_urun_grubu" in result_chart_base_df.columns
        else result_chart_base_df
    )

    # Ürün grubuna göre adet grafiği
    st.markdown("### Ürün Grubu Adet Grafiği")
    if "sonuc_urun_grubu" in filtered_sonuc_chart_df.columns:
        sonuc_adet = (
            filtered_sonuc_chart_df.groupby("sonuc_urun_grubu", as_index=False)
            .size()
            .rename(columns={"size": "adet"})
            .sort_values("adet", ascending=False)
        )
        if not sonuc_adet.empty:
            fig = px.bar(
                sonuc_adet,
                x="sonuc_urun_grubu",
                y="adet",
                title=f"{status} İhaleler - Sonuç Ürün Grubuna Göre Adet",
                labels={"sonuc_urun_grubu": "Sonuç Ürün Grubu", "adet": "İhale Adedi"},
                custom_data=["adet"],
            )
            fig.update_traces(
                hovertemplate="<b>Ürün Grubu:</b> %{x}<br><b>İhale Adedi:</b> %{customdata[0]}<extra></extra>"
            )
            fig = style_plotly(fig)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Seçili kurumlar için ürün grubu adet verisi yok.")

    # Yönetim tablosu: kurum + ürün grubu kırılımı
    if kind == "won":
        detay_df = (
            result_chart_base_df.groupby(["istirak_firma", "kurum", "sonuc_urun_grubu"], as_index=False)
            .agg({"sozlesme_bedeli_num": "sum", "yillik_getiri_num": "sum", "id": "count"})
            .rename(columns={
                "istirak_firma": "İştirak Eden Firma",
                "kurum": "Kurum",
                "sonuc_urun_grubu": "Ürün Grubu",
                "sozlesme_bedeli_num": "Sözleşme Bedeli",
                "yillik_getiri_num": "Yıllık Getiri",
                "id": "Adet",
            })
            .sort_values(["Sözleşme Bedeli"], ascending=False)
        )
        st.markdown("### Kurum Bazlı Ürün Grubu Detayı")
        render_html_table(format_result_display_df(detay_df), empty_message="Kurum bazlı ürün grubu detayı yok.")

    if kind != "won":
        return

    tender_ids = [int(x) for x in result_chart_base_df["id"].dropna().tolist()]
    device_brand_df = pd.DataFrame()
    device_model_df = pd.DataFrame()
    device_raw_df = pd.DataFrame()

    if tender_ids:
        id_sql = ",".join([str(x) for x in tender_ids])
        device_raw_df = fetch_df(f"""
            SELECT 
                d.ihale_id,
                COALESCE(t.kurum, 'Kurum belirtilmemiş') AS kurum,
                COALESCE(NULLIF(TRIM(d.marka), ''), 'Marka Girilmemiş') AS marka,
                COALESCE(NULLIF(TRIM(CONCAT(COALESCE(d.marka,''), ' ', COALESCE(d.model,''))), ''), 'Model Girilmemiş') AS cihaz_model,
                COALESCE(d.cihaz_adedi, 1) AS cihaz_adedi
            FROM devices d
            LEFT JOIN tenders t ON t.id = d.ihale_id
            WHERE d.ihale_id IN ({id_sql})
        """).fillna("")

    if not device_raw_df.empty:
        st.markdown("### Kazanılan İş Cihaz Raporları")

        device_raw_df["kurum"] = device_raw_df["kurum"].fillna("Kurum belirtilmemiş").astype(str)
        device_raw_df["cihaz_adedi"] = pd.to_numeric(device_raw_df["cihaz_adedi"], errors="coerce").fillna(0)

        # Cihaz grafikleri de yukarıdaki kurum filtresine göre çalışır.
        device_chart_df = device_raw_df.copy()

        if device_chart_df.empty:
            st.info("Seçili kurumlar için cihaz verisi yok.")
            return

        device_brand_df = (
            device_chart_df.groupby("marka", as_index=False)
            .agg({"cihaz_adedi": "sum", "ihale_id": "count"})
            .rename(columns={"ihale_id": "satir_adedi"})
            .sort_values("cihaz_adedi", ascending=False)
        )

        device_model_df = (
            device_chart_df.groupby("cihaz_model", as_index=False)
            .agg({"cihaz_adedi": "sum", "ihale_id": "count"})
            .rename(columns={"ihale_id": "satir_adedi"})
            .sort_values("cihaz_adedi", ascending=False)
        )

        brand_total = float(pd.to_numeric(device_brand_df["cihaz_adedi"], errors="coerce").fillna(0).sum() or 0)
        model_total = float(pd.to_numeric(device_model_df["cihaz_adedi"], errors="coerce").fillna(0).sum() or 0)
        device_brand_df["cihaz_adedi_goster"] = device_brand_df["cihaz_adedi"].apply(format_tr_number)
        device_brand_df["oran_goster"] = device_brand_df["cihaz_adedi"].apply(
            lambda x: format_tr_percent_display((float(x or 0) / brand_total * 100) if brand_total else 0)
        )
        device_model_df["cihaz_adedi_goster"] = device_model_df["cihaz_adedi"].apply(format_tr_number)
        device_model_df["oran_goster"] = device_model_df["cihaz_adedi"].apply(
            lambda x: format_tr_percent_display((float(x or 0) / model_total * 100) if model_total else 0)
        )

        kurum_notu = "Tüm kurumlar" if not selected_result_kurumlar else ", ".join(selected_result_kurumlar)
        st.caption(f"Cihaz grafikleri kurum filtresi: {kurum_notu}")

        dc1, dc2 = st.columns(2)
        with dc1:
            if not device_brand_df.empty:
                render_html_table(
                    format_result_display_df(device_brand_df.rename(columns={
                        "marka": "Marka",
                        "cihaz_adedi": "Cihaz Adedi",
                        "satir_adedi": "Kayıt Satırı"
                    })),
                    empty_message="Cihaz marka verisi yok."
                )
                fig = px.pie(
                    device_brand_df,
                    names="marka",
                    values="cihaz_adedi",
                    title="Cihaz Markalarına Göre Adet",
                    custom_data=["cihaz_adedi_goster", "oran_goster"]
                )
                fig = style_plotly(fig)
                fig.update_traces(
                    textinfo="percent+label",
                    hovertemplate="<b>Marka:</b> %{label}<br><b>Cihaz Adedi:</b> %{customdata[0]}<br><b>Oran:</b> %{customdata[1]}%<extra></extra>"
                )
                st.plotly_chart(fig, use_container_width=True)
        with dc2:
            if not device_model_df.empty:
                render_html_table(
                    format_result_display_df(device_model_df.rename(columns={
                        "cihaz_model": "Cihaz Model",
                        "cihaz_adedi": "Cihaz Adedi",
                        "satir_adedi": "Kayıt Satırı"
                    })),
                    empty_message="Cihaz model verisi yok."
                )
                fig = px.bar(
                    device_model_df,
                    x="cihaz_model",
                    y="cihaz_adedi",
                    title="Cihaz Modeline Göre Adet",
                    labels={"cihaz_model": "Cihaz Model", "cihaz_adedi": "Cihaz Adedi"},
                    custom_data=["cihaz_adedi_goster", "oran_goster"]
                )
                fig = style_plotly(fig)
                fig.update_traces(
                    hovertemplate="<b>Cihaz Model:</b> %{x}<br><b>Cihaz Adedi:</b> %{customdata[0]}<br><b>Oran:</b> %{customdata[1]}%<extra></extra>"
                )
                st.plotly_chart(fig, use_container_width=True)


def ensure_private_job_schema():
    if st.session_state.get("private_schema_done"):
        return
    st.session_state.private_schema_done = True
    sqls = [
        """
        CREATE TABLE IF NOT EXISTS private_job_devices (
          id int NOT NULL AUTO_INCREMENT,
          private_job_id int NOT NULL,
          sira_no int DEFAULT 1,
          marka varchar(255) DEFAULT NULL,
          model varchar(255) DEFAULT NULL,
          kurulum_yapilacak_hastane_bilgisi text,
          PRIMARY KEY (id),
          KEY idx_private_job_devices_job (private_job_id),
          CONSTROtomatikNT fk_private_job_devices_job FOREIGN KEY (private_job_id) REFERENCES private_jobs (id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_turkish_ci
        """,
        "ALTER TABLE private_job_tests ADD COLUMN ihale_toplam_test_sayisi int DEFAULT 0",
    ]
    with ENGINE.begin() as conn:
        for s in sqls:
            try:
                conn.execute(text(s))
            except Exception:
                pass


def ensure_v24_columns():
    runtime_alters = [
        "ALTER TABLE tenders ADD COLUMN ihale_suresi_ay int DEFAULT NULL",
        "ALTER TABLE tenders ADD COLUMN yillik_getiri decimal(18,2) DEFAULT NULL",
        "ALTER TABLE private_jobs ADD COLUMN is_suresi_ay int DEFAULT NULL",
        "ALTER TABLE private_jobs ADD COLUMN yillik_getiri decimal(18,2) DEFAULT NULL",
        "ALTER TABLE private_job_devices ADD COLUMN cihaz_adedi int DEFAULT 1",
    ]
    for q in runtime_alters:
        try:
            execute(q)
        except Exception:
            pass



def ensure_v28_contract_columns():
    runtime_alters = [
        "ALTER TABLE tenders ADD COLUMN ihale_suresi_ay int DEFAULT NULL",
        "ALTER TABLE tenders ADD COLUMN yillik_getiri decimal(18,2) DEFAULT NULL",
        "ALTER TABLE tenders ADD COLUMN sozlesme_baslangic_tarihi date DEFAULT NULL",
        "ALTER TABLE won_tenders ADD COLUMN sozlesme_baslangic_tarihi date DEFAULT NULL",
        "ALTER TABLE won_tenders ADD COLUMN ihale_suresi_ay int DEFAULT NULL",
        "ALTER TABLE won_tenders ADD COLUMN yillik_getiri decimal(18,2) DEFAULT NULL",
    ]
    for q in runtime_alters:
        try:
            execute(q)
        except Exception:
            pass



def ensure_v30_columns():
    runtime_alters = [
        "ALTER TABLE tenders ADD COLUMN sonuc_urun_grubu varchar(100) DEFAULT NULL",
        "ALTER TABLE tenders ADD COLUMN eksik_bilgi_hatirlatma_tarihi date DEFAULT NULL",
        "ALTER TABLE won_tenders ADD COLUMN sonuc_urun_grubu varchar(100) DEFAULT NULL",
        "ALTER TABLE lost_tenders ADD COLUMN sonuc_urun_grubu varchar(100) DEFAULT NULL",
    ]
    for q in runtime_alters:
        try:
            execute(q)
        except Exception:
            pass



def ensure_v32_columns():
    runtime_alters = [
        "ALTER TABLE tenders MODIFY COLUMN sonuc_urun_grubu varchar(255) DEFAULT NULL",
        "ALTER TABLE won_tenders MODIFY COLUMN sonuc_urun_grubu varchar(255) DEFAULT NULL",
        "ALTER TABLE lost_tenders MODIFY COLUMN sonuc_urun_grubu varchar(255) DEFAULT NULL",
        "ALTER TABLE tenders ADD COLUMN ihale_suresi_ay int DEFAULT NULL",
        "ALTER TABLE tenders ADD COLUMN yillik_getiri decimal(18,2) DEFAULT NULL",
        "ALTER TABLE tenders ADD COLUMN sozlesme_baslangic_tarihi date DEFAULT NULL",
        "ALTER TABLE won_tenders ADD COLUMN ihale_suresi_ay int DEFAULT NULL",
        "ALTER TABLE won_tenders ADD COLUMN yillik_getiri decimal(18,2) DEFAULT NULL",
        "ALTER TABLE won_tenders ADD COLUMN sozlesme_baslangic_tarihi date DEFAULT NULL",
    ]
    for q in runtime_alters:
        try:
            execute(q)
        except Exception:
            pass




def ensure_v35_lost_columns():
    runtime_alters = [
        "ALTER TABLE lost_tenders ADD COLUMN bizim_fiyat decimal(18,2) DEFAULT NULL",
        "ALTER TABLE lost_tenders ADD COLUMN fiyat_farki decimal(18,2) DEFAULT NULL",
        "ALTER TABLE lost_tenders ADD COLUMN fark_yuzdesi decimal(10,2) DEFAULT NULL",
        "ALTER TABLE lost_tenders MODIFY COLUMN sozlesme_bedeli decimal(18,2) NULL",
        "ALTER TABLE lost_tenders MODIFY COLUMN bizim_fiyat decimal(18,2) NULL",
        "ALTER TABLE lost_tenders MODIFY COLUMN fiyat_farki decimal(18,2) NULL",
        "ALTER TABLE lost_tenders MODIFY COLUMN fark_yuzdesi decimal(10,2) NULL",
    ]
    for q in runtime_alters:
        try:
            execute(q)
        except Exception:
            pass


def ensure_partial_result_schema():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS tender_result_parts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ihale_id INT NOT NULL,
                sonuc_durum VARCHAR(30) NOT NULL,
                sonuc_urun_grubu VARCHAR(100) NOT NULL,
                istirak_firma VARCHAR(100) DEFAULT NULL,
                sozlesme_bedeli DECIMAL(18,2) DEFAULT NULL,
                bizim_fiyat DECIMAL(18,2) DEFAULT NULL,
                fiyat_farki DECIMAL(18,2) DEFAULT NULL,
                fark_yuzdesi DECIMAL(10,2) DEFAULT NULL,
                test_rakami INT DEFAULT NULL,
                birim_puan VARCHAR(100) DEFAULT NULL,
                birim_test_fiyati VARCHAR(100) DEFAULT NULL,
                alan_firma VARCHAR(255) DEFAULT NULL,
                kazanan_cihaz VARCHAR(255) DEFAULT NULL,
                sozlesme_baslangic_tarihi DATE DEFAULT NULL,
                ihale_suresi_ay INT DEFAULT NULL,
                yillik_getiri DECIMAL(18,2) DEFAULT NULL,
                admin_notu TEXT DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_tender_result_group (ihale_id, sonuc_urun_grubu),
                KEY idx_trp_ihale (ihale_id),
                KEY idx_trp_status (sonuc_durum),
                KEY idx_trp_group (sonuc_urun_grubu),
                KEY idx_trp_firma (istirak_firma)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_turkish_ci
        """)
    except Exception:
        pass

    try:
        execute("ALTER TABLE tender_result_parts ADD COLUMN istirak_firma VARCHAR(100) DEFAULT NULL")
    except Exception:
        pass

    try:
        execute("CREATE INDEX idx_trp_firma ON tender_result_parts (istirak_firma)")
    except Exception:
        pass

    # Eski tek sonuç kayıtlarını kısmi sonuç tablosuna taşır. Zaten varsa tekrar yazmaz.
    try:
        execute("""
            INSERT IGNORE INTO tender_result_parts
            (ihale_id, sonuc_durum, sonuc_urun_grubu, sozlesme_bedeli, test_rakami,
             birim_puan, birim_test_fiyati, sozlesme_baslangic_tarihi, ihale_suresi_ay,
             yillik_getiri, admin_notu, created_at, updated_at)
            SELECT w.ihale_id, 'Kazanıldı',
                   COALESCE(NULLIF(w.sonuc_urun_grubu,''), 'Belirtilmemiş'),
                   w.sozlesme_bedeli, w.test_rakami, w.birim_puan, w.birim_test_fiyati,
                   w.sozlesme_baslangic_tarihi, w.ihale_suresi_ay, w.yillik_getiri,
                   w.admin_notu, COALESCE(w.kazanma_tarihi, NOW()), NOW()
            FROM won_tenders w
            WHERE w.ihale_id IS NOT NULL
        """)
    except Exception:
        pass

    try:
        execute("""
            INSERT IGNORE INTO tender_result_parts
            (ihale_id, sonuc_durum, sonuc_urun_grubu, sozlesme_bedeli, bizim_fiyat,
             fiyat_farki, fark_yuzdesi, alan_firma, kazanan_cihaz, admin_notu,
             created_at, updated_at)
            SELECT l.ihale_id, 'Kaybedildi',
                   COALESCE(NULLIF(l.sonuc_urun_grubu,''), 'Belirtilmemiş'),
                   l.sozlesme_bedeli, l.bizim_fiyat,
                   COALESCE(l.fiyat_farki, COALESCE(l.bizim_fiyat,0)-COALESCE(l.sozlesme_bedeli,0)),
                   COALESCE(l.fark_yuzdesi, CASE WHEN COALESCE(l.sozlesme_bedeli,0)>0 THEN ((COALESCE(l.bizim_fiyat,0)-COALESCE(l.sozlesme_bedeli,0))/l.sozlesme_bedeli)*100 ELSE 0 END),
                   l.alan_firma, l.kazanan_cihaz, l.admin_notu,
                   COALESCE(l.kaybetme_tarihi, NOW()), NOW()
            FROM lost_tenders l
            WHERE l.ihale_id IS NOT NULL
        """)
    except Exception:
        pass



def ensure_indexes():
    if st.session_state.get("indexes_done"):
        return
    st.session_state.indexes_done = True
    sqls = [
        "CREATE INDEX idx_tenders_durum ON tenders (durum)",
        "CREATE INDEX idx_tenders_takip ON tenders (takip_ediliyor)",
        "CREATE INDEX idx_tenders_ihale ON tenders (ihale_tarihi)",
        "CREATE INDEX idx_devices_ihale ON devices (ihale_id)",
        "CREATE INDEX idx_expenses_ihale ON expenses (ihale_id)",
        "CREATE INDEX idx_comments_ihale ON comments (ihale_id)",
        "CREATE INDEX idx_won_ihale ON won_tenders (ihale_id)",
        "CREATE INDEX idx_lost_ihale ON lost_tenders (ihale_id)",
    ]
    with ENGINE.begin() as conn:
        for s in sqls:
            try:
                conn.execute(text(s))
            except Exception:
                pass



def page_users():
    require_login()
    render_brand()
    st.title("Kullanıcılar")

    if not is_admin():
        st.warning("Bu sayfaya sadece admin erişebilir.")
        return

    df = fetch_df("""
        SELECT id, kullanici_adi, ad_soyad, rol, email, aktif
        FROM users
        ORDER BY id ASC
    """).fillna("")

    render_html_table(df, empty_message="Kullanıcı kaydı yok.")

    st.divider()
    st.markdown("### Yeni Kullanıcı Ekle")

    with st.form("add_user_form", enter_to_submit=False):
        c1, c2 = st.columns(2)
        kullanici_adi = c1.text_input("Kullanıcı Adı")
        ad_soyad = c2.text_input("Ad Soyad")

        c3, c4 = st.columns(2)
        sifre = c3.text_input("Şifre", type="password")
        rol = c4.selectbox("Rol", ["Satis", "Admin"])

        email = st.text_input("E-posta")
        aktif = st.selectbox("Aktif", ["Evet", "Hayır"], index=0)

        kaydet = st.form_submit_button("Kullanıcıyı Kaydet")

    if kaydet:
        if not kullanici_adi or not sifre or not ad_soyad:
            st.error("Kullanıcı adı, ad soyad ve şifre zorunludur.")
            st.stop()

        execute("""
            INSERT INTO users
            (kullanici_adi, sifre, ad_soyad, rol, email, aktif)
            VALUES
            (:kullanici_adi, :sifre, :ad_soyad, :rol, :email, :aktif)
        """, {
            "kullanici_adi": kullanici_adi,
            "sifre": sifre,
            "ad_soyad": ad_soyad,
            "rol": rol,
            "email": email,
            "aktif": 1 if aktif == "Evet" else 0
        })

        clear_caches()
        st.success("Kullanıcı eklendi.")
        st.rerun()

    st.divider()
    st.markdown("### Kullanıcı Düzenle / Pasifleştir")

    if not df.empty:
        opts = [
            f"{int(r.get('id'))} | {r.get('ad_soyad')} | {r.get('kullanici_adi')}"
            for _, r in df.iterrows()
        ]

        selected = st.selectbox(
            "Düzenlenecek kullanıcı",
            [""] + opts,
            key="edit_user_selectbox"
        )

        if selected:
            user_id = int(selected.split("|")[0].strip())
            user_df = fetch_df("SELECT * FROM users WHERE id=:id", {"id": user_id}).fillna("")

            if not user_df.empty:
                u = user_df.iloc[0]

                with st.form(f"edit_user_form_{user_id}", enter_to_submit=False):
                    c1, c2 = st.columns(2)
                    edit_kullanici_adi = c1.text_input("Kullanıcı Adı", value=str(u.get("kullanici_adi", "") or ""))
                    edit_ad_soyad = c2.text_input("Ad Soyad", value=str(u.get("ad_soyad", "") or ""))

                    c3, c4 = st.columns(2)
                    edit_sifre = c3.text_input("Şifre", value=str(u.get("sifre", "") or ""), type="password")
                    edit_rol = c4.selectbox(
                        "Rol",
                        ["Satis", "Admin"],
                        index=0 if str(u.get("rol", "")) != "Admin" else 1
                    )

                    edit_email = st.text_input("E-posta", value=str(u.get("email", "") or ""))
                    edit_aktif = st.selectbox(
                        "Aktif",
                        ["Evet", "Hayır"],
                        index=0 if int(u.get("aktif") or 0) == 1 else 1
                    )

                    guncelle = st.form_submit_button("Kullanıcıyı Güncelle")

                if guncelle:
                    execute("""
                        UPDATE users
                        SET kullanici_adi=:kullanici_adi,
                            sifre=:sifre,
                            ad_soyad=:ad_soyad,
                            rol=:rol,
                            email=:email,
                            aktif=:aktif
                        WHERE id=:id
                    """, {
                        "id": user_id,
                        "kullanici_adi": edit_kullanici_adi,
                        "sifre": edit_sifre,
                        "ad_soyad": edit_ad_soyad,
                        "rol": edit_rol,
                        "email": edit_email,
                        "aktif": 1 if edit_aktif == "Evet" else 0
                    })

                    clear_caches()
                    st.success("Kullanıcı güncellendi.")
                    st.rerun()


def page_mail_settings():
    require_login()
    render_brand()
    st.title("Mail Ayarları")

    if not is_admin():
        st.warning("Bu sayfaya sadece admin erişebilir.")
        return

    df = fetch_df("""
        SELECT *
        FROM mail_settings
        ORDER BY id DESC
    """).fillna("")

    render_html_table(df, empty_message="Mail ayarı yok.")

    current = {}
    if not df.empty:
        current = df.iloc[0].to_dict()

    st.divider()
    st.markdown("### Mail Ayarı Ekle / Güncelle")

    with st.form("mail_settings_form", enter_to_submit=False):
        c1, c2 = st.columns(2)
        smtp_host = c1.text_input("SMTP Host", value=str(current.get("smtp_host", "") or ""))
        smtp_port = c2.number_input("SMTP Port", min_value=1, max_value=9999, value=int(current.get("smtp_port") or 587))

        c3, c4 = st.columns(2)
        smtp_user = c3.text_input("SMTP Kullanıcı", value=str(current.get("smtp_user", "") or ""))
        smtp_password = c4.text_input("SMTP Şifre", value=str(current.get("smtp_password", "") or ""), type="password")

        c5, c6 = st.columns(2)
        from_email = c5.text_input("Gönderen Mail", value=str(current.get("from_email", "") or current.get("smtp_user", "") or ""))
        volkan_email = c6.text_input("Volkan Bildirim Maili", value=str(current.get("volkan_email", "") or ""))

        aktif = st.selectbox("Aktif", ["Evet", "Hayır"], index=0 if int(current.get("aktif") or 0) == 1 else 1)

        kaydet = st.form_submit_button("Mail Ayarlarını Kaydet")

    if kaydet:
        execute("UPDATE mail_settings SET aktif=0", {})

        execute("""
            INSERT INTO mail_settings
            (smtp_host, smtp_port, smtp_user, smtp_password, from_email, volkan_email, aktif)
            VALUES
            (:smtp_host, :smtp_port, :smtp_user, :smtp_password, :from_email, :volkan_email, :aktif)
        """, {
            "smtp_host": smtp_host,
            "smtp_port": int(smtp_port),
            "smtp_user": smtp_user,
            "smtp_password": smtp_password,
            "from_email": from_email,
            "volkan_email": volkan_email,
            "aktif": 1 if aktif == "Evet" else 0
        })

        clear_caches()
        st.success("Mail ayarları kaydedildi.")
        st.rerun()
def page_users():
    render_brand()
    st.title("Kullanıcılar")

    if not is_admin():
        st.warning("Bu sayfaya sadece admin erişebilir.")
        return

    df = fetch_df("""
        SELECT id, kullanici_adi, ad_soyad, rol, email, aktif
        FROM users
        ORDER BY id ASC
    """).fillna("")

    if not df.empty:
        view = df.rename(columns={
            "id": "ID",
            "kullanici_adi": "Kullanıcı Adı",
            "ad_soyad": "Ad Soyad",
            "rol": "Rol",
            "email": "E-posta",
            "aktif": "Aktif",
        })

        if "Aktif" in view.columns:
            view["Aktif"] = view["Aktif"].apply(
                lambda x: "Evet" if int(float(x or 0)) == 1 else "Hayır"
            )

        render_html_table(view, empty_message="Kullanıcı kaydı yok.")
    else:
        st.info("Kullanıcı kaydı yok.")

    st.divider()
    st.markdown("### Yeni Kullanıcı Ekle")

    with st.form("add_user_form_fixed", enter_to_submit=False):
        c1, c2 = st.columns(2)

        kullanici_adi = c1.text_input("Kullanıcı Adı")
        ad_soyad = c2.text_input("Ad Soyad")

        c3, c4 = st.columns(2)

        sifre = c3.text_input("Şifre", type="password")
        rol = c4.selectbox(
            "Rol",
            ["admin", "satis"],
            format_func=lambda x: "Admin" if x == "admin" else "Satış"
        )

        email = st.text_input("E-posta")
        aktif = st.selectbox("Aktif", ["Evet", "Hayır"], index=0)

        kaydet = st.form_submit_button("Kullanıcıyı Kaydet")

    if kaydet:
        if not kullanici_adi.strip() or not ad_soyad.strip() or not sifre.strip():
            st.error("Kullanıcı adı, ad soyad ve şifre zorunludur.")
            st.stop()

        execute("""
            INSERT INTO users
            (kullanici_adi, sifre, ad_soyad, rol, email, aktif)
            VALUES
            (:kullanici_adi, :sifre, :ad_soyad, :rol, :email, :aktif)
        """, {
            "kullanici_adi": kullanici_adi.strip(),
            "sifre": sifre.strip(),
            "ad_soyad": ad_soyad.strip(),
            "rol": rol,
            "email": email.strip(),
            "aktif": 1 if aktif == "Evet" else 0
        })

        clear_caches()
        st.success("Kullanıcı eklendi.")
        st.rerun()

    st.divider()
    st.markdown("### Kullanıcı Düzenle")

    df_edit = fetch_df("""
        SELECT id, kullanici_adi, sifre, ad_soyad, rol, email, aktif
        FROM users
        ORDER BY id ASC
    """).fillna("")

    if not df_edit.empty:
        opts = [
            f"{int(r.get('id'))} | {r.get('ad_soyad')} | {r.get('kullanici_adi')}"
            for _, r in df_edit.iterrows()
        ]

        selected_user = st.selectbox(
            "Düzenlenecek kullanıcı",
            [""] + opts,
            key="edit_user_selectbox_fixed"
        )

        if selected_user:
            user_id = int(selected_user.split("|")[0].strip())
            user_df = fetch_df("SELECT * FROM users WHERE id=:id", {"id": user_id}).fillna("")

            if not user_df.empty:
                u = user_df.iloc[0].to_dict()

                with st.form(f"edit_user_form_fixed_{user_id}", enter_to_submit=False):
                    c1, c2 = st.columns(2)

                    edit_kullanici_adi = c1.text_input(
                        "Kullanıcı Adı",
                        value=str(u.get("kullanici_adi", "") or "")
                    )

                    edit_ad_soyad = c2.text_input(
                        "Ad Soyad",
                        value=str(u.get("ad_soyad", "") or "")
                    )

                    c3, c4 = st.columns(2)

                    edit_sifre = c3.text_input(
                        "Şifre",
                        value=str(u.get("sifre", "") or ""),
                        type="password"
                    )

                    current_role = str(u.get("rol", "") or "satis").lower()

                    edit_rol = c4.selectbox(
                        "Rol",
                        ["admin", "satis"],
                        index=0 if current_role == "admin" else 1,
                        format_func=lambda x: "Admin" if x == "admin" else "Satış"
                    )

                    edit_email = st.text_input(
                        "E-posta",
                        value=str(u.get("email", "") or "")
                    )

                    aktif_val = int(float(u.get("aktif") or 0))

                    edit_aktif = st.selectbox(
                        "Aktif",
                        ["Evet", "Hayır"],
                        index=0 if aktif_val == 1 else 1
                    )

                    guncelle = st.form_submit_button("Kullanıcıyı Güncelle")

                if guncelle:
                    execute("""
                        UPDATE users
                        SET kullanici_adi=:kullanici_adi,
                            sifre=:sifre,
                            ad_soyad=:ad_soyad,
                            rol=:rol,
                            email=:email,
                            aktif=:aktif
                        WHERE id=:id
                    """, {
                        "id": user_id,
                        "kullanici_adi": edit_kullanici_adi.strip(),
                        "sifre": edit_sifre.strip(),
                        "ad_soyad": edit_ad_soyad.strip(),
                        "rol": edit_rol,
                        "email": edit_email.strip(),
                        "aktif": 1 if edit_aktif == "Evet" else 0
                    })

                    clear_caches()
                    st.success("Kullanıcı güncellendi.")
                    st.rerun()


def page_mail_settings():
    render_brand()
    st.title("Mail Ayarları")

    if not is_admin():
        st.warning("Bu sayfaya sadece admin erişebilir.")
        return

    df = fetch_df("""
        SELECT id, smtp_host, smtp_port, smtp_user, from_email, aktif
        FROM mail_settings
        ORDER BY id DESC
    """).fillna("")

    if not df.empty:
        view = df.rename(columns={
            "id": "ID",
            "smtp_host": "SMTP Host",
            "smtp_port": "SMTP Port",
            "smtp_user": "SMTP Kullanıcı",
            "from_email": "Gönderen Mail",
            "aktif": "Aktif",
        })

        if "Aktif" in view.columns:
            view["Aktif"] = view["Aktif"].apply(
                lambda x: "Evet" if int(float(x or 0)) == 1 else "Hayır"
            )

        render_html_table(view, empty_message="Mail ayarı yok.")
    else:
        st.info("Mail ayarı yok.")

    current = {}

    full_df = fetch_df("""
        SELECT *
        FROM mail_settings
        ORDER BY id DESC
        LIMIT 1
    """).fillna("")

    if not full_df.empty:
        current = full_df.iloc[0].to_dict()

    st.divider()
    st.markdown("### Mail Ayarı Ekle / Güncelle")

    with st.form("mail_settings_form_fixed", enter_to_submit=False):
        c1, c2 = st.columns(2)

        smtp_host = c1.text_input(
            "SMTP Host",
            value=str(current.get("smtp_host", "") or "")
        )

        smtp_port = c2.number_input(
            "SMTP Port",
            min_value=1,
            max_value=9999,
            value=int(float(current.get("smtp_port") or 587))
        )

        c3, c4 = st.columns(2)

        smtp_user = c3.text_input(
            "SMTP Kullanıcı",
            value=str(current.get("smtp_user", "") or "")
        )

        smtp_password = c4.text_input(
            "SMTP Şifre",
            value=str(current.get("smtp_password", "") or ""),
            type="password"
        )

        from_email = st.text_input(
            "Gönderen Mail",
            value=str(current.get("from_email", "") or current.get("smtp_user", "") or "")
        )

        aktif = st.selectbox(
            "Aktif",
            ["Evet", "Hayır"],
            index=0 if int(float(current.get("aktif") or 0)) == 1 else 1
        )

        kaydet = st.form_submit_button("Mail Ayarlarını Kaydet")

    if kaydet:
        if not smtp_host.strip():
            st.error("SMTP Host zorunludur.")
            st.stop()

        execute("UPDATE mail_settings SET aktif=0", {})

        execute("""
            INSERT INTO mail_settings
            (smtp_host, smtp_port, smtp_user, smtp_password, from_email, aktif)
            VALUES
            (:smtp_host, :smtp_port, :smtp_user, :smtp_password, :from_email, :aktif)
        """, {
            "smtp_host": smtp_host.strip(),
            "smtp_port": int(smtp_port),
            "smtp_user": smtp_user.strip(),
            "smtp_password": smtp_password,
            "from_email": from_email.strip(),
            "aktif": 1 if aktif == "Evet" else 0
        })

        clear_caches()
        st.success("Mail ayarları kaydedildi.")
        st.rerun()


def main():
    ensure_deleted_tender_schema()
    ensure_partial_result_schema()
    ensure_v35_lost_columns()
    ensure_v32_columns()
    ensure_v30_columns()
    ensure_v28_contract_columns()
    ensure_v24_columns()
    inject_css()
    ensure_private_job_schema()
    ensure_indexes()
    if not st.session_state.get("logged"):
        login()
        return

    page = sidebar_nav()
    if page == "İhale Listesi":
        page_tenders()
    elif page == "Takvim":
        page_calendar()
    elif page == "Takip Edilenler":
        page_followed()
    elif page == "Kazanılanlar":
        page_won()
    elif page == "Kaybedilenler":
        page_lost()
    elif page == "Özel İşler":
        page_private_jobs()
    elif page == "Alınan Özel İşler":
        page_private_jobs_won()
    elif page == "Satış Analizi":
        page_sales_analysis()
    elif page == "Silinen İhaleler":
        page_deleted_tenders()
    elif page == "Kullanıcılar":
        page_users()
    elif page == "Mail Ayarları":
        page_mail_settings()


if __name__ == "__main__":
    main()
