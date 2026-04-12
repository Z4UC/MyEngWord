import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random

# --- Konfigürasyon ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
except Exception as e:
    st.error("Gemini API hatası.")
    st.stop()

# --- Google Sheets Bağlantısı ---
conn = st.connection("gsheets", type=GSheetsConnection)

def verileri_yukle():
    # Google Sheets'ten verileri çek (ilk sayfa)
    return conn.read(ttl=0) # ttl=0 her seferinde taze veri çeker

def kelime_durum_guncelle(kelime, yeni_durum):
    df = verileri_yukle()
    df.loc[df['kelime'] == kelime, 'durum'] = yeni_durum
    conn.update(data=df)
    st.cache_data.clear()

# --- Gemini Fonksiyonu ---
def gemini_ile_anlam_getir(kelime):
    prompt = f"'{kelime}' kelimesinin Türkçe anlamını(türüyle) ve İngilizce örnek cümlesini JSON formatında 'anlam' ve 'kullanim' anahtarlarıyla ver."
    try:
        response = model.generate_content(prompt)
        import json
        clean_response = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_response)
    except:
        return None

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
            st.success(f"**Anlam:** {st.session_state.gosterilen_anlam.get('anlam')}")
            st.info(f"**Örnek:** {st.session_state.gosterilen_anlam.get('kullanim')}")

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
