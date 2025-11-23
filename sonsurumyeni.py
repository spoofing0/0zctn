import re
import random
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
import asyncio
import sys
from datetime import datetime
from collections import deque

# ==============================================================================
# Telegram API Bilgileri ve Kanal Ayarları
# ==============================================================================
API_ID = 27518940
API_HASH = '30b6658a1870f8462108130783fef14f'

# --- Kanal Bilgileri ---
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@kbubakara"

client = TelegramClient('kbu_baccarat_bot', API_ID, API_HASH)

# ==============================================================================
# Global Değişkenler ve Takip Mekanizmaları
# ==============================================================================
game_results = {}
MAX_MARTINGALE_STEPS = 7  # 0'dan 7'ye toplam 8 adım

# Tüm stratejiler sadece OYUNCU için - BAĞIMSIZ
c23_trackers = {}
c32_trackers = {}
c22_trackers = {}
c33_trackers = {}
color_trackers = {}
card_value_trackers = {}

# Renk takip için
last_colors = deque(maxlen=10)

# ==============================================================================
# Yardımcı Fonksiyonlar
# ==============================================================================

def get_baccarat_value(card_char):
    """Kart karakterinin Baccarat değerini döndürür."""
    if card_char == '10':
        return 10
    if card_char in 'AKQJ2T':
        return 0
    elif card_char.isdigit():
        return int(card_char)
    return -1

def get_highest_card_value(player_cards_str):
    """Oyuncu kartlarındaki en yüksek değerli kartın karakterini döndürür."""
    # Tüm oyuncu kartlarını bul (2 veya 3 kart)
    cards = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards_str)
    if not cards:
        return None

    max_value = -1
    highest_card_char = None
    
    for card_char, suit in cards:
        value = get_baccarat_value(card_char)
        if value > max_value:
            max_value = value
            highest_card_char = card_char
    
    return highest_card_char

def get_all_card_values(player_cards_str):
    """Oyuncu kartlarındaki tüm kart değerlerini (karakter olarak) döndürür."""
    cards = re.findall(r'(10|[A2-9TJQK])[♣♦♥♠]', player_cards_str)
    return cards

def get_next_game_number(current_game_num):
    """Oyun numarası 1440'ı geçtiğinde numarayı 1'e döndürür."""
    next_num = current_game_num + 1
    if next_num > 1440:
        return 1
    return next_num

def extract_player_suit(player_cards_str):
    """Oyuncu kartlarındaki en yüksek değerli kartın sembolünü döndürür."""
    # Tüm oyuncu kartlarını bul (2 veya 3 kart)
    cards = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards_str)
    if not cards:
        return None

    max_value = -1
    largest_value_suit = None
    
    # Tüm kartların değerlerini al
    values = [get_baccarat_value(card[0]) for card in cards]
    
    # Eğer tüm değerler eşitse None döndür
    if len(values) > 1 and all(v == values[0] for v in values):
        return None

    # En yüksek değerli kartı bul
    for card_char, suit in cards:
        value = get_baccarat_value(card_char)
        if value > max_value:
            max_value = value
            largest_value_suit = suit

    if max_value == 0:
        return None
        
    return largest_value_suit

def is_player_drawing(text):
    """Mesaj metninde oyuncunun kart çekme beklentisi olup olmadığını kontrol eder."""
    return '▶️' in text

def extract_game_info_from_message(text):
    """Mesaj metninden oyun numarasını, oyuncu ve banker kartlarını ayrıştırır."""
    game_info = {'game_number': None, 'player_cards': '', 'banker_cards': '',
                 'is_final': False, 'is_player_drawing': False, 
                 'is_c2_3': False, 'is_c3_2': False, 'is_c2_2': False, 'is_c3_3': False}
    
    game_info['is_player_drawing'] = is_player_drawing(text)

    # Geliştirilmiş regex pattern - 3 kart durumunu da yakalar
    game_match = re.search(
        r'#N(\d+)\s+.*?\((.*?)\)\s+.*?(\d+\s+\(.*\))\s+.*?(#C(\d)_(\d))',
        text.replace('️', ''),
        re.DOTALL
    )

    if game_match:
        game_info['game_number'] = int(game_match.group(1))
        game_info['player_cards'] = game_match.group(2)
        game_info['banker_cards'] = game_match.group(3)
        c_tag = game_match.group(4)
        
        # Tüm C patternlerini kontrol et
        if c_tag == '#C2_3':
            game_info['is_c2_3'] = True
        elif c_tag == '#C3_2':
            game_info['is_c3_2'] = True
        elif c_tag == '#C2_2':
            game_info['is_c2_2'] = True
        elif c_tag == '#C3_3':
            game_info['is_c3_3'] = True
        
        # OYUNCU 3. KARTINI BEKLE: Eğer oyuncu kart çekmiyorsa ve sonuç işaretleri varsa final
        if not game_info['is_player_drawing'] and ('✅' in text or '🔰' in text or '#X' in text):
            game_info['is_final'] = True
    
    return game_info

def get_color_from_suit(suit):
    """Kart sembolünden rengi döndürür."""
    if suit in ['♥', '♦']:
        return 'red'
    elif suit in ['♣', '♠']:
        return 'black'
    return None

def get_random_suit_by_color(color):
    """Renge göre rastgele bir kart sembolü döndürür."""
    if color == 'red':
        return random.choice(['♥', '♦'])
    else:  # black
        return random.choice(['♣', '♠'])

def check_color_pattern(player_cards):
    """Renk desenini kontrol eder ve renk değişim sinyali üretir."""
    global last_colors
    
    # Sadece Oyuncu'nun kartlarını dikkate al
    suit = extract_player_suit(player_cards)
    
    if not suit:
        return None
    
    current_color = get_color_from_suit(suit)
    
    # Son renkleri güncelle
    last_colors.append(current_color)
    
    # Renk değişim sinyali kontrolü
    if len(last_colors) >= 4:
        # Son 4 renk aynı mı?
        last_4_colors = list(last_colors)[-4:]
        if len(set(last_4_colors)) == 1:  # Tümü aynı renk
            # Zıt renk sinyali ver
            opposite_color = 'black' if current_color == 'red' else 'red'
            return opposite_color
    
    return None

async def send_signal(game_num, signal_value, strategy_type):
    """Yeni sinyal gönderir ve ilgili stratejinin Martingale takibini başlatır."""
    
    # Tüm stratejiler sadece OYUNCU için - BAĞIMSIZ
    if strategy_type == "c23":
        signal_full_text = f"**#N{game_num} | Oyuncu {signal_value} - {MAX_MARTINGALE_STEPS}D**"
        trackers_dict = c23_trackers
    elif strategy_type == "c32":
        signal_full_text = f"**#N{game_num} | Oyuncu {signal_value} - {MAX_MARTINGALE_STEPS}D**"
        trackers_dict = c32_trackers
    elif strategy_type == "c22":
        signal_full_text = f"**#N{game_num} | Oyuncu {signal_value} - {MAX_MARTINGALE_STEPS}D**"
        trackers_dict = c22_trackers
    elif strategy_type == "c33":
        signal_full_text = f"**#N{game_num} | Oyuncu {signal_value} - {MAX_MARTINGALE_STEPS}D**"
        trackers_dict = c33_trackers
    elif strategy_type == "color":
        signal_full_text = f"**#N{game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D**"
        trackers_dict = color_trackers
    elif strategy_type == "card_value":
        signal_full_text = f"**#N{game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D**"
        trackers_dict = card_value_trackers
    else:
        return

    # Strateji BAĞIMSIZ - her strateji kendi içinde çalışır
    try:
        sent_message = await client.send_message(KANAL_HEDEF, signal_full_text)
        print(f"🆕 YENİ SİNYAL: {signal_full_text}")

        trackers_dict[game_num] = {
            'message_obj': sent_message,
            'step': 0,  # 0'dan başla
            'signal_value': signal_value,
            'sent_game_number': game_num,
            'expected_game_number_for_check': game_num,
            'strategy_type': strategy_type
        }

    except FloodWaitError as e:
        print(f"⏳ FloodWait: {e.seconds}s")
        await asyncio.sleep(e.seconds)
        await send_signal(game_num, signal_value, strategy_type)
    except Exception as e:
        print(f"❌ Sinyal gönderme hatası: {e}")

async def check_martingale_trackers():
    """Tüm stratejilerin Martingale takiplerini kontrol eder."""
    
    # Tüm strateji takipçilerini BAĞIMSIZ olarak kontrol et
    for strategy_name, trackers_dict in [
        ("C2_3", c23_trackers),
        ("C3_2", c32_trackers), 
        ("C2_2", c22_trackers),
        ("C3_3", c33_trackers),
        ("Renk", color_trackers),
        ("Kart Değeri", card_value_trackers)
    ]:
        await check_single_strategy_trackers(strategy_name, trackers_dict)

async def check_single_strategy_trackers(strategy_name, trackers_dict):
    """Tek bir stratejinin Martingale takibini yapar."""
    
    trackers_to_remove = []

    for signal_game_num, tracker_info in list(trackers_dict.items()):
        current_step = tracker_info['step']
        signal_message_obj = tracker_info['message_obj']
        signal_value = tracker_info['signal_value']
        strategy_type = tracker_info['strategy_type']
        
        game_to_check = tracker_info['expected_game_number_for_check']
        
        if game_to_check not in game_results:
            continue
        
        result_info = game_results.get(game_to_check)

        if not result_info['is_final']:
            continue
        
        player_cards_str = result_info['player_cards']
        
        # Kazanç kontrolü strateji türüne göre değişir
        if strategy_type == "card_value":
            # Kart Değeri stratejisi: Sinyal değeri oyuncu kartlarındaki herhangi bir kartın değeri ile eşleşiyor mu?
            card_values = get_all_card_values(player_cards_str)
            signal_won_this_step = (signal_value in card_values)
        else:
            # Diğer stratejiler: Sinyal değeri (sembol) Oyuncu kartlarında var mı?
            signal_won_this_step = bool(re.search(re.escape(signal_value), player_cards_str))
        
        print(f"🔍 {strategy_name} #N{signal_game_num} (Adım {current_step}): {'✅' if signal_won_this_step else '❌'}")

        if signal_won_this_step:
            # KAZANÇ - Martingale başarılı
            if strategy_type == "color":
                new_text = f"**#N{signal_game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D | ✅ {current_step}️⃣**"
            elif strategy_type == "card_value":
                new_text = f"**#N{signal_game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D | ✅ {current_step}️⃣**"
            else:
                new_text = f"**#N{signal_game_num} | Oyuncu {signal_value} - {MAX_MARTINGALE_STEPS}D | ✅ {current_step}️⃣**"
            
            try:
                await signal_message_obj.edit(new_text)
                print(f"🎉 KAZANÇ: {strategy_name} #N{signal_game_num} (Adım {current_step})")
            except MessageNotModifiedError:
                pass
            except Exception as e:
                print(f"⚠️ Mesaj düzenleme hatası (kazandı): {e}")
            
            trackers_to_remove.append(signal_game_num)

        else:
            # KAYIP - Martingale devam et veya sonlandır
            if current_step < MAX_MARTINGALE_STEPS:
                # Bir sonraki adıma geç
                next_step = current_step + 1
                next_game_num = get_next_game_number(game_to_check)
                
                trackers_dict[signal_game_num]['step'] = next_step
                trackers_dict[signal_game_num]['expected_game_number_for_check'] = next_game_num
                print(f"🔄 DEVAM: {strategy_name} #N{signal_game_num} → Adım {next_step}")
            else:
                # Maksimum adıma ulaşıldı, KAYIP
                if strategy_type == "color":
                    new_text = f"**#N{signal_game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D | ❌**"
                elif strategy_type == "card_value":
                    new_text = f"**#N{signal_game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D | ❌**"
                else:
                    new_text = f"**#N{signal_game_num} | Oyuncu {signal_value} - {MAX_MARTINGALE_STEPS}D | ❌**"
                
                try:
                    await signal_message_obj.edit(new_text)
                    print(f"💥 KAYIP: {strategy_name} #N{signal_game_num} (Maksimum adım)")
                except MessageNotModifiedError:
                    pass
                except Exception as e:
                    print(f"⚠️ Mesaj düzenleme hatası (kaybetti): {e}")
                
                trackers_to_remove.append(signal_game_num)

    # Tamamlanan takipçileri kaldır
    for game_num_to_remove in trackers_to_remove:
        if game_num_to_remove in trackers_dict:
            del trackers_dict[game_num_to_remove]

# ==============================================================================
# Telegram Mesaj İşleyicileri
# ==============================================================================

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_source_channel_message(event):
    message = event.message
    cleaned_text = re.sub(r'\*\*', '', message.text).strip()
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 Mesaj: '{cleaned_text}'")

    game_info = extract_game_info_from_message(cleaned_text)
    game_info['original_text'] = cleaned_text

    if game_info['game_number'] is None:
        return

    game_results[game_info['game_number']] = game_info
    
    # Tüm stratejilerin takiplerini BAĞIMSIZ olarak kontrol et
    await check_martingale_trackers()

    # TÜM STRATEJİLER BAĞIMSIZ - öncelik sistemi YOK
    if game_info['is_final']:
        trigger_game_num = game_info['game_number']
        next_game_num = get_next_game_number(trigger_game_num)
        
        # 1. C2_3 Stratejisi - BAĞIMSIZ
        if game_info.get('is_c2_3'):
            signal_suit = extract_player_suit(game_info['player_cards'])
            if signal_suit is not None:
                await send_signal(next_game_num, signal_suit, "c23")
        
        # 2. C3_2 Stratejisi - BAĞIMSIZ
        if game_info.get('is_c3_2'):
            signal_suit = extract_player_suit(game_info['player_cards'])
            if signal_suit is not None:
                await send_signal(next_game_num, signal_suit, "c32")
        
        # 3. C2_2 Stratejisi - BAĞIMSIZ
        if game_info.get('is_c2_2'):
            signal_suit = extract_player_suit(game_info['player_cards'])
            if signal_suit is not None:
                await send_signal(next_game_num, signal_suit, "c22")
        
        # 4. C3_3 Stratejisi - BAĞIMSIZ
        if game_info.get('is_c3_3'):
            signal_suit = extract_player_suit(game_info['player_cards'])
            if signal_suit is not None:
                await send_signal(next_game_num, signal_suit, "c33")
        
        # 5. Renk Stratejisi - BAĞIMSIZ
        color_signal = check_color_pattern(game_info['player_cards'])
        if color_signal:
            signal_suit = get_random_suit_by_color(color_signal)
            await send_signal(next_game_num, signal_suit, "color")
        
        # 6. Kart Değeri Stratejisi - BAĞIMSIZ
        highest_card = get_highest_card_value(game_info['player_cards'])
        if highest_card is not None:
            await send_signal(next_game_num, highest_card, "card_value")

# ==============================================================================
# Botun Başlatılması
# ==============================================================================
if __name__ == '__main__':
    print("🎯 BACCARAT BOTU BAŞLATILIYOR...")
    print(f"📊 Martingale: 0️⃣'dan {MAX_MARTINGALE_STEPS}️⃣'ye kadar")
    print("🔄 Tüm stratejiler BAĞIMSIZ çalışacak")
    print("⏳ Oyuncu 3. kartını bekleyecek")
    print("🎴 Tüm kartlar (2 veya 3) okunacak")
    print("🔢 Kart Değeri stratejisi: Sinyal değeri oyuncu kartlarında HERHANGİ BİR KART olarak mevcutsa kazanç")
    print("🚀 Aktif stratejiler: C2_3, C3_2, C2_2, C3_3, Renk, Kart Değeri")
    print("🎯 TÜM stratejiler sadece OYUNCU için çalışır")
    
    with client:
        client.run_until_disconnected()
