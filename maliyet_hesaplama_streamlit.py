import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Maliyet Raporu", page_icon="📊", layout="wide")

DB_FILE = "maliyet_raporu.db"

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

conn = get_connection()

def create_table():
    conn.execute("""
        CREATE TABLE IF NOT EXISTS maliyet_raporu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            urun_adi TEXT,
            kur REAL,
            cozgu_usd REAL,
            atki_usd REAL,
            cozgu_tl REAL,
            atki_tl REAL,
            iplik_toplam REAL,
            dokuma REAL,
            boya REAL,
            konfeksiyon REAL,
            aksesuar REAL,
            nakliye REAL,
            satis REAL,
            toplam_maliyet REAL,
            kar REAL,
            kar_marji REAL
        )
    """)
    conn.commit()

create_table()

def kayit_ekle(veri):
    conn.execute("""
        INSERT INTO maliyet_raporu (
            tarih, urun_adi, kur, cozgu_usd, atki_usd, cozgu_tl, atki_tl,
            iplik_toplam, dokuma, boya, konfeksiyon, aksesuar, nakliye,
            satis, toplam_maliyet, kar, kar_marji
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, veri)
    conn.commit()

def kayitlari_getir():
    query = "SELECT * FROM maliyet_raporu ORDER BY id DESC"
    return pd.read_sql_query(query, conn)

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

st.title("Maliyet Hesaplama ve Raporlama")

tab1, tab2 = st.tabs(["Yeni Kayıt", "Raporlar"])

with tab1:
    st.subheader("Ürün Maliyet Girişi")

    col1, col2, col3 = st.columns(3)

    with col1:
        urun_adi = st.text_input("Ürün adı")
        kur = st.number_input("Dolar kuru", min_value=0.0, value=38.00, step=0.01)
        cozgu_usd = st.number_input("Çözgü iplik fiyatı ($)", min_value=0.0, value=0.0, step=0.01)

    with col2:
        atki_usd = st.number_input("Atkı iplik fiyatı ($)", min_value=0.0, value=0.0, step=0.01)
        dokuma = st.number_input("Dokuma maliyeti (TL)", min_value=0.0, value=0.0, step=0.01)
        boya = st.number_input("Boyahane maliyeti (TL)", min_value=0.0, value=0.0, step=0.01)

    with col3:
        konfeksiyon = st.number_input("Konfeksiyon (TL)", min_value=0.0, value=0.0, step=0.01)
        aksesuar = st.number_input("Aksesuar (TL)", min_value=0.0, value=0.0, step=0.01)
        nakliye = st.number_input("Nakliye (TL)", min_value=0.0, value=0.0, step=0.01)

    satis = st.number_input("Satış fiyatı (TL)", min_value=0.0, value=0.0, step=0.01)

    cozgu_tl = cozgu_usd * kur
    atki_tl = atki_usd * kur
    iplik_toplam = cozgu_tl + atki_tl
    toplam_maliyet = iplik_toplam + dokuma + boya + konfeksiyon + aksesuar + nakliye
    kar = satis - toplam_maliyet
    kar_marji = (kar / satis * 100) if satis > 0 else 0

    st.markdown("### Ön İzleme")
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("İplik Toplamı", f"{iplik_toplam:,.2f} TL")
    o2.metric("Toplam Maliyet", f"{toplam_maliyet:,.2f} TL")
    o3.metric("Kâr", f"{kar:,.2f} TL")
    o4.metric("Kâr Marjı", f"%{kar_marji:,.2f}")

    if st.button("Kaydet", use_container_width=True):
        if not urun_adi.strip():
            st.error("Lütfen ürün adı girin.")
        else:
            veri = (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                urun_adi.strip(),
                float(kur),
                float(cozgu_usd),
                float(atki_usd),
                float(cozgu_tl),
                float(atki_tl),
                float(iplik_toplam),
                float(dokuma),
                float(boya),
                float(konfeksiyon),
                float(aksesuar),
                float(nakliye),
                float(satis),
                float(toplam_maliyet),
                float(kar),
                float(kar_marji),
            )
            kayit_ekle(veri)
            st.success("Kayıt başarıyla kaydedildi.")

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
        k2.metric("Toplam Satış", f"{df['satis'].sum():,.2f} TL")
        k3.metric("Toplam Maliyet", f"{df['toplam_maliyet'].sum():,.2f} TL")
        k4.metric("Toplam Kâr", f"{df['kar'].sum():,.2f} TL")

        st.dataframe(df, use_container_width=True)

        csv_data = df.to_csv(index=False).encode("utf-8-sig")
        excel_data = to_excel_bytes(df)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "CSV indir",
                data=csv_data,
                file_name="maliyet_raporu.csv",
                mime="text/csv",
                use_container_width=True
            )
        with c2:
            st.download_button(
                "Excel indir",
                data=excel_data,
                file_name="maliyet_raporu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.markdown("### Kayıt Sil")
        secenekler = {
            f"#{row['id']} - {row['urun_adi']} - {row['tarih']}": int(row["id"])
            for _, row in df.iterrows()
        }

        secilen = st.selectbox("Silinecek kayıt", list(secenekler.keys()))
        if st.button("Seçili Kaydı Sil"):
            kayit_sil(secenekler[secilen])
            st.success("Kayıt silindi.")
            st.rerun()

        if st.button("Tüm Kayıtları Sil"):
            tumunu_sil()
            st.success("Tüm kayıtlar silindi.")
            st.rerun()
