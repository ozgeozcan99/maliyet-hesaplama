import streamlit as st

st.set_page_config(page_title="Maliyet Hesaplama", layout="centered")

st.title("Maliyet Hesaplama")

st.subheader("Kur Bilgisi")
kur = st.number_input("Dolar kuru", min_value=0.0, value=38.00, step=0.01)

st.subheader("İplik Fiyatları (USD)")
cozgu_usd = st.number_input("Çözgü iplik fiyatı ($)", min_value=0.0, value=0.0, step=0.01)
atki_usd = st.number_input("Atkı iplik fiyatı ($)", min_value=0.0, value=0.0, step=0.01)

st.subheader("Diğer Maliyetler (TL)")
dokuma = st.number_input("Dokuma maliyeti", min_value=0.0, value=0.0, step=0.01)
boya = st.number_input("Boyahane maliyeti", min_value=0.0, value=0.0, step=0.01)
konf = st.number_input("Konfeksiyon", min_value=0.0, value=0.0, step=0.01)
aksesuar = st.number_input("Aksesuar", min_value=0.0, value=0.0, step=0.01)
nakliye = st.number_input("Nakliye", min_value=0.0, value=0.0, step=0.01)

st.subheader("Satış")
satis = st.number_input("Satış fiyatı (TL)", min_value=0.0, value=0.0, step=0.01)

if st.button("HESAPLA"):
    cozgu_tl = cozgu_usd * kur
    atki_tl = atki_usd * kur
    iplik_toplam = cozgu_tl + atki_tl

    toplam_maliyet = iplik_toplam + dokuma + boya + konf + aksesuar + nakliye
    kar = satis - toplam_maliyet
    kar_marji = (kar / satis * 100) if satis > 0 else 0

    st.subheader("Sonuçlar")
    st.write(f"Çözgü TL: {cozgu_tl:.2f}")
    st.write(f"Atkı TL: {atki_tl:.2f}")
    st.write(f"İplik Toplamı: {iplik_toplam:.2f}")
    st.write(f"Toplam Maliyet: {toplam_maliyet:.2f}")
    st.write(f"Kâr: {kar:.2f}")
    st.write(f"Kâr Marjı %: {kar_marji:.2f}")
