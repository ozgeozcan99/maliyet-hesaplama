import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

st.set_page_config(page_title="Maliyet Hesaplama", layout="wide")

# ----------------------------
# DATABASE
# ----------------------------
conn = sqlite3.connect("maliyet_v4.db", check_same_thread=False)

conn.execute("""
CREATE TABLE IF NOT EXISTS rapor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tarih TEXT,
    urun TEXT,
    maliyet REAL,
    satis REAL,
    kar REAL,
    marj REAL
)
""")
conn.commit()

# ----------------------------
# HELPERS
# ----------------------------
def pct(x):
    return x / 100

def safe_div(a,b):
    return a/b if b != 0 else 0

# ----------------------------
# UI
# ----------------------------
st.title("Maliyet Hesaplama")

# ----------------------------
# SABİTLER
# ----------------------------
with st.expander("Sabitler", expanded=True):

    col1,col2,col3 = st.columns(3)

    with col1:
        punch_katsayi = st.number_input("Punch katsayı", value=1.1693)
        mt_bolen = st.number_input("MT bölme değeri", value=1000.0)

    with col2:
        toplam_fire = st.number_input("Toplam fire %", value=8.0)
        aksesuar_fire = st.number_input("Aksesuar fire %", value=7.0)

    with col3:
        trendyol_komisyon = st.number_input("Trendyol %", value=21.0)
        kargo = st.number_input("Kargo", value=93.0)

# ----------------------------
# GİRİŞLER
# ----------------------------
col1,col2,col3 = st.columns(3)

with col1:
    ip_no = st.number_input("İp no", value=35.0)
    tarak = st.number_input("Tarak end", value=195.0)
    ham = st.number_input("Ham end", value=190.0)
    atkı_sayisi = st.number_input("Atkı sayısı", value=46.0)

with col2:
    iplik_fiyat = st.number_input("İplik fiyat USD", value=1.5)
    urun_maliyet = st.number_input("Ürün maliyet TL", value=20.0)
    konf = st.number_input("Konf maliyet TL", value=30.0)

with col3:
    alis_kur = st.number_input("Alış kur", value=38.0)
    satis_kur = st.number_input("Satış kur", value=40.0)
    kar_oran = st.number_input("Kar %", value=60.0)

# ----------------------------
# HESAPLA
# ----------------------------
if st.button("HESAPLA"):

    # ----------------------------
    # PUNCH (DÜZELTİLDİ)
    # ----------------------------
    punch = ((tarak / ham) * (atkı_sayisi / punch_katsayi)) / ip_no

    # ----------------------------
    # MT TÜL GRAMAJ (DÜZELTİLDİ)
    # ----------------------------
    mt = (punch * tarak) / mt_bolen

    # ----------------------------
    # FIRE (DÜZELTİLDİ)
    # ----------------------------
    fireli = mt + (mt * pct(toplam_fire))

    # ----------------------------
    # İPLİK MALİYET
    # ----------------------------
    iplik_maliyet = fireli * iplik_fiyat

    # ----------------------------
    # HAM BEZ
    # ----------------------------
    ham_bez_usd = iplik_maliyet
    ham_bez_tl = ham_bez_usd * satis_kur

    # ----------------------------
    # ÜRÜN MALİYET
    # ----------------------------
    urun_usd = urun_maliyet / alis_kur

    # ----------------------------
    # TOPLAM MALİYET
    # ----------------------------
    toplam_usd = ham_bez_usd + urun_usd + (konf / alis_kur)
    toplam_tl = toplam_usd * satis_kur

    # ----------------------------
    # KAR
    # ----------------------------
    kar = toplam_tl * pct(kar_oran)
    satis = toplam_tl + kar

    # ----------------------------
    # TRENDYOL
    # ----------------------------
    komisyon = satis * pct(trendyol_komisyon)
    toplam_kargo = kargo

    net_kar = satis - komisyon - toplam_kargo - toplam_tl

    # ----------------------------
    # MARJ
    # ----------------------------
    marj = 1 - safe_div(toplam_tl, satis)

    # ----------------------------
    # EKRAN
    # ----------------------------
    st.success("Hesaplandı")

    c1,c2,c3,c4 = st.columns(4)

    c1.metric("Punch", round(punch,4))
    c2.metric("MT Gramaj", round(mt,4))
    c3.metric("Toplam Maliyet TL", round(toplam_tl,2))
    c4.metric("Satış TL", round(satis,2))

    c5,c6,c7,c8 = st.columns(4)

    c5.metric("Kar TL", round(net_kar,2))
    c6.metric("Marj %", round(marj*100,2))
    c7.metric("Komisyon", round(komisyon,2))
    c8.metric("Kargo", round(toplam_kargo,2))

    # ----------------------------
    # KAYDET
    # ----------------------------
    if st.button("KAYDET"):
        conn.execute(
            "INSERT INTO rapor (tarih, urun, maliyet, satis, kar, marj) VALUES (?,?,?,?,?,?)",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                "urun",
                toplam_tl,
                satis,
                net_kar,
                marj*100
            )
        )
        conn.commit()
        st.success("Kaydedildi")

# ----------------------------
# RAPOR
# ----------------------------
st.subheader("Kayıtlar")

df = pd.read_sql("SELECT * FROM rapor ORDER BY id DESC", conn)

if not df.empty:
    st.dataframe(df)
