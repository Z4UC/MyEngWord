import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
import json

st.set_page_config(page_title="Kelime Kartları", page_icon="🧠", layout="centered")

# --- Sayfayı Tek Ekrana Sığdıran CSS Düzenlemeleri ---
st.markdown("""
<style>
    /* Üst ve alt boşlukları minimuma indir */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 1rem !important;
        max-width: 600px;
    }
    /* Kelime başlığı boyutu */
    .kelime-baslik {
        font-size: 1.45rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 0.4rem;
    }
    /* Anlam ve örnek için ince/kompakt kart */
    .anlam-kutusu {
        background-color: rgba(128, 128, 128, 0.08);
        border-left: 3px solid #2e7d32;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 0.90rem;
        line-height: 1.4;
    }
</style>
""", unsafe_allow_html=True)

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
    df['durum'] = pd.to_numeric(df['durum'], errors='coerce').fillna(0).astype(int)
    return df

def kelime_durum_guncelle(kelime, yeni_durum):
    try:
        df = conn.read(ttl=0)
        df['durum'] = pd.to_numeric(df['durum'], errors='coerce').fillna(0).astype(int)
        df.loc[df['kelime'] == kelime, 'durum'] = yeni_durum
        conn.update(data=df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Güncelleme hatası: {e}")

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

# --- Veri Çekme & Filtreleme ---
df = verileri_yukle()
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

# --- Kompakt Kart Alanı ---
if st.session_state.mevcut_kelime:
    with st.container(border=True):
        st.markdown(f"<div class='kelime-baslik'>{st.session_state.mevcut_kelime.capitalize()}</div>", unsafe_allow_html=True)
        
        # Anlam henüz açılmadıysa butonu göster, açıldıysa buton yerine kompakt bilgiyi getir
        if not st.session_state.gosterilen_anlam:
            if st.button("👁️ Anlamı Göster", use_container_width=True):
                with st.spinner("Getiriliyor..."):
                    st.session_state.gosterilen_anlam = gemini_ile_anlam_getir(st.session_state.mevcut_kelime)
                st.rerun()
        else:
            anlam = st.session_state.gosterilen_anlam.get("anlam")
            ornek = st.session_state.gosterilen_anlam.get("kullanim")
            st.markdown(f"""
            <div class='anlam-kutusu'>
                <div><b>📖 Anlam:</b> {anlam}</div>
                <div style="margin-top: 3px;"><b>💡 Örnek:</b> <i>{ornek}</i></div>
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
if st.sidebar.button("🔄 Listeyi Yenile", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
