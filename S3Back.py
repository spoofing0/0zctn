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

client = TelegramClient('baccarat_final_bot_v38', API_ID, API_HASH)

# ==============================================================================
# SİSTEM SABİTLERİ
# ==============================================================================
MAX_GAME_NUMBER = 1440
MAX_MARTINGALE_STEP = 7  # 7D sabit
BACK_SYSTEM_COUNT = 53  # 10 yerine 53 back sistemi

# ==============================================================================
# DURUM DEPOLARI
# ==============================================================================
player_results = {}        # {game_num: "cards string"}
martingale_tracker = {}    # {signal_key: {msg_id, bet_game, suit, step, checked, signal_type}}
sent_signals = set()

# ==============================================================================
# EMOJİ ve MESAJ KÜTÜPHANESİ
# ==============================================================================

# Step emojileri - ilerleyen kısım
STEP_EMOJIS = {
    0: "0️⃣", 1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 
    4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣"
}

# Kazanç mesajları
WIN_MESSAGES = [
    "🔥 Çat Diye Geldi!", "💎 Temiz İş!", "🎯 Tam İsabet!", "⚡ Nokta Atışı!", 
    "💥 Net Vuruş!", "🏆 Gümbür Gümbür!", "🚀 Jet Gibi Geldi!", "🏆 Altın Vuruş!",
    "🔥 Elite Win!", "🚀 Kusursuz Kazanç!", "🎯 Pro Seviye İsabet!", "💥 Patlattık!",
    "🧨 Çatladı Geldi!", "🚀 Roketledi!", "🎉 Bingo!", "🎯 Tahmin Doğrulandı.",
    "💎 Hedef Gerçekleşti.", "🔥 Beklenen Oldu.", "⚡ Fırtına Gibi Geldi!", 
    "💎 Kusursuz Tuttu!", "🎯 Direkt 12'den!", "💥 Çiviledik!", "🏹 Hedefi Vurduk!",
    "📌 Nokta Koyduk!", "🔒 Kilidi Açtık!", "💣 Bombayı Patlattık!", "🔥 Ayakta Alkışlanır!",
    "⚡ Şimşek Etkisi!", "💎 Taş Gibi İsabet!", "🌪️ Kasırga Gibi!", "🎉 Jackpot Gibi!",
    "🔥 Sıfır Hata!", "🚀 Turbo Etki!", "🏹 Tek Atış Tek Vuruş!", "💥 Bam! Diye Geldi!",
    "🎖️ Zafer Geldi!", "💎 Elmas Kalite İsabet!", "💫 Yıldız Gibi Parladı!", 
    "🎉 Güm Güm Geldi!", "🔥 Masaya Yumruğu Koyduk!", "🚀 Uçuşa Geçti!", 
    "🏆 Büyük Zafer!", "💥 Sıkı Darbe!", "⚡ Kıvılcım Gibi Çaktı!", 
    "🔥 Alev Alev Geldi!", "🎯 İsabetle Sonuçlandı!", "🚀 Tavan Yaptı!", 
    "💎 Kristal Netliğinde Tuttu!"
]

# Kayıp mesajları
LOSS_MESSAGES = [
    "❌ Kaçırdı!", "💢 Iska Geçti!", "🔻 Yere Çakıldı!", "🔥 Söndü Kaldı!", 
    "⚠️ Olmadı Bu!", "💥 Dağıldı Gitti!", "🌑 Karanlıkta Kaldı!", "📉 Çöküş Yaşadı!",
    "🚫 Hedefe Ulaşamadı!", "🩸 Kan Kaybetti!", "💔 Tutmadı!", "🌫️ Buhar Oldu Gitti!",
    "⚡ Çarpıldı Kaldı!", "🔧 Arıza Verdi!", "💣 Patladı Ama İşe Yaramadı!", 
    "🎭 Maskesi Düştü!", "🧊 Dondu Kaldı!", "📌 Sapa Sattı!", "🕳️ Boşa Düştü!",
    "🚷 Yolu Kapandı!", "🧨 Erken Patladı!", "🎯 Hedefin Yanından Geçti!", 
    "🛑 Durdu Kaldı!", "💀 Bitti Gitti!", "📉 Dibe Vurdu!", "🪓 Kesildi!", 
    "🌀 Tutunamadı!", "⚠️ Geri Döndü!", "🧩 Parçalar Uymadı!", "💢 Duvara Tosladı!"
]

# Bekleme mesajları
WAITING_MESSAGES = [
    "⏳ Devam Ediyor…", "🔄 Süreç İşliyor…", "🕒 Takipte!", "👀 İzlemede!", 
    "🧭 Yolculuk Sürüyor…", "📡 Sinyal Bekleniyor…", "🌓 Dengede Duruyor…", 
    "🎛️ Ayar Tutuyor…", "📍 Kritik Eşikte…", "🔍 İnceleme Devam Ediyor…", 
    "🧱 Kırılma Anı Yaklaşıyor…", "⚙️ Mekanizma Çalışıyor…", "🧮 Hesaplamalar Sürüyor…", 
    "💭 Belirsizlik Devam Ediyor…", "🔋 Yükleniyor…", "🎯 Hedefe Yakın!", 
    "📡 Radar Açık!", "🌙 Sessizlik Sürmekte…", "🪫 Düşük Ama Devam!", 
    "🔄 Akışta!", "📌 Son Anlar!", "🧩 Tamamlanmak Üzere!", "📊 Veriler Toplanıyor…", 
    "🕹️ Süreç Kontrol Altında…", "🛠️ Hazırlık Yapılıyor…", "🎬 Sahne Kuruluyor…"
]

# ==============================================================================
# RENK GRUPLARI ve DÖNÜŞÜM KURALLARI
# ==============================================================================
RED_GROUP = {"♦️", "♥️", "♦", "♥"}
BLACK_GROUP = {"♣️", "♠️", "♣", "♠"}

GROUP_FLIP_RULES = {
    "♦️": BLACK_GROUP, "♥️": BLACK_GROUP, 
    "♣️": RED_GROUP, "♠️": RED_GROUP,
    "♦": BLACK_GROUP, "♥": BLACK_GROUP,
    "♣": RED_GROUP, "♠": RED_GROUP
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
        # Emoji formatını standardize et
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

def get_opposite_group_suit(current_suit):
    """Mevcut renkten zıt gruptan bir renk seç"""
    if not current_suit:
        return None
    
    opposite_group = GROUP_FLIP_RULES.get(current_suit)
    if opposite_group:
        return "♦️" if "♦️" in opposite_group else "♣️"
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
# MARTINGALE SİSTEMİ
# ==============================================================================

async def update_martingale(current_game, player_cards_string):
    """Tüm aktif Martingale stratejilerini güncelle"""
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
# SİNYAL YÖNETİMİ
# ==============================================================================

async def send_signal(signal_game, signal_suit, signal_type):
    """Sinyal gönderme"""
    signal_key = f"{signal_game}_{signal_type}"
    
    if signal_key in sent_signals:
        logger.debug(f"📨 Sinyal zaten gönderilmiş: {signal_key}")
        return False
    
    type_display = signal_type.capitalize()
    waiting_message = get_random_waiting_message()
    current_time = get_current_time()
    
    # GÜNCELLENMİŞ SİNYAL FORMATI: 14:30:15 | #N419 | ♣️ - 7D | 53-BC-Middle | 🔃 0️⃣ | Devam Ediyor…
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
        
        logger.info(f"🎯 YENİ SİNYAL: #N{signal_game} | {signal_suit} - 7D | 53-BC-{type_display}")
        return True
    except Exception as e:
        logger.error(f"❌ Sinyal gönderilemedi: {e}")
        return False

# ==============================================================================
# 53-OYUN GERİ SİSTEMİ
# ==============================================================================

async def check_53_game_back_system(current_game, current_player_cards):
    """53 oyun geri sistemi"""
    previous_game_53 = get_previous_game(current_game, BACK_SYSTEM_COUNT)
    
    if previous_game_53 not in player_results:
        return
    
    previous_player_cards = player_results[previous_game_53]
    
    # İlk Kart Eşleşmesi
    current_first_suit = get_first_card_suit(current_player_cards)
    previous_first_suit = get_first_card_suit(previous_player_cards)
    
    if current_first_suit and previous_first_suit and current_first_suit == previous_first_suit:
        signal_source_game = get_next_game_number(previous_game_53, 1)
        if signal_source_game in player_results:
            signal_source_first_suit = get_first_card_suit(player_results[signal_source_game])
            if signal_source_first_suit:
                signal_suit = get_opposite_group_suit(signal_source_first_suit)
                signal_game = get_next_game_number(previous_game_53, BACK_SYSTEM_COUNT + 1)
                if signal_suit:
                    await send_signal(signal_game, signal_suit, "first")

    # Orta Kart Eşleşmesi
    current_middle_suit = get_middle_card_suit(current_player_cards)
    previous_middle_suit = get_middle_card_suit(previous_player_cards)
    
    if current_middle_suit and previous_middle_suit and current_middle_suit == previous_middle_suit:
        signal_source_game = get_next_game_number(previous_game_53, 1)
        if signal_source_game in player_results:
            signal_source_middle_suit = get_middle_card_suit(player_results[signal_source_game])
            if signal_source_middle_suit:
                signal_suit = get_opposite_group_suit(signal_source_middle_suit)
                signal_game = get_next_game_number(previous_game_53, BACK_SYSTEM_COUNT + 1)
                if signal_suit:
                    await send_signal(signal_game, signal_suit, "middle")

    # Son Kart Eşleşmesi
    current_last_suit = get_last_card_suit(current_player_cards)
    previous_last_suit = get_last_card_suit(previous_player_cards)
    
    if current_last_suit and previous_last_suit and current_last_suit == previous_last_suit:
        signal_source_game = get_next_game_number(previous_game_53, 1)
        if signal_source_game in player_results:
            signal_source_last_suit = get_last_card_suit(player_results[signal_source_game])
            if signal_source_last_suit:
                signal_suit = get_opposite_group_suit(signal_source_last_suit)
                signal_game = get_next_game_number(previous_game_53, BACK_SYSTEM_COUNT + 1)
                if signal_suit:
                    await send_signal(signal_game, signal_suit, "last")

# ==============================================================================
# ANA MESAJ HANDLER
# ==============================================================================

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handler(event):
    """Ana mesaj işleme handler'ı"""
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

    # 3. kart bekleniyorsa sessizce bekle (MESAJ GÖNDERME)
    if player_has_arrow(text):
        return

    player_results[game_number] = player_cards
    logger.info(f"💾 #{game_number} kaydedildi: {player_cards}")

    # 1) Martingale güncelleme
    await update_martingale(game_number, player_cards)

    # 2) 53-back stratejisini çalıştır
    try:
        await check_53_game_back_system(game_number, player_cards)
    except Exception as e:
        logger.error(f"❌ 53-back stratejisinde hata: {e}")

# ==============================================================================
# SİSTEM BAŞLATMA
# ==============================================================================

async def main():
    """Ana başlatma fonksiyonu"""
    logger.info("🎯 BACCARAT BOT v38 BAŞLATILIYOR...")
    logger.info("✅ SADECE SİNYAL MESAJLARI AKTİF!")
    
    await client.start()
    
    startup_msg = (
        f"🤖 BOT AKTİF - SADECE SİNYAL MESAJLARI! 🚀\n"
        f"⏰ Başlangıç: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"🎯 Strateji: 53-back (3 kart pozisyonu)\n"
        f"⚡ Martingale: SABİT 7D - Emoji ilerler (0️⃣→7️⃣)\n"
        f"💎 Mesajlar: {len(WIN_MESSAGES)} kazanç, {len(LOSS_MESSAGES)} kayıp, {len(WAITING_MESSAGES)} bekleme"
    )
    logger.info(startup_msg)
    
    logger.info("🟢 Bot çalışmaya hazır - mesajlar bekleniyor...")
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