# -*- coding: utf-8 -*-
import re
import asyncio
import random
import logging
import json
import os
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
# TELEGRAM API BİLGİLERİ ve KANAL AYARLARI (KENDİ BİLGİLERİNLE DEĞİŞTİR)
# ==============================================================================
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@kbbbaccarat_bot"

client = TelegramClient('kbbbaccarat', API_ID, API_HASH)

# ==============================================================================
# SİSTEM SABİTLERİ
# ==============================================================================
MAX_GAME_NUMBER = 1440
MAX_MARTINGALE_STEP = 7  # 7D sabit

# ==============================================================================
# BACK SİSTEMLERİ - SADECE 5, 6 ve 7
# ==============================================================================
BACK_SYSTEMS = [5, 6, 7]   # 5, 6 ve 7 back sistemleri aktif

# ==============================================================================
# DURUM DEPOLARI
# ==============================================================================
player_results = {}        # {game_num: "cards string"}
martingale_tracker = {}    # {signal_key: {msg_id, bet_game, suit, step, checked, signal_type, position}}
sent_signals = set()

# ==============================================================================
# İSTATİSTİK DEPOLARI
# ==============================================================================
position_stats = {
    "first": {"total": 0, "won": 0, "lost": 0},
    "middle": {"total": 0, "won": 0, "lost": 0},
    "last": {"total": 0, "won": 0, "lost": 0}
}

STATS_FILE = "position_stats.json"

def load_stats():
    """Dosyadan istatistikleri yükle"""
    global position_stats
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Yapıyı kontrol et
                if all(k in loaded for k in ["first", "middle", "last"]):
                    position_stats = loaded
                    logger.info("📂 İstatistikler dosyadan yüklendi.")
        except Exception as e:
            logger.error(f"❌ İstatistikler yüklenemedi: {e}")

def save_stats():
    """İstatistikleri dosyaya kaydet"""
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(position_stats, f, indent=2, ensure_ascii=False)
        logger.debug("💾 İstatistikler dosyaya kaydedildi.")
    except Exception as e:
        logger.error(f"❌ İstatistikler kaydedilemedi: {e}")

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
# YARDIMCI FONKSİYONLAR (GÜÇLENDİRİLMİŞ)
# ==============================================================================

def get_current_time():
    """Şu anki saati istenen formatta döndürür"""
    return datetime.now().strftime("%H:%M:%S")

def clean_text(text):
    """Metni temizle ve normalize et"""
    return re.sub(r'\s+', ' ', text.replace('️','').replace('\u200b','')).strip()

def get_previous_game(current_game, back):
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
    """Parantez içindeki oyuncu kartlarını çıkar - geliştirilmiş"""
    pattern = r'\((.*?)\)'
    matches = re.findall(pattern, text)
    
    if matches:
        # Tüm boşlukları, virgülleri ve gereksiz karakterleri kaldır
        raw = re.sub(r'[\s,;]+', '', matches[0])
        # Renk emojilerini normalize et (bazı mesajlarda farklı olabilir)
        raw = (raw.replace('♣', '♣️').replace('♦', '♦️')
                  .replace('♥', '♥️').replace('♠', '♠️'))
        logger.info(f"🎴 Kart çıkarıldı: {raw}")
        return raw
    return None

def player_has_arrow(text):
    """Ok kontrolü - 3. kart bekleniyor mu?"""
    arrow_patterns = ["👉", "➡️", "→", "▶", "⇒", "⟹"]
    has_arrow = any(pattern in text for pattern in arrow_patterns)
    if has_arrow:
        logger.info("⏳ 3. kart bekleniyor (ok tespit edildi)")
    return has_arrow

def suits_from_cards(card_string):
    """
    Kart dizisinden tüm renkleri çıkarır.
    Hem normal sembol (♣) hem emoji (♣️) formatını destekler.
    """
    if not card_string:
        return []
    suits = []
    i = 0
    while i < len(card_string):
        char = card_string[i]
        if char in '♣♥♦♠':
            if i + 1 < len(card_string) and card_string[i+1] == '️':
                suits.append(char + '️')
                i += 2
            else:
                suits.append(char)
                i += 1
        else:
            i += 1
    return suits

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
        return random.choice(list(opposite_group))
    return None

def get_random_win_message():
    return random.choice(WIN_MESSAGES)

def get_random_loss_message():
    return random.choice(LOSS_MESSAGES)

def get_random_waiting_message():
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
            new_text = f"{current_time} | #N{bet_game} | {target_suit} - 7D | {type_display} | ✅ {STEP_EMOJIS[current_step]} | {win_message}"
            
            try:
                await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                logger.info(f"✅ #N{bet_game} KAZANÇ: Step {current_step}'de kazanıldı")
                info["checked"] = True
                
                # İstatistik güncelle - kazanç
                position = info.get("position")
                if position and position in position_stats:
                    position_stats[position]["won"] += 1
                    logger.info(f"📊 {position} kazanç: {position_stats[position]['won']}/{position_stats[position]['total']}")
                
            except Exception as e:
                logger.error(f"❌ #N{bet_game} düzenlenirken hata: {e}")
        else:
            # KAYIP - bir sonraki step'e geç
            next_step = current_step + 1
            
            if next_step > MAX_MARTINGALE_STEP:
                # TAM KAYIP - ❌
                loss_message = get_random_loss_message()
                new_text = f"{current_time} | #N{bet_game} | {target_suit} - 7D | {type_display} | ❌ | {loss_message}"
                try:
                    await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                    logger.info(f"❌ #N{bet_game} KAYIP: Maksimum step aşıldı")
                    info["checked"] = True
                    
                    # İstatistik güncelle - kayıp
                    position = info.get("position")
                    if position and position in position_stats:
                        position_stats[position]["lost"] += 1
                        logger.info(f"📊 {position} kayıp: {position_stats[position]['lost']}/{position_stats[position]['total']}")
                    
                except Exception as e:
                    logger.error(f"❌ #N{bet_game} düzenlenirken hata: {e}")
            else:
                # BİR SONRAKİ ADIM - step güncelle
                info["step"] = next_step
                waiting_message = get_random_waiting_message()
                new_text = f"{current_time} | #N{bet_game} | {target_suit} - 7D | {type_display} | 🔃 {STEP_EMOJIS[next_step]} | {waiting_message}"
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
    """Dengeli sinyal gönderme"""
    signal_key = f"{signal_game}_{signal_type}"
    
    if signal_key in sent_signals:
        logger.debug(f"📨 Sinyal zaten gönderilmiş: {signal_key}")
        return False
    
    type_display = signal_type.capitalize()
    waiting_message = get_random_waiting_message()
    current_time = get_current_time()
    
    text = f"{current_time} | #N{signal_game} | {signal_suit} - 7D | {type_display} | 🔃 {STEP_EMOJIS[0]} | {waiting_message}"
    
    try:
        sent = await client.send_message(KANAL_HEDEF, text)
        sent_signals.add(signal_key)
        
        # İstatistik güncelle - sinyal tipinden pozisyonu ayır
        position = signal_type.split('-')[-1]  # "first", "middle" veya "last"
        if position in position_stats:
            position_stats[position]["total"] += 1
            logger.info(f"📊 İstatistik güncellendi: {position} toplam={position_stats[position]['total']}")
        
        martingale_tracker[signal_key] = {
            "msg_id": sent.id,
            "bet_game": signal_game,
            "suit": signal_suit, 
            "step": 0,
            "checked": False,
            "signal_type": signal_type,
            "position": position
        }
        
        logger.info(f"🎯 DENGELİ SİNYAL: #N{signal_game} | {signal_suit} - 7D | {type_display}")
        return True
    except Exception as e:
        logger.error(f"❌ Sinyal gönderilemedi: {e}")
        return False

# ==============================================================================
# GENEL BACK SİSTEMİ FONKSİYONU (5,6,7 için)
# ==============================================================================

async def check_back_system(current_game, current_player_cards, back_value, system_prefix):
    """Belirli bir back değeri için dengeli sistem kontrolü"""
    previous_game = get_previous_game(current_game, back_value)
    
    if previous_game not in player_results:
        logger.info(f"⚠️ Back={back_value}: previous_game #{previous_game} kayıtlı değil, atlanıyor.")
        return
    
    previous_player_cards = player_results[previous_game]
    
    logger.info(f"🔍 Back={back_value} kontrol: current_game=#{current_game}, previous_game=#{previous_game}")
    logger.info(f"   current_cards={current_player_cards}, previous_cards={previous_player_cards}")
    
    checks = [
        ("first", get_first_card_suit(current_player_cards), get_first_card_suit(previous_player_cards)),
        ("middle", get_middle_card_suit(current_player_cards), get_middle_card_suit(previous_player_cards)),
        ("last", get_last_card_suit(current_player_cards), get_last_card_suit(previous_player_cards))
    ]
    
    for position, current_suit, previous_suit in checks:
        logger.info(f"   {position}: current_suit={current_suit}, previous_suit={previous_suit}")
        
        if current_suit and previous_suit:
            if current_suit == previous_suit:
                logger.info(f"   ✅ {position} eşleşti!")
                source_game = get_next_game_number(previous_game, 1)
                if source_game in player_results:
                    source_cards = player_results[source_game]
                    source_suit = None
                    if position == "first":
                        source_suit = get_first_card_suit(source_cards)
                    elif position == "middle":
                        source_suit = get_middle_card_suit(source_cards)
                    elif position == "last":
                        source_suit = get_last_card_suit(source_cards)
                    
                    if source_suit:
                        signal_suit = get_balanced_opposite_suit(source_suit)
                        signal_game = get_next_game_number(current_game, 1)
                        if signal_suit:
                            signal_type = f"{system_prefix}-{position}"
                            await send_balanced_signal(signal_game, signal_suit, signal_type)
                            logger.info(f"🎯 {signal_type} sinyal üretti: #{signal_game} -> {signal_suit} (back={back_value})")
                        else:
                            logger.info(f"   ⚠️ {position}: zıt renk bulunamadı")
                    else:
                        logger.info(f"   ⚠️ {position}: source_game #{source_game}'da {position} rengi yok")
                else:
                    logger.info(f"   ⚠️ {position}: source_game #{source_game} kayıtlı değil")
            else:
                logger.info(f"   ❌ {position} eşleşmedi")
        else:
            logger.info(f"   ⚠️ {position} eksik: current_suit={current_suit}, previous_suit={previous_suit}")

# ==============================================================================
# STATS KOMUTU HANDLER
# ==============================================================================

@client.on(events.NewMessage(pattern=r'^/stats$'))
async def stats_handler(event):
    """İstatistikleri göster - sadece hedef kanalda veya özel mesajda çalışır"""
    # İsteğe bağlı: sadece hedef kanalda çalışmasını istersen
    if event.chat_id != KANAL_HEDEF and event.chat_id != (await client.get_me()).id:
        return
    
    lines = ["📊 **POZİSYON İSTATİSTİKLERİ**\n"]
    for position, stats in position_stats.items():
        total = stats["total"]
        won = stats["won"]
        lost = stats["lost"]
        success_rate = (won / total * 100) if total > 0 else 0
        pending = total - (won + lost)
        lines.append(
            f"**{position.capitalize()}**\n"
            f"  🎯 Toplam: {total}\n"
            f"  ✅ Kazanç: {won}\n"
            f"  ❌ Kayıp: {lost}\n"
            f"  ⏳ Bekleyen: {pending}\n"
            f"  📈 Başarı: %{success_rate:.1f}\n"
        )
    
    active = sum(1 for info in martingale_tracker.values() if not info.get("checked"))
    lines.append(f"\n🔄 Takip edilen aktif sinyal: {active}")
    
    stats_text = "\n".join(lines)
    await event.reply(stats_text)

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

    if player_has_arrow(text):
        return

    player_results[game_number] = player_cards
    logger.info(f"💾 #{game_number} kaydedildi: {player_cards}")

    await update_martingale(game_number, player_cards)

    for back_value in BACK_SYSTEMS:
        try:
            system_prefix = f"{back_value}-BC"
            await check_back_system(game_number, player_cards, back_value, system_prefix)
        except Exception as e:
            logger.error(f"❌ {back_value}-back sisteminde hata: {e}")

# ==============================================================================
# SİSTEM BAŞLATMA
# ==============================================================================

async def main():
    """Ana başlatma fonksiyonu"""
    logger.info("🎯 DENGELİ BACCARAT BOT v53 (STATS EKLENMİŞ) BAŞLATILIYOR...")
    logger.info(f"✅ AKTİF BACK SİSTEMLERİ: {BACK_SYSTEMS}")
    logger.info("✅ TÜM POZİSYONLAR AKTİF: first, middle, last")
    logger.info("✅ /stats komutu eklendi.")
    
    load_stats()  # İstatistikleri yükle
    
    await client.start()
    
    startup_msg = (
        f"🤖 DENGELİ BOT AKTİF - 5-6-7 BACK SİSTEMLERİ! 🚀\n"
        f"⏰ Başlangıç: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"🎯 Strateji: {BACK_SYSTEMS}-back DENGELİ (first/middle/last)\n"
        f"⚡ Martingale: SABİT 7D - Emoji ilerler (0️⃣→7️⃣)\n"
        f"📊 /stats komutu ile anlık istatistikleri görebilirsiniz.\n"
        f"💎 Mesajlar: {len(WIN_MESSAGES)} kazanç, {len(LOSS_MESSAGES)} kayıp, {len(WAITING_MESSAGES)} bekleme\n"
        f"🃏 Kartlar: ♥️♦️♣️♠️ tam deste - Gelişmiş renk ayrıştırıcı aktif"
    )
    logger.info(startup_msg)
    
    logger.info("🟢 Dengeli bot çalışmaya hazır - logları izleyin...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot manuel durduruldu.")
    except Exception as e:
        logger.error(f"❌ Genel hata: {e}")
    finally:
        save_stats()  # İstatistikleri kaydet
        logger.info("🔴 Bot sonlandırıldı.")
