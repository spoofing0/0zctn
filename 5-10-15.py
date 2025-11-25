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

KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@kbubakara"

client = TelegramClient('kbu_baccarat_bot', API_ID, API_HASH)

# ==============================================================================
# Global Değişkenler ve Takip Mekanizmaları
# ==============================================================================
game_results = {}
MAX_MARTINGALE_STEPS = 7

card_value_trackers = {}
last_player_cards = deque(maxlen=50)  # Son 50 oyunu sakla

# ==============================================================================
# Yardımcı Fonksiyonlar
# ==============================================================================

def get_baccarat_value(card_char):
    if card_char == '10':
        return 10
    if card_char in 'AKQJ2T':
        return 0
    elif card_char.isdigit():
        return int(card_char)
    return -1

def get_all_card_values(player_cards_str):
    cards = re.findall(r'(10|[A2-9TJQK])[♣♦♥♠]', player_cards_str)
    return cards

def get_next_game_number(current_game_num):
    next_num = current_game_num + 1
    if next_num > 1440:
        return 1
    return next_num

def extract_game_info_from_message(text):
    game_info = {'game_number': None, 'player_cards': '', 'banker_cards': '',
                 'is_final': False, 'is_player_drawing': False}
    
    game_info['is_player_drawing'] = '▶️' in text

    game_match = re.search(
        r'#N(\d+)\s+.*?\((.*?)\)\s+.*?(\d+\s+\(.*\))\s+.*?(#C(\d)_(\d))',
        text.replace('️', ''),
        re.DOTALL
    )

    if game_match:
        game_info['game_number'] = int(game_match.group(1))
        game_info['player_cards'] = game_match.group(2)
        game_info['banker_cards'] = game_match.group(3)
        
        if not game_info['is_player_drawing'] and ('✅' in text or '🔰' in text or '#X' in text):
            game_info['is_final'] = True
    
    return game_info

def get_multi_level_signal():
    """5-10-15 EL SEVİYELİ SİSTEM"""
    global last_player_cards
    
    all_possible_cards = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    
    # Seviye 3: 15 El kontrolü
    if len(last_player_cards) >= 15:
        last_15_cards = []
        for cards_list in list(last_player_cards)[-15:]:
            last_15_cards.extend(cards_list)
        
        missing_15 = [card for card in all_possible_cards if card not in last_15_cards]
        if missing_15:
            selected_card = random.choice(missing_15)
            print(f"🎯 15-EL SİNYAL: {selected_card} (Son 15 elde çıkmayan)")
            return selected_card, "15-HNCO"
    
    # Seviye 2: 10 El kontrolü
    if len(last_player_cards) >= 10:
        last_10_cards = []
        for cards_list in list(last_player_cards)[-10:]:
            last_10_cards.extend(cards_list)
        
        missing_10 = [card for card in all_possible_cards if card not in last_10_cards]
        if missing_10:
            selected_card = random.choice(missing_10)
            print(f"🎯 10-EL SİNYAL: {selected_card} (Son 10 elde çıkmayan)")
            return selected_card, "10-HNCO"
    
    # Seviye 1: 5 El kontrolü
    if len(last_player_cards) >= 5:
        last_5_cards = []
        for cards_list in list(last_player_cards)[-5:]:
            last_5_cards.extend(cards_list)
        
        missing_5 = [card for card in all_possible_cards if card not in last_5_cards]
        if missing_5:
            selected_card = random.choice(missing_5)
            print(f"🎯 5-EL SİNYAL: {selected_card} (Son 5 elde çıkmayan)")
            return selected_card, "5-HNCO"
    
    # Seviye 0: Güvenli kartlar (hiçbiri çalışmazsa)
    selected_card = random.choice(['8', '9'])
    print(f"🎯 GÜVENLİ SİNYAL: {selected_card} (Tüm seviyelerde kartlar çıktı)")
    return selected_card, "GÜVENLİ"

async def send_signal(game_num, signal_data):
    signal_value, level_info = signal_data
    
    signal_full_text = f"**#N{game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D | {level_info}**"

    try:
        sent_message = await client.send_message(KANAL_HEDEF, signal_full_text)
        print(f"🆕 YENİ SİNYAL: {signal_full_text}")

        card_value_trackers[game_num] = {
            'message_obj': sent_message,
            'step': 0,
            'signal_value': signal_value,
            'level_info': level_info,
            'sent_game_number': game_num,
            'expected_game_number_for_check': game_num
        }

    except FloodWaitError as e:
        print(f"⏳ FloodWait: {e.seconds}s")
        await asyncio.sleep(e.seconds)
        await send_signal(game_num, signal_data)
    except Exception as e:
        print(f"❌ Sinyal gönderme hatası: {e}")

async def check_martingale_trackers():
    trackers_to_remove = []

    for signal_game_num, tracker_info in list(card_value_trackers.items()):
        current_step = tracker_info['step']
        signal_message_obj = tracker_info['message_obj']
        signal_value = tracker_info['signal_value']
        level_info = tracker_info['level_info']
        
        game_to_check = tracker_info['expected_game_number_for_check']
        
        if game_to_check not in game_results:
            continue
        
        result_info = game_results.get(game_to_check)

        if not result_info['is_final']:
            continue
        
        player_cards_str = result_info['player_cards']
        card_values = get_all_card_values(player_cards_str)
        signal_won_this_step = (signal_value in card_values)
        
        print(f"🔍 {level_info} #N{signal_game_num} (Adım {current_step}): {'✅' if signal_won_this_step else '❌'}")

        if signal_won_this_step:
            new_text = f"**#N{signal_game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D | {level_info} | ✅ {current_step}️⃣**"
            
            try:
                await signal_message_obj.edit(new_text)
                print(f"🎉 KAZANÇ: {level_info} #N{signal_game_num} (Adım {current_step})")
            except MessageNotModifiedError:
                pass
            except Exception as e:
                print(f"⚠️ Mesaj düzenleme hatası (kazandı): {e}")
            
            trackers_to_remove.append(signal_game_num)

        else:
            if current_step < MAX_MARTINGALE_STEPS:
                next_step = current_step + 1
                next_game_num = get_next_game_number(game_to_check)
                
                card_value_trackers[signal_game_num]['step'] = next_step
                card_value_trackers[signal_game_num]['expected_game_number_for_check'] = next_game_num
                print(f"🔄 DEVAM: {level_info} #N{signal_game_num} → Adım {next_step}")
            else:
                new_text = f"**#N{signal_game_num} | {signal_value} - {MAX_MARTINGALE_STEPS}D | {level_info} | ❌**"
                
                try:
                    await signal_message_obj.edit(new_text)
                    print(f"💥 KAYIP: {level_info} #N{signal_game_num} (Maksimum adım)")
                except MessageNotModifiedError:
                    pass
                except Exception as e:
                    print(f"⚠️ Mesaj düzenleme hatası (kaybetti): {e}")
                
                trackers_to_remove.append(signal_game_num)

    for game_num_to_remove in trackers_to_remove:
        if game_num_to_remove in card_value_trackers:
            del card_value_trackers[game_num_to_remove]

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
    
    await check_martingale_trackers()

    if game_info['is_final']:
        player_cards = get_all_card_values(game_info['player_cards'])
        if player_cards:
            last_player_cards.append(player_cards)
            print(f"📊 Kart verisi kaydedildi: {len(last_player_cards)} oyun")
        
        trigger_game_num = game_info['game_number']
        next_game_num = get_next_game_number(trigger_game_num)
        
        signal_data = get_multi_level_signal()
        await send_signal(next_game_num, signal_data)

if __name__ == '__main__':
    print("🎯 BACCARAT BOTU BAŞLATILIYOR...")
    print(f"📊 Martingale: 0️⃣'dan {MAX_MARTINGALE_STEPS}️⃣'ye kadar")
    print("🎯 YENİ STRATEJİ: 5-10-15 EL SEVİYELİ SİSTEM")
    print("📈 Seviye 3: 15 el (en güçlü sinyal)")
    print("📈 Seviye 2: 10 el (güçlü sinyal)") 
    print("📈 Seviye 1: 5 el (temel sinyal)")
    print("📈 Seviye 0: Güvenli kartlar (fallback)")
    print("🔍 Sinyal mesajlarında seviye bilgisi görünecek")
    
    with client:
        client.run_until_disconnected()
