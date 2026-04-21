import streamlit as st
import pandas as pd
import sqlite3
import json
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Maliyet Hesaplama", layout="wide")

DB_FILE = "maliyet_raporu_v3_yeni.db"

TABLECLOTH_PRESETS = {
    "80x80": {"width_cm": 80, "height_cm": 80, "sarfiyat_m": 0.45},
    "80x100": {"width_cm": 80, "height_cm": 100, "sarfiyat_m": 0.55},
    "80x120": {"width_cm": 80, "height_cm": 120, "sarfiyat_m": 0.65},
    "120x160": {"width_cm": 120, "height_cm": 160, "sarfiyat_m": 1.35},
    "140x160": {"width_cm": 140, "height_cm": 160, "sarfiyat_m": 1.55},
    "160x160": {"width_cm": 160, "height_cm": 160, "sarfiyat_m": 1.75},
    "160x200": {"width_cm": 160, "height_cm": 200, "sarfiyat_m": 2.15},
    "160x220": {"width_cm": 160, "height_cm": 220, "sarfiyat_m": 2.35},
    "160x240": {"width_cm": 160, "height_cm": 240, "sarfiyat_m": 2.55},
}


# ----------------------------
# DATABASE
# ----------------------------
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


conn = get_connection()


def column_exists(table_name, column_name):
    cur = conn.execute(f"PRAGMA table_info({table_name})")
    cols = [row[1] for row in cur.fetchall()]
    return column_name in cols


def create_table():
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS maliyet_raporu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            urun_adi TEXT,
            detay_json TEXT
        )
        """
    )
    conn.commit()

    if not column_exists("maliyet_raporu", "urun_tipi"):
        conn.execute("ALTER TABLE maliyet_raporu ADD COLUMN urun_tipi TEXT DEFAULT 'Minder'")
        conn.commit()


create_table()


def kayit_ekle(tarih, urun_adi, urun_tipi, detay_json):
    conn.execute(
        """
        INSERT INTO maliyet_raporu (tarih, urun_adi, urun_tipi, detay_json)
        VALUES (?, ?, ?, ?)
        """,
        (tarih, urun_adi, urun_tipi, detay_json),
    )
    conn.commit()


def kayitlari_getir():
    return pd.read_sql_query("SELECT * FROM maliyet_raporu ORDER BY id DESC", conn)


def kayit_sil(kayit_id):
    conn.execute("DELETE FROM maliyet_raporu WHERE id = ?", (kayit_id,))
    conn.commit()


def tumunu_sil():
    conn.execute("DELETE FROM maliyet_raporu")
    conn.commit()


def to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Rapor")
    output.seek(0)
    return output.getvalue()


# ----------------------------
# HELPERS
# ----------------------------
def safe_div(a, b):
    return a / b if b not in (0, None) else 0


def pct(x):
    return x / 100.0


def df_download_button(df, label, file_name):
    if df is not None and not df.empty:
        st.download_button(
            label=label,
            data=to_excel_bytes(df),
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


# ----------------------------
# MINDER HESAPLAR
# ----------------------------
def dokuma_taban_hesapla(
    ip_no_cozgu,
    ip_no_atki,
    tarak_end_cozgu,
    tarak_end_atki,
    ham_end_cozgu,
    ham_end_atki,
    cozgu_atki_sayisi_cozgu,
    cozgu_atki_sayisi_atki,
    fire_cozgu_yuzde,
    fire_atki_yuzde,
    iplik_fiyati_usd_cozgu,
    iplik_fiyati_usd_atki,
    cozgu_atki_fiyati_tl_cozgu,
    cozgu_atki_fiyati_tl_atki,
    punch_katsayi,
    punch_toplam_bolen,
    mt_bolen,
):
    fire_cozgu = pct(fire_cozgu_yuzde)
    fire_atki = pct(fire_atki_yuzde)

    tel_sayisi_cozgu = tarak_end_cozgu * cozgu_atki_sayisi_cozgu
    tel_sayisi_atki = tarak_end_atki * cozgu_atki_sayisi_atki

    punch_gramaj_cozgu = ((((tarak_end_cozgu / ham_end_cozgu) * cozgu_atki_sayisi_cozgu) / punch_katsayi) / ip_no_cozgu)
    punch_gramaj_atki = ((((tarak_end_atki / ham_end_atki) * cozgu_atki_sayisi_atki) / punch_katsayi) / ip_no_atki)
    punch_gramaj_toplam = safe_div((punch_gramaj_cozgu + punch_gramaj_atki), punch_toplam_bolen)

    mt_tul_gramaj_cozgu = (punch_gramaj_cozgu * tarak_end_cozgu) / mt_bolen
    mt_tul_gramaj_atki = (punch_gramaj_atki * tarak_end_atki) / mt_bolen
    mt_tul_gramaj_toplam = mt_tul_gramaj_cozgu + mt_tul_gramaj_atki

    fireli_mt_tul_gramaj_cozgu = (mt_tul_gramaj_cozgu * fire_cozgu) + mt_tul_gramaj_cozgu
    fireli_mt_tul_gramaj_atki = (mt_tul_gramaj_atki * fire_atki) + mt_tul_gramaj_atki
    fireli_mt_tul_gramaj_toplam = fireli_mt_tul_gramaj_cozgu + fireli_mt_tul_gramaj_atki

    iplik_dolar_maliyeti_cozgu = iplik_fiyati_usd_cozgu * fireli_mt_tul_gramaj_cozgu
    iplik_dolar_maliyeti_atki = iplik_fiyati_usd_atki * fireli_mt_tul_gramaj_atki
    iplik_dolar_maliyeti_toplam = iplik_dolar_maliyeti_cozgu + iplik_dolar_maliyeti_atki

    atki_cozgu_tl_maliyet_cozgu = cozgu_atki_fiyati_tl_cozgu
    atki_cozgu_tl_maliyet_atki = cozgu_atki_fiyati_tl_atki * cozgu_atki_sayisi_atki
    atki_cozgu_tl_maliyet_toplam = atki_cozgu_tl_maliyet_cozgu + atki_cozgu_tl_maliyet_atki

    return {
        "Tel Sayısı Çözgü": {"USD": tel_sayisi_cozgu, "TL": None},
        "Tel Sayısı Atkı": {"USD": tel_sayisi_atki, "TL": None},
        "Punch Gramaj Çözgü": {"USD": punch_gramaj_cozgu, "TL": None},
        "Punch Gramaj Atkı": {"USD": punch_gramaj_atki, "TL": None},
        "Punch Gramaj Toplam": {"USD": punch_gramaj_toplam, "TL": None},
        "MT Tül Gramaj Çözgü": {"USD": mt_tul_gramaj_cozgu, "TL": None},
        "MT Tül Gramaj Atkı": {"USD": mt_tul_gramaj_atki, "TL": None},
        "MT Tül Gramaj Toplam": {"USD": mt_tul_gramaj_toplam, "TL": None},
        "Fireli MT Tül Gramaj Çözgü": {"USD": fireli_mt_tul_gramaj_cozgu, "TL": None},
        "Fireli MT Tül Gramaj Atkı": {"USD": fireli_mt_tul_gramaj_atki, "TL": None},
        "Fireli MT Tül Gramaj Toplam": {"USD": fireli_mt_tul_gramaj_toplam, "TL": None},
        "İplik Dolar Maliyeti Toplam": {"USD": iplik_dolar_maliyeti_toplam, "TL": None},
        "Atkı Çözgü TL Maliyeti Toplam": {"USD": None, "TL": atki_cozgu_tl_maliyet_toplam},
    }


def ham_bez_hesapla(iplik_dolar_maliyeti_toplam, atki_cozgu_tl_maliyet_toplam, alis_kuru, satis_kuru):
    atki_cozgu_usd_karsiligi = safe_div(atki_cozgu_tl_maliyet_toplam, alis_kuru)
    ham_bez_fiyati_usd = iplik_dolar_maliyeti_toplam + atki_cozgu_usd_karsiligi
    ham_bez_fiyati_tl = ham_bez_fiyati_usd * satis_kuru

    return {
        "Ham Bez Fiyatı": {"USD": ham_bez_fiyati_usd, "TL": ham_bez_fiyati_tl},
    }


def atki_maliyeti_hesapla(tezgah_devir, dakika, gun_saati, randiman, siklik, maliyet_tl):
    gunluk_mt = safe_div(((tezgah_devir * dakika * gun_saati * randiman) / siklik), 10000)
    karsiz_atki_maliyeti = safe_div(safe_div(maliyet_tl, gunluk_mt), siklik)

    return {
        "Atkı Günlük MT": {"USD": gunluk_mt, "TL": None},
        "Atkı Kârsız Maliyet": {"USD": karsiz_atki_maliyeti, "TL": None},
    }


def dokuma_toplam_maliyet_hesapla(
    ham_bez_maliyeti_usd,
    alis_kuru,
    satis_kuru,
    boyahane_fiyati_pike_usd,
    hambez_kdv_yuzde,
    boyahane_cekme_yuzde,
    boyahane_kdv_yuzde,
    nakliye_sabit_tl,
):
    hambez_kdv_orani = pct(hambez_kdv_yuzde)
    boyahane_cekme_orani = pct(boyahane_cekme_yuzde)
    boyahane_kdv_orani = pct(boyahane_kdv_yuzde)

    ham_bez_maliyeti_tl = ham_bez_maliyeti_usd * satis_kuru
    ham_bez_kdv_usd = ham_bez_maliyeti_usd * hambez_kdv_orani
    ham_bez_kdv_tl = ham_bez_maliyeti_tl * hambez_kdv_orani

    boyahane_cekme_usd = (ham_bez_maliyeti_usd + ham_bez_kdv_usd) * boyahane_cekme_orani
    boyahane_cekme_tl = boyahane_cekme_usd * satis_kuru

    boyahane_maliyet_usd = boyahane_fiyati_pike_usd
    boyahane_maliyet_tl = boyahane_maliyet_usd * satis_kuru

    boyahane_kdv_usd = boyahane_maliyet_usd * boyahane_kdv_orani
    boyahane_kdv_tl = boyahane_maliyet_tl * boyahane_kdv_orani

    nakliye_usd = safe_div(nakliye_sabit_tl, alis_kuru)
    nakliye_tl = nakliye_usd * satis_kuru

    dokuma_toplam_maliyet_kdvli_usd = (
        ham_bez_maliyeti_usd
        + ham_bez_kdv_usd
        + boyahane_cekme_usd
        + boyahane_maliyet_usd
        + boyahane_kdv_usd
        + nakliye_usd
    )

    dokuma_toplam_maliyet_kdvli_tl = (
        ham_bez_maliyeti_tl
        + ham_bez_kdv_tl
        + boyahane_cekme_tl
        + boyahane_maliyet_tl
        + boyahane_kdv_tl
        + nakliye_tl
    )

    return {
        "Dokuma Toplam Maliyet": {"USD": dokuma_toplam_maliyet_kdvli_usd, "TL": dokuma_toplam_maliyet_kdvli_tl},
    }


def satis_maliyet_ve_kar_hesapla(
    kumas_baz_usd,
    kumas_baz_tl,
    alis_kuru,
    urun_maliyeti_tl,
    konfeksiyon_dikim_tl,
    konf_kesim_tl,
    konf_paket_tl,
    aksesuar_tl,
    nakliye_tl,
    kar_orani_yuzde,
    kumas_cift_kisilik_sarfiyat,
    urun_sarfiyat,
    toplam_fire_yuzde,
    aksesuar_kdv_yuzde,
    aksesuar_fire_yuzde,
    nakliye_kdv_yuzde,
):
    toplam_fire_orani = pct(toplam_fire_yuzde)
    aksesuar_kdv_orani = pct(aksesuar_kdv_yuzde)
    aksesuar_fire_orani = pct(aksesuar_fire_yuzde)
    nakliye_kdv_orani = pct(nakliye_kdv_yuzde)
    kar_orani = pct(kar_orani_yuzde)

    kumas_sarfiyat_gercek = kumas_cift_kisilik_sarfiyat

    kumas_maliyeti_usd = kumas_baz_usd * kumas_sarfiyat_gercek
    kumas_maliyeti_tl = kumas_baz_tl * kumas_sarfiyat_gercek

    urun_maliyeti_usd = safe_div(urun_maliyeti_tl, alis_kuru)
    urun_maliyet_toplam_usd = urun_sarfiyat * urun_maliyeti_usd
    urun_maliyet_toplam_tl = urun_sarfiyat * urun_maliyeti_tl

    toplam_fire_usd = (kumas_maliyeti_usd + urun_maliyet_toplam_usd) * toplam_fire_orani
    toplam_fire_tl = (kumas_maliyeti_tl + urun_maliyet_toplam_tl) * toplam_fire_orani

    konf_kesim_usd = safe_div(konf_kesim_tl, alis_kuru)
    konf_dikim_usd = safe_div(konfeksiyon_dikim_tl, alis_kuru)
    konf_paket_usd = safe_div(konf_paket_tl, alis_kuru)

    aksesuar_usd = safe_div(aksesuar_tl, alis_kuru)
    aksesuar_kdv_usd = aksesuar_usd * aksesuar_kdv_orani
    aksesuar_kdv_tl = aksesuar_tl * aksesuar_kdv_orani
    aksesuar_fire_usd = (aksesuar_usd + aksesuar_kdv_usd) * aksesuar_fire_orani
    aksesuar_fire_tl = (aksesuar_tl + aksesuar_kdv_tl) * aksesuar_fire_orani

    nakliye_usd = safe_div(nakliye_tl, alis_kuru)
    nakliye_kdv_usd = nakliye_usd * nakliye_kdv_orani
    nakliye_kdv_tl = nakliye_tl * nakliye_kdv_orani

    toplam_maliyet_usd = (
        kumas_maliyeti_usd
        + urun_maliyet_toplam_usd
        + toplam_fire_usd
        + konf_kesim_usd
        + konf_dikim_usd
        + konf_paket_usd
        + aksesuar_usd
        + aksesuar_kdv_usd
        + aksesuar_fire_usd
        + nakliye_usd
        + nakliye_kdv_usd
    )

    toplam_maliyet_tl = (
        kumas_maliyeti_tl
        + urun_maliyet_toplam_tl
        + toplam_fire_tl
        + konf_kesim_tl
        + konfeksiyon_dikim_tl
        + konf_paket_tl
        + aksesuar_tl
        + aksesuar_kdv_tl
        + aksesuar_fire_tl
        + nakliye_tl
        + nakliye_kdv_tl
    )

    kar_usd = toplam_maliyet_usd * kar_orani
    kar_tl = toplam_maliyet_tl * kar_orani

    satis_fiyati_usd = toplam_maliyet_usd + kar_usd
    satis_fiyati_tl = toplam_maliyet_tl + kar_tl

    return {
        "Satış Toplam Maliyet": {"USD": toplam_maliyet_usd, "TL": toplam_maliyet_tl},
        "Kâr": {"USD": kar_usd, "TL": kar_tl},
        "Satış Fiyatı": {"USD": satis_fiyati_usd, "TL": satis_fiyati_tl},
    }


def senaryo_hesapla(
    adet,
    psf,
    kargo_ucreti_kdv_dahil,
    dokuma_toplam_usd,
    dokuma_toplam_tl,
    alis_kuru,
    urun_maliyeti_tl,
    konfeksiyon_dikim_tl,
    konf_kesim_tl,
    konf_paket_tl,
    aksesuar_tl,
    nakliye_tl,
    kar_orani_yuzde,
    kumas_cift_kisilik_sarfiyat,
    urun_sarfiyat,
    toplam_fire_yuzde,
    aksesuar_kdv_yuzde,
    aksesuar_fire_yuzde,
    nakliye_kdv_yuzde,
    trendyol_komisyon_orani_yuzde,
    panel_ucreti_sabit,
    iade_orani_kargo_yuzde,
):
    satis = satis_maliyet_ve_kar_hesapla(
        dokuma_toplam_usd,
        dokuma_toplam_tl,
        alis_kuru,
        urun_maliyeti_tl,
        konfeksiyon_dikim_tl * adet,
        konf_kesim_tl * adet,
        konf_paket_tl * adet,
        aksesuar_tl * adet,
        nakliye_tl,
        kar_orani_yuzde,
        kumas_cift_kisilik_sarfiyat * adet,
        urun_sarfiyat * adet,
        toplam_fire_yuzde,
        aksesuar_kdv_yuzde,
        aksesuar_fire_yuzde,
        nakliye_kdv_yuzde,
    )

    satis_fiyati_tl = satis["Satış Fiyatı"]["TL"]
    toplam_maliyet_tl = satis["Satış Toplam Maliyet"]["TL"]
    kar_tl = satis["Kâr"]["TL"]

    trendyol_komisyon = psf * pct(trendyol_komisyon_orani_yuzde)
    iade_tutari = kargo_ucreti_kdv_dahil * pct(iade_orani_kargo_yuzde)
    gider = kargo_ucreti_kdv_dahil + trendyol_komisyon + panel_ucreti_sabit + iade_tutari
    kazanc = psf - gider
    kar_zarar = kazanc - satis_fiyati_tl
    marj = 1 - safe_div((satis_fiyati_tl + gider), psf) if psf > 0 else 0
    konya_marj = safe_div(kar_zarar, satis_fiyati_tl) if satis_fiyati_tl > 0 else 0

    return {
        "Senaryo": f"{adet} Minder",
        "PSF": round(psf, 2),
        "Kargo": round(kargo_ucreti_kdv_dahil, 2),
        "Kumaş Sarfiyat": round(kumas_cift_kisilik_sarfiyat * adet, 4),
        "Ürün Sarfiyat": round(urun_sarfiyat * adet, 4),
        "Kesim TL": round(konf_kesim_tl * adet, 4),
        "Dikim TL": round(konfeksiyon_dikim_tl * adet, 4),
        "Paket TL": round(konf_paket_tl * adet, 4),
        "Aksesuar TL": round(aksesuar_tl * adet, 4),
        "Toplam Maliyet TL": round(toplam_maliyet_tl, 4),
        "Satış Fiyatı TL": round(satis_fiyati_tl, 4),
        "Kâr TL": round(kar_tl, 4),
        "Kâr/Zarar TL": round(kar_zarar, 4),
        "Marj %": round(marj * 100, 4),
        "Konya Marj %": round(konya_marj * 100, 4),
    }


def dict_to_detail_df(*blocks):
    rows = []
    for block in blocks:
        for key, val in block.items():
            rows.append([key, val.get("USD"), val.get("TL")])
    return pd.DataFrame(rows, columns=["Kalem", "USD", "TL"])


# ----------------------------
# MASA ÖRTÜSÜ HESAPLAR
# ----------------------------
def masa_ortusu_hesapla(
    preset_olcu,
    en_cm,
    boy_cm,
    sarfiyat_m,
    adet,
    kumas_tl_metre,
    kumas_fire_yuzde,
    kesim_tl,
    dikim_tl,
    paket_tl,
    aksesuar_tl,
    aksesuar_kdv_yuzde,
    aksesuar_fire_yuzde,
    nakliye_tl,
    nakliye_kdv_yuzde,
    kar_orani_yuzde,
    psf,
):
    kumas_fire_orani = pct(kumas_fire_yuzde)
    aksesuar_kdv_orani = pct(aksesuar_kdv_yuzde)
    aksesuar_fire_orani = pct(aksesuar_fire_yuzde)
    nakliye_kdv_orani = pct(nakliye_kdv_yuzde)
    kar_orani = pct(kar_orani_yuzde)

    kumas_maliyeti = kumas_tl_metre * sarfiyat_m
    kumas_fire_tutari = kumas_maliyeti * kumas_fire_orani

    aksesuar_kdv_tutari = aksesuar_tl * aksesuar_kdv_orani
    aksesuar_fire_tutari = aksesuar_tl * aksesuar_fire_orani
    aksesuar_toplami = aksesuar_tl + aksesuar_kdv_tutari + aksesuar_fire_tutari

    nakliye_kdv_tutari = nakliye_tl * nakliye_kdv_orani

    birim_toplam_maliyet = (
        kumas_maliyeti
        + kumas_fire_tutari
        + kesim_tl
        + dikim_tl
        + paket_tl
        + aksesuar_toplami
        + nakliye_tl
        + nakliye_kdv_tutari
    )

    birim_kar = birim_toplam_maliyet * kar_orani
    birim_satis_fiyati = birim_toplam_maliyet + birim_kar
    toplam_maliyet = birim_toplam_maliyet * adet
    toplam_satis = birim_satis_fiyati * adet
    marj_yuzde = safe_div(birim_kar, birim_satis_fiyati) * 100 if birim_satis_fiyati > 0 else 0

    detay_rows = [
        ["Hazır Ölçü", preset_olcu, None],
        ["En (cm)", en_cm, None],
        ["Boy (cm)", boy_cm, None],
        ["Sarfiyat (m)", sarfiyat_m, None],
        ["Kumaş TL / metre", None, kumas_tl_metre],
        ["Kumaş Maliyeti", None, kumas_maliyeti],
        ["Kumaş Fire Tutarı", None, kumas_fire_tutari],
        ["Kesim", None, kesim_tl],
        ["Dikim", None, dikim_tl],
        ["Paket", None, paket_tl],
        ["Aksesuar", None, aksesuar_tl],
        ["Aksesuar KDV", None, aksesuar_kdv_tutari],
        ["Aksesuar Fire", None, aksesuar_fire_tutari],
        ["Aksesuar Toplamı", None, aksesuar_toplami],
        ["Nakliye", None, nakliye_tl],
        ["Nakliye KDV", None, nakliye_kdv_tutari],
        ["Birim Toplam Maliyet", None, birim_toplam_maliyet],
        ["Birim Kâr", None, birim_kar],
        ["Birim Satış Fiyatı", None, birim_satis_fiyati],
        ["Toplam Maliyet", None, toplam_maliyet],
        ["Toplam Satış", None, toplam_satis],
        ["Marj %", marj_yuzde, None],
        ["PSF", None, psf],
    ]

    detay_df = pd.DataFrame(detay_rows, columns=["Kalem", "USD", "TL"])

    ozet_df = pd.DataFrame([
        {
            "Ürün": "Masa Örtüsü",
            "Ölçü": preset_olcu,
            "En (cm)": en_cm,
            "Boy (cm)": boy_cm,
            "Adet": adet,
            "Sarfiyat (m)": round(sarfiyat_m, 4),
            "Birim Maliyet TL": round(birim_toplam_maliyet, 4),
            "Birim Satış Fiyatı TL": round(birim_satis_fiyati, 4),
            "Toplam Maliyet TL": round(toplam_maliyet, 4),
            "Toplam Satış TL": round(toplam_satis, 4),
            "Marj %": round(marj_yuzde, 4),
            "PSF": round(psf, 2),
        }
    ])

    return detay_df, ozet_df


# ----------------------------
# SESSION
# ----------------------------
if "minder_detay_df" not in st.session_state:
    st.session_state.minder_detay_df = None
if "minder_senaryo_df" not in st.session_state:
    st.session_state.minder_senaryo_df = None
if "minder_kayit_json" not in st.session_state:
    st.session_state.minder_kayit_json = None

if "masa_detay_df" not in st.session_state:
    st.session_state.masa_detay_df = None
if "masa_ozet_df" not in st.session_state:
    st.session_state.masa_ozet_df = None
if "masa_kayit_json" not in st.session_state:
    st.session_state.masa_kayit_json = None


# ----------------------------
# UI
# ----------------------------
st.title("Maliyet Hesaplama ve Raporlama")

tab1, tab2, tab3 = st.tabs(["Minder", "Masa Örtüsü", "Kayıtlı Raporlar"])

# ----------------------------
# TAB 1 - MINDER
# ----------------------------
with tab1:
    st.subheader("Genel Bilgiler")

    g1, g2 = st.columns(2)
    with g1:
        urun_adi = st.text_input("Ürün adı", value="Minder", key="minder_urun_adi")
    with g2:
        stok_adedi = st.number_input("Stok adedi", min_value=0.0, value=100.0, step=1.0, key="minder_stok_adedi")

    st.subheader("1 / 2 / 4 / 6 Minder PSF")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        psf_1 = st.number_input("1 Minder PSF", min_value=0.0, value=400.0, step=0.01, key="psf_1")
    with p2:
        psf_2 = st.number_input("2 Minder PSF", min_value=0.0, value=750.0, step=0.01, key="psf_2")
    with p3:
        psf_4 = st.number_input("4 Minder PSF", min_value=0.0, value=1400.0, step=0.01, key="psf_4")
    with p4:
        psf_6 = st.number_input("6 Minder PSF", min_value=0.0, value=2000.0, step=0.01, key="psf_6")

    st.subheader("1 / 2 / 4 / 6 Minder Kargo KDV Dahil")
    kg1, kg2, kg3, kg4 = st.columns(4)
    with kg1:
        kargo_1 = st.number_input("1 Minder Kargo", min_value=0.0, value=93.0, key="kargo_1")
    with kg2:
        kargo_2 = st.number_input("2 Minder Kargo", min_value=0.0, value=129.6, key="kargo_2")
    with kg3:
        kargo_4 = st.number_input("4 Minder Kargo", min_value=0.0, value=184.8, key="kargo_4")
    with kg4:
        kargo_6 = st.number_input("6 Minder Kargo", min_value=0.0, value=222.0, key="kargo_6")

    st.subheader("Kur Bilgileri")
    c1, c2 = st.columns(2)
    with c1:
        alis_kuru = st.number_input("Alış kuru", min_value=0.0, value=43.0, step=0.01, key="alis_kuru")
    with c2:
        satis_kuru = st.number_input("Satış kuru", min_value=0.0, value=44.0, step=0.01, key="satis_kuru")

    with st.expander("Varsayılanlar / Sabitler", expanded=False):
        v1, v2, v3, v4 = st.columns(4)
        with v1:
            ip_no_cozgu = st.number_input("İp no çözgü", value=35.4400472533963, step=0.000001, format="%.12f", key="ip_no_cozgu")
            tarak_end_cozgu = st.number_input("Tarak end çözgü", value=195.0, step=1.0, key="tarak_end_cozgu")
            ham_end_cozgu = st.number_input("Ham end çözgü", value=190.0, step=1.0, key="ham_end_cozgu")
            cozgu_atki_sayisi_cozgu = st.number_input("Çözgü atkı sayısı çözgü", value=46.0, step=1.0, key="cozgu_atki_sayisi_cozgu")
            fire_cozgu_yuzde = st.number_input("Fire çözgü %", value=7.0, step=0.1, key="fire_cozgu_yuzde")

        with v2:
            ip_no_atki = st.number_input("İp no atkı", value=6.0, step=1.0, key="ip_no_atki")
            tarak_end_atki = st.number_input("Tarak end atkı", value=195.0, step=1.0, key="tarak_end_atki")
            ham_end_atki = st.number_input("Ham end atkı", value=190.0, step=1.0, key="ham_end_atki")
            cozgu_atki_sayisi_atki = st.number_input("Çözgü atkı sayısı atkı", value=11.0, step=1.0, key="cozgu_atki_sayisi_atki")
            fire_atki_yuzde = st.number_input("Fire atkı %", value=10.0, step=0.1, key="fire_atki_yuzde")

        with v3:
            tezgah_devir = st.number_input("Tezgah devir", value=350.0, step=1.0, key="tezgah_devir")
            dakika = st.number_input("Dakika", value=60.0, step=1.0, key="dakika")
            gun_saati = st.number_input("Gün saati", value=24.0, step=1.0, key="gun_saati")
            randiman = st.number_input("Randıman", value=50.0, step=1.0, key="randiman")
            atki_maliyet_tl = st.number_input("Atkı maliyet TL", value=2100.0, step=0.01, key="atki_maliyet_tl")

        with v4:
            hambez_kdv_yuzde = st.number_input("Hambez KDV %", value=10.0, step=0.1, key="hambez_kdv_yuzde")
            boyahane_cekme_yuzde = st.number_input("Boyahane çekme %", value=13.0, step=0.1, key="boyahane_cekme_yuzde")
            boyahane_kdv_yuzde = st.number_input("Boyahane KDV %", value=20.0, step=0.1, key="boyahane_kdv_yuzde")
            nakliye_sabit_tl = st.number_input("Dokuma nakliye sabit TL", value=0.60, step=0.01, key="nakliye_sabit_tl")
            kumas_cift_kisilik_sarfiyat = st.number_input("Kumaş çift kişilik sarfiyat", value=0.25, step=0.01, key="kumas_cift_kisilik_sarfiyat")
            urun_sarfiyat = st.number_input("Ürün sarfiyat", value=1.0, step=0.01, key="urun_sarfiyat")
            toplam_fire_yuzde = st.number_input("Toplam fire %", value=8.0, step=0.1, key="toplam_fire_yuzde")
            aksesuar_kdv_yuzde = st.number_input("Aksesuar KDV %", value=20.0, step=0.1, key="aksesuar_kdv_yuzde")
            aksesuar_fire_yuzde = st.number_input("Aksesuar fire %", value=7.0, step=0.1, key="aksesuar_fire_yuzde")
            nakliye_kdv_yuzde = st.number_input("Nakliye KDV %", value=20.0, step=0.1, key="nakliye_kdv_yuzde")
            trendyol_komisyon_orani_yuzde = st.number_input("Trendyol komisyon %", value=21.0, step=0.1, key="trendyol_komisyon_orani_yuzde")
            punch_katsayi = st.number_input("Punch katsayısı", value=1.693, step=0.001, format="%.3f", key="punch_katsayi")
            punch_toplam_bolen = st.number_input("Punch toplam bölme değeri", value=10.0, step=1.0, key="punch_toplam_bolen")
            mt_bolen = st.number_input("MT tül gramaj bölme değeri", value=1000.0, step=1.0, key="mt_bolen")

    st.subheader("Dokuma Manuel Giriş")
    d1, d2 = st.columns(2)
    with d1:
        iplik_fiyati_usd_cozgu = st.number_input("Çözgü iplik fiyatı USD", min_value=0.0, value=1.69, step=0.01, key="iplik_fiyati_usd_cozgu")
        iplik_fiyati_usd_atki = st.number_input("Atkı iplik fiyatı USD", min_value=0.0, value=2.00, step=0.01, key="iplik_fiyati_usd_atki")
    with d2:
        cozgu_atki_fiyati_tl_cozgu = st.number_input("Çözgü atkı fiyatı TL", min_value=0.0, value=1.30, step=0.01, key="cozgu_atki_fiyati_tl_cozgu")
        cozgu_atki_fiyati_tl_atki = st.number_input("Atkı çözgü fiyatı TL", min_value=0.0, value=0.75, step=0.01, key="cozgu_atki_fiyati_tl_atki")

    st.subheader("Konfeksiyon Manuel Giriş")
    k1, k2, k3 = st.columns(3)
    with k1:
        urun_maliyeti_tl = st.number_input("Ürün maliyeti TL", min_value=0.0, value=23.00, step=0.01, key="urun_maliyeti_tl")
        konf_kesim_tl = st.number_input("Konfeksiyon kesim TL", min_value=0.0, value=0.00, step=0.01, key="konf_kesim_tl")
    with k2:
        konfeksiyon_dikim_tl = st.number_input("Konfeksiyon dikim TL", min_value=0.0, value=28.00, step=0.01, key="konfeksiyon_dikim_tl")
        konf_paket_tl = st.number_input("Konfeksiyon paket TL", min_value=0.0, value=0.00, step=0.01, key="konf_paket_tl")
    with k3:
        aksesuar_tl = st.number_input("Aksesuar TL", min_value=0.0, value=5.00, step=0.01, key="aksesuar_tl")
        nakliye_tl = st.number_input("Satış tarafı nakliye TL", min_value=0.0, value=0.00, step=0.01, key="nakliye_tl")
        kar_orani_yuzde = st.number_input("Kâr oranı %", min_value=0.0, value=60.0, step=0.1, key="kar_orani_yuzde")

    st.subheader("Son Rapor Sabitleri")
    r1, r2 = st.columns(2)
    with r1:
        panel_ucreti_sabit = st.number_input("Panel ücreti KDV dahil", min_value=0.0, value=10.18, step=0.01, key="panel_ucreti_sabit")
    with r2:
        iade_orani_kargo_yuzde = st.number_input("İade oranı (kargo üzerinden) %", min_value=0.0, value=10.0, step=0.1, key="iade_orani_kargo_yuzde")

    if st.button("MINDER HESAPLA", use_container_width=True):
        dokuma_taban = dokuma_taban_hesapla(
            ip_no_cozgu,
            ip_no_atki,
            tarak_end_cozgu,
            tarak_end_atki,
            ham_end_cozgu,
            ham_end_atki,
            cozgu_atki_sayisi_cozgu,
            cozgu_atki_sayisi_atki,
            fire_cozgu_yuzde,
            fire_atki_yuzde,
            iplik_fiyati_usd_cozgu,
            iplik_fiyati_usd_atki,
            cozgu_atki_fiyati_tl_cozgu,
            cozgu_atki_fiyati_tl_atki,
            punch_katsayi,
            punch_toplam_bolen,
            mt_bolen,
        )

        ham_bez = ham_bez_hesapla(
            dokuma_taban["İplik Dolar Maliyeti Toplam"]["USD"],
            dokuma_taban["Atkı Çözgü TL Maliyeti Toplam"]["TL"],
            alis_kuru,
            satis_kuru,
        )

        atki_bilgisi = atki_maliyeti_hesapla(
            tezgah_devir,
            dakika,
            gun_saati,
            randiman,
            cozgu_atki_sayisi_atki,
            atki_maliyet_tl,
        )

        dokuma_toplam = dokuma_toplam_maliyet_hesapla(
            ham_bez["Ham Bez Fiyatı"]["USD"],
            alis_kuru,
            satis_kuru,
            1.00,
            hambez_kdv_yuzde,
            boyahane_cekme_yuzde,
            boyahane_kdv_yuzde,
            nakliye_sabit_tl,
        )

        detay_df = dict_to_detail_df(dokuma_taban, ham_bez, atki_bilgisi, dokuma_toplam)

        senaryo_df = pd.DataFrame([
            senaryo_hesapla(
                1, psf_1, kargo_1,
                dokuma_toplam["Dokuma Toplam Maliyet"]["USD"],
                dokuma_toplam["Dokuma Toplam Maliyet"]["TL"],
                alis_kuru,
                urun_maliyeti_tl,
                konfeksiyon_dikim_tl,
                konf_kesim_tl,
                konf_paket_tl,
                aksesuar_tl,
                nakliye_tl,
                kar_orani_yuzde,
                kumas_cift_kisilik_sarfiyat,
                urun_sarfiyat,
                toplam_fire_yuzde,
                aksesuar_kdv_yuzde,
                aksesuar_fire_yuzde,
                nakliye_kdv_yuzde,
                trendyol_komisyon_orani_yuzde,
                panel_ucreti_sabit,
                iade_orani_kargo_yuzde,
            ),
            senaryo_hesapla(
                2, psf_2, kargo_2,
                dokuma_toplam["Dokuma Toplam Maliyet"]["USD"],
                dokuma_toplam["Dokuma Toplam Maliyet"]["TL"],
                alis_kuru,
                urun_maliyeti_tl,
                konfeksiyon_dikim_tl,
                konf_kesim_tl,
                konf_paket_tl,
                aksesuar_tl,
                nakliye_tl,
                kar_orani_yuzde,
                kumas_cift_kisilik_sarfiyat,
                urun_sarfiyat,
                toplam_fire_yuzde,
                aksesuar_kdv_yuzde,
                aksesuar_fire_yuzde,
                nakliye_kdv_yuzde,
                trendyol_komisyon_orani_yuzde,
                panel_ucreti_sabit,
                iade_orani_kargo_yuzde,
            ),
            senaryo_hesapla(
                4, psf_4, kargo_4,
                dokuma_toplam["Dokuma Toplam Maliyet"]["USD"],
                dokuma_toplam["Dokuma Toplam Maliyet"]["TL"],
                alis_kuru,
                urun_maliyeti_tl,
                konfeksiyon_dikim_tl,
                konf_kesim_tl,
                konf_paket_tl,
                aksesuar_tl,
                nakliye_tl,
                kar_orani_yuzde,
                kumas_cift_kisilik_sarfiyat,
                urun_sarfiyat,
                toplam_fire_yuzde,
                aksesuar_kdv_yuzde,
                aksesuar_fire_yuzde,
                nakliye_kdv_yuzde,
                trendyol_komisyon_orani_yuzde,
                panel_ucreti_sabit,
                iade_orani_kargo_yuzde,
            ),
            senaryo_hesapla(
                6, psf_6, kargo_6,
                dokuma_toplam["Dokuma Toplam Maliyet"]["USD"],
                dokuma_toplam["Dokuma Toplam Maliyet"]["TL"],
                alis_kuru,
                urun_maliyeti_tl,
                konfeksiyon_dikim_tl,
                konf_kesim_tl,
                konf_paket_tl,
                aksesuar_tl,
                nakliye_tl,
                kar_orani_yuzde,
                kumas_cift_kisilik_sarfiyat,
                urun_sarfiyat,
                toplam_fire_yuzde,
                aksesuar_kdv_yuzde,
                aksesuar_fire_yuzde,
                nakliye_kdv_yuzde,
                trendyol_komisyon_orani_yuzde,
                panel_ucreti_sabit,
                iade_orani_kargo_yuzde,
            ),
        ])

        st.session_state.minder_detay_df = detay_df
        st.session_state.minder_senaryo_df = senaryo_df

        payload = {
            "urun_tipi": "Minder",
            "detay_df": detay_df.to_dict(orient="records"),
            "senaryo_df": senaryo_df.to_dict(orient="records"),
        }
        st.session_state.minder_kayit_json = json.dumps(payload, ensure_ascii=False)

    if st.session_state.minder_detay_df is not None:
        st.subheader("Dokuma Detayları")
        st.dataframe(st.session_state.minder_detay_df, use_container_width=True)
        df_download_button(st.session_state.minder_detay_df, "Dokuma detaylarını Excel indir", "minder_dokuma_detaylari.xlsx")

    if st.session_state.minder_senaryo_df is not None:
        st.subheader("Senaryo Karşılaştırması")
        st.dataframe(st.session_state.minder_senaryo_df, use_container_width=True)
        df_download_button(st.session_state.minder_senaryo_df, "Senaryo tablosunu Excel indir", "minder_senaryo_karsilastirmasi.xlsx")

    if st.button("MINDER KAYDET", use_container_width=True, key="kaydet_minder_hesap"):
        if st.session_state.minder_kayit_json is None:
            st.error("Önce hesaplama yapmalısın.")
        else:
            try:
                kayit_ekle(
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    urun_adi,
                    "Minder",
                    st.session_state.minder_kayit_json,
                )
                st.success("Minder raporu kaydedildi.")
            except Exception as e:
                st.error(f"Kayıt hatası: {e}")


# ----------------------------
# TAB 2 - MASA ÖRTÜSÜ
# ----------------------------
with tab2:
    st.subheader("Masa Örtüsü Bilgileri")

    m1, m2 = st.columns(2)
    with m1:
        masa_urun_adi = st.text_input("Ürün adı", value="Masa Örtüsü", key="masa_urun_adi")
    with m2:
        masa_adet = st.number_input("Adet", min_value=1, value=1, step=1, key="masa_adet")

    preset_list = list(TABLECLOTH_PRESETS.keys())
    secilen_preset = st.selectbox("Hazır ölçü", preset_list, index=preset_list.index("160x200"))

    preset = TABLECLOTH_PRESETS[secilen_preset]

    mm1, mm2, mm3 = st.columns(3)
    with mm1:
        masa_en = st.number_input("En (cm)", min_value=0.0, value=float(preset["width_cm"]), step=1.0, key="masa_en")
    with mm2:
        masa_boy = st.number_input("Boy (cm)", min_value=0.0, value=float(preset["height_cm"]), step=1.0, key="masa_boy")
    with mm3:
        masa_sarfiyat = st.number_input("Sarfiyat (m)", min_value=0.0, value=float(preset["sarfiyat_m"]), step=0.01, key="masa_sarfiyat")

    st.subheader("Maliyet Girdileri")
    t1, t2, t3 = st.columns(3)
    with t1:
        kumas_tl_metre = st.number_input("Kumaş TL / metre", min_value=0.0, value=106.1004, step=0.01, key="kumas_tl_metre")
        kumas_fire_yuzde = st.number_input("Kumaş fire %", min_value=0.0, value=4.0, step=0.1, key="kumas_fire_yuzde")
        kesim_tl = st.number_input("Kesim TL", min_value=0.0, value=0.0, step=0.01, key="masa_kesim_tl")
    with t2:
        dikim_tl = st.number_input("Dikim TL", min_value=0.0, value=50.0, step=0.01, key="masa_dikim_tl")
        paket_tl = st.number_input("Paket TL", min_value=0.0, value=0.0, step=0.01, key="masa_paket_tl")
        aksesuar_tl_masa = st.number_input("Aksesuar TL", min_value=0.0, value=17.0, step=0.01, key="masa_aksesuar_tl")
    with t3:
        aksesuar_kdv_yuzde_masa = st.number_input("Aksesuar KDV %", min_value=0.0, value=20.0, step=0.1, key="masa_aksesuar_kdv")
        aksesuar_fire_yuzde_masa = st.number_input("Aksesuar fire %", min_value=0.0, value=7.0, step=0.1, key="masa_aksesuar_fire")
        nakliye_tl_masa = st.number_input("Nakliye TL", min_value=0.0, value=0.0, step=0.01, key="masa_nakliye_tl")
        nakliye_kdv_yuzde_masa = st.number_input("Nakliye KDV %", min_value=0.0, value=20.0, step=0.1, key="masa_nakliye_kdv")
        kar_orani_yuzde_masa = st.number_input("Kâr oranı %", min_value=0.0, value=20.0, step=0.1, key="masa_kar_orani")
        masa_psf = st.number_input("PSF", min_value=0.0, value=0.0, step=0.01, key="masa_psf")

    if st.button("MASA ÖRTÜSÜ HESAPLA", use_container_width=True):
        masa_detay_df, masa_ozet_df = masa_ortusu_hesapla(
            secilen_preset,
            masa_en,
            masa_boy,
            masa_sarfiyat,
            masa_adet,
            kumas_tl_metre,
            kumas_fire_yuzde,
            kesim_tl,
            dikim_tl,
            paket_tl,
            aksesuar_tl_masa,
            aksesuar_kdv_yuzde_masa,
            aksesuar_fire_yuzde_masa,
            nakliye_tl_masa,
            nakliye_kdv_yuzde_masa,
            kar_orani_yuzde_masa,
            masa_psf,
        )

        st.session_state.masa_detay_df = masa_detay_df
        st.session_state.masa_ozet_df = masa_ozet_df

        payload = {
            "urun_tipi": "Masa Örtüsü",
            "detay_df": masa_detay_df.to_dict(orient="records"),
            "ozet_df": masa_ozet_df.to_dict(orient="records"),
        }
        st.session_state.masa_kayit_json = json.dumps(payload, ensure_ascii=False)

    if st.session_state.masa_detay_df is not None:
        st.subheader("Masa Örtüsü Detayları")
        st.dataframe(st.session_state.masa_detay_df, use_container_width=True)
        df_download_button(st.session_state.masa_detay_df, "Masa örtüsü detaylarını Excel indir", "masa_ortusu_detaylari.xlsx")

    if st.session_state.masa_ozet_df is not None:
        st.subheader("Masa Örtüsü Özet")
        st.dataframe(st.session_state.masa_ozet_df, use_container_width=True)
        df_download_button(st.session_state.masa_ozet_df, "Masa örtüsü özeti Excel indir", "masa_ortusu_ozet.xlsx")

    if st.button("MASA ÖRTÜSÜ KAYDET", use_container_width=True, key="kaydet_masa_ortusu"):
        if st.session_state.masa_kayit_json is None:
            st.error("Önce hesaplama yapmalısın.")
        else:
            try:
                kayit_ekle(
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    masa_urun_adi,
                    "Masa Örtüsü",
                    st.session_state.masa_kayit_json,
                )
                st.success("Masa örtüsü raporu kaydedildi.")
            except Exception as e:
                st.error(f"Kayıt hatası: {e}")


# ----------------------------
# TAB 3 - KAYITLI RAPORLAR
# ----------------------------
with tab3:
    st.subheader("Kayıtlı Raporlar")
    df = kayitlari_getir()

    if df.empty:
        st.info("Henüz kayıt yok.")
    else:
        if "urun_tipi" not in df.columns:
            df["urun_tipi"] = "Minder"

        filtre = st.selectbox("Ürün tipi filtresi", ["Tümü", "Minder", "Masa Örtüsü"])
        if filtre != "Tümü":
            df = df[df["urun_tipi"] == filtre]

        if df.empty:
            st.info("Bu filtre için kayıt bulunamadı.")
        else:
            st.dataframe(df.drop(columns=["detay_json"]), use_container_width=True)

            secenekler = {
                f"#{row['id']} - {row['urun_tipi']} - {row['urun_adi']} - {row['tarih']}": int(row["id"])
                for _, row in df.iterrows()
            }

            secilen = st.selectbox("Detayını görmek istediğin kayıt", list(secenekler.keys()))
            secilen_id = secenekler[secilen]
            secilen_satir = df[df["id"] == secilen_id].iloc[0]

            if st.button("Kayıt detayını göster", use_container_width=True):
                try:
                    payload = json.loads(secilen_satir["detay_json"])

                    if "detay_df" in payload:
                        st.subheader("Detay")
                        st.dataframe(pd.DataFrame(payload["detay_df"]), use_container_width=True)

                    if "senaryo_df" in payload:
                        st.subheader("Senaryo Karşılaştırması")
                        senaryo_df = pd.DataFrame(payload["senaryo_df"])
                        st.dataframe(senaryo_df, use_container_width=True)
                        df_download_button(senario_df, "Senaryo tablosunu indir", "kayit_senaryo.xlsx")

                    if "ozet_df" in payload:
                        st.subheader("Özet")
                        ozet_df = pd.DataFrame(payload["ozet_df"])
                        st.dataframe(ozet_df, use_container_width=True)
                        df_download_button(ozet_df, "Özet tabloyu indir", "kayit_ozet.xlsx")

                except Exception as e:
                    st.error(f"Detay okuma hatası: {e}")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Seçili kaydı sil", use_container_width=True):
                    kayit_sil(secilen_id)
                    st.success("Kayıt silindi.")
                    st.rerun()
            with c2:
                if st.button("Tüm kayıtları sil", use_container_width=True):
                    tumunu_sil()
                    st.success("Tüm kayıtlar silindi.")
                    st.rerun()
