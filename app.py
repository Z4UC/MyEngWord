import streamlit as st
import google.generativeai as genai
import json
import random

# --- API Konfigürasyonu ---
# secrets.toml dosyasından API anahtarını al
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
except Exception as e:
    st.error(f"API anahtarı yapılandırılamadı. Lütfen .streamlit/secrets.toml dosyanızı kontrol edin. Hata: {e}")
    st.stop()


# --- Yardımcı Fonksiyonlar ---

def dosyadan_kelimeleri_yukle():
    """JSON dosyalarından kelime listelerini yükler."""
    try:
        with open('ogrenilecekler.json', 'r', encoding='utf-8') as f:
            ogrenilecekler = json.load(f)['kelimeler']
        with open('bilinenler.json', 'r', encoding='utf-8') as f:
            bilinenler = json.load(f)['kelimeler']
        return ogrenilecekler, bilinenler
    except FileNotFoundError:
        # Dosyalar yoksa, boş listelerle başla
        return ["word", "example", "test"], []

def kelimeleri_dosyaya_kaydet(ogrenilecekler, bilinenler):
    """Kelime listelerini JSON dosyalarına kaydeder."""
    with open('ogrenilecekler.json', 'w', encoding='utf-8') as f:
        json.dump({"kelimeler": ogrenilecekler}, f, indent=2)
    with open('bilinenler.json', 'w', encoding='utf-8') as f:
        json.dump({"kelimeler": bilinenler}, f, indent=2)

def gemini_ile_anlam_getir(kelime):
    """Gemini API'sine bağlanıp kelimenin anlamını ve kullanımını alır."""
    prompt = f"""
    Lütfen '{kelime}' kelimesinin Türkçe anlamını, parantez içinde türünü (ör: sıfat, fiil, isim, zarf gibi) ve bu kelimenin geçtiği basit bir İngilizce örnek cümle yaz.
    Cevabını sadece JSON formatında ve 'anlam' ve 'kullanim' anahtarlarıyla ver. Başka hiçbir açıklama ekleme.
    Örnek: {{"anlam": "Bir şeyin anlamı. (Türü)", "kullanim": "This is an example sentence."}}
    """
    try:
        response = model.generate_content(prompt)
        # Bazen Gemini'nin cevabı markdown formatında gelebilir, temizleyelim.
        clean_response = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_response)
    except Exception as e:
        st.error(f"API'den cevap alınırken bir hata oluştu: {e}")
        return None

# --- Session State (Uygulama Hafızası) Başlatma ---

# Sayfa yeniden yüklendiğinde hafızanın silinmemesi için session_state kullanılır.
if 'ogrenilecekler' not in st.session_state:
    st.session_state.ogrenilecekler, st.session_state.bilinenler = dosyadan_kelimeleri_yukle()
    st.session_state.mevcut_kelime = None
    st.session_state.gosterilen_anlam = None

# Eğer öğrenilecek kelime kalmadıysa veya ilk defa çalışıyorsa yeni kelime seç
if not st.session_state.mevcut_kelime and st.session_state.ogrenilecekler:
    st.session_state.mevcut_kelime = random.choice(st.session_state.ogrenilecekler)

# --- ARAYÜZ (UI) ---

st.title("🧠 Akıllı Kelime Kartları")
st.write("Öğrenmek istediğin kelimenin üzerine tıkla ve anlamını Gemini'den öğren!")

# Kelime kartı alanı
if st.session_state.mevcut_kelime:
    # Kartı bir container içinde gösterelim
    with st.container(border=True):
        st.header(st.session_state.mevcut_kelime.capitalize())

        # Anlamı göster butonu
        if st.button("Anlamı Göster", key="show_meaning"):
            with st.spinner("Gemini düşünüyor..."):
                st.session_state.gosterilen_anlam = gemini_ile_anlam_getir(st.session_state.mevcut_kelime)
        
        # Eğer anlam yüklendiyse göster
        if st.session_state.gosterilen_anlam:
            st.divider()
            st.success(f"**Anlamı:** {st.session_state.gosterilen_anlam.get('anlam', 'Bulunamadı.')}")
            st.info(f"**Örnek Kullanım:** {st.session_state.gosterilen_anlam.get('kullanim', 'Bulunamadı.')}")

    st.write("") # Boşluk bırakmak için

    # "Biliyorum" ve "Bilmiyorum" Butonları
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Biliyorum", use_container_width=True):
            kelime = st.session_state.mevcut_kelime
            if kelime in st.session_state.ogrenilecekler:
                st.session_state.ogrenilecekler.remove(kelime)
                st.session_state.bilinenler.append(kelime)
                kelimeleri_dosyaya_kaydet(st.session_state.ogrenilecekler, st.session_state.bilinenler)
                st.toast(f"'{kelime}' bilinenlere eklendi!", icon="✅")
            
            # Reset and get a new word
            st.session_state.mevcut_kelime = None
            st.session_state.gosterilen_anlam = None
            st.rerun()

    with col2:
        if st.button("➡️ Sonraki Kelime (Bilmiyorum)", use_container_width=True):
            st.toast("Bu kelimeyi sonra tekrar göreceksin!", icon="👍")
            # Reset and get a new word
            st.session_state.mevcut_kelime = None
            st.session_state.gosterilen_anlam = None
            st.rerun()

else:
    st.success("🎉 Tebrikler! Öğrenilecek tüm kelimeleri tamamladın!")
    if st.button("Yeniden Başla"):
        # bilinenler.json dosyasını sıfırlayarak yeniden başlatma mantığı eklenebilir.
        st.warning("Bu özellik henüz eklenmedi.")

# Kenar çubuğunda istatistikleri gösterelim
st.sidebar.title("İstatistikler")
st.sidebar.write(f"Öğrenilecek Kelime Sayısı: **{len(st.session_state.ogrenilecekler)}**")
st.sidebar.write(f"Bilinen Kelime Sayısı: **{len(st.session_state.bilinenler)}**")