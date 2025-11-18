# -*- coding: utf-8 -*-
import re
import asyncio
from telethon import TelegramClient, events

API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@kbubakara"

client = TelegramClient('baccarat_sinyal_bot', API_ID, API_HASH)

# -------------------------
# ⚙️ SİSTEM AYARLARI
# -------------------------
player_results = {}
banker_results = {}
triggers = {}
martingale_tracker = {}
sent_signals = set()
MAX_GAME_NUMBER = 1440
MAX_MARTINGALE_STEP = 7
step_emojis = {0: "0️⃣", 1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣"}
LOOKBACK_GAMES = 5

# 📊 İSTATİSTİKLER
stats = {
    "total_signals": 0,
    "win_signals": 0,
    "lose_signals": 0,
    "active_martingales": 0,
    "total_profit": 0
}

# 🎨 TASARIM SABİTLERİ
EMOJİ = {
    "sinyal": "🎯",
    "kazanç": "✅",
    "kayıp": "❌",
    "devam": "🔄",
    "bonus": "🔥",
    "analiz": "🔍",
    "para": "💰",
    "sonraki": "⏭️",
    "flip": "🔄",
    "otomatik": "⚡"
}

# -------------------------
# 🧠 STRATEJİ SİSTEMİ - DÜZELTİLMİŞ
# -------------------------
def kayıp_renk_analizi(mevcut_oyun):
    """🔍 Kayıp renk stratejisi - DÜZELTİLMİŞ VERSİYON"""
    if len(player_results) < LOOKBACK_GAMES:
        return None, "Veri yetersiz"
    
    # Son 5 oyunu bul
    son_oyunlar = []
    for i in range(LOOKBACK_GAMES):
        onceki_oyun = mevcut_oyun - i
        if onceki_oyun < 1:
            onceki_oyun += MAX_GAME_NUMBER
        son_oyunlar.append(onceki_oyun)
    
    print(f"🔍 Kayıp renk analizi: Son {LOOKBACK_GAMES} oyun: {son_oyunlar}")
    
    tum_renkler = ['♥️', '♦️', '♣️', '♠️']
    gorulen_renkler = set()
    
    # Son 5 oyunda görülen tüm renkleri topla
    for oyun_no in son_oyunlar:
        if oyun_no in player_results:
            oyun_renkleri = set(kartlardan_renkleri_al(player_results[oyun_no]))
            gorulen_renkler.update(oyun_renkleri)
            print(f"  Oyun #{oyun_no}: {oyun_renkleri}")
    
    print(f"  Görülen renkler: {gorulen_renkler}")
    
    # Görülmeyen renkleri bul
    kayıp_renkler = [renk for renk in tum_renkler if renk not in gorulen_renkler]
    print(f"  Kayıp renkler: {kayıp_renkler}")
    
    if kayıp_renkler:
        secilen_renk = kayıp_renkler[0]
        analiz_metni = f"🔍 Kayıp renk: Son {LOOKBACK_GAMES} elde {secilen_renk} hiç görülmedi"
        print(f"✅ Kayıp renk bulundu: {secilen_renk}")
        return secilen_renk, analiz_metni
    
    print("❌ Kayıp renk bulunamadı")
    return None, "Tüm renkler görüldü"

def guvenli_flip_analizi(banker_kartlari):
    """🔄 Güvenli flip stratejisi"""
    renkler = kartlardan_renkleri_al(banker_kartlari)
    if not renkler or len(renkler) < 2:
        return None, "Kart verisi yetersiz"
    
    orta_kart = renkler[1]
    
    # Aynı renk grubu içinde flip
    if orta_kart in ['♣️', '♠️']:  # Siyah grup
        flip_renk = '♠️' if orta_kart == '♣️' else '♣️'
    else:  # Kırmızı grup
        flip_renk = '♦️' if orta_kart == '♥️' else '♥️'
    
    return flip_renk, "🔄 Güvenli flip seçildi"

def strateji_karari(banker_kartlari, mevcut_oyun):
    """⚡ Ana strateji karar mekanizması"""
    print(f"🎯 Strateji kararı için oyun #{mevcut_oyun}")
    
    # Öncelik: Kayıp renk stratejisi
    kayıp_renk, kayıp_analiz = kayıp_renk_analizi(mevcut_oyun)
    if kayıp_renk:
        print(f"✅ Kayıp renk stratejisi seçildi: {kayıp_renk}")
        return kayıp_renk, kayıp_analiz, "KAYIP_RENK"
    
    # Yedek: Güvenli flip
    flip_renk, flip_analiz = guvenli_flip_analizi(banker_kartlari)
    if flip_renk:
        print(f"✅ Güvenli flip stratejisi seçildi: {flip_renk}")
        return flip_renk, flip_analiz, "GUVENLI_FLIP"
    
    # Varsayılan
    print("✅ Varsayılan strateji seçildi: ♠️")
    return '♠️', "⚡ Otomatik seçim", "OTOMATIK"

# -------------------------
# 🛠️ YARDIMCI FONKSİYONLAR
# -------------------------
def metni_temizle(text):
    """Metni temizle ve normalize et"""
    return re.sub(r'\s+', ' ', text.replace('️', '').replace('\u200b', '')).strip()

def sonraki_oyun_numarasi(n, adim=1):
    """Sonraki oyun numarasını hesapla"""
    n = int(n) + adim
    if n > MAX_GAME_NUMBER:
        n -= MAX_GAME_NUMBER
    return n

def kartlari_ayikla(text):
    """Oyuncu ve banker kartlarını metinden ayıkla"""
    gruplar = re.findall(r'\((.*?)\)', text)
    if not gruplar:
        return None, None
    
    oyuncu_kartlari = gruplar[0].replace(' ', '')
    banker_kartlari = gruplar[1].replace(' ', '') if len(gruplar) > 1 else ""
    
    # Emoji formatını düzelt
    oyuncu_kartlari = oyuncu_kartlari.replace('♣', '♣️').replace('♦', '♦️').replace('♥', '♥️').replace('♠', '♠️')
    banker_kartlari = banker_kartlari.replace('♣', '♣️').replace('♦', '♦️').replace('♥', '♥️').replace('♠', '♠️')
    
    return oyuncu_kartlari, banker_kartlari

def oyuncu_ok_var_mi(text):
    """Oyuncuda ok işareti var mı kontrol et"""
    return "👉" in text.split('(')[0]

def kartlardan_renkleri_al(kart_str):
    """Kart string'inden renkleri çıkar"""
    renkler = re.findall(r'[♣♥♦♠]️?', kart_str)
    # Benzersiz renkleri döndür (tekrar edenleri kaldır)
    return list(set(renkler)) if kart_str else []

def tetikleyici_renkleri_al(kartlar_str):
    """Tetikleyici renkleri belirle"""
    renkler = []
    for renk in ['♥️', '♦️', '♣️', '♠️']:
        if renk in kartlar_str:
            renkler.append(renk)
    return renkler

# -------------------------
# 💰 MARTINGALE SİSTEMİ
# -------------------------
async def martingale_guncelle(mevcut_oyun, oyuncu_kartlari):
    """Martingale durumunu güncelle"""
    for bahis_oyunu, bilgi in list(martingale_tracker.items()):
        if bilgi.get("kontrol_edildi"):
            continue
            
        beklenen_oyun = bahis_oyunu + bilgi["adim"]
        if beklenen_oyun > MAX_GAME_NUMBER:
            beklenen_oyun -= MAX_GAME_NUMBER
            
        if mevcut_oyun != beklenen_oyun:
            continue

        if bilgi["renk"] in oyuncu_kartlari:
            # ✅ KAZANÇ
            kar = bilgi["adim"] + 1
            stats["win_signals"] += 1
            stats["total_profit"] += kar
            stats["active_martingales"] -= 1
            
            yeni_metin = f"#N{bahis_oyunu} - {bilgi['renk']} | ✅ {step_emojis[bilgi['adim']]}\n{EMOJİ['para']} +{kar}x"
            
            try:
                await client.edit_message(KANAL_HEDEF, bilgi["mesaj_id"], yeni_metin)
                print(f"✅ Kazanç: #N{bahis_oyunu} - {bilgi['renk']} (+{kar}x)")
            except Exception as e:
                print(f"Mesaj güncelleme hatası: {e}")
            bilgi["kontrol_edildi"] = True
            
        else:
            bilgi["adim"] += 1
            if bilgi["adim"] > MAX_MARTINGALE_STEP:
                # ❌ KAYIP
                stats["lose_signals"] += 1
                stats["active_martingales"] -= 1
                
                yeni_metin = f"#N{bahis_oyunu} - {bilgi['renk']} | ❌"
                
                try:
                    await client.edit_message(KANAL_HEDEF, bilgi["mesaj_id"], yeni_metin)
                    print(f"❌ Kayıp: #N{bahis_oyunu} - {bilgi['renk']}")
                except Exception as e:
                    print(f"Mesaj güncelleme hatası: {e}")
                bilgi["kontrol_edildi"] = True
                
            else:
                # 🔄 DEVAM
                yeni_metin = f"#N{bahis_oyunu} - {bilgi['renk']} | 🔄 {step_emojis[bilgi['adim']]}"
                
                try:
                    await client.edit_message(KANAL_HEDEF, bilgi["mesaj_id"], yeni_metin)
                    print(f"🔄 Devam: #N{bahis_oyunu} - {bilgi['renk']} (Adım {bilgi['adim']})")
                except Exception as e:
                    print(f"Mesaj güncelleme hatası: {e}")

# -------------------------
# 🚀 SİNYAL SİSTEMİ
# -------------------------
async def sinyal_gonder(sinyal_oyunu, tahmin, analiz, strateji, tetik_renk):
    """Sinyal mesajını gönder"""
    if not tahmin or sinyal_oyunu in sent_signals:
        print(f"❌ Sinyal gönderilemedi: #{sinyal_oyunu} - {tahmin}")
        return

    stats["total_signals"] += 1
    stats["active_martingales"] += 1

    # Bonus kontrolü
    bonus_metin = ""
    if tahmin == tetik_renk:
        bonus_metin = "\n🔥 BONUS: Banker+Oyuncu uyumlu"

    # Kısa analiz metni
    kisa_analiz = ""
    if "Kayıp renk" in analiz:
        kisa_analiz = analiz  # Tam analiz metnini göster
    elif "Güvenli flip" in analiz:
        kisa_analiz = "🔄 Güvenli flip"
    elif "Otomatik" in analiz:
        kisa_analiz = "⚡ Otomatik"

    metin = f"#N{sinyal_oyunu} - {tahmin} | 🎯 {step_emojis[0]}\n{kisa_analiz}{bonus_metin}"

    try:
        gonderilen = await client.send_message(KANAL_HEDEF, metin)
        sent_signals.add(sinyal_oyunu)
        martingale_tracker[sinyal_oyunu] = {
            "mesaj_id": gonderilen.id,
            "renk": tahmin,
            "adim": 0,
            "kontrol_edildi": False,
            "analiz": analiz + bonus_metin,
            "strateji": strateji
        }
        print(f"✅ Sinyal gönderildi: #N{sinyal_oyunu} - {tahmin}")
        print(f"   Strateji: {strateji}")
        print(f"   Analiz: {analiz}")
    except Exception as e:
        print(f"❌ Sinyal gönderme hatası: {e}")

# -------------------------
# 🎮 TELEGRAM KOMUTLARI
# -------------------------
@client.on(events.NewMessage(pattern='/start'))
async def baslat_komutu(event):
    """Botu başlatma komutu"""
    hosgeldin_metni = """
🎯 **BACCARAT SİNYAL SİSTEMİ**

Hoş geldiniz! Sistem aktif ve sinyal üretimine hazır.

📊 **Kullanılabilir Komutlar:**
/istatistik - Sistem istatistikleri
/durum - Sistem durumu
/yardim - Yardım menüsü

🚀 **Sistem çalışıyor...**
    """
    await event.reply(hosgeldin_metni)

@client.on(events.NewMessage(pattern='/istatistik'))
async def istatistik_komutu(event):
    """İstatistikleri göster"""
    if stats["total_signals"] > 0:
        basari_orani = (stats["win_signals"] / stats["total_signals"]) * 100
    else:
        basari_orani = 0
    
    istatistik_metni = f"""
📊 **SİSTEM İSTATİSTİKLERİ**

🎯 Toplam Sinyal: **{stats['total_signals']}**
✅ Kazanç: **{stats['win_signals']}**
❌ Kayıp: **{stats['lose_signals']}**
📈 Başarı Oranı: **%{basari_orani:.1f}**

💰 Toplam Kar: **+{stats['total_profit']}x**
🔄 Aktif Takip: **{stats['active_martingales']}**
    """
    await event.reply(istatistik_metni)

@client.on(events.NewMessage(pattern='/durum'))
async def durum_komutu(event):
    """Sistem durumunu göster"""
    aktif_takip = len([t for t in martingale_tracker.values() if not t.get("kontrol_edildi")])
    
    durum_metni = f"""
⚡ **SİSTEM DURUMU**

📊 İşlenen Oyun: **{len(player_results)}**
🎯 Aktif Takip: **{aktif_takip}**
🔍 Aktif Tetikleyici: **{len(triggers)}**

💾 Bellek Kullanımı: **Normal**
🔄 Sistem: **Aktif**
    """
    await event.reply(durum_metni)

@client.on(events.NewMessage(pattern='/yardim'))
async def yardim_komutu(event):
    """Yardım menüsü"""
    yardim_metni = """
ℹ️ **YARDIM MENÜSÜ**

🎯 **Sistem Nasıl Çalışır?**
- Sistem otomatik olarak baccarat oyunlarını analiz eder
- Matematiksel stratejilerle sinyal üretir
- Akıllı martingale ile riski yönetir

📊 **Sinyal Formatı:**
#N1217 - ♦️ | 🎯 0️⃣
🔍 Kayıp renk: Son 5 elde ♦️ hiç görülmedi

✅ **Kazanç Formatı:**
#N1217 - ♦️ | ✅ 2️⃣
💰 +3x

🔄 **Devam Formatı:**
#N1217 - ♦️ | 🔄 1️⃣

⚠️ **Risk Uyarısı:**
Sadece kaybedebileceğiniz tutarlarla oynayın!
    """
    await event.reply(yardim_metni)

# -------------------------
# 📡 ANA MESAJ İŞLEYİCİ
# -------------------------
@client.on(events.NewMessage)
@client.on(events.MessageEdited)
async def mesaj_isleyici(event):
    """Gelen mesajları işle"""
    if event.chat_id != KANAL_KAYNAK_ID:
        return
    
    if not event.message or not event.message.text:
        return

    # Metni temizle ve oyun numarasını bul
    temiz_metin = metni_temizle(event.message.text)
    eslesme = re.search(r'(?:#N|№)(\d+)', temiz_metin)
    if not eslesme:
        return
        
    oyun_numarasi = int(eslesme.group(1))
    print(f"📥 Oyun işleniyor: #N{oyun_numarasi}")

    # Kartları ayıkla
    oyuncu_kartlari, banker_kartlari = kartlari_ayikla(temiz_metin)
    if not oyuncu_kartlari:
        return

    # 3. kart bekleniyorsa bekle
    if oyuncu_ok_var_mi(temiz_metin):
        print(f"⏳ 3. kart bekleniyor: #N{oyun_numarasi}")
        return

    # Verileri kaydet
    banker_kartlari = banker_kartlari or ""
    player_results[oyun_numarasi] = oyuncu_kartlari
    banker_results[oyun_numarasi] = banker_kartlari

    print(f"💾 Oyun kaydedildi: #N{oyun_numarasi}")
    print(f"   Oyuncu: {oyuncu_kartlari}")
    print(f"   Banker: {banker_kartlari}")

    # Tetikleyici renkleri kontrol et
    tetik_renkler = tetikleyici_renkleri_al(oyuncu_kartlari)
    if tetik_renkler:
        triggers[oyun_numarasi] = tetik_renkler
        print(f"🎯 Tetikleyici renkler: {tetik_renkler}")

    # Martingale güncelle
    await martingale_guncelle(oyun_numarasi, oyuncu_kartlari)

    # Sinyal kontrolü
    for baslangic, tetik_renk_listesi in list(triggers.items()):
        sonraki1 = sonraki_oyun_numarasi(baslangic, 1)
        sonraki2 = sonraki_oyun_numarasi(baslangic, 2)

        for tetik_renk in tetik_renk_listesi[:]:
            if (sonraki1 in player_results and sonraki2 in player_results and
                tetik_renk not in player_results[sonraki1] and 
                tetik_renk not in player_results[sonraki2]):

                sinyal_oyunu = sonraki_oyun_numarasi(sonraki2, 1)
                
                print(f"🎯 Sinyal tetiklendi: #{sinyal_oyunu}")
                print(f"   Tetikleyici: #{baslangic} - {tetik_renk}")
                print(f"   Kontrol edilen oyunlar: #{sonraki1}, #{sonraki2}")
                
                # Strateji kararı al
                tahmin, analiz, strateji = strateji_karari(
                    banker_results.get(sonraki2, ""), 
                    sonraki2
                )

                await sinyal_gonder(sinyal_oyunu, tahmin, analiz, strateji, tetik_renk)
                tetik_renk_listesi.remove(tetik_renk)

        if not tetik_renk_listesi:
            triggers.pop(baslangic, None)

# -------------------------
# 🎪 BAŞLATMA
# -------------------------
async def main():
    """Ana fonksiyon"""
    baslangic_metni = """
🎯 **BACCARAT SİNYAL SİSTEMİ BAŞLATILIYOR...**

✅ Sistem yükleniyor...
🔍 Stratejiler aktif ediliyi...
💰 Martingale sistemi hazırlanıyor...

🚀 **Sistem başarıyla başlatıldı!**
    """
    print(baslangic_metni)
    
    try:
        await client.start()
        print("✅ Telegram bağlantısı başarılı!")
        
        # Bot bilgilerini al
        bot_bilgisi = await client.get_me()
        print(f"🤖 Bot kullanıcı adı: @{bot_bilgisi.username}")
        print(f"🔗 Hedef kanal: {KANAL_HEDEF}")
        
        # Başlangıç mesajını kanala gönder
        try:
            await client.send_message(KANAL_HEDEF, "🎯 Sinyal sistemi aktif! Veriler izleniyor...")
        except Exception as e:
            print(f"⚠️ Kanal mesajı gönderilemedi: {e}")
        
        print("⏳ Mesajlar dinleniyor...")
        await client.run_until_disconnected()
        
    except Exception as e:
        print(f"❌ Başlatma hatası: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Bot kullanıcı tarafından durduruldu")
    except Exception as e:
        print(f"❌ Beklenmeyen hata: {e}")
