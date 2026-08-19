import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
import json

# --- Konfigürasyon ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-flash-lite-latest')
except Exception as e:
    st.error("Gemini API hatası.")
    st.stop()

# --- Google Sheets Bağlantısı ---
conn = st.connection("gsheets", type=GSheetsConnection)

def verileri_yukle():
    df = conn.read(ttl=0)
    # Durum sütunundaki olası boşlukları veya tipleri sayıya çevir
    df['durum'] = pd.to_numeric(df['durum'], errors='coerce').fillna(0).astype(int)
    return df

def kelime_durum_guncelle(kelime, yeni_durum):
    try:
        df = conn.read(ttl=0)
        df['durum'] = pd.to_numeric(df['durum'], errors='coerce').fillna(0).astype(int)
        
        # Sadece ilgili satırın durumunu güncelle
        df.loc[df['kelime'] == kelime, 'durum'] = yeni_durum
        
        # Google Sheets'e geri yaz
        conn.update(data=df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Güncelleme sırasında hata oluştu: {e}")

# --- Gemini Fonksiyonu ---
def gemini_ile_anlam_getir(kelime):
    prompt = f"""
    Lütfen '{kelime}' kelimesi için şu bilgileri ver:
    1. Anlamı: Kelimenin Türkçe anlamı ve parantez içinde türü (örn: isim, fiil).
    2. Kullanım: Kelimenin geçtiği sadece bir tane İngilizce örnek cümle.
    
    Cevabını sadece şu JSON formatında ver, başka hiçbir açıklama ekleme:
    {{"anlam": "kelime anlamı (türü)", "kullanim": "English example sentence."}}
    """
    try:
        response = model.generate_content(prompt)
        clean_response = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_response)
        
        return {
            "anlam": data.get("anlam", "Anlam bulunamadı"),
            "kullanim": data.get("kullanim", data.get("ingilizce_ornek", "Örnek bulunamadı"))
        }
    except:
        return {"anlam": "Hata oluştu", "kullanim": "Hata oluştu"}

# --- Uygulama Mantığı ---
st.title("🧠 Kalıcı Kelime Kartları")

df = verileri_yukle()

# Veri filtreleri
hic_bilinmeyenler_df = df[df['durum'] == 0]
calisilacaklar_df = df[df['durum'] == 1]
tam_bilinenler_sayisi = len(df[df['durum'] == 2])

# --- ÜST BUTONLAR / MOD SEÇİMİ ---
st.write("### 🎯 Çalışma Modu")
calisma_modu = st.radio(
    label="Hangi gruptan kelime çalışmak istiyorsunuz?",
    options=["🔴 Hiç Bilmediklerim", "🟡 Çalışmam Gerekenler (Tekrar)"],
    horizontal=True,
    label_visibility="collapsed"
)

# Mod değiştiğinde mevcut kelimeyi sıfırlama mekanizması
if 'aktif_mod' not in st.session_state:
    st.session_state.aktif_mod = calisma_modu

if st.session_state.aktif_mod != calisma_modu:
    st.session_state.aktif_mod = calisma_modu
    st.session_state.mevcut_kelime = None
    st.session_state.gosterilen_anlam = None

# Seçilen moda göre gösterilecek kelime havuzu
if "Hiç Bilmediklerim" in calisma_modu:
    aktif_df = hic_bilinmeyenler_df
else:
    aktif_df = calisilacaklar_df

# Session state ilk tanımlamaları
if 'mevcut_kelime' not in st.session_state:
    st.session_state.mevcut_kelime = None
    st.session_state.gosterilen_anlam = None

# Havuzdan rastgele kelime seçme
if not st.session_state.mevcut_kelime and not aktif_df.empty:
    st.session_state.mevcut_kelime = random.choice(aktif_df['kelime'].values)

# --- Arayüz / Kart Görünümü ---
if st.session_state.mevcut_kelime:
    with st.container(border=True):
        st.header(st.session_state.mevcut_kelime.capitalize())
        
        if st.button("👁️ Anlamı Göster", use_container_width=True):
            with st.spinner("Gemini hazırlanıyor..."):
                st.session_state.gosterilen_anlam = gemini_ile_anlam_getir(st.session_state.mevcut_kelime)
        
        if st.session_state.gosterilen_anlam:
            st.divider()
            anlam_metni = st.session_state.gosterilen_anlam.get("anlam")
            ornek_metni = st.session_state.gosterilen_anlam.get("kullanim")
            
            st.success(f"**Anlam:** {anlam_metni}")
            st.info(f"**Örnek:** {ornek_metni}")

    st.write("#### Kelimeyi Değerlendir:")
    
    # --- ALTTAKİ 3 BUTON ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("❌ Hiç Bilmiyorum", use_container_width=True, help="Kelimeyi hiç bilinmeyenler (0) havuzuna atar."):
            kelime_durum_guncelle(st.session_state.mevcut_kelime, 0)
            st.session_state.mevcut_kelime = None
            st.session_state.gosterilen_anlam = None
            st.rerun()

    with col2:
        if st.button("🟡 Çalışmam Lazım", use_container_width=True, help="Zor/unutulan kelimeler (1) havuzuna atar."):
            kelime_durum_guncelle(st.session_state.mevcut_kelime, 1)
            st.session_state.mevcut_kelime = None
            st.session_state.gosterilen_anlam = None
            st.rerun()

    with col3:
        if st.button("✅ Kolay / Biliyorum", use_container_width=True, help="Kelimeyi tamamen öğrenildi (2) olarak işaretler."):
            kelime_durum_guncelle(st.session_state.mevcut_kelime, 2)
            st.session_state.mevcut_kelime = None
            st.session_state.gosterilen_anlam = None
            st.rerun()

else:
    st.balloons()
    st.success(f"Tebrikler! Seçili gruptaki ({calisma_modu}) tüm kelimeleri tamamladınız.")

# --- Yan Panel (İstatistikler) ---
st.sidebar.header("📊 Durum Özeti")
st.sidebar.metric("🔴 Hiç Bilinmeyenler", len(hic_bilinmeyenler_df))
st.sidebar.metric("🟡 Çalışılacak / Tekrar", len(calisilacaklar_df))
st.sidebar.metric("🟢 Tamamen Öğrenilenler", tam_bilinenler_sayisi)

st.sidebar.divider()
if st.sidebar.button("🔄 Listeyi Yenile", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
