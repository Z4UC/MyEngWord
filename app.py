import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
import json

st.set_page_config(page_title="Kelime Kartları", page_icon="🧠", layout="centered")

# --- CSS Düzenlemeleri ---
st.markdown("""
<style>
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 1.5rem !important;
        max-width: 580px;
    }
    .kelime-baslik {
        font-size: 1.35rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 0.2rem;
    }
    .anlam-kutusu {
        background-color: rgba(128, 128, 128, 0.08);
        border-left: 3px solid #2e7d32;
        padding: 6px 10px;
        border-radius: 6px;
        font-size: 0.88rem;
        line-height: 1.35;
        margin-top: 6px;
    }
</style>
""", unsafe_allow_html=True)

# --- Gemini Konfigürasyon ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-flash-lite-latest')
except Exception as e:
    st.error("Gemini API anahtarı doğrulanamadı.")
    st.stop()

# --- Google Sheets Bağlantısı ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. VERİLERİ HAFIZAYA (SESSION STATE) ALMA ---
# Sayfa her yenilendiğinde Google'a gitmez, sadece ilk açılışta 1 kere çeker!
if 'df' not in st.session_state:
    try:
        raw_df = conn.read(ttl=0)
        raw_df['durum'] = pd.to_numeric(raw_df['durum'], errors='coerce').fillna(0).astype(int)
        st.session_state.df = raw_df
    except Exception as e:
        st.error("Google Sheets'e bağlanılamadı. Lütfen 30 saniye bekleyip sayfayı yenileyin.")
        st.stop()

def kelime_durum_guncelle(kelime, yeni_durum):
    """Hafızadaki veriyi günceller ve Google Sheets'e tek bir yazma isteği atar"""
    # 1. Önce hafızayı güncelle (Arayüz anında değişir)
    st.session_state.df.loc[st.session_state.df['kelime'] == kelime, 'durum'] = int(yeni_durum)
    
    # 2. Google Sheets'e yazmayı dene (Kotaya takılsa bile kullanıcı akışı bozulmaz)
    try:
        conn.update(data=st.session_state.df)
    except Exception:
        st.toast("⚠️ Google API yoğun, değişiklik yerel hafızaya kaydedildi.", icon="⚠️")

# --- Gemini Fonksiyonu ---
def gemini_ile_anlam_getir(kelime):
    prompt = f"""
    Lütfen '{kelime}' kelimesi için şu bilgileri ver:
    1. Anlamı: Kelimenin Türkçe anlamı ve parantez içinde türü (örn: isim, fiil).
    2. Kullanım: Kelimenin geçtiği kısa ve net tek bir İngilizce örnek cümle.
    
    Cevabını sadece şu JSON formatında ver:
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

# --- Filtrelemeler (Doğrudan Hafızadan Yapılır) ---
df = st.session_state.df
hic_bilinmeyenler_df = df[df['durum'] == 0]
calisilacaklar_df = df[df['durum'] == 1]
tam_bilinenler_sayisi = len(df[df['durum'] == 2])

# --- Üst Seçim Butonları ---
calisma_modu = st.radio(
    label="Mod Seçimi",
    options=["🔴 Hiç Bilmediklerim", "🟡 Çalışmam Gerekenler"],
    horizontal=True,
    label_visibility="collapsed"
)

if 'aktif_mod' not in st.session_state:
    st.session_state.aktif_mod = calisma_modu

if st.session_state.aktif_mod != calisma_modu:
    st.session_state.aktif_mod = calisma_modu
    st.session_state.mevcut_kelime = None
    st.session_state.gosterilen_anlam = None

aktif_df = hic_bilinmeyenler_df if "Hiç Bilmediklerim" in calisma_modu else calisilacaklar_df

if 'mevcut_kelime' not in st.session_state:
    st.session_state.mevcut_kelime = None
    st.session_state.gosterilen_anlam = None

if not st.session_state.mevcut_kelime and not aktif_df.empty:
    st.session_state.mevcut_kelime = random.choice(aktif_df['kelime'].values)

# --- Kelime Kartı Alanı ---
if st.session_state.mevcut_kelime:
    with st.container(border=True):
        st.markdown(f"<div class='kelime-baslik'>{st.session_state.mevcut_kelime.capitalize()}</div>", unsafe_allow_html=True)
        
        if st.button("👁️ Anlamı Göster", use_container_width=True):
            with st.spinner("Getiriliyor..."):
                st.session_state.gosterilen_anlam = gemini_ile_anlam_getir(st.session_state.mevcut_kelime)
        
        if st.session_state.gosterilen_anlam:
            anlam = st.session_state.gosterilen_anlam.get("anlam")
            ornek = st.session_state.gosterilen_anlam.get("kullanim")
            st.markdown(f"""
            <div class='anlam-kutusu'>
                <div><b>📖 Anlam:</b> {anlam}</div>
                <div style="margin-top: 2px;"><b>💡 Örnek:</b> <i>{ornek}</i></div>
            </div>
            """, unsafe_allow_html=True)

    # --- Değerlendirme Butonları ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("❌ Bilmiyorum", use_container_width=True):
            kelime_durum_guncelle(st.session_state.mevcut_kelime, 0)
            st.session_state.mevcut_kelime = None
            st.session_state.gosterilen_anlam = None
            st.rerun()

    with col2:
        if st.button("🟡 Tekrar Et", use_container_width=True):
            kelime_durum_guncelle(st.session_state.mevcut_kelime, 1)
            st.session_state.mevcut_kelime = None
            st.session_state.gosterilen_anlam = None
            st.rerun()

    with col3:
        if st.button("✅ Biliyorum", use_container_width=True):
            kelime_durum_guncelle(st.session_state.mevcut_kelime, 2)
            st.session_state.mevcut_kelime = None
            st.session_state.gosterilen_anlam = None
            st.rerun()

else:
    st.balloons()
    st.success(f"Tebrikler! Bu gruptaki ({calisma_modu}) tüm kelimeler bitti.")

# --- Yan Panel ---
st.sidebar.header("📊 Durum Özeti")
st.sidebar.metric("🔴 Hiç Bilinmeyen", len(hic_bilinmeyenler_df))
st.sidebar.metric("🟡 Çalışılacak", len(calisilacaklar_df))
st.sidebar.metric("🟢 Öğrenilen", tam_bilinenler_sayisi)

st.sidebar.divider()
if st.sidebar.button("🔄 Listeyi Yenile (Sheet'ten Çek)", use_container_width=True):
    if 'df' in st.session_state:
        del st.session_state['df']
    st.cache_data.clear()
    st.rerun()
