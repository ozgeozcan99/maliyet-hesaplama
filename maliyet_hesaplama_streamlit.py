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


def to_excel_bytes(df_dict):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in df_dict.items():
            if df is not None and not df.empty:
                df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
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
            data=to_excel_bytes({"Rapor": df}),
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
        "Tel SayÄ±sÄ± ÃÃ¶zgÃ¼": {"USD": tel_sayisi_cozgu, "TL": None},
        "Tel SayÄ±sÄ± AtkÄ±": {"USD": tel_sayisi_atki, "TL": None},
        "Punch Gramaj ÃÃ¶zgÃ¼": {"USD": punch_gramaj_cozgu, "TL": None},
        "Punch Gramaj AtkÄ±": {"USD": punch_gramaj_atki, "TL": None},
        "Punch Gramaj Toplam": {"USD": punch_gramaj_toplam, "TL": None},
        "MT TÃ¼l Gramaj ÃÃ¶zgÃ¼": {"USD": mt_tul_gramaj_cozgu, "TL": None},
        "MT TÃ¼l Gramaj AtkÄ±": {"USD": mt_tul_gramaj_atki, "TL": None},
        "MT TÃ¼l Gramaj Toplam": {"USD": mt_tul_gramaj_toplam, "TL": None},
        "Fireli MT TÃ¼l Gramaj ÃÃ¶zgÃ¼": {"USD": fireli_mt_tul_gramaj_cozgu, "TL": None},
        "Fireli MT TÃ¼l Gramaj AtkÄ±": {"USD": fireli_mt_tul_gramaj_atki, "TL": None},
        "Fireli MT TÃ¼l Gramaj Toplam": {"USD": fireli_mt_tul_gramaj_toplam, "TL": None},
        "Ä°plik Dolar Maliyeti Toplam": {"USD": iplik_dolar_maliyeti_toplam, "TL": None},
        "AtkÄ± ÃÃ¶zgÃ¼ TL Maliyeti Toplam": {"USD": None, "TL": atki_cozgu_tl_maliyet_toplam},
    }


def ham_bez_hesapla(iplik_dolar_maliyeti_toplam, atki_cozgu_tl_maliyet_toplam, alis_kuru, satis_kuru):
    atki_cozgu_usd_karsiligi = safe_div(atki_cozgu_tl_maliyet_toplam, alis_kuru)
    ham_bez_fiyati_usd = iplik_dolar_maliyeti_toplam + atki_cozgu_usd_karsiligi
    ham_bez_fiyati_tl = ham_bez_fiyati_usd * satis_kuru

    return {
        "Ham Bez FiyatÄ±": {"USD": ham_bez_fiyati_usd, "TL": ham_bez_fiyati_tl},
    }


def atki_maliyeti_hesapla(tezgah_devir, dakika, gun_saati, randiman, siklik, maliyet_tl):
    gunluk_mt = safe_div(((tezgah_devir * dakika * gun_saati * randiman) / siklik), 10000)
    karsiz_atki_maliyeti = safe_div(safe_div(maliyet_tl, gunluk_mt), siklik)

    return {
        "AtkÄ± GÃ¼nlÃ¼k MT": {"USD": gunluk_mt, "TL": None},
        "AtkÄ± KÃ¢rsÄ±z Maliyet": {"USD": karsiz_atki_maliyeti, "TL": None},
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
        "SatÄ±Å Toplam Maliyet": {"USD": toplam_maliyet_usd, "TL": toplam_maliyet_tl},
        "KÃ¢r": {"USD": kar_usd, "TL": kar_tl},
        "SatÄ±Å FiyatÄ±": {"USD": satis_fiyati_usd, "TL": satis_fiyati_tl},
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

    satis_fiyati_tl = satis["SatÄ±Å FiyatÄ±"]["TL"]
    toplam_maliyet_tl = satis["SatÄ±Å Toplam Maliyet"]["TL"]
    kar_tl = satis["KÃ¢r"]["TL"]

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
        "KumaÅ Sarfiyat": round(kumas_cift_kisilik_sarfiyat * adet, 4),
        "ÃrÃ¼n Sarfiyat": round(urun_sarfiyat * adet, 4),
        "Kesim TL": round(konf_kesim_tl * adet, 4),
        "Dikim TL": round(konfeksiyon_dikim_tl * adet, 4),
        "Paket TL": round(konf_paket_tl * adet, 4),
        "Aksesuar TL": round(aksesuar_tl * adet, 4),
        "Toplam Maliyet TL": round(toplam_maliyet_tl, 4),
        "SatÄ±Å FiyatÄ± TL": round(satis_fiyati_tl, 4),
        "KÃ¢r TL": round(kar_tl, 4),
        "KÃ¢r/Zarar TL": round(kar_zarar, 4),
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
# MASA ÃRTÃSÃ HESAPLAR
# ----------------------------
def masa_ortusu_tek_satir_hesapla(
    olcu_adi,
    en_cm,
    boy_cm,
    sarfiyat_m,
    alis_kuru,
    satis_kuru,
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
):
    kumas_fire_orani = pct(kumas_fire_yuzde)
    aksesuar_kdv_orani = pct(aksesuar_kdv_yuzde)
    aksesuar_fire_orani = pct(aksesuar_fire_yuzde)
    nakliye_kdv_orani = pct(nakliye_kdv_yuzde)
    kar_orani = pct(kar_orani_yuzde)

    kumas_maliyeti_tl = kumas_tl_metre * sarfiyat_m
    kumas_fire_tl = kumas_maliyeti_tl * kumas_fire_orani

    aksesuar_kdv_tl = aksesuar_tl * aksesuar_kdv_orani
    aksesuar_fire_tl = (aksesuar_tl + aksesuar_kdv_tl) * aksesuar_fire_orani
    aksesuar_toplam_tl = aksesuar_tl + aksesuar_kdv_tl + aksesuar_fire_tl

    nakliye_kdv_tl = nakliye_tl * nakliye_kdv_orani

    birim_maliyet_tl = (
        kumas_maliyeti_tl
        + kumas_fire_tl
        + kesim_tl
        + dikim_tl
        + paket_tl
        + aksesuar_toplam_tl
        + nakliye_tl
        + nakliye_kdv_tl
    )

    birim_kar_tl = birim_maliyet_tl * kar_orani
    satis_fiyati_tl = birim_maliyet_tl + birim_kar_tl
    marj_yuzde = safe_div(birim_kar_tl, satis_fiyati_tl) * 100 if satis_fiyati_tl > 0 else 0

    kumas_maliyeti_usd = safe_div(kumas_maliyeti_tl, alis_kuru)
    birim_maliyet_usd = safe_div(birim_maliyet_tl, alis_kuru)
    satis_fiyati_usd = safe_div(satis_fiyati_tl, satis_kuru)

    return {
        "ÃlÃ§Ã¼": olcu_adi,
        "En (cm)": en_cm,
        "Boy (cm)": boy_cm,
        "Sarfiyat (m)": round(sarfiyat_m, 4),
        "KumaÅ Maliyeti TL": round(kumas_maliyeti_tl, 4),
        "KumaÅ Fire TL": round(kumas_fire_tl, 4),
        "Aksesuar Toplam TL": round(aksesuar_toplam_tl, 4),
        "Kesim TL": round(kesim_tl, 4),
        "Dikim TL": round(dikim_tl, 4),
        "Paket TL": round(paket_tl, 4),
        "Nakliye TL": round(nakliye_tl, 4),
        "Birim Maliyet TL": round(birim_maliyet_tl, 4),
        "SatÄ±Å FiyatÄ± TL": round(satis_fiyati_tl, 4),
        "Birim KÃ¢r TL": round(birim_kar_tl, 4),
        "Marj %": round(marj_yuzde, 4),
        "KumaÅ Maliyeti USD": round(kumas_maliyeti_usd, 4),
        "Birim Maliyet USD": round(birim_maliyet_usd, 4),
        "SatÄ±Å FiyatÄ± USD": round(satis_fiyati_usd, 4),
    }


def masa_ortusu_toplu_hesapla(
    alis_kuru,
    satis_kuru,
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
):
    rows = []
    for olcu_adi, meta in TABLECLOTH_PRESETS.items():
        rows.append(
            masa_ortusu_tek_satir_hesapla(
                olcu_adi,
                meta["width_cm"],
                meta["height_cm"],
                meta["sarfiyat_m"],
                alis_kuru,
                satis_kuru,
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
            )
        )
    return pd.DataFrame(rows)


def masa_ortusu_sabitler_df(
    alis_kuru,
    satis_kuru,
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
):
    rows = [
        ["AlÄ±Å Kuru", alis_kuru],
        ["SatÄ±Å Kuru", satis_kuru],
        ["KumaÅ TL / metre", kumas_tl_metre],
        ["KumaÅ Fire %", kumas_fire_yuzde],
        ["Kesim TL", kesim_tl],
        ["Dikim TL", dikim_tl],
        ["Paket TL", paket_tl],
        ["Aksesuar TL", aksesuar_tl],
        ["Aksesuar KDV %", aksesuar_kdv_yuzde],
        ["Aksesuar Fire %", aksesuar_fire_yuzde],
        ["Nakliye TL", nakliye_tl],
        ["Nakliye KDV %", nakliye_kdv_yuzde],
        ["KÃ¢r OranÄ± %", kar_orani_yuzde],
    ]
    return pd.DataFrame(rows, columns=["Sabit Alan", "DeÄer"])


# ----------------------------
# SESSION
# ----------------------------
if "minder_detay_df" not in st.session_state:
    st.session_state.minder_detay_df = None
if "minder_senaryo_df" not in st.session_state:
    st.session_state.minder_senaryo_df = None
if "minder_kayit_json" not in st.session_state:
    st.session_state.minder_kayit_json = None

if "masa_sabitler_df" not in st.session_state:
    st.session_state.masa_sabitler_df = None
if "masa_toplu_df" not in st.session_state:
    st.session_state.masa_toplu_df = None
if "masa_kayit_json" not in st.session_state:
    st.session_state.masa_kayit_json = None


# ----------------------------
# UI
# ----------------------------
st.title("Maliyet Hesaplama ve Raporlama")

tab1, tab2, tab3 = st.tabs(["Minder", "Masa ÃrtÃ¼sÃ¼", "KayÄ±tlÄ± Raporlar"])

# ----------------------------
# TAB 1 - MINDER
# ----------------------------
with tab1:
    st.subheader("Genel Bilgiler")

    g1, g2 = st.columns(2)
    with g1:
        urun_adi = st.text_input("ÃrÃ¼n adÄ±", value="Minder", key="minder_urun_adi")
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
        alis_kuru = st.number_input("AlÄ±Å kuru", min_value=0.0, value=43.0, step=0.01, key="alis_kuru")
    with c2:
        satis_kuru = st.number_input("SatÄ±Å kuru", min_value=0.0, value=44.0, step=0.01, key="satis_kuru")

    with st.expander("VarsayÄ±lanlar / Sabitler", expanded=False):
        v1, v2, v3, v4 = st.columns(4)
        with v1:
            ip_no_cozgu = st.number_input("Ä°p no Ã§Ã¶zgÃ¼", value=35.4400472533963, step=0.000001, format="%.12f", key="ip_no_cozgu")
            tarak_end_cozgu = st.number_input("Tarak end Ã§Ã¶zgÃ¼", value=195.0, step=1.0, key="tarak_end_cozgu")
            ham_end_cozgu = st.number_input("Ham end Ã§Ã¶zgÃ¼", value=190.0, step=1.0, key="ham_end_cozgu")
            cozgu_atki_sayisi_cozgu = st.number_input("ÃÃ¶zgÃ¼ atkÄ± sayÄ±sÄ± Ã§Ã¶zgÃ¼", value=46.0, step=1.0, key="cozgu_atki_sayisi_cozgu")
            fire_cozgu_yuzde = st.number_input("Fire Ã§Ã¶zgÃ¼ %", value=7.0, step=0.1, key="fire_cozgu_yuzde")

        with v2:
            ip_no_atki = st.number_input("Ä°p no atkÄ±", value=6.0, step=1.0, key="ip_no_atki")
            tarak_end_atki = st.number_input("Tarak end atkÄ±", value=195.0, step=1.0, key="tarak_end_atki")
            ham_end_atki = st.number_input("Ham end atkÄ±", value=190.0, step=1.0, key="ham_end_atki")
            cozgu_atki_sayisi_atki = st.number_input("ÃÃ¶zgÃ¼ atkÄ± sayÄ±sÄ± atkÄ±", value=11.0, step=1.0, key="cozgu_atki_sayisi_atki")
            fire_atki_yuzde = st.number_input("Fire atkÄ± %", value=10.0, step=0.1, key="fire_atki_yuzde")

        with v3:
            tezgah_devir = st.number_input("Tezgah devir", value=350.0, step=1.0, key="tezgah_devir")
            dakika = st.number_input("Dakika", value=60.0, step=1.0, key="dakika")
            gun_saati = st.number_input("GÃ¼n saati", value=24.0, step=1.0, key="gun_saati")
            randiman = st.number_input("RandÄ±man", value=50.0, step=1.0, key="randiman")
            atki_maliyet_tl = st.number_input("AtkÄ± maliyet TL", value=2100.0, step=0.01, key="atki_maliyet_tl")

        with v4:
            hambez_kdv_yuzde = st.number_input("Hambez KDV %", value=10.0, step=0.1, key="hambez_kdv_yuzde")
            boyahane_cekme_yuzde = st.number_input("Boyahane Ã§ekme %", value=13.0, step=0.1, key="boyahane_cekme_yuzde")
            boyahane_kdv_yuzde = st.number_input("Boyahane KDV %", value=20.0, step=0.1, key="boyahane_kdv_yuzde")
            nakliye_sabit_tl = st.number_input("Dokuma nakliye sabit TL", value=0.60, step=0.01, key="nakliye_sabit_tl")
            kumas_cift_kisilik_sarfiyat = st.number_input("KumaÅ Ã§ift kiÅilik sarfiyat", value=0.25, step=0.01, key="kumas_cift_kisilik_sarfiyat")
            urun_sarfiyat = st.number_input("ÃrÃ¼n sarfiyat", value=1.0, step=0.01, key="urun_sarfiyat")
            toplam_fire_yuzde = st.number_input("Toplam fire %", value=8.0, step=0.1, key="toplam_fire_yuzde")
            aksesuar_kdv_yuzde = st.number_input("Aksesuar KDV %", value=20.0, step=0.1, key="aksesuar_kdv_yuzde")
            aksesuar_fire_yuzde = st.number_input("Aksesuar fire %", value=7.0, step=0.1, key="aksesuar_fire_yuzde")
            nakliye_kdv_yuzde = st.number_input("Nakliye KDV %", value=20.0, step=0.1, key="nakliye_kdv_yuzde")
            trendyol_komisyon_orani_yuzde = st.number_input("Trendyol komisyon %", value=21.0, step=0.1, key="trendyol_komisyon_orani_yuzde")
            punch_katsayi = st.number_input("Punch katsayÄ±sÄ±", value=1.693, step=0.001, format="%.3f", key="punch_katsayi")
            punch_toplam_bolen = st.number_input("Punch toplam bÃ¶lme deÄeri", value=10.0, step=1.0, key="punch_toplam_bolen")
            mt_bolen = st.number_input("MT tÃ¼l gramaj bÃ¶lme deÄeri", value=1000.0, step=1.0, key="mt_bolen")

    st.subheader("Dokuma Manuel GiriÅ")
    d1, d2 = st.columns(2)
    with d1:
        iplik_fiyati_usd_cozgu = st.number_input("ÃÃ¶zgÃ¼ iplik fiyatÄ± USD", min_value=0.0, value=1.69, step=0.01, key="iplik_fiyati_usd_cozgu")
        iplik_fiyati_usd_atki = st.number_input("AtkÄ± iplik fiyatÄ± USD", min_value=0.0, value=2.00, step=0.01, key="iplik_fiyati_usd_atki")
    with d2:
        cozgu_atki_fiyati_tl_cozgu = st.number_input("ÃÃ¶zgÃ¼ atkÄ± fiyatÄ± TL", min_value=0.0, value=1.30, step=0.01, key="cozgu_atki_fiyati_tl_cozgu")
        cozgu_atki_fiyati_tl_atki = st.number_input("AtkÄ± Ã§Ã¶zgÃ¼ fiyatÄ± TL", min_value=0.0, value=0.75, step=0.01, key="cozgu_atki_fiyati_tl_atki")

    st.subheader("Konfeksiyon Manuel GiriÅ")
    k1, k2, k3 = st.columns(3)
    with k1:
        urun_maliyeti_tl = st.number_input("ÃrÃ¼n maliyeti TL", min_value=0.0, value=23.00, step=0.01, key="urun_maliyeti_tl")
        konf_kesim_tl = st.number_input("Konfeksiyon kesim TL", min_value=0.0, value=0.00, step=0.01, key="konf_kesim_tl")
    with k2:
        konfeksiyon_dikim_tl = st.number_input("Konfeksiyon dikim TL", min_value=0.0, value=28.00, step=0.01, key="konfeksiyon_dikim_tl")
        konf_paket_tl = st.number_input("Konfeksiyon paket TL", min_value=0.0, value=0.00, step=0.01, key="konf_paket_tl")
    with k3:
        aksesuar_tl = st.number_input("Aksesuar TL", min_value=0.0, value=5.00, step=0.01, key="aksesuar_tl")
        nakliye_tl = st.number_input("SatÄ±Å tarafÄ± nakliye TL", min_value=0.0, value=0.00, step=0.01, key="nakliye_tl")
        kar_orani_yuzde = st.number_input("KÃ¢r oranÄ± %", min_value=0.0, value=60.0, step=0.1, key="kar_orani_yuzde")

    st.subheader("Son Rapor Sabitleri")
    r1, r2 = st.columns(2)
    with r1:
        panel_ucreti_sabit = st.number_input("Panel Ã¼creti KDV dahil", min_value=0.0, value=10.18, step=0.01, key="panel_ucreti_sabit")
    with r2:
        iade_orani_kargo_yuzde = st.number_input("Ä°ade oranÄ± (kargo Ã¼zerinden) %", min_value=0.0, value=10.0, step=0.1, key="iade_orani_kargo_yuzde")

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
            dokuma_taban["Ä°plik Dolar Maliyeti Toplam"]["USD"],
            dokuma_taban["AtkÄ± ÃÃ¶zgÃ¼ TL Maliyeti Toplam"]["TL"],
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
            ham_bez["Ham Bez FiyatÄ±"]["USD"],
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
        st.subheader("Dokuma DetaylarÄ±")
        st.dataframe(st.session_state.minder_detay_df, use_container_width=True)
        df_download_button(st.session_state.minder_detay_df, "Dokuma detaylarÄ±nÄ± Excel indir", "minder_dokuma_detaylari.xlsx")

    if st.session_state.minder_senaryo_df is not None:
        st.subheader("Senaryo KarÅÄ±laÅtÄ±rmasÄ±")
        st.dataframe(st.session_state.minder_senaryo_df, use_container_width=True)
        df_download_button(st.session_state.minder_senaryo_df, "Senaryo tablosunu Excel indir", "minder_senaryo_karsilastirmasi.xlsx")

    if st.button("MINDER KAYDET", use_container_width=True, key="kaydet_minder_hesap"):
        if st.session_state.minder_kayit_json is None:
            st.error("Ãnce hesaplama yapmalÄ±sÄ±n.")
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
                st.error(f"KayÄ±t hatasÄ±: {e}")


# ----------------------------
# TAB 2 - MASA ÃRTÃSÃ
# ----------------------------
with tab2:
    st.subheader("Masa ÃrtÃ¼sÃ¼ Genel Bilgiler")

    m1, m2 = st.columns(2)
    with m1:
        masa_urun_adi = st.text_input("ÃrÃ¼n adÄ±", value="Masa ÃrtÃ¼sÃ¼", key="masa_urun_adi")
    with m2:
        masa_not = st.text_input("Not", value="", key="masa_not")

    st.subheader("Kur Bilgileri")
    kur1, kur2 = st.columns(2)
    with kur1:
        masa_alis_kuru = st.number_input("AlÄ±Å kuru", min_value=0.0, value=43.0, step=0.01, key="masa_alis_kuru")
    with kur2:
        masa_satis_kuru = st.number_input("SatÄ±Å kuru", min_value=0.0, value=44.0, step=0.01, key="masa_satis_kuru")

    with st.expander("VarsayÄ±lanlar / Sabitler", expanded=True):
        t1, t2, t3 = st.columns(3)
        with t1:
            kumas_tl_metre = st.number_input("KumaÅ TL / metre", min_value=0.0, value=106.1004, step=0.01, key="kumas_tl_metre")
            kumas_fire_yuzde = st.number_input("KumaÅ fire %", min_value=0.0, value=4.0, step=0.1, key="kumas_fire_yuzde")
            kesim_tl = st.number_input("Kesim TL", min_value=0.0, value=0.0, step=0.01, key="masa_kesim_tl")
            dikim_tl = st.number_input("Dikim TL", min_value=0.0, value=50.0, step=0.01, key="masa_dikim_tl")
        with t2:
            paket_tl = st.number_input("Paket TL", min_value=0.0, value=0.0, step=0.01, key="masa_paket_tl")
            aksesuar_tl_masa = st.number_input("Aksesuar TL", min_value=0.0, value=17.0, step=0.01, key="masa_aksesuar_tl")
            aksesuar_kdv_yuzde_masa = st.number_input("Aksesuar KDV %", min_value=0.0, value=20.0, step=0.1, key="masa_aksesuar_kdv")
            aksesuar_fire_yuzde_masa = st.number_input("Aksesuar fire %", min_value=0.0, value=7.0, step=0.1, key="masa_aksesuar_fire")
        with t3:
            nakliye_tl_masa = st.number_input("Nakliye TL", min_value=0.0, value=0.0, step=0.01, key="masa_nakliye_tl")
            nakliye_kdv_yuzde_masa = st.number_input("Nakliye KDV %", min_value=0.0, value=20.0, step=0.1, key="masa_nakliye_kdv")
            kar_orani_yuzde_masa = st.number_input("KÃ¢r oranÄ± %", min_value=0.0, value=20.0, step=0.1, key="masa_kar_orani")

    st.info("Tek tek Ã¶lÃ§Ã¼ seÃ§mek yerine, tÃ¼m hazÄ±r Ã¶lÃ§Ã¼ler aÅaÄÄ±da toplu tablo halinde hesaplanÄ±r.")

    if st.button("TÃM ÃLÃÃLERÄ° HESAPLA", use_container_width=True):
        masa_sabitler = masa_ortusu_sabitler_df(
            masa_alis_kuru,
            masa_satis_kuru,
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
        )

        masa_toplu_df = masa_ortusu_toplu_hesapla(
            masa_alis_kuru,
            masa_satis_kuru,
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
        )

        st.session_state.masa_sabitler_df = masa_sabitler
        st.session_state.masa_toplu_df = masa_toplu_df

        payload = {
            "urun_tipi": "Masa ÃrtÃ¼sÃ¼",
            "not": masa_not,
            "sabitler_df": masa_sabitler.to_dict(orient="records"),
            "toplu_df": masa_toplu_df.to_dict(orient="records"),
        }
        st.session_state.masa_kayit_json = json.dumps(payload, ensure_ascii=False)

    if st.session_state.masa_sabitler_df is not None:
        st.subheader("KullanÄ±lan Sabit Alanlar")
        st.dataframe(st.session_state.masa_sabitler_df, use_container_width=True)

    if st.session_state.masa_toplu_df is not None:
        st.subheader("TÃ¼m ÃlÃ§Ã¼ler Ä°Ã§in HazÄ±r Maliyet ve Marj Tablosu")
        st.dataframe(st.session_state.masa_toplu_df, use_container_width=True)

        st.download_button(
            label="Masa Ã¶rtÃ¼sÃ¼ tÃ¼m Ã¶lÃ§Ã¼ler Excel indir",
            data=to_excel_bytes({
                "Sabitler": st.session_state.masa_sabitler_df,
                "Toplu Tablo": st.session_state.masa_toplu_df,
            }),
            file_name="masa_ortusu_tum_olculer_raporu.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    if st.button("MASA ÃRTÃSÃ KAYDET", use_container_width=True, key="kaydet_masa_ortusu"):
        if st.session_state.masa_kayit_json is None:
            st.error("Ãnce hesaplama yapmalÄ±sÄ±n.")
        else:
            try:
                kayit_ekle(
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    masa_urun_adi,
                    "Masa ÃrtÃ¼sÃ¼",
                    st.session_state.masa_kayit_json,
                )
                st.success("Masa Ã¶rtÃ¼sÃ¼ raporu kaydedildi.")
            except Exception as e:
                st.error(f"KayÄ±t hatasÄ±: {e}")


# ----------------------------
# TAB 3 - KAYITLI RAPORLAR
# ----------------------------
with tab3:
    st.subheader("KayÄ±tlÄ± Raporlar")
    df = kayitlari_getir()

    if df.empty:
        st.info("HenÃ¼z kayÄ±t yok.")
    else:
        if "urun_tipi" not in df.columns:
            df["urun_tipi"] = "Minder"

        filtre = st.selectbox("ÃrÃ¼n tipi filtresi", ["TÃ¼mÃ¼", "Minder", "Masa ÃrtÃ¼sÃ¼"])
        if filtre != "TÃ¼mÃ¼":
            df = df[df["urun_tipi"] == filtre]

        if df.empty:
            st.info("Bu filtre iÃ§in kayÄ±t bulunamadÄ±.")
        else:
            st.dataframe(df.drop(columns=["detay_json"]), use_container_width=True)

            secenekler = {
                f"#{row['id']} - {row['urun_tipi']} - {row['urun_adi']} - {row['tarih']}": int(row["id"])
                for _, row in df.iterrows()
            }

            secilen = st.selectbox("DetayÄ±nÄ± gÃ¶rmek istediÄin kayÄ±t", list(secenekler.keys()))
            secilen_id = secenekler[secilen]
            secilen_satir = df[df["id"] == secilen_id].iloc[0]

            if st.button("KayÄ±t detayÄ±nÄ± gÃ¶ster", use_container_width=True):
                try:
                    payload = json.loads(secilen_satir["detay_json"])

                    if "detay_df" in payload:
                        st.subheader("Detay")
                        st.dataframe(pd.DataFrame(payload["detay_df"]), use_container_width=True)

                    if "senaryo_df" in payload:
                        st.subheader("Senaryo KarÅÄ±laÅtÄ±rmasÄ±")
                        senaryo_df = pd.DataFrame(payload["senaryo_df"])
                        st.dataframe(senaryo_df, use_container_width=True)
                        df_download_button(senaryo_df, "Senaryo tablosunu indir", "kayit_senaryo.xlsx")

                    if "sabitler_df" in payload:
                        st.subheader("Sabit Alanlar")
                        sabitler_df = pd.DataFrame(payload["sabitler_df"])
                        st.dataframe(sabitler_df, use_container_width=True)

                    if "toplu_df" in payload:
                        st.subheader("Toplu ÃlÃ§Ã¼ Tablosu")
                        toplu_df = pd.DataFrame(payload["toplu_df"])
                        st.dataframe(toplu_df, use_container_width=True)
                        st.download_button(
                            label="Toplu tabloyu Excel indir",
                            data=to_excel_bytes({"Toplu Tablo": toplu_df}),
                            file_name="kayit_masa_ortusu_toplu_tablo.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )

                except Exception as e:
                    st.error(f"Detay okuma hatasÄ±: {e}")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("SeÃ§ili kaydÄ± sil", use_container_width=True):
                    kayit_sil(secilen_id)
                    st.success("KayÄ±t silindi.")
                    st.rerun()
            with c2:
                if st.button("TÃ¼m kayÄ±tlarÄ± sil", use_container_width=True):
                    tumunu_sil()
                    st.success("TÃ¼m kayÄ±tlar silindi.")
                    st.rerun()
