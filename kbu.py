import re
import random
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
import asyncio
import sys
from datetime import datetime

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
MAX_MARTINGALE_STEPS = 7 # 0'dan 7'ye toplam 8 adım
MAX_GAME_NUMBER = 1440

# Tüm stratejiler sadece OYUNCU için
c23_trackers = {}
c32_trackers = {}
c22_trackers = {}
c33_trackers = {}
color_trackers = {}
card_value_trackers = {}  # Yeni Kart Değeri stratejisi için

# Renk takip için global değişkenler
last_colors = [] # Son renkleri tutacak liste (max 10)
color_pattern_threshold = 3 # Renk değişimi için eşik

# ==============================================================================
# Yardımcı Fonksiyonlar
# ==============================================================================

def get_baccarat_value(card_char):
    """
    Belirtilen kart karakterinin Baccarat stratejisine göre değerini döndürür.
    """
    if card_char == '10':
        return 10
    if card_char in 'AKQJ2T':
        return 0
    elif card_char.isdigit():
        return int(card_char)
    return -1

def get_highest_card_value(player_cards_str):
    """
    Oyuncu kartlarındaki en yüksek değerli kartın karakterini döndürür.
    A, K, Q, J, 2, T = 0 değerinde
    3-9 ve 10 = normal değerlerinde
    """
    # Tüm oyuncu kartlarını bul (2 veya 3 kart)
    cards = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards_str)
    if not cards:
        return None

    max_value = -1
    highest_card_char = None
    
    # Tüm kartların değerlerini al
    for card_char, suit in cards:
        value = get_baccarat_value(card_char)
        if value > max_value:
            max_value = value
            highest_card_char = card_char
    
    return highest_card_char

def get_next_game_number(current_game_num):
    """
    Oyun numarası 1440'ı geçtiğinde numarayı 1'e döndürür.
    """
    next_num = current_game_num + 1
    if next_num > MAX_GAME_NUMBER:
        return 1
    return next_num

def extract_player_suit(player_cards_str):
    """
    Oyuncu kartlarındaki en yüksek değerli kartın sembolünü döndürür.
    Oyuncu'nun 3 kartını da dikkate alır.
    """
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
        elif value == max_value:
            # Aynı değerde birden fazla kart varsa, ilkini tut
            pass

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
        
        if ('✅' in text or '🔰' in text or '#X' in text):
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

def check_color_pattern(player_cards, banker_cards, winner):
    """
    Renk desenini kontrol eder ve renk değişim sinyali üretir.
    Sadece OYUNCU için çalışır.
    """
    global last_colors
    
    # Sadece Oyuncu'nun kartlarını dikkate al
    suit = extract_player_suit(player_cards)
    
    if not suit:
        return None
    
    current_color = get_color_from_suit(suit)
    
    # Son renkleri güncelle (max 10 tane tut)
    last_colors.append(current_color)
    if len(last_colors) > 10:
        last_colors.pop(0)
    
    # Renk değişim sinyali kontrolü
    if len(last_colors) >= color_pattern_threshold:
        # Son 'color_pattern_threshold' renk aynı mı?
        last_n_colors = last_colors[-color_pattern_threshold:]
        if len(set(last_n_colors)) == 1:  # Tümü aynı renk
            # Zıt renk sinyali ver
            opposite_color = 'black' if current_color == 'red' else 'red'
            return opposite_color
    
    return None

async def send_signal(game_num, signal_value, strategy_type):
    """Yeni sinyal gönderir ve ilgili stratejinin Martingale takibini başlatır."""
    
    # Tüm stratejiler sadece OYUNCU için
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
    elif strategy_type == "card_value":  # Yeni Kart Değeri stratejisi
        signal_full_text = f"**#N{game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D**"
        trackers_dict = card_value_trackers
    else:
        return

    # Strateji zaten aktif mi kontrol et
    if trackers_dict:
        print(f"UYARI: {strategy_type} stratejisi zaten aktif. Yeni sinyal gönderilmiyor.")
        return

    try:
        sent_message = await client.send_message(KANAL_HEDEF, signal_full_text)
        print(f"Yeni sinyal gönderildi: {signal_full_text}")

        trackers_dict[game_num] = {
            'message_obj': sent_message,
            'step': 0,
            'signal_value': signal_value,
            'sent_game_number': game_num,
            'expected_game_number_for_check': game_num,
            'strategy_type': strategy_type
        }

    except FloodWaitError as e:
        print(f"FloodWait hatası (sinyal gönderimi): {e.seconds} saniye bekleniyor.")
        await asyncio.sleep(e.seconds)
        await send_signal(game_num, signal_value, strategy_type)
    except Exception as e:
        print(f"Sinyal gönderme hatası: {e}")

async def check_martingale_trackers():
    """Tüm stratejilerin Martingale takiplerini kontrol eder."""
    
    # Tüm strateji takipçilerini kontrol et
    for strategy_name, trackers_dict in [
        ("C2_3", c23_trackers),
        ("C3_2", c32_trackers), 
        ("C2_2", c22_trackers),
        ("C3_3", c33_trackers),
        ("Renk", color_trackers),
        ("Kart Değeri", card_value_trackers)  # Yeni strateji
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
            # Kart Değeri stratejisi: Oyuncu'nun en yüksek kart değeri sinyal değeriyle eşleşiyor mu?
            highest_card = get_highest_card_value(player_cards_str)
            signal_won_this_step = (highest_card == signal_value)
        else:
            # Diğer stratejiler: Sinyal değeri (sembol) Oyuncu kartlarında var mı?
            signal_won_this_step = bool(re.search(re.escape(signal_value), player_cards_str))
        
        print(f"DEBUG: {strategy_name} Sinyal #N{signal_game_num} (Adım {current_step}): Kazandı mı? {signal_won_this_step}")

        if signal_won_this_step:
            # Kazanma durumu
            if strategy_type == "color":
                new_text = f"**#N{signal_game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D | ✅ {current_step}️⃣**"
            elif strategy_type == "card_value":
                new_text = f"**#N{signal_game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D | ✅ {current_step}️⃣**"
            else:
                new_text = f"**#N{signal_game_num} | Oyuncu {signal_value} - {MAX_MARTINGALE_STEPS}D | ✅ {current_step}️⃣**"
            
            try:
                await signal_message_obj.edit(new_text)
                print(f"DEBUG: {strategy_name} Sinyal #N{signal_game_num} kazanma nedeniyle düzenlendi.")
            except MessageNotModifiedError:
                pass
            except Exception as e:
                print(f"Mesaj düzenleme hatası (kazandı): {e}")
            
            trackers_to_remove.append(signal_game_num)

        else:
            # Kaybetme durumu
            if current_step < MAX_MARTINGALE_STEPS:
                # Bir sonraki adıma geç
                next_step = current_step + 1
                next_game_num = get_next_game_number(game_to_check)
                
                trackers_dict[signal_game_num]['step'] = next_step
                trackers_dict[signal_game_num]['expected_game_number_for_check'] = next_game_num
                print(f"DEBUG: {strategy_name} Sinyal #N{signal_game_num} kayıp (Adım {current_step}). {next_step}. adıma geçiliyor.")
            else:
                # Maksimum adıma ulaşıldı, kayıp
                if strategy_type == "color":
                    new_text = f"**#N{signal_game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D | ❌**"
                elif strategy_type == "card_value":
                    new_text = f"**#N{signal_game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D | ❌**"
                else:
                    new_text = f"**#N{signal_game_num} | Oyuncu {signal_value} - {MAX_MARTINGALE_STEPS}D | ❌**"
                
                try:
                    await signal_message_obj.edit(new_text)
                    print(f"DEBUG: {strategy_name} Sinyal #N{signal_game_num} kayıp nedeniyle düzenlendi.")
                except MessageNotModifiedError:
                    pass
                except Exception as e:
                    print(f"Mesaj düzenleme hatası (kaybetti): {e}")
                
                trackers_to_remove.append(signal_game_num)

    # Tamamlanan takipçileri kaldır
    for game_num_to_remove in trackers_to_remove:
        if game_num_to_remove in trackers_dict:
            del trackers_dict[game_num_to_remove]
            print(f"DEBUG: {strategy_name} takipçisi #N{game_num_to_remove} kaldırıldı.")

# ==============================================================================
# Telegram Mesaj İşleyicileri
# ==============================================================================

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_source_channel_message(event):
    message = event.message
    cleaned_text = re.sub(r'\*\*', '', message.text).strip()
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] KAYNAK KANAL Yeni/Düzenlenen Mesaj Alındı. ID: {message.id}, Metin: '{cleaned_text}'", file=sys.stderr)

    game_info = extract_game_info_from_message(cleaned_text)
    game_info['original_text'] = cleaned_text  # Orijinal metni sakla

    if game_info['game_number'] is None:
        return

    game_results[game_info['game_number']] = game_info
    
    # Tüm stratejilerin takiplerini kontrol et
    await check_martingale_trackers()

    # Tüm stratejiler sadece OYUNCU için ve bağımsız çalışır
    if game_info['is_final']:
        trigger_game_num = game_info['game_number']
        next_game_num = get_next_game_number(trigger_game_num)
        
        # 1. C2_3 Stratejisi - Sadece Oyuncu
        if game_info.get('is_c2_3') and not c23_trackers:
            signal_suit = extract_player_suit(game_info['player_cards'])
            if signal_suit is not None:
                await send_signal(next_game_num, signal_suit, "c23")
        
        # 2. C3_2 Stratejisi - Sadece Oyuncu
        if game_info.get('is_c3_2') and not c32_trackers:
            signal_suit = extract_player_suit(game_info['player_cards'])
            if signal_suit is not None:
                await send_signal(next_game_num, signal_suit, "c32")
        
        # 3. C2_2 Stratejisi - Sadece Oyuncu
        if game_info.get('is_c2_2') and not c22_trackers:
            signal_suit = extract_player_suit(game_info['player_cards'])
            if signal_suit is not None:
                await send_signal(next_game_num, signal_suit, "c22")
        
        # 4. C3_3 Stratejisi - Sadece Oyuncu
        if game_info.get('is_c3_3') and not c33_trackers:
            signal_suit = extract_player_suit(game_info['player_cards'])
            if signal_suit is not None:
                await send_signal(next_game_num, signal_suit, "c33")
        
        # 5. Renk Stratejisi - Sadece Oyuncu
        if not color_trackers:
            # Renk desenini kontrol et (sadece Oyuncu kartlarına göre)
            color_signal = check_color_pattern(game_info['player_cards'], game_info['banker_cards'], 'player')
            
            if color_signal:
                # Renk sinyali için rastgele bir kart sembolü seç
                signal_suit = get_random_suit_by_color(color_signal)
                await send_signal(next_game_num, signal_suit, "color")
        
        # 6. Yeni Kart Değeri Stratejisi - Sadece Oyuncu
        if not card_value_trackers:
            # Oyuncu'nun en yüksek kart değerini al
            highest_card = get_highest_card_value(game_info['player_cards'])
            if highest_card is not None:
                # Bu değeri bir sonraki oyun için sinyal olarak gönder
                await send_signal(next_game_num, highest_card, "card_value")

# ==============================================================================
# Botun Başlatılması
# ==============================================================================
if __name__ == '__main__':
    print("Bot başlatılıyor...")
    print(f"Martingale adım sayısı: {MAX_MARTINGALE_STEPS}")
    print("Aktif stratejiler: C2_3, C3_2, C2_2, C3_3, Renk Değişim, Kart Değeri")
    print("TÜM stratejiler sadece OYUNCU için çalışır")
    print("Oyuncu'nun 3 kartı da dikkate alınır")
    print("Öncelik sistemi YOK - tüm stratejiler bağımsız çalışır")
    with client:
        client.run_until_disconnected()