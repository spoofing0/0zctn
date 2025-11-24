# -*- coding: utf-8 -*-
import re
import asyncio
from telethon import TelegramClient, events
import logging
from datetime import datetime

# Logging ayarı
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('baccarat_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

API_ID = 27518940
API_HASH = '30b6658a1870f8462108130783fef14f'

# --- Kanal Bilgileri ---
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@kbubakara"
client = TelegramClient('baccarat_final_bot_v37', API_ID, API_HASH)

# -------------------------
# Durum depoları
# -------------------------
player_results = {}        # {game_num: "cards string"}
martingale_tracker = {}    # {signal_key: {msg_id, bet_game, suit, step, checked, signal_type, strategy}}
sent_signals = set()
MAX_GAME_NUMBER = 1440
MAX_MARTINGALE_STEP = 7
step_emojis = {0:"0️⃣",1:"1️⃣",2:"2️⃣",3:"3️⃣",4:"4️⃣",5:"5️⃣",6:"6️⃣",7:"7️⃣"}

# Felaket Sistemi için suit tracker
suit_tracker = {
    '♦️': {'count': 0, 'last_seen': 0},
    '♥️': {'count': 0, 'last_seen': 0},
    '♠️': {'count': 0, 'last_seen': 0},
    '♣️': {'count': 0, 'last_seen': 0}
}

# Renk çevirme kuralları
suit_flip = {"♣️": "♦️", "♦️": "♣️", "♥️": "♠️", "♠️": "♥️",
             "♣":"♦️","♦":"♣️","♥":"♠️","♠":"♥️"}

# -------------------------
# Helper fonksiyonlar
# -------------------------
def clean_text(t):
    """Metni temizle"""
    return re.sub(r'\s+', ' ', t.replace('️','').replace('\u200b','')).strip()

def get_previous_game(n, back=10):
    """n oyunundan back kadar geriye git (döngüsel)"""
    r = n - back
    while r < 1:
        r += MAX_GAME_NUMBER
    return r

def get_next_game_number(n, step=1):
    """Sonraki oyun numarasını getir"""
    n = int(n) + step
    if n > MAX_GAME_NUMBER:
        n -= MAX_GAME_NUMBER
    elif n < 1:
        n += MAX_GAME_NUMBER
    return n

def extract_player_cards(text):
    """SADECE oyuncu kartlarını çıkar - banker kartlarını görmezden gel"""
    patterns = [
        r'\((.*?)\)',  # Normal parantez
        r'Player\s*[:]?\s*([♣♥♦♠️\s]+)',  # Sadece Player
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            if isinstance(matches[0], tuple):
                player_cards = matches[0][0].replace(' ', '')
            else:
                player_cards = matches[0].replace(' ', '')
            
            # normalize variants to emoji form
            player_cards = player_cards.replace('♣','♣️').replace('♦','♦️').replace('♥','♥️').replace('♠','♠️')
            return player_cards
    
    return None

def player_has_arrow(text):
    """Ok kontrolü - 3. kart bekleniyor mu? SADECE BANKER İÇİN OLAN OKLARI GÖRMEZDEN GEL"""
    # Önce oyuncu kartlarını al
    player_cards = extract_player_cards(text)
    if not player_cards:
        return False
    
    # Oyuncu kart sayısını kontrol et (2 kart ise 3. kart beklenmiyor demektir)
    suits = suits_from_cards(player_cards)
    if len(suits) == 2:
        return False  # Oyuncunun 2 kartı varsa 3. kart beklenmiyor
    
    # Eğer oyuncunun 3 kartı varsa, ok işareti olsa bile 3. kart açılmış demektir
    if len(suits) == 3:
        return False  # 3. kart zaten açılmış
    
    # Eğer oyuncunun 1 kartı varsa veya kart sayısı belirsizse, ok kontrolü yap
    arrow_patterns = ["👉", "➡️", "→", "▶", "⇒", "⟹"]
    return any(pattern in text for pattern in arrow_patterns)

def suits_from_cards(card_str):
    """Kartlardan renkleri çıkar - 2 veya 3 kartlı durumlar için"""
    if not card_str:
        return []
    # Hem emoji hem de normal sembolleri yakala
    suits = re.findall(r'[♣♥♦♠]️?', card_str)
    # Normalize et
    normalized_suits = []
    for suit in suits:
        if suit in ['♣', '♣️']:
            normalized_suits.append('♣️')
        elif suit in ['♦', '♦️']:
            normalized_suits.append('♦️')
        elif suit in ['♥', '♥️']:
            normalized_suits.append('♥️')
        elif suit in ['♠', '♠️']:
            normalized_suits.append('♠️')
    return normalized_suits

def get_first_card_suit(cards_str):
    """Oyuncunun ilk kartının rengini döndürür - 2 veya 3 kartlı durumlar için"""
    suits = suits_from_cards(cards_str)
    return suits[0] if suits else None

def get_middle_card_suit(cards_str):
    """Oyuncunun orta kartının rengini döndürür (en az 2 kart varsa)"""
    suits = suits_from_cards(cards_str)
    return suits[1] if len(suits) >= 2 else None

# -------------------------
# Martingale Sistemi (0-7)
# -------------------------
async def update_martingale(current_game, player_cards_str):
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
        
        # Sadece beklenen oyun numarası eşleşirse işlem yap
        if current_game != expected_game:
            continue
            
        updated_count += 1
        
        # Renk kontrolü - info["suit"] player_cards_str içinde var mı?
        if info["suit"] in player_cards_str:
            # KAZANILDI - ✅
            new_text = f"#N{bet_game} | {info['suit']} - 7D | {info['strategy']} | ✅ {step_emojis[current_step]}"
            try:
                await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                logger.info(f"✅ #N{bet_game} KAZANÇ: Step {current_step}'de kazanıldı - {info['suit']} | {info['strategy']}")
                info["checked"] = True
            except Exception as e:
                logger.error(f"❌ #N{bet_game} düzenlenirken hata: {e}")
        else:
            # KAYIP - bir sonraki step'e geç
            next_step = current_step + 1
            
            if next_step > MAX_MARTINGALE_STEP:
                # TAM KAYIP - ❌ (Maksimum step aşıldı)
                new_text = f"#N{bet_game} | {info['suit']} - 7D | {info['strategy']} | ❌"
                try:
                    await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                    logger.info(f"❌ #N{bet_game} KAYIP: Maksimum step aşıldı - {info['suit']} | {info['strategy']}")
                    info["checked"] = True
                except Exception as e:
                    logger.error(f"❌ #N{bet_game} düzenlenirken hata: {e}")
            else:
                # BİR SONRAKİ ADIM - step güncelle
                info["step"] = next_step
                new_text = f"#N{bet_game} | {info['suit']} - 7D | {info['strategy']} | {step_emojis[next_step]}"
                try:
                    await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                    logger.info(f"🔄 #N{bet_game} STEP GÜNCELLENDİ: {current_step} → {next_step} - {info['suit']} | {info['strategy']}")
                except Exception as e:
                    logger.error(f"❌ #N{bet_game} düzenlenirken hata: {e}")
    
    if updated_count > 0:
        logger.info(f"📊 Martingale güncelleme: {updated_count} sinyal işlendi")

# -------------------------
# Sinyal Gönderme - DÜZELTİLMİŞ (DUPLICATE ÖNLEME)
# -------------------------
async def send_signal(signal_game, signal_suit, signal_type, strategy_name="10-BC"):
    """Sinyal gönderme - DUPLICATE ÖNLEME EKLENDİ"""
    # DÜZELTME: Sinyal key'ine suit ve type ekleyerek duplicate'leri önle
    signal_key = f"{signal_game}_{signal_suit}_{signal_type}_{strategy_name}"
    
    if signal_key in sent_signals:
        logger.debug(f"📨 Sinyal zaten gönderilmiş: {signal_key}")
        return False
    
    # YENİ FORMAT: #N211 | ♦ - 7D | 10-BC
    text = f"#N{signal_game} | {signal_suit} - 7D | {strategy_name}"
    
    try:
        sent = await client.send_message(KANAL_HEDEF, text)
        sent_signals.add(signal_key)
        
        # Martingale tracker'a signal_key ile kaydet ve step 0'dan başlat
        martingale_tracker[signal_key] = {
            "msg_id": sent.id,
            "bet_game": signal_game,
            "suit": signal_suit, 
            "step": 0,
            "checked": False,
            "signal_type": signal_type,
            "strategy": strategy_name
        }
        logger.info(f"🎯 YENİ SİNYAL: #{signal_game} | {signal_suit} - 7D | {strategy_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Sinyal gönderilemedi: {e}")
        return False

# -------------------------
# 10-oyun geri sistemi (ANA STRATEJİ)
# -------------------------
async def check_10_game_back_system(current_game, current_player_cards):
    """10 oyun geri sistemi"""
    previous_game_10 = get_previous_game(current_game, 10)
    
    if previous_game_10 not in player_results:
        logger.debug(f"10-back: #{previous_game_10} verisi yok")
        return
    
    previous_player_cards = player_results[previous_game_10]
    
    # İlk Kart Eşleşmesi
    current_first_suit = get_first_card_suit(current_player_cards)
    previous_first_suit = get_first_card_suit(previous_player_cards)
    
    if current_first_suit and previous_first_suit and current_first_suit == previous_first_suit:
        signal_source_game = get_next_game_number(previous_game_10, 1)
        if signal_source_game in player_results:
            signal_source_first_suit = get_first_card_suit(player_results[signal_source_game])
            if signal_source_first_suit:
                signal_suit = suit_flip.get(signal_source_first_suit)
                signal_game = get_next_game_number(previous_game_10, 11)
                success = await send_signal(signal_game, signal_suit, "first", "10-BC")
                if success:
                    logger.info(f"🔄 10-BC İlk kart: #{previous_game_10}-#{current_game} → #{signal_game} - {signal_suit}")

    # Orta Kart Eşleşmesi
    current_middle_suit = get_middle_card_suit(current_player_cards)
    previous_middle_suit = get_middle_card_suit(previous_player_cards)
    
    if (current_middle_suit and previous_middle_suit and 
        current_middle_suit == previous_middle_suit):
        signal_source_game = get_next_game_number(previous_game_10, 1)
        if signal_source_game in player_results:
            signal_source_middle_suit = get_middle_card_suit(player_results[signal_source_game])
            if signal_source_middle_suit:
                signal_suit = suit_flip.get(signal_source_middle_suit)
                signal_game = get_next_game_number(previous_game_10, 11)
                success = await send_signal(signal_game, signal_suit, "middle", "10-BC")
                if success:
                    logger.info(f"🔄 10-BC Orta kart: #{previous_game_10}-#{current_game} → #{signal_game} - {signal_suit}")

# -------------------------
# FELAKET SİSTEMİ (5-UP ve 7-UP)
# -------------------------
async def update_disaster_system(current_game, player_cards_str):
    """Felaket Sistemi - 5+ ve 7+ el çıkmayan renkleri tespit et"""
    # Oyuncu kartlarındaki renkleri al
    current_suits = set(suits_from_cards(player_cards_str))
    
    # Tüm renkler için count güncelle
    for suit in suit_tracker.keys():
        if suit in current_suits:
            # Renk görüldü - count sıfırla ve last_seen güncelle
            suit_tracker[suit]['count'] = 0
            suit_tracker[suit]['last_seen'] = current_game
        else:
            # Renk görülmedi - count artır
            suit_tracker[suit]['count'] += 1
    
    # Sinyal kontrolü
    for suit, data in suit_tracker.items():
        count = data['count']
        
        # 5-UP sinyali (5+ el çıkmayan)
        if count == 5:
            signal_game = get_next_game_number(current_game, 1)
            success = await send_signal(signal_game, suit, "disaster", "5-UP")
            if success:
                logger.info(f"🚨 5-UP: #{current_game} - {suit} {count} el çıkmadı → #{signal_game}")
        
        # 7-UP sinyali (7+ el çıkmayan)  
        elif count == 7:
            signal_game = get_next_game_number(current_game, 1)
            success = await send_signal(signal_game, suit, "disaster", "7-UP")
            if success:
                logger.info(f"🔥 7-UP: #{current_game} - {suit} {count} el çıkmadı → #{signal_game}")

# -------------------------
# Ana Handler
# -------------------------
@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handler(event):
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
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            game_number = int(m.group(1))
            break
    
    if not game_number:
        return

    # Geçersiz oyun numarası kontrolü
    if game_number < 1 or game_number > MAX_GAME_NUMBER:
        logger.warning(f"⚠️ Geçersiz oyun numarası: #{game_number}")
        return

    # SADECE OYUNCU KARTLARINI çıkar - BANKER KARTLARINI GÖRMEZDEN GEL
    player_cards = extract_player_cards(text)
    if not player_cards:
        logger.debug(f"#{game_number}: Oyuncu kartları bulunamadı")
        return

    # Oyuncu kart sayısını kontrol et
    suits = suits_from_cards(player_cards)
    
    # Eğer oyuncuda 2 kart varsa, 3. kart beklenmiyor demektir - işleme devam et
    # Eğer oyuncuda 3 kart varsa, 3. kart zaten açılmış demektir - işleme devam et
    # Sadece oyuncunun 1 kartı varsa ve ok işareti varsa 3. kart bekleniyor demektir
    if len(suits) == 1 and player_has_arrow(text):
        logger.info(f"⏳ #N{game_number}: Oyuncunun 3. kartı bekleniyor - {player_cards}")
        return

    # Oyuncu kartlarını kaydet (2 veya 3 kart)
    player_results[game_number] = player_cards
    logger.info(f"💾 #N{game_number} kaydedildi: {player_cards} (sadece oyuncu)")

    # 1) Martingale güncelleme (0-7 arası)
    await update_martingale(game_number, player_cards)

    # 2) FELAKET SİSTEMİ güncelleme
    await update_disaster_system(game_number, player_cards)

    # 3) 10-BC SİSTEMİ
    strategies = [
        check_10_game_back_system(game_number, player_cards),
    ]
    
    # Tüm stratejileri paralel çalıştır
    results = await asyncio.gather(*strategies, return_exceptions=True)
    
    # Hataları logla
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            strategy_names = ["10-BC"]
            logger.error(f"❌ {strategy_names[i]} stratejisinde hata: {result}")

# -------------------------
# Sistem İzleme ve Başlatma
# -------------------------
async def system_status():
    """Sistem durumunu logla"""
    active_signals = len([x for x in martingale_tracker.values() if not x.get("checked")])
    total_games = len(player_results)
    completed_signals = len([x for x in martingale_tracker.values() if x.get("checked")])
    
    # Aktif sinyallerin step dağılımı
    step_distribution = {}
    for signal in martingale_tracker.values():
        if not signal.get("checked"):
            step = signal.get("step", 0)
            step_distribution[step] = step_distribution.get(step, 0) + 1
    
    # Stratejilere göre sinyal dağılımı
    strategy_distribution = {}
    for signal in martingale_tracker.values():
        if not signal.get("checked"):
            strategy = signal.get("strategy", "unknown")
            strategy_distribution[strategy] = strategy_distribution.get(strategy, 0) + 1
    
    # Felaket Sistemi durumu
    disaster_status = {}
    for suit, data in suit_tracker.items():
        disaster_status[suit] = data['count']
    
    status_msg = (
        f"📊 SİSTEM DURUMU:\n"
        f"• Aktif sinyaller: {active_signals}\n"
        f"• Tamamlanan sinyaller: {completed_signals}\n"
        f"• Kayıtlı oyunlar: {total_games}\n"
        f"• Step dağılımı: {step_distribution}\n"
        f"• Strateji dağılımı: {strategy_distribution}\n"
        f"• Felaket Sistemi: {disaster_status}\n"
        f"• Martingale: 0️⃣→{MAX_MARTINGALE_STEP}️⃣\n"
        f"• Son güncelleme: {datetime.now().strftime('%H:%M:%S')}"
    )
    logger.info(status_msg)
    return status_msg

async def periodic_status():
    """Her 5 dakikada bir sistem durumunu logla"""
    while True:
        await asyncio.sleep(300)
        try:
            await system_status()
        except Exception as e:
            logger.error(f"Periodik durum kontrolü hatası: {e}")

async def main():
    logger.info("🎯 BACCARAT BOT v37 BAŞLATILIYOR...")
    logger.info("✅ YENİ SİSTEM: 10-BC + FELAKET SİSTEMİ (5-UP/7-UP)")
    
    await client.start()
    me = await client.get_me()
    
    startup_msg = (
        f"🤖 BOT AKTİF: {me.username if me.username else me.first_name}\n"
        f"⏰ Başlangıç: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"🎯 Stratejiler: 10-BC, 5-UP, 7-UP\n"
        f"⚡ Martingale: Step 0️⃣→{MAX_MARTINGALE_STEP}️⃣ ({MAX_MARTINGALE_STEP+1} adım)\n"
        f"🎴 Sadece Oyuncu Kartları: Evet\n"
        f"⏳ 3. Kart Bekleme: Geliştirilmiş (Sadece oyuncu 1 kart + ok)\n"
        f"🔥 Felaket Sistemi: Aktif (5+/7+ el)\n"
        f"🔄 Duplicate Önleme: Aktif"
    )
    logger.info(startup_msg)
    
    # Arkaplan görevlerini başlat
    asyncio.create_task(periodic_status())
    
    # Başlangıç durumunu göster
    await system_status()
    
    logger.info("🟢 Bot çalışmaya hazır - Felaket Sistemi aktif...")
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
