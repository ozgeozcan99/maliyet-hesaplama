import streamlit as st
import pandas as pd
import sqlite3
import json
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Maliyet Hesaplama Raporu", page_icon="📊", layout="wide")

DB_FILE = "maliyet_raporu_tekli_senaryolu.db"


# ----------------------------
# DATABASE
# ----------------------------
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


conn = get_connection()


def create_table():
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS maliyet_raporu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            urun_adi TEXT,
            urun_adedi REAL,
            stok_adedi REAL,
            alis_kuru REAL,
            satis_kuru REAL,
            psf REAL,
            trendyol_komisyon_orani REAL,
            kargo_ucreti REAL,
            toplam_maliyet_usd REAL,
            toplam_maliyet_tl REAL,
            kar_orani REAL,
            kar_usd REAL,
            kar_tl REAL,
            satis_fiyati_usd REAL,
            satis_fiyati_tl REAL,
            stok_ciro REAL,
            toplam_maliyet REAL,
            smm_stok REAL,
            trendyol_komisyon_tutari REAL,
            panel_ucreti REAL,
            iade_tutari REAL,
            gerceklesen_gider REAL,
            kazanc REAL,
            kar_zarar REAL,
            marj_yuzde REAL,
            konya_marj_yuzde REAL,
            detay_json TEXT
        )
        """
    )
    conn.commit()


def ensure_detay_json_column():
    cols = pd.read_sql_query("PRAGMA table_info(maliyet_raporu)", conn)
    if "detay_json" not in cols["name"].tolist():
        conn.execute("ALTER TABLE maliyet_raporu ADD COLUMN detay_json TEXT")
        conn.commit()


create_table()
ensure_detay_json_column()


def kayit_ekle(veri):
    conn.execute(
        """
        INSERT INTO maliyet_raporu (
            tarih, urun_adi, urun_adedi, stok_adedi,
            alis_kuru, satis_kuru, psf, trendyol_komisyon_orani,
            kargo_ucreti, toplam_maliyet_usd, toplam_maliyet_tl,
            kar_orani, kar_usd, kar_tl, satis_fiyati_usd, satis_fiyati_tl,
            stok_ciro, toplam_maliyet, smm_stok, trendyol_komisyon_tutari,
            panel_ucreti, iade_tutari, gerceklesen_gider, kazanc,
            kar_zarar, marj_yuzde, konya_marj_yuzde, detay_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        veri,
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


def pct_to_ratio(x):
    return x / 100.0


# ----------------------------
# HESAP BLOKLARI
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
    fire_cozgu = pct_to_ratio(fire_cozgu_yuzde)
    fire_atki = pct_to_ratio(fire_atki_yuzde)

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
        "tel_sayisi_cozgu": tel_sayisi_cozgu,
        "tel_sayisi_atki": tel_sayisi_atki,
        "punch_gramaj_cozgu": punch_gramaj_cozgu,
        "punch_gramaj_atki": punch_gramaj_atki,
        "punch_gramaj_toplam": punch_gramaj_toplam,
        "mt_tul_gramaj_cozgu": mt_tul_gramaj_cozgu,
        "mt_tul_gramaj_atki": mt_tul_gramaj_atki,
        "mt_tul_gramaj_toplam": mt_tul_gramaj_toplam,
        "fireli_mt_tul_gramaj_cozgu": fireli_mt_tul_gramaj_cozgu,
        "fireli_mt_tul_gramaj_atki": fireli_mt_tul_gramaj_atki,
        "fireli_mt_tul_gramaj_toplam": fireli_mt_tul_gramaj_toplam,
        "iplik_dolar_maliyeti_cozgu": iplik_dolar_maliyeti_cozgu,
        "iplik_dolar_maliyeti_atki": iplik_dolar_maliyeti_atki,
        "iplik_dolar_maliyeti_toplam": iplik_dolar_maliyeti_toplam,
        "atki_cozgu_tl_maliyet_cozgu": atki_cozgu_tl_maliyet_cozgu,
        "atki_cozgu_tl_maliyet_atki": atki_cozgu_tl_maliyet_atki,
        "atki_cozgu_tl_maliyet_toplam": atki_cozgu_tl_maliyet_toplam,
    }


def ham_bez_hesapla(iplik_dolar_maliyeti_toplam, atki_cozgu_tl_maliyet_toplam, alis_kuru, satis_kuru):
    atki_cozgu_usd_karsiligi = safe_div(atki_cozgu_tl_maliyet_toplam, alis_kuru)
    ham_bez_fiyati_usd = iplik_dolar_maliyeti_toplam + atki_cozgu_usd_karsiligi
    ham_bez_fiyati_tl = ham_bez_fiyati_usd * satis_kuru

    return {
        "atki_cozgu_usd_karsiligi": atki_cozgu_usd_karsiligi,
        "ham_bez_fiyati_usd": ham_bez_fiyati_usd,
        "ham_bez_fiyati_tl": ham_bez_fiyati_tl,
    }


def atki_maliyeti_hesapla(
    tezgah_devir,
    dakika,
    gun_saati,
    randiman,
    siklik,
    calisan_tezgah,
    maliyet_tl,
):
    gunluk_mt = safe_div(((tezgah_devir * dakika * gun_saati * randiman) / siklik), 10000)
    alinmasi_gereken_uretim = gunluk_mt
    karsiz_atki_maliyeti = safe_div(safe_div(maliyet_tl, alinmasi_gereken_uretim), siklik)

    return {
        "calisan_tezgah": calisan_tezgah,
        "gunluk_mt": gunluk_mt,
        "alinmasi_gereken_uretim": alinmasi_gereken_uretim,
        "karsiz_atki_maliyeti": karsiz_atki_maliyeti,
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
    hambez_kdv_orani = pct_to_ratio(hambez_kdv_yuzde)
    boyahane_cekme_orani = pct_to_ratio(boyahane_cekme_yuzde)
    boyahane_kdv_orani = pct_to_ratio(boyahane_kdv_yuzde)

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
        "ham_bez_maliyeti_usd": ham_bez_maliyeti_usd,
        "ham_bez_maliyeti_tl": ham_bez_maliyeti_tl,
        "ham_bez_kdv_usd": ham_bez_kdv_usd,
        "ham_bez_kdv_tl": ham_bez_kdv_tl,
        "boyahane_cekme_usd": boyahane_cekme_usd,
        "boyahane_cekme_tl": boyahane_cekme_tl,
        "boyahane_maliyet_usd": boyahane_maliyet_usd,
        "boyahane_maliyet_tl": boyahane_maliyet_tl,
        "boyahane_kdv_usd": boyahane_kdv_usd,
        "boyahane_kdv_tl": boyahane_kdv_tl,
        "nakliye_usd": nakliye_usd,
        "nakliye_tl": nakliye_tl,
        "dokuma_toplam_maliyet_kdvli_usd": dokuma_toplam_maliyet_kdvli_usd,
        "dokuma_toplam_maliyet_kdvli_tl": dokuma_toplam_maliyet_kdvli_tl,
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
    toplam_fire_orani = pct_to_ratio(toplam_fire_yuzde)
    aksesuar_kdv_orani = pct_to_ratio(aksesuar_kdv_yuzde)
    aksesuar_fire_orani = pct_to_ratio(aksesuar_fire_yuzde)
    nakliye_kdv_orani = pct_to_ratio(nakliye_kdv_yuzde)
    kar_orani = pct_to_ratio(kar_orani_yuzde)

    kumas_sarfiyat_gercek = kumas_cift_kisilik_sarfiyat * urun_sarfiyat

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
        "kumas_sarfiyat_gercek": kumas_sarfiyat_gercek,
        "kumas_maliyeti_usd": kumas_maliyeti_usd,
        "kumas_maliyeti_tl": kumas_maliyeti_tl,
        "urun_maliyeti_usd": urun_maliyeti_usd,
        "urun_maliyet_toplam_usd": urun_maliyet_toplam_usd,
        "urun_maliyet_toplam_tl": urun_maliyet_toplam_tl,
        "toplam_fire_usd": toplam_fire_usd,
        "toplam_fire_tl": toplam_fire_tl,
        "konf_kesim_usd": konf_kesim_usd,
        "konf_kesim_tl": konf_kesim_tl,
        "konf_dikim_usd": konf_dikim_usd,
        "konf_dikim_tl": konfeksiyon_dikim_tl,
        "konf_paket_usd": konf_paket_usd,
        "konf_paket_tl": konf_paket_tl,
        "aksesuar_usd": aksesuar_usd,
        "aksesuar_tl": aksesuar_tl,
        "aksesuar_kdv_usd": aksesuar_kdv_usd,
        "aksesuar_kdv_tl": aksesuar_kdv_tl,
        "aksesuar_fire_usd": aksesuar_fire_usd,
        "aksesuar_fire_tl": aksesuar_fire_tl,
        "nakliye_usd": nakliye_usd,
        "nakliye_tl": nakliye_tl,
        "nakliye_kdv_usd": nakliye_kdv_usd,
        "nakliye_kdv_tl": nakliye_kdv_tl,
        "toplam_maliyet_usd": toplam_maliyet_usd,
        "toplam_maliyet_tl": toplam_maliyet_tl,
        "kar_usd": kar_usd,
        "kar_tl": kar_tl,
        "satis_fiyati_usd": satis_fiyati_usd,
        "satis_fiyati_tl": satis_fiyati_tl,
    }


def son_rapor_tablosu_hesapla(
    urun_adi,
    urun_adedi,
    stok_adedi,
    maliyet_kdvli_tl,
    psf,
    trendyol_komisyon_orani_yuzde,
    kargo_ucreti_kdv_dahil,
    panel_ucreti_sabit,
    iade_orani_kargo_yuzde,
):
    trendyol_komisyon_orani = trendyol_komisyon_orani_yuzde / 100
    iade_orani = iade_orani_kargo_yuzde / 100

    trendyol_komisyon_tutari = psf * trendyol_komisyon_orani
    panel_ucreti = panel_ucreti_sabit
    iade_tutari = kargo_ucreti_kdv_dahil * iade_orani

    gerceklesen_gider = (
        kargo_ucreti_kdv_dahil
        + trendyol_komisyon_tutari
        + panel_ucreti
        + iade_tutari
    )

    kazanc = psf - gerceklesen_gider
    kar_zarar = kazanc - maliyet_kdvli_tl

    toplam_maliyet = maliyet_kdvli_tl * stok_adedi
    smm_stok = stok_adedi * (
        maliyet_kdvli_tl
        + kargo_ucreti_kdv_dahil
        + trendyol_komisyon_tutari
        + panel_ucreti
        + iade_tutari
    )
    stok_ciro = stok_adedi * psf

    marj = 1 - (smm_stok / stok_ciro) if stok_ciro > 0 else 0
    konya_marj = (kar_zarar / maliyet_kdvli_tl) if maliyet_kdvli_tl > 0 else 0

    return {
        "urun_adi": urun_adi,
        "urun_adedi": urun_adedi,
        "stok_adedi": stok_adedi,
        "maliyet_kdvli_tl": maliyet_kdvli_tl,
        "psf": psf,
        "trendyol_komisyon_orani_yuzde": trendyol_komisyon_orani_yuzde,
        "trendyol_komisyon_tutari": trendyol_komisyon_tutari,
        "kargo_ucreti_kdv_dahil": kargo_ucreti_kdv_dahil,
        "panel_ucreti": panel_ucreti,
        "iade_orani_kargo_yuzde": iade_orani_kargo_yuzde,
        "iade_tutari": iade_tutari,
        "gerceklesen_gider": gerceklesen_gider,
        "kazanc": kazanc,
        "kar_zarar": kar_zarar,
        "toplam_maliyet": toplam_maliyet,
        "smm_stok": smm_stok,
        "stok_ciro": stok_ciro,
        "marj_yuzde": marj * 100,
        "konya_marj_yuzde": konya_marj * 100,
    }


def senaryo_hesapla(
    adet,
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
    psf,
    trendyol_komisyon_orani_yuzde,
    kargo_ucreti_kdv_dahil,
    panel_ucreti_sabit,
    iade_orani_kargo_yuzde,
):
    satis = satis_maliyet_ve_kar_hesapla(
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
        kumas_cift_kisilik_sarfiyat * adet,
        urun_sarfiyat * adet,
        toplam_fire_yuzde,
        aksesuar_kdv_yuzde,
        aksesuar_fire_yuzde,
        nakliye_kdv_yuzde,
    )

    rapor = son_rapor_tablosu_hesapla(
        urun_adi=f"{adet} Adet Senaryo",
        urun_adedi=adet,
        stok_adedi=1,
        maliyet_kdvli_tl=satis["satis_fiyati_tl"],
        psf=psf,
        trendyol_komisyon_orani_yuzde=trendyol_komisyon_orani_yuzde,
        kargo_ucreti_kdv_dahil=kargo_ucreti_kdv_dahil,
        panel_ucreti_sabit=panel_ucreti_sabit,
        iade_orani_kargo_yuzde=iade_orani_kargo_yuzde,
    )

    return {
        "adet": adet,
        "kumas_sarfiyat": kumas_cift_kisilik_sarfiyat * adet,
        "urun_sarfiyat": urun_sarfiyat * adet,
        "toplam_maliyet_tl": satis["toplam_maliyet_tl"],
        "satis_fiyati_tl": satis["satis_fiyati_tl"],
        "kar_tl": satis["kar_tl"],
        "kar_zarar": rapor["kar_zarar"],
        "marj_yuzde": rapor["marj_yuzde"],
        "konya_marj_yuzde": rapor["konya_marj_yuzde"],
    }


# ----------------------------
# SESSION
# ----------------------------
if "sonuc_hazir" not in st.session_state:
    st.session_state.sonuc_hazir = False
if "kayit_verisi" not in st.session_state:
    st.session_state.kayit_verisi = None
if "detay_df" not in st.session_state:
    st.session_state.detay_df = None
if "final_df" not in st.session_state:
    st.session_state.final_df = None
if "senaryo_df" not in st.session_state:
    st.session_state.senaryo_df = None
if "ozet" not in st.session_state:
    st.session_state.ozet = None


# ----------------------------
# UI
# ----------------------------
st.title("Maliyet Hesaplama ve Raporlama - TEK Lİ")

tab1, tab2 = st.tabs(["Yeni Hesap", "Kayıtlı Raporlar"])

with tab1:
    st.subheader("1) Genel Bilgiler")

    g1, g2, g3, g4, g5 = st.columns(5)
    with g1:
        urun_adi = st.text_input("Ürün adı", value="Minder")
    with g2:
        urun_adedi = st.number_input("Ürün adedi", min_value=0.0, value=1.0, step=1.0)
    with g3:
        stok_adedi = st.number_input("Stok adedi", min_value=0.0, value=100.0, step=1.0)
    with g4:
        psf = st.number_input("PSF", min_value=0.0, value=400.0, step=0.01)
    with g5:
        maksimum_adet_senaryosu = st.number_input("Maksimum adet senaryosu", min_value=1, value=4, step=1)

    st.subheader("2) Kur Bilgileri")
    c1, c2 = st.columns(2)
    with c1:
        alis_kuru = st.number_input("Alış kuru", min_value=0.0, value=43.0, step=0.01)
    with c2:
        satis_kuru = st.number_input("Satış kuru", min_value=0.0, value=44.0, step=0.01)

    with st.expander("Varsayılanlar / Sabitler", expanded=False):
        st.caption("TEK Lİ sheet’e göre düzenlendi.")

        v1, v2, v3, v4 = st.columns(4)
        with v1:
            ip_no_cozgu = st.number_input("İp no çözgü", value=35.4400472533963, step=0.000001, format="%.12f")
            tarak_end_cozgu = st.number_input("Tarak end çözgü", value=195.0, step=1.0)
            ham_end_cozgu = st.number_input("Ham end çözgü", value=190.0, step=1.0)
            cozgu_atki_sayisi_cozgu = st.number_input("Çözgü atkı sayısı çözgü", value=46.0, step=1.0)
            fire_cozgu_yuzde = st.number_input("Fire çözgü %", value=7.0, step=0.1)

        with v2:
            ip_no_atki = st.number_input("İp no atkı", value=6.0, step=1.0)
            tarak_end_atki = st.number_input("Tarak end atkı", value=195.0, step=1.0)
            ham_end_atki = st.number_input("Ham end atkı", value=190.0, step=1.0)
            cozgu_atki_sayisi_atki = st.number_input("Çözgü atkı sayısı atkı", value=11.0, step=1.0)
            fire_atki_yuzde = st.number_input("Fire atkı %", value=10.0, step=0.1)

        with v3:
            tezgah_devir = st.number_input("Tezgah devir", value=350.0, step=1.0)
            dakika = st.number_input("Dakika", value=60.0, step=1.0)
            gun_saati = st.number_input("Gün saati", value=24.0, step=1.0)
            randiman = st.number_input("Randıman", value=50.0, step=1.0)
            calisan_tezgah = st.number_input("Çalışan tezgah", value=1.0, step=1.0)
            atki_maliyet_tl = st.number_input("Atkı maliyet TL", value=2100.0, step=0.01)

        with v4:
            hambez_kdv_yuzde = st.number_input("Hambez KDV %", value=10.0, step=0.1)
            boyahane_cekme_yuzde = st.number_input("Boyahane çekme %", value=13.0, step=0.1)
            boyahane_kdv_yuzde = st.number_input("Boyahane KDV %", value=20.0, step=0.1)
            nakliye_sabit_tl = st.number_input("Dokuma nakliye sabit TL", value=0.60, step=0.01)
            kumas_cift_kisilik_sarfiyat = st.number_input("Kumaş çift kişilik sarfiyat", value=0.25, step=0.01)
            urun_sarfiyat = st.number_input("Ürün sarfiyat", value=1.0, step=0.01)
            toplam_fire_yuzde = st.number_input("Toplam fire %", value=8.0, step=0.1)
            aksesuar_kdv_yuzde = st.number_input("Aksesuar KDV %", value=20.0, step=0.1)
            aksesuar_fire_yuzde = st.number_input("Aksesuar fire %", value=7.0, step=0.1)
            nakliye_kdv_yuzde = st.number_input("Nakliye KDV %", value=20.0, step=0.1)
            trendyol_komisyon_orani_yuzde = st.number_input("Trendyol komisyon %", value=21.0, step=0.1)
            kargo_ucreti_kdv_dahil = st.number_input("Kargo ücreti KDV dahil", value=93.0, step=0.01)
            punch_katsayi = st.number_input("Punch katsayısı", value=1.693, step=0.001, format="%.3f")
            punch_toplam_bolen = st.number_input("Punch toplam bölme değeri", value=10.0, step=1.0)
            mt_bolen = st.number_input("MT tül gramaj bölme değeri", value=1000.0, step=1.0)

    st.subheader("3) Manuel Giriş Alanları")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        iplik_fiyati_usd_cozgu = st.number_input("Çözgü iplik fiyatı USD", min_value=0.0, value=1.69, step=0.01)
        cozgu_atki_fiyati_tl_cozgu = st.number_input("Çözgü atkı fiyatı TL", min_value=0.0, value=1.30, step=0.01)
        boyahane_fiyati_pike_usd = st.number_input("Boyahane fiyatı pike USD", min_value=0.0, value=1.00, step=0.01)

    with m2:
        iplik_fiyati_usd_atki = st.number_input("Atkı iplik fiyatı USD", min_value=0.0, value=2.00, step=0.01)
        cozgu_atki_fiyati_tl_atki = st.number_input("Atkı çözgü fiyatı TL", min_value=0.0, value=0.75, step=0.01)
        urun_maliyeti_tl = st.number_input("Ürün maliyeti TL", min_value=0.0, value=23.00, step=0.01)

    with m3:
        konfeksiyon_dikim_tl = st.number_input("Konfeksiyon dikim TL", min_value=0.0, value=28.00, step=0.01)
        konf_kesim_tl = st.number_input("Konfeksiyon kesim TL", min_value=0.0, value=0.00, step=0.01)
        konf_paket_tl = st.number_input("Konfeksiyon paket TL", min_value=0.0, value=0.00, step=0.01)

    with m4:
        aksesuar_tl = st.number_input("Aksesuar TL", min_value=0.0, value=5.00, step=0.01)
        nakliye_tl = st.number_input("Satış tarafı nakliye TL", min_value=0.0, value=0.00, step=0.01)
        kar_orani_yuzde = st.number_input("Kâr oranı %", min_value=0.0, value=60.0, step=0.1)

    st.subheader("4) Son Rapor Sabitleri")
    r1, r2 = st.columns(2)
    with r1:
        panel_ucreti_sabit = st.number_input("Panel ücreti KDV dahil", min_value=0.0, value=10.18, step=0.01)
    with r2:
        iade_orani_kargo_yuzde = st.number_input("İade oranı (kargo üzerinden) %", min_value=0.0, value=10.0, step=0.1)

    if st.button("HESAPLA", use_container_width=True):
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
            dokuma_taban["iplik_dolar_maliyeti_toplam"],
            dokuma_taban["atki_cozgu_tl_maliyet_toplam"],
            alis_kuru,
            satis_kuru,
        )

        atki_bilgisi = atki_maliyeti_hesapla(
            tezgah_devir,
            dakika,
            gun_saati,
            randiman,
            cozgu_atki_sayisi_atki,
            calisan_tezgah,
            atki_maliyet_tl,
        )

        dokuma_toplam = dokuma_toplam_maliyet_hesapla(
            ham_bez["ham_bez_fiyati_usd"],
            alis_kuru,
            satis_kuru,
            boyahane_fiyati_pike_usd,
            hambez_kdv_yuzde,
            boyahane_cekme_yuzde,
            boyahane_kdv_yuzde,
            nakliye_sabit_tl,
        )

        satis_maliyet = satis_maliyet_ve_kar_hesapla(
            dokuma_toplam["dokuma_toplam_maliyet_kdvli_usd"],
            dokuma_toplam["dokuma_toplam_maliyet_kdvli_tl"],
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
        )

        son_rapor = son_rapor_tablosu_hesapla(
            urun_adi,
            urun_adedi,
            stok_adedi,
            satis_maliyet["satis_fiyati_tl"],
            psf,
            trendyol_komisyon_orani_yuzde,
            kargo_ucreti_kdv_dahil,
            panel_ucreti_sabit,
            iade_orani_kargo_yuzde,
        )

        senaryo_listesi = []
        for adet in range(1, maksimum_adet_senaryosu + 1):
            senaryo_listesi.append(
                senaryo_hesapla(
                    adet=adet,
                    dokuma_toplam_usd=dokuma_toplam["dokuma_toplam_maliyet_kdvli_usd"],
                    dokuma_toplam_tl=dokuma_toplam["dokuma_toplam_maliyet_kdvli_tl"],
                    alis_kuru=alis_kuru,
                    urun_maliyeti_tl=urun_maliyeti_tl,
                    konfeksiyon_dikim_tl=konfeksiyon_dikim_tl,
                    konf_kesim_tl=konf_kesim_tl,
                    konf_paket_tl=konf_paket_tl,
                    aksesuar_tl=aksesuar_tl,
                    nakliye_tl=nakliye_tl,
                    kar_orani_yuzde=kar_orani_yuzde,
                    kumas_cift_kisilik_sarfiyat=kumas_cift_kisilik_sarfiyat,
                    urun_sarfiyat=urun_sarfiyat,
                    toplam_fire_yuzde=toplam_fire_yuzde,
                    aksesuar_kdv_yuzde=aksesuar_kdv_yuzde,
                    aksesuar_fire_yuzde=aksesuar_fire_yuzde,
                    nakliye_kdv_yuzde=nakliye_kdv_yuzde,
                    psf=psf,
                    trendyol_komisyon_orani_yuzde=trendyol_komisyon_orani_yuzde,
                    kargo_ucreti_kdv_dahil=kargo_ucreti_kdv_dahil,
                    panel_ucreti_sabit=panel_ucreti_sabit,
                    iade_orani_kargo_yuzde=iade_orani_kargo_yuzde,
                )
            )

        senaryo_df = pd.DataFrame(senaryo_listesi)

        detay_df = pd.DataFrame(
            [
                ["Tel Sayısı Çözgü", dokuma_taban["tel_sayisi_cozgu"], None],
                ["Tel Sayısı Atkı", dokuma_taban["tel_sayisi_atki"], None],
                ["Punch Gramaj Çözgü", dokuma_taban["punch_gramaj_cozgu"], None],
                ["Punch Gramaj Atkı", dokuma_taban["punch_gramaj_atki"], None],
                ["Punch Gramaj Toplam", dokuma_taban["punch_gramaj_toplam"], None],
                ["MT Tül Gramaj Çözgü", dokuma_taban["mt_tul_gramaj_cozgu"], None],
                ["MT Tül Gramaj Atkı", dokuma_taban["mt_tul_gramaj_atki"], None],
                ["MT Tül Gramaj Toplam", dokuma_taban["mt_tul_gramaj_toplam"], None],
                ["Fireli MT Tül Gramaj Çözgü", dokuma_taban["fireli_mt_tul_gramaj_cozgu"], None],
                ["Fireli MT Tül Gramaj Atkı", dokuma_taban["fireli_mt_tul_gramaj_atki"], None],
                ["Fireli MT Tül Gramaj Toplam", dokuma_taban["fireli_mt_tul_gramaj_toplam"], None],
                ["İplik Dolar Maliyeti Toplam", dokuma_taban["iplik_dolar_maliyeti_toplam"], None],
                ["Atkı Çözgü TL Maliyeti Toplam", None, dokuma_taban["atki_cozgu_tl_maliyet_toplam"]],
                ["Ham Bez Fiyatı", ham_bez["ham_bez_fiyati_usd"], ham_bez["ham_bez_fiyati_tl"]],
                ["Atkı Günlük MT", atki_bilgisi["gunluk_mt"], None],
                ["Atkı Kârsız Maliyet", atki_bilgisi["karsiz_atki_maliyeti"], None],
                ["Dokuma Toplam Maliyet KDV'li", dokuma_toplam["dokuma_toplam_maliyet_kdvli_usd"], dokuma_toplam["dokuma_toplam_maliyet_kdvli_tl"]],
                ["Satış Kumaş Maliyeti", satis_maliyet["kumas_maliyeti_usd"], satis_maliyet["kumas_maliyeti_tl"]],
                ["Ürün Maliyeti Toplam", satis_maliyet["urun_maliyet_toplam_usd"], satis_maliyet["urun_maliyet_toplam_tl"]],
                ["Toplam Fire", satis_maliyet["toplam_fire_usd"], satis_maliyet["toplam_fire_tl"]],
                ["Konfeksiyon Kesim", satis_maliyet["konf_kesim_usd"], satis_maliyet["konf_kesim_tl"]],
                ["Konfeksiyon Dikim", satis_maliyet["konf_dikim_usd"], satis_maliyet["konf_dikim_tl"]],
                ["Konfeksiyon Paket", satis_maliyet["konf_paket_usd"], satis_maliyet["konf_paket_tl"]],
                ["Aksesuar", satis_maliyet["aksesuar_usd"], satis_maliyet["aksesuar_tl"]],
                ["Aksesuar KDV", satis_maliyet["aksesuar_kdv_usd"], satis_maliyet["aksesuar_kdv_tl"]],
                ["Aksesuar Fire", satis_maliyet["aksesuar_fire_usd"], satis_maliyet["aksesuar_fire_tl"]],
                ["Nakliye", satis_maliyet["nakliye_usd"], satis_maliyet["nakliye_tl"]],
                ["Nakliye KDV", satis_maliyet["nakliye_kdv_usd"], satis_maliyet["nakliye_kdv_tl"]],
                ["Satış Toplam Maliyet KDV'li", satis_maliyet["toplam_maliyet_usd"], satis_maliyet["toplam_maliyet_tl"]],
                ["Kâr", satis_maliyet["kar_usd"], satis_maliyet["kar_tl"]],
                ["Satış Fiyatı", satis_maliyet["satis_fiyati_usd"], satis_maliyet["satis_fiyati_tl"]],
            ],
            columns=["Kalem", "USD / Değer", "TL"],
        )

        final_df = pd.DataFrame([son_rapor])

        detay_payload = {
            "detay_df": detay_df.to_dict(orient="records"),
            "final_df": final_df.to_dict(orient="records"),
            "senaryo_df": senaryo_df.to_dict(orient="records"),
        }

        st.session_state.sonuc_hazir = True
        st.session_state.detay_df = detay_df
        st.session_state.final_df = final_df
        st.session_state.senaryo_df = senaryo_df
        st.session_state.ozet = {
            "toplam_maliyet_usd": satis_maliyet["toplam_maliyet_usd"],
            "toplam_maliyet_tl": satis_maliyet["toplam_maliyet_tl"],
            "satis_fiyati_usd": satis_maliyet["satis_fiyati_usd"],
            "satis_fiyati_tl": satis_maliyet["satis_fiyati_tl"],
            "stok_ciro": son_rapor["stok_ciro"],
            "kar_zarar": son_rapor["kar_zarar"],
            "marj_yuzde": son_rapor["marj_yuzde"],
            "konya_marj_yuzde": son_rapor["konya_marj_yuzde"],
        }

        st.session_state.kayit_verisi = (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            urun_adi,
            float(urun_adedi),
            float(stok_adedi),
            float(alis_kuru),
            float(satis_kuru),
            float(psf),
            float(trendyol_komisyon_orani_yuzde),
            float(kargo_ucreti_kdv_dahil),
            float(satis_maliyet["toplam_maliyet_usd"]),
            float(satis_maliyet["toplam_maliyet_tl"]),
            float(kar_orani_yuzde),
            float(satis_maliyet["kar_usd"]),
            float(satis_maliyet["kar_tl"]),
            float(satis_maliyet["satis_fiyati_usd"]),
            float(satis_maliyet["satis_fiyati_tl"]),
            float(son_rapor["stok_ciro"]),
            float(son_rapor["toplam_maliyet"]),
            float(son_rapor["smm_stok"]),
            float(son_rapor["trendyol_komisyon_tutari"]),
            float(son_rapor["panel_ucreti"]),
            float(son_rapor["iade_tutari"]),
            float(son_rapor["gerceklesen_gider"]),
            float(son_rapor["kazanc"]),
            float(son_rapor["kar_zarar"]),
            float(son_rapor["marj_yuzde"]),
            float(son_rapor["konya_marj_yuzde"]),
            json.dumps(detay_payload, ensure_ascii=False),
        )

    if st.session_state.sonuc_hazir and st.session_state.ozet is not None:
        st.success("Hesaplama tamamlandı.")

        ozet = st.session_state.ozet

        st.subheader("Özet Sonuçlar")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Toplam Maliyet USD", f"{ozet['toplam_maliyet_usd']:,.6f}")
        s2.metric("Toplam Maliyet TL", f"{ozet['toplam_maliyet_tl']:,.6f}")
        s3.metric("Satış Fiyatı USD", f"{ozet['satis_fiyati_usd']:,.6f}")
        s4.metric("Satış Fiyatı TL", f"{ozet['satis_fiyati_tl']:,.6f}")

        st.subheader("Marj Sonuçları")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Stok Ciro", f"{ozet['stok_ciro']:,.2f} TL")
        m2.metric("Kâr / Zarar", f"{ozet['kar_zarar']:,.6f} TL")
        m3.metric("Marj", f"%{ozet['marj_yuzde']:,.6f}")
        m4.metric("Konya Marj", f"%{ozet['konya_marj_yuzde']:,.6f}")

        st.subheader("Detay Tablolar")
        st.dataframe(st.session_state.detay_df, use_container_width=True)

        st.subheader("Adet Senaryoları")
        st.dataframe(st.session_state.senaryo_df, use_container_width=True)

        st.subheader("Son Rapor Tablosu")
        st.dataframe(st.session_state.final_df, use_container_width=True)

        if st.button("KAYDET", use_container_width=True):
            if st.session_state.kayit_verisi is not None:
                kayit_ekle(st.session_state.kayit_verisi)
                st.success("Rapor kaydedildi.")
            else:
                st.error("Önce hesaplama yapmalısın.")

with tab2:
    st.subheader("Kayıtlı Raporlar")
    df = kayitlari_getir()

    if df.empty:
        st.info("Henüz kayıt yok.")
    else:
        filtre = st.text_input("Ürün adına göre ara")
        if filtre:
            df = df[df["urun_adi"].str.contains(filtre, case=False, na=False)]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Toplam Kayıt", len(df))

        toplam_satis = df["satis_fiyati_tl"].sum() if "satis_fiyati_tl" in df.columns else 0
        toplam_kar = df["kar_tl"].sum() if "kar_tl" in df.columns else 0
        ortalama_marj = df["marj_yuzde"].mean() if "marj_yuzde" in df.columns else 0

        k2.metric("Toplam Satış Fiyatı TL", f"{toplam_satis:,.2f}")
        k3.metric("Toplam Kâr TL", f"{toplam_kar:,.2f}")
        k4.metric("Ortalama Marj", f"%{ortalama_marj:,.2f}")

        st.dataframe(df.drop(columns=["detay_json"]) if "detay_json" in df.columns else df, use_container_width=True)

        csv_data = df.to_csv(index=False).encode("utf-8-sig")
        excel_data = to_excel_bytes(df)

        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "CSV indir",
                data=csv_data,
                file_name="maliyet_raporu.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with d2:
            st.download_button(
                "Excel indir",
                data=excel_data,
                file_name="maliyet_raporu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        secenekler = {
            f"#{row['id']} - {row['urun_adi']} - {row['tarih']}": int(row["id"])
            for _, row in df.iterrows()
        }

        secilen = st.selectbox("Detayını görmek / silmek istediğin kayıt", list(secenekler.keys()))
        secilen_id = secenekler[secilen]
        secilen_satir = df[df["id"] == secilen_id].iloc[0]

        if st.button("Kayıt detayını göster", use_container_width=True):
            st.subheader("Kayıt Özeti")
            st.dataframe(pd.DataFrame([secilen_satir]).drop(columns=["detay_json"]) if "detay_json" in secilen_satir.index else pd.DataFrame([secilen_satir]), use_container_width=True)

            if "detay_json" in secilen_satir.index and pd.notna(secilen_satir["detay_json"]):
                try:
                    payload = json.loads(secilen_satir["detay_json"])

                    if "detay_df" in payload:
                        st.subheader("Detay Tablolar")
                        st.dataframe(pd.DataFrame(payload["detay_df"]), use_container_width=True)

                    if "senaryo_df" in payload:
                        st.subheader("Adet Senaryoları")
                        st.dataframe(pd.DataFrame(payload["senaryo_df"]), use_container_width=True)

                    if "final_df" in payload:
                        st.subheader("Son Rapor Tablosu")
                        st.dataframe(pd.DataFrame(payload["final_df"]), use_container_width=True)

                except Exception:
                    st.warning("Bu kayıt eski formatta olduğu için detay gösterilemiyor.")

        if st.button("Seçili kaydı sil"):
            kayit_sil(secilen_id)
            st.success("Kayıt silindi.")
            st.rerun()

        if st.button("Tüm kayıtları sil"):
            tumunu_sil()
            st.success("Tüm kayıtlar silindi.")
            st.rerun()
