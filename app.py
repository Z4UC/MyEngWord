import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random

# --- Konfigürasyon ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
except Exception as e:
    st.error("Gemini API hatası.")
    st.stop()

# --- Google Sheets Bağlantısı ---
conn = st.connection("gsheets", type=GSheetsConnection)

def verileri_yukle():
    # Google Sheets'ten verileri çek (ilk sayfa)
    return conn.read(ttl=0) # ttl=0 her seferinde taze veri çeker

def kelime_durum_guncelle(kelime, yeni_durum):
    try:
        # Mevcut veriyi çek
        df = conn.read(ttl=0)
        
        # Sadece ilgili satırı güncelle
        df.loc[df['kelime'] == kelime, 'durum'] = yeni_durum
        
        # Güncellenmiş DataFrame'i geri gönder
        conn.update(data=df)
        
        # Önbelleği temizle ki yeni veriyi hemen görsün
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Güncelleme sırasında hata oluştu: {e}")

# --- Gemini Fonksiyonu ---
def gemini_ile_anlam_getir(kelime):
    # Talimatı çok netleştiriyoruz
    prompt = f"""
    Lütfen '{kelime}' kelimesi için şu bilgileri ver:
    1. Anlamı: Kelimenin Türkçe anlamı ve parantez içinde türü (örn: isim, fiil).
    2. Kullanım: Kelimenin geçtiği sadece bir tane İngilizce örnek cümle.
    
    Cevabını sadece şu JSON formatında ver, başka hiçbir açıklama ekleme:
    {{"anlam": "kelime anlamı (türü)", "kullanim": "English example sentence."}}
    """
    try:
        response = model.generate_content(prompt)
        import json
        # Markdown işaretlerini temizle
        clean_response = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_response)
        
        # Eğer Gemini yine de farklı anahtarlar gönderirse diye kontrol edelim
        # Sadece metin kısmını döndürelim
        return {
            "anlam": data.get("anlam", "Anlam bulunamadı"),
            "kullanim": data.get("kullanim", data.get("ingilizce_ornek", "Örnek bulunamadı"))
        }
    except:
        return {"anlam": "Hata oluştu", "kullanim": "Hata oluştu"}

# --- Uygulama Mantığı ---
st.title("🧠 Kalıcı Kelime Kartları")

df = verileri_yukle()
# Durumu 0 olanlar öğrenileceklerdir
ogrenilecekler_df = df[df['durum'] == 0]
bilinenler_sayisi = len(df[df['durum'] == 1])

if 'mevcut_kelime' not in st.session_state:
    st.session_state.mevcut_kelime = None
    st.session_state.gosterilen_anlam = None

if not st.session_state.mevcut_kelime and not ogrenilecekler_df.empty:
    st.session_state.mevcut_kelime = random.choice(ogrenilecekler_df['kelime'].values)

# --- Arayüz ---
if st.session_state.mevcut_kelime:
    with st.container(border=True):
        st.header(st.session_state.mevcut_kelime.capitalize())
        
        if st.button("Anlamı Göster"):
            with st.spinner("Gemini geliyor..."):
                st.session_state.gosterilen_anlam = gemini_ile_anlam_getir(st.session_state.mevcut_kelime)
        
        if st.session_state.gosterilen_anlam:
            st.divider()
            
            # .get("anlam") diyerek sözlükten sadece o metni çekiyoruz
            anlam_metni = st.session_state.gosterilen_anlam.get("anlam")
            ornek_metni = st.session_state.gosterilen_anlam.get("kullanim")
            
            st.success(f"**Anlam:** {anlam_metni}")
            st.info(f"**Örnek:** {ornek_metni}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Biliyorum", use_container_width=True):
            kelime_durum_guncelle(st.session_state.mevcut_kelime, 1)
            st.session_state.mevcut_kelime = None
            st.session_state.gosterilen_anlam = None
            st.rerun()
    with col2:
        if st.button("➡️ Sonraki", use_container_width=True):
            st.session_state.mevcut_kelime = None
            st.session_state.gosterilen_anlam = None
            st.rerun()
else:
    st.balloons()
    st.success("Tüm kelimeler bitti!")

# Yan Panel
st.sidebar.write(f"Öğrenilecek: {len(ogrenilecekler_df)}")
st.sidebar.write(f"Bilinen: {bilinenler_sayisi}")
if st.sidebar.button("Listeyi Yenile"):
    st.cache_data.clear()
    st.rerun()
