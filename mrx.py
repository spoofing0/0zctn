# -*- coding: utf-8 -*-
import re
import asyncio
import random
import logging
from datetime import datetime
from telethon import TelegramClient, events

# ==============================================================================
# LOGGING AYARLARI
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('baccarat_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==============================================================================
# TELEGRAM API BİLGİLERİ ve KANAL AYARLARI
# ==============================================================================
API_ID = 27518940
API_HASH = '30b6658a1870f8462108130783fef14f'
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@kbubakara"

client = TelegramClient('baccarat_balanced_v53', API_ID, API_HASH)

# ==============================================================================
# SİSTEM SABİTLERİ
# ==============================================================================
MAX_GAME_NUMBER = 1440
MAX_MARTINGALE_STEP = 7  # 7D sabit
BACK_SYSTEM_COUNT = 53   # 53 back sistemi

# ==============================================================================
# DURUM DEPOLARI
# ==============================================================================
player_results = {}        # {game_num: "cards string"}
martingale_tracker = {}    # {signal_key: {msg_id, bet_game, suit, step, checked, signal_type}}
sent_signals = set()

# ==============================================================================
# EMOJİ ve MESAJ KÜTÜPHANESİ
# ==============================================================================

# Step emojileri
STEP_EMOJIS = {
    0: "0️⃣", 1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 
    4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣"
}

# Dengeli kazanç mesajları
WIN_MESSAGES = [
    "🔥 Dengeli Kazanç!", "💎 Stabil Başarı!", "🎯 Sabit İsabet!", "⚡ Denge Vuruşu!", 
    "💥 Kontrollü Zafer!", "🏆 Ölçülü Başarı!", "🚀 Dengeli Yükseliş!", "🏆 Sistem Çalışıyor!",
    "🔥 Matematiksel Zafer!", "🚀 Algoritma Başarısı!", "🎯 İstatistiksel İsabet!", "💥 Formül Tuttu!",
    "🧨 Hesaplı Kazanç!", "🚀 Olasılık Gerçekleşti!", "🎉 Sistem Doğrulandı!", "🎯 Teori Uygulandı.",
    "💎 Bilimsel Sonuç.", "🔥 Veri Tabanlı Kazanç!", "⚡ Analiz Başarısı!", 
    "💎 Rasyonel Sonuç!", "🎯 Matematik Konuştu!", "💥 İstatistik Kazandı!", "🏹 Algoritma Vuruşu!",
    "📌 Veri Noktası!", "🔒 Bilimsel Kilidi Açtık!", "💣 Hesaplanmış Başarı!", "🔥 Sistem Zaferi!",
    "⚡ Dengeli Etki!", "💎 Rasyonel İsabet!", "🌪️ Kontrollü Fırtına!", "🎉 Matematiksel Zafer!",
    "🔥 İstatistiksel Başarı!", "🚀 Veri Odaklı Sonuç!", "🏹 Bilimsel Vuruş!", "💥 Analiz Doğrulandı!",
    "🎖️ Sistem Başarısı!", "💎 Algoritmik İsabet!", "💫 Matematiksel Parlama!", 
    "🎉 Veri Tabanlı Zafer!", "🔥 Bilimsel Başarı!", "🚀 Rasyonel Yükseliş!", 
    "🏆 İstatistiksel Zafer!", "💥 Kontrollü Darbe!", "⚡ Dengeli Çakış!", 
    "🔥 Sistemsel Başarı!", "🎯 Matematiksel İsabet!", "🚀 Veri Destekli Sonuç!", 
    "💎 Bilimsel Netlik!"
]

# Dengeli kayıp mesajları
LOSS_MESSAGES = [
    "❌ Sistem Testi!", "💢 Olasılık Dışı!", "🔻 Geçici Kayıp!", "🔥 Veri Toplama Aşaması!", 
    "⚠️ Sistem Kalibrasyonu!", "💥 İstatistiksel Dalgalanma!", "🌑 Geçici Kararma!", "📉 Anlık Düşüş!",
    "🚫 Veri Noktası!", "🩸 Sistem Analizi!", "💔 Matematiksel Ara!", "🌫️ Veri İşleme!",
    "⚡ Algoritma Testi!", "🔧 Sistem Ayarı!", "💣 Analiz Süreci!", 
    "🎭 Veri Doğrulama!", "🧊 Sistem Soğuması!", "📌 İstatistiksel Anomali!", "🕳️ Geçici Boşluk!",
    "🚷 Veri Filtreleme!", "🧨 Sistem Optimizasyonu!", "🎯 Matematiksel Ara!", 
    "🛑 Veri İşleme Durağı!", "💀 İstatistiksel Reset!", "📉 Sistem Kalibrasyonu!", "🪓 Veri Temizliği!",
    "🌀 Algoritma Güncellemesi!", "⚠️ Sistem Kontrolü!", "🧩 Veri Yeniden Yapılandırması!", "💢 Matematiksel Dengeleme!"
]

# Dengeli bekleme mesajları
WAITING_MESSAGES = [
    "⏳ Sistem Aktif…", "🔄 Veri İşleniyor…", "🕒 Matematiksel Hesaplama!", "👀 İstatistik Takibi!", 
    "🧭 Algoritma Çalışıyor…", "📡 Veri Akışı Bekleniyor…", "🌓 Sistem Dengesi…", 
    "🎛️ Olasılık Hesaplaması…", "📍 Kritik Veri Noktası…", "🔍 Matematiksel Analiz…", 
    "🧱 İstatistiksel Eşik…", "⚙️ Algoritma İşliyor…", "🧮 Veri Hesaplaması…", 
    "💭 Olasılık Değerlendirmesi…", "🔋 Sistem Yükleniyor…", "🎯 Matematiksel Hedef!", 
    "📡 Veri Alımı Aktif!", "🌙 İstatistiksel Bekleme…", "🪫 Sistem Optimizasyonu…", 
    "🔄 Veri Akışı!", "📌 Son Hesaplamalar!", "🧩 Matematiksel Tamamlama!", "📊 İstatistik Toplama…", 
    "🕹️ Sistem Kontrolü…", "🛠️ Algoritma Güncellemesi…", "🎬 Veri Senaryosu…"
]

# ==============================================================================
# RENK GRUPLARI ve DENGELİ SİSTEM
# ==============================================================================
RED_GROUP = {"♦️", "♥️"}
BLACK_GROUP = {"♣️", "♠️"}

# Dengeli dönüşüm kuralları - her renk diğer gruba
BALANCED_FLIP_RULES = {
    "♦️": BLACK_GROUP, "♥️": BLACK_GROUP, 
    "♣️": RED_GROUP, "♠️": RED_GROUP
}

# ==============================================================================
# YARDIMCI FONKSİYONLAR
# ==============================================================================

def get_current_time():
    """Şu anki saati istenen formatta döndürür"""
    return datetime.now().strftime("%H:%M:%S")

def clean_text(text):
    """Metni temizle ve normalize et"""
    return re.sub(r'\s+', ' ', text.replace('️','').replace('\u200b','')).strip()

def get_previous_game(current_game, back=BACK_SYSTEM_COUNT):
    """n oyunundan back kadar geriye git (döngüsel)"""
    previous = current_game - back
    while previous < 1:
        previous += MAX_GAME_NUMBER
    return previous

def get_next_game_number(current_game, step=1):
    """Sonraki oyun numarasını getir (döngüsel)"""
    next_game = current_game + step
    if next_game > MAX_GAME_NUMBER:
        next_game -= MAX_GAME_NUMBER
    elif next_game < 1:
        next_game += MAX_GAME_NUMBER
    return next_game

def extract_player_cards(text):
    """Parantez içindeki oyuncu kartlarını çıkar"""
    pattern = r'\((.*?)\)'
    matches = re.findall(pattern, text)
    
    if matches:
        player_cards = matches[0].replace(' ', '')
        # Sadece standart emoji formatını koru
        player_cards = (player_cards
                       .replace('♣','♣️').replace('♦','♦️')
                       .replace('♥','♥️').replace('♠','♠️'))
        logger.info(f"🎴 Kart çıkarıldı: {player_cards}")
        return player_cards
    return None

def player_has_arrow(text):
    """Ok kontrolü - 3. kart bekleniyor mu?"""
    arrow_patterns = ["👉", "➡️", "→", "▶", "⇒", "⟹"]
    has_arrow = any(pattern in text for pattern in arrow_patterns)
    if has_arrow:
        logger.info("⏳ 3. kart bekleniyor (ok tespit edildi)")
    return has_arrow

def suits_from_cards(card_string):
    """Kartlardan renkleri çıkar"""
    if not card_string:
        return []
    return re.findall(r'[♣♥♦♠]️?', card_string)

def get_first_card_suit(cards_string):
    """Oyuncunun ilk kartının rengini döndürür"""
    suits = suits_from_cards(cards_string)
    return suits[0] if suits else None

def get_middle_card_suit(cards_string):
    """Oyuncunun orta kartının rengini döndürür (en az 2 kart varsa)"""
    suits = suits_from_cards(cards_string)
    return suits[1] if len(suits) >= 2 else None

def get_last_card_suit(cards_string):
    """Oyuncunun son kartının rengini döndürür (en az 3 kart varsa)"""
    suits = suits_from_cards(cards_string)
    return suits[2] if len(suits) >= 3 else None

def get_balanced_opposite_suit(current_suit):
    """Dengeli zıt renk seçimi - inat durumlarına karşı"""
    if not current_suit:
        return None
    
    opposite_group = BALANCED_FLIP_RULES.get(current_suit)
    if opposite_group:
        # Dengeli dağılım için rastgele seçim
        return random.choice(list(opposite_group))
    return None

def get_random_win_message():
    """Rastgele kazanç mesajı seç"""
    return random.choice(WIN_MESSAGES)

def get_random_loss_message():
    """Rastgele kayıp mesajı seç"""
    return random.choice(LOSS_MESSAGES)

def get_random_waiting_message():
    """Rastgele bekleme mesajı seç"""
    return random.choice(WAITING_MESSAGES)

# ==============================================================================
# DENGELİ MARTINGALE SİSTEMİ
# ==============================================================================

async def update_martingale(current_game, player_cards_string):
    """Tüm aktif Martingale stratejilerini dengeli şekilde güncelle"""
    updated_count = 0
    
    for signal_key, info in list(martingale_tracker.items()):
        if info.get("checked"):
            continue
        
        bet_game = info["bet_game"]
        current_step = info["step"]
        
        # Beklenen oyunu hesapla: sinyal oyunu + step
        expected_game = get_next_game_number(bet_game, current_step)
        
        logger.info(f"🎯 Martingale kontrol: Oyun #{current_game}, Sinyal #{bet_game}, Step {current_step}, Beklenen: #{expected_game}")
        
        if current_game != expected_game:
            continue
            
        updated_count += 1
        signal_type = info.get("signal_type", "first")
        type_display = signal_type.capitalize()
        current_time = get_current_time()
        
        target_suit = info["suit"]
        if target_suit in player_cards_string:
            # KAZANILDI - ✅
            win_message = get_random_win_message()
            new_text = f"{current_time} | #N{bet_game} | {target_suit} - 7D | 53-BC-{type_display} | ✅ {STEP_EMOJIS[current_step]} | {win_message}"
            
            try:
                await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                logger.info(f"✅ #N{bet_game} KAZANÇ: Step {current_step}'de kazanıldı")
                info["checked"] = True
                
            except Exception as e:
                logger.error(f"❌ #N{bet_game} düzenlenirken hata: {e}")
        else:
            # KAYIP - bir sonraki step'e geç
            next_step = current_step + 1
            
            if next_step > MAX_MARTINGALE_STEP:
                # TAM KAYIP - ❌
                loss_message = get_random_loss_message()
                new_text = f"{current_time} | #N{bet_game} | {target_suit} - 7D | 53-BC-{type_display} | ❌ | {loss_message}"
                try:
                    await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                    logger.info(f"❌ #N{bet_game} KAYIP: Maksimum step aşıldı")
                    info["checked"] = True
                    
                except Exception as e:
                    logger.error(f"❌ #N{bet_game} düzenlenirken hata: {e}")
            else:
                # BİR SONRAKİ ADIM - step güncelle
                info["step"] = next_step
                waiting_message = get_random_waiting_message()
                new_text = f"{current_time} | #N{bet_game} | {target_suit} - 7D | 53-BC-{type_display} | 🔃 {STEP_EMOJIS[next_step]} | {waiting_message}"
                try:
                    await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                    logger.info(f"🔄 #N{bet_game} STEP GÜNCELLENDİ: {current_step} → {next_step}")
                    
                except Exception as e:
                    logger.error(f"❌ #N{bet_game} düzenlenirken hata: {e}")
    
    if updated_count > 0:
        logger.info(f"📊 Martingale güncelleme: {updated_count} sinyal işlendi")

# ==============================================================================
# DENGELİ SİNYAL YÖNETİMİ
# ==============================================================================

async def send_balanced_signal(signal_game, signal_suit, signal_type):
    """Dengeli sinyal gönderme - herhangi bir kısıtlama yok"""
    signal_key = f"{signal_game}_{signal_type}"
    
    if signal_key in sent_signals:
        logger.debug(f"📨 Sinyal zaten gönderilmiş: {signal_key}")
        return False
    
    type_display = signal_type.capitalize()
    waiting_message = get_random_waiting_message()
    current_time = get_current_time()
    
    # DENGELİ SİNYAL FORMATI
    text = f"{current_time} | #N{signal_game} | {signal_suit} - 7D | 53-BC-{type_display} | 🔃 {STEP_EMOJIS[0]} | {waiting_message}"
    
    try:
        sent = await client.send_message(KANAL_HEDEF, text)
        sent_signals.add(signal_key)
        
        martingale_tracker[signal_key] = {
            "msg_id": sent.id,
            "bet_game": signal_game,
            "suit": signal_suit, 
            "step": 0,
            "checked": False,
            "signal_type": signal_type
        }
        
        logger.info(f"🎯 DENGELİ SİNYAL: #N{signal_game} | {signal_suit} - 7D | 53-BC-{type_display}")
        return True
    except Exception as e:
        logger.error(f"❌ Sinyal gönderilemedi: {e}")
        return False

# ==============================================================================
# 53-OYUN DENGELİ GERİ SİSTEM
# ==============================================================================

async def check_53_balanced_system(current_game, current_player_cards):
    """53 oyun geri dengeli sistem - hiçbir kısıtlama yok"""
    previous_game_53 = get_previous_game(current_game, BACK_SYSTEM_COUNT)
    
    if previous_game_53 not in player_results:
        return
    
    previous_player_cards = player_results[previous_game_53]
    
    # TÜM KART POZİSYONLARI EŞIT ÖNEMDE
    checks = [
        ("first", get_first_card_suit(current_player_cards), get_first_card_suit(previous_player_cards)),
        ("middle", get_middle_card_suit(current_player_cards), get_middle_card_suit(previous_player_cards)),
        ("last", get_last_card_suit(current_player_cards), get_last_card_suit(previous_player_cards))
    ]
    
    for signal_type, current_suit, previous_suit in checks:
        if current_suit and previous_suit and current_suit == previous_suit:
            signal_source_game = get_next_game_number(previous_game_53, 1)
            if signal_source_game in player_results:
                source_cards = player_results[signal_source_game]
                source_suit = None
                
                if signal_type == "first":
                    source_suit = get_first_card_suit(source_cards)
                elif signal_type == "middle":
                    source_suit = get_middle_card_suit(source_cards)
                elif signal_type == "last":
                    source_suit = get_last_card_suit(source_cards)
                
                if source_suit:
                    signal_suit = get_balanced_opposite_suit(source_suit)
                    signal_game = get_next_game_number(previous_game_53, BACK_SYSTEM_COUNT + 1)
                    if signal_suit:
                        await send_balanced_signal(signal_game, signal_suit, signal_type)
                        logger.info(f"🎯 {signal_type.upper()} pozisyonu sinyal üretti: #{signal_game} -> {signal_suit}")

# ==============================================================================
# ANA MESAJ HANDLER
# ==============================================================================

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def balanced_handler(event):
    """Dengeli mesaj işleme handler'ı"""
    msg = event.message
    if not msg or not msg.text:
        return

    text = clean_text(msg.text)
    
    # Oyun numarası tespiti
    game_number_patterns = [
        r'(?:#N|№|#)\s*(\d+)',
        r'Game\s*[:]?\s*(\d+)',
        r'Oyun\s*[:]?\s*(\d+)'
    ]
    
    game_number = None
    for pattern in game_number_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            game_number = int(match.group(1))
            break
    
    if not game_number:
        return

    if game_number < 1 or game_number > MAX_GAME_NUMBER:
        return

    player_cards = extract_player_cards(text)
    if not player_cards:
        return

    # 3. kart bekleniyorsa sessizce bekle
    if player_has_arrow(text):
        return

    player_results[game_number] = player_cards
    logger.info(f"💾 #{game_number} kaydedildi: {player_cards}")

    # 1) Martingale güncelleme
    await update_martingale(game_number, player_cards)

    # 2) 53-back dengeli stratejisini çalıştır
    try:
        await check_53_balanced_system(game_number, player_cards)
    except Exception as e:
        logger.error(f"❌ 53-back dengeli stratejisinde hata: {e}")

# ==============================================================================
# SİSTEM BAŞLATMA
# ==============================================================================

async def main():
    """Ana başlatma fonksiyonu"""
    logger.info("🎯 DENGELİ BACCARAT BOT v53 BAŞLATILIYOR...")
    logger.info("✅ HERHANGİ BİR KISITLAMA YOK - TÜM POZİSYONLAR AKTİF!")
    
    await client.start()
    
    startup_msg = (
        f"🤖 DENGELİ BOT AKTİF - HER POZİSYON EŞIT! 🚀\n"
        f"⏰ Başlangıç: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"🎯 Strateji: 53-back DENGELİ (3 kart pozisyonu)\n"
        f"⚡ Martingale: SABİT 7D - Emoji ilerler (0️⃣→7️⃣)\n"
        f"💎 Mesajlar: {len(WIN_MESSAGES)} kazanç, {len(LOSS_MESSAGES)} kayıp, {len(WAITING_MESSAGES)} bekleme\n"
        f"🃏 Kartlar: ♥️♦️♣️♠️ tam deste - İnat durumlarına karşı dengeli"
    )
    logger.info(startup_msg)
    
    logger.info("🟢 Dengeli bot çalışmaya hazır - tüm pozisyonlar aktif...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot manuel durduruldu.")
    except Exception as e:
        logger.error(f"❌ Genel hata: {e}")
    finally:
        logger.info("🔴 Bot sonlandırıldı.")