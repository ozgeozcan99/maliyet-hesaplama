# USD → TL dönüşüm
cozgu_tl = cozgu_usd * kur
atki_tl = atki_usd * kur

iplik_toplam = cozgu_tl + atki_tl

toplam = iplik_toplam + dokuma + boya + konf + aksesuar + nakliye
kar = satis - toplam
marj = (kar / satis * 100) if satis > 0 else 0

st.subheader("Sonuçlar")

st.write("Çözgü TL:", cozgu_tl)
st.write("Atkı TL:", atki_tl)
st.write("İplik toplam:", iplik_toplam)

st.write("Toplam maliyet:", toplam)
st.write("Kar:", kar)
st.write("Kar marjı %:", marj)
