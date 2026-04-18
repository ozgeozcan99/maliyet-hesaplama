import streamlit as st

st.title("Maliyet Hesaplama")

cozgu = st.number_input("Çözgü iplik fiyatı", 0.0)
atki = st.number_input("Atkı iplik fiyatı", 0.0)
dokuma = st.number_input("Dokuma maliyeti", 0.0)
boya = st.number_input("Boyahane maliyeti", 0.0)
konf = st.number_input("Konfeksiyon", 0.0)
aksesuar = st.number_input("Aksesuar", 0.0)
nakliye = st.number_input("Nakliye", 0.0)
satis = st.number_input("Satış fiyatı", 0.0)

if st.button("HESAPLA"):
    toplam = cozgu + atki + dokuma + boya + konf + aksesuar + nakliye
    kar = satis - toplam
    marj = (kar / satis * 100) if satis > 0 else 0

    st.write("Toplam maliyet:", toplam)
    st.write("Kar:", kar)
    st.write("Kar marjı %:", marj)
