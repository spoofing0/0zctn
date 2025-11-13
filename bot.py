import re
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
KANAL_HEDEF = "@emirbot5"

client = TelegramClient('my_new_baccarat_bot', API_ID, API_HASH)

# ==============================================================================
# Global Değişkenler ve Takip Mekanizmaları
# ==============================================================================
game_results = {}
martingale_trackers = {} # Aktif sinyallerin takibi
MAX_MARTINGALE_STEPS = 3 # 0, 1, 2, 3 -> 4 adım
MAX_GAME_NUMBER = 1440 # OYUN DÖNGÜSÜNÜN SONU
is_signal_active = False # Aktif sinyal takibi devam ediyorsa True

# Kart sembollerinden rengi (suit) ayıran regex
SUIT_REGEX = re.compile(r'([♣♦♥♠])')

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

def get_next_game_number(current_game_num):
    """
    Oyun numarası 1440'ı geçtiğinde numarayı 1'e döndürür.
    """
    next_num = current_game_num + 1
    if next_num > MAX_GAME_NUMBER:
        return 1
    return next_num

def extract_largest_value_suit(cards_str):
    """
    Oyuncu kartlarındaki en yüksek değerli kartın sembolünü döndürür.
    """
    cards = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', cards_str)
    if not cards:
        return None

    max_value = -1
    largest_value_suit = None
    
    values = [get_baccarat_value(card[0]) for card in cards]
    if len(values) == 2 and values[0] == values[1]:
        return None

    for card_char, suit in cards:
        value = get_baccarat_value(card_char)
        if value > max_value:
            max_value = value
            largest_value_suit = suit
        elif value == max_value:
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
                 'is_final': False, 'is_player_drawing': False, 'is_c2_3': False}
    
    game_info['is_player_drawing'] = is_player_drawing(text)

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
        
        if c_tag == '#C2_3':
            game_info['is_c2_3'] = True
        
        if ('✅' in text or '🔰' in text or '#X' in text):
            game_info['is_final'] = True
    
    return game_info

async def send_new_signal(game_num, signal_suit):
    """Yeni sinyal gönderir ve Martingale takibini başlatır."""
    
    global is_signal_active
    
    if is_signal_active:
        print("UYARI: Zaten aktif bir sinyal takibi var. Yeni sinyal gönderilmiyor.")
        return
        
    signal_full_text = f"**#N{game_num} - Oyuncu {signal_suit} - {MAX_MARTINGALE_STEPS}D**"

    try:
        sent_message = await client.send_message(KANAL_HEDEF, signal_full_text)
        print(f"Yeni sinyal gönderildi: {signal_full_text}")

        martingale_trackers[game_num] = {
            'message_obj': sent_message,
            'step': 0,
            'signal_suit': signal_suit,
            'sent_game_number': game_num,
            'expected_game_number_for_check': game_num
        }
        is_signal_active = True
        print(f"DEBUG: Sinyal #N{game_num} takibe alındı. is_signal_active = True")

    except FloodWaitError as e:
        print(f"FloodWait hatası (sinyal gönderimi): {e.seconds} saniye bekleniyor.")
        await asyncio.sleep(e.seconds)
        await send_new_signal(game_num, signal_suit)
    except Exception as e:
        print(f"Sinyal gönderme hatası: {e}")

async def check_martingale_trackers():
    """Gönderilen sinyallerin Martingale adımlarını takip eder ve günceller."""
    global martingale_trackers, is_signal_active

    trackers_to_remove = []

    for signal_game_num, tracker_info in list(martingale_trackers.items()):
        current_step = tracker_info['step']
        signal_message_obj = tracker_info['message_obj']
        signal_suit = tracker_info['signal_suit']
        
        game_to_check = tracker_info['expected_game_number_for_check']
        
        if game_to_check not in game_results:
            continue
        
        result_info = game_results.get(game_to_check)

        if not result_info['is_final']:
            continue
        
        player_cards_str = result_info['player_cards']
        
        # Sinyalin kazanıp kazanmadığı daha güvenli bir şekilde kontrol ediliyor
        signal_won_this_step = bool(re.search(re.escape(signal_suit), player_cards_str))
            
        print(f"DEBUG: Sinyal #N{signal_game_num} (Adım {current_step}): Kontrol ediliyor. Beklenen: '{signal_suit}', Oyuncu kartlarındaki string: '{player_cards_str}'")

        if signal_won_this_step:
            new_text = f"**#N{signal_game_num} - Oyuncu {signal_suit} | ✅ {current_step}️⃣**"
            try:
                await signal_message_obj.edit(new_text)
                print(f"DEBUG: Sinyal #N{signal_game_num} kazanma nedeniyle başarıyla düzenlendi.")
            except MessageNotModifiedError:
                pass
            except Exception as e:
                print(f"Mesaj düzenleme hatası (kazandı): {e}")
            
            trackers_to_remove.append(signal_game_num)
            is_signal_active = False
            print("DEBUG: Sinyal serisi kazandı. is_signal_active = False")

        else:
            if current_step < MAX_MARTINGALE_STEPS:
                next_step = current_step + 1
                # Bir sonraki oyun numarasını döngü kontrolü ile hesapla
                next_game_num = get_next_game_number(game_to_check)
                
                martingale_trackers[signal_game_num]['step'] = next_step
                martingale_trackers[signal_game_num]['expected_game_number_for_check'] = next_game_num
                print(f"DEBUG: Sinyal #N{signal_game_num} kazanılmadı (Adım {current_step}). Takip #N{martingale_trackers[signal_game_num]['expected_game_number_for_check']} ile {next_step}. adıma geçiliyor.")
            else:
                new_text = f"**#N{signal_game_num} - Oyuncu {signal_suit} | ❌**"
                try:
                    await signal_message_obj.edit(new_text)
                    print(f"DEBUG: Sinyal #N{signal_game_num} kayıp nedeniyle başarıyla düzenlendi.")
                except MessageNotModifiedError:
                    pass
                except Exception as e:
                    print(f"Mesaj düzenleme hatası (kaybetti): {e}")
                
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False
                print("DEBUG: Sinyal serisi kaybetti. is_signal_active = False")

    for game_num_to_remove in trackers_to_remove:
        if game_num_to_remove in martingale_trackers:
            del martingale_trackers[game_num_to_remove]
            print(f"DEBUG: Martingale takipçisi #N{game_num_to_remove} kaldırıldı.")
    print(f"DEBUG: Martingale takipçileri güncellendi: {martingale_trackers}")


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

    if game_info['game_number'] is None:
        return

    game_results[game_info['game_number']] = game_info
    
    await check_martingale_trackers()

    if not is_signal_active:
        if game_info['is_final'] and game_info.get('is_c2_3'):
            trigger_game_num = game_info['game_number']
            signal_suit = extract_largest_value_suit(game_info['player_cards'])
            
            if signal_suit is not None:
                # Sinyali bir sonraki döngüsel oyun numarasına gönder
                next_game_num = get_next_game_number(trigger_game_num)
                await send_new_signal(next_game_num, signal_suit)
            else:
                print(f"DEBUG: Oyun #N{trigger_game_num} için sinyal koşulları sağlanmadı (aynı değerli veya 0 değerli kartlar). Sinyal gönderilmiyor.")

# ==============================================================================
# Botun Başlatılması
# ==============================================================================
if __name__ == '__main__':
    print("Bot başlatılıyor...")
    with client:
        client.run_until_disconnected()