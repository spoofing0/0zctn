# -*- coding: utf-8 -*-
import re, json, os, asyncio, sys, pytz, signal
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
from collections import defaultdict, deque

# 🔐 API BİLGİLERİ
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
BOT_TOKEN = ''  # 🔑 Buraya bot tokenınızı yazın
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"  # 📢 Hedef kanal
ADMIN_ID = 1136442929  # 👑 Admin ID
SISTEM_MODU = "normal_hibrit"
GMT3 = pytz.timezone('Europe/Istanbul')

# 🎯 SİSTEM DEĞİŞKENLERİ
game_results, martingale_trackers, color_trend, recent_games = {}, {}, [], []
MAX_MARTINGALE_STEPS, MAX_GAME_NUMBER, is_signal_active, daily_signal_count = 3, 1440, False, 0

# 🎰 5.5 ALT/ÜST SİSTEMİ
alt_ust_stats = {
    'alt': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0},
    'ust': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0}
}
alt_ust_trend = []
ALT_UST_MARTINGALE_STEPS = 3

# 🃏 10.5 OYUNCU+BANKER SİSTEMİ
oyuncu_banker_stats = {
    'alt': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0},
    'ust': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0}
}
oyuncu_banker_trend = []
OYUNCU_BANKER_MARTINGALE_STEPS = 3

# 🔥 C2-3 TRİGGER SİSTEMİ
C2_3_TYPES = {
    '#C2_3': {'emoji': '🔴', 'name': 'KLASİK', 'confidence': 0.9, 'stats': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0}},
    '#C2_2': {'emoji': '🔵', 'name': 'ALTERNATİF', 'confidence': 0.7, 'stats': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0}},
    '#C3_2': {'emoji': '🟢', 'name': 'VARYANT', 'confidence': 0.6, 'stats': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0}},
    '#C3_3': {'emoji': '🟡', 'name': 'ÖZEL', 'confidence': 0.7, 'stats': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0}}
}

# 🚀 İSTEMCİ BAŞLATMA - HATA YÖNETİMİ İLE
try:
    client = TelegramClient('/root/0zctn/sansar_bot.session', API_ID, API_HASH)
    client.start(bot_token=BOT_TOKEN)
    print("✅ Telegram istemcisi başarıyla başlatıldı!")
except Exception as e:
    print(f"❌ İstemci başlatma hatası: {e}")
    sys.exit(1)

# 🎴 KART SİSTEMİ FONKSİYONLARI
def get_suit_display_name(suit_symbol):
    suit_names = {'♠': '♠️ MAÇA', '♥': '♥️ KALP', '♦': '♦️ KARO', '♣': '♣️ SİNEK'}
    return suit_names.get(suit_symbol, f"❓ {suit_symbol}")

def get_baccarat_value(card_char):
    if card_char == '10': return 10
    if card_char in 'AKQJ2T': return 0
    elif card_char.isdigit(): return int(card_char)
    return -1

def extract_largest_value_suit(cards_str):
    try:
        cards = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', cards_str)
        if not cards: return None
        max_value, largest_value_suit = -1, None
        values = [get_baccarat_value(card[0]) for card in cards]
        if len(values) == 2 and values[0] == values[1]: return None
        for card_char, suit in cards:
            value = get_baccarat_value(card_char)
            if value > max_value: max_value, largest_value_suit = value, suit
        return largest_value_suit if max_value > 0 else None
    except Exception as e:
        print(f"❌ Hata extract_largest_value_suit: {e}")
        return None

def extract_game_info_from_message(text):
    game_info = {'game_number': None, 'player_cards': '', 'banker_cards': '', 'is_final': False, 'is_player_drawing': False, 'is_c2_3': False, 'c2_3_type': None, 'c2_3_description': ''}
    try:
        game_match = re.search(r'#N(\d+)', text)
        if game_match: 
            game_info['game_number'] = int(game_match.group(1))
        
        player_match = re.search(r'Player\s*:\s*(\d+)\s*\((.*?)\)', text)
        if not player_match:
            player_match = re.search(r'(\d+)\s*\((.*?)\)', text)
        if player_match: 
            game_info['player_cards'] = player_match.group(2)
        
        banker_match = re.search(r'Banker\s*:\s*(\d+)\s*\((.*?)\)', text)
        if not banker_match:
            banker_match = re.search(r'\d+\s+\((.*?)\)', text)
        if banker_match: 
            game_info['banker_cards'] = banker_match.group(1) if banker_match.lastindex >= 1 else banker_match.group(0)
        
        for trigger_type, trigger_data in C2_3_TYPES.items():
            if trigger_type in text:
                game_info['is_c2_3'], game_info['c2_3_type'], game_info['c2_3_description'] = True, trigger_type, trigger_data['name']
                break
        
        if ('✅' in text or '🔰' in text or '#X' in text or 'RESULT' in text or 'RES:' in text):
            game_info['is_final'] = True
            
        print(f"🎮 Oyun #{game_info['game_number']} bilgisi: Player={game_info['player_cards'][:30]}..., Banker={game_info['banker_cards'][:30]}..., Final={game_info['is_final']}, C2_3={game_info['is_c2_3']}")
        
    except Exception as e: 
        print(f"❌ Oyun bilgisi çıkarma hatası: {e}")
    
    return game_info

# 🎯 5.5 ALT/ÜST TAHMİN SİSTEMİ
def predict_alt_ust(player_cards, banker_cards):
    try:
        player_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
        player_values = [get_baccarat_value(card[0]) for card in player_card_data]
        total_value = sum(player_values)
        
        if total_value <= 5.5:
            return "alt", total_value
        else:
            return "ust", total_value
            
    except Exception as e:
        print(f"❌ Alt/Üst tahmin hatası: {e}")
        return None, 0

# 🃏 10.5 OYUNCU+BANKER TAHMİN SİSTEMİ
def calculate_player_banker_total(player_cards, banker_cards):
    try:
        player_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
        player_values = [get_baccarat_value(card[0]) for card in player_card_data]
        player_total = sum(player_values) % 10
        
        banker_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)
        banker_values = [get_baccarat_value(card[0]) for card in banker_card_data]
        banker_total = sum(banker_values) % 10
        
        total_hand_value = player_total + banker_total
        
        if total_hand_value <= 10.5:
            return "alt", total_hand_value
        else:
            return "ust", total_hand_value
            
    except Exception as e:
        print(f"❌ Oyuncu+Banker toplam hatası: {e}")
        return None, 0

# 🔍 5.5 ALT/ÜST PATTERN ANALİZİ
def analyze_alt_ust_pattern(player_cards, banker_cards, game_number):
    try:
        tahmin, deger = predict_alt_ust(player_cards, banker_cards)
        if not tahmin:
            return None, "❌ Hesaplama hatası"
        
        alt_ust_trend.append(tahmin)
        if len(alt_ust_trend) > 10:
            alt_ust_trend.pop(0)
        
        player_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
        total_cards = len(player_card_data)
        total_value = sum([get_baccarat_value(card[0]) for card in player_card_data])
        
        if total_cards >= 5:
            return tahmin, "🎴 5+ KART - ALT/UST"
        elif total_value <= 3:
            return "alt", "📉 DÜŞÜK DEĞER - ALT"
        elif total_value >= 8:
            return "ust", "📈 YÜKSEK DEĞER - ÜST"
        elif len(alt_ust_trend) >= 3 and alt_ust_trend[-3:] == [tahmin] * 3:
            return tahmin, "🔄 3x TEKRAR - ALT/UST"
        else:
            return tahmin, "⚡ STANDART - ALT/UST"
            
    except Exception as e:
        print(f"❌ Alt/Üst pattern analiz hatası: {e}")
        return None, f"❌ Hata: {e}"

# 🔍 10.5 OYUNCU+BANKER PATTERN ANALİZİ
def analyze_player_banker_pattern(player_cards, banker_cards, game_number):
    try:
        tahmin, deger = calculate_player_banker_total(player_cards, banker_cards)
        if not tahmin:
            return None, "❌ Hesaplama hatası"
        
        oyuncu_banker_trend.append(tahmin)
        if len(oyuncu_banker_trend) > 10:
            oyuncu_banker_trend.pop(0)
        
        player_total = sum([get_baccarat_value(card[0]) for card in re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)]) % 10
        banker_total = sum([get_baccarat_value(card[0]) for card in re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)]) % 10
        total_hand_value = player_total + banker_total
        
        if total_hand_value <= 8:
            return "alt", "📉 DÜŞÜK EL TOPLAM"
        elif total_hand_value >= 13:
            return "ust", "📈 YÜKSEK EL TOPLAM"
        elif player_total >= 7 and banker_total >= 7:
            return "ust", "🎯 ÇİFT YÜKSEK EL"
        elif len(oyuncu_banker_trend) >= 3 and oyuncu_banker_trend[-3:] == [tahmin] * 3:
            return tahmin, "🔄 3x TEKRAR - O/B TOPLAM"
        else:
            return tahmin, "⚡ STANDART - O/B TOPLAM"
            
    except Exception as e:
        print(f"❌ Oyuncu+Banker pattern analiz hatası: {e}")
        return None, f"❌ Hata: {e}"

def get_next_game_number(current_game_num):
    next_num = current_game_num + 1
    return 1 if next_num > MAX_GAME_NUMBER else next_num

# 🚀 5.5 ALT/ÜST HİBRİT SİSTEM
async def alt_ust_hibrit_sistemi(game_info):
    print("🎯 5.5 ALT/UST analiz başlıyor...")
    
    tahmin, sebep = analyze_alt_ust_pattern(game_info['player_cards'], 
                                          game_info['banker_cards'], 
                                          game_info['game_number'])
    
    if not tahmin:
        print(f"❌ Alt/Üst: Tahmin yapılamadı - {sebep}")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    await send_alt_ust_signal(next_game_num, tahmin, sebep, game_info)

# 🚀 10.5 OYUNCU+BANKER HİBRİT SİSTEM
async def oyuncu_banker_hibrit_sistemi(game_info):
    print("🎯 OYUNCU+BANKER 10.5 analiz başlıyor...")
    
    tahmin, sebep = analyze_player_banker_pattern(game_info['player_cards'], 
                                          game_info['banker_cards'], 
                                          game_info['game_number'])
    
    if not tahmin:
        print(f"❌ Oyuncu+Banker 10.5: Tahmin yapılamadı - {sebep}")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    await send_player_banker_signal(next_game_num, tahmin, sebep, game_info)

# 📢 5.5 ALT/ÜST SİNYAL GÖNDERME
async def send_alt_ust_signal(game_num, tahmin, reason, game_info=None):
    global is_signal_active, daily_signal_count
        
    try:
        tahmin_emoji = "⬇️ ALT" if tahmin == "alt" else "⬆️ ÜST"
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        
        signal_text = f"""🎯 **5.5 ALT/UST SİNYALİ** 🎯

#N{game_num} - {tahmin_emoji}
📊 Sebep: {reason}
🎮 Strateji: Martingale {ALT_UST_MARTINGALE_STEPS} Seviye
🕒 {gmt3_time} (GMT+3)

🔮 SONUÇ: BEKLENİYOR... ⏳"""
        
        sent_message = await client.send_message(KANAL_HEDEF, signal_text)
        print(f"📢 5.5 Alt/Üst sinyal gönderildi: #N{game_num} - {tahmin_emoji}")
        
        tracker_key = f"{game_num}_alt_ust"
        martingale_trackers[tracker_key] = {
            'message_obj': sent_message, 
            'step': 0, 
            'signal_type': 'alt_ust',
            'signal_tahmin': tahmin,
            'sent_game_number': game_num, 
            'expected_game_number_for_check': game_num, 
            'start_time': datetime.now(GMT3), 
            'reason': reason,
            'results': []
        }
        
        is_signal_active = True
        daily_signal_count += 1
        
    except Exception as e: 
        print(f"❌ 5.5 Alt/Üst sinyal gönderme hatası: {e}")

# 📢 10.5 OYUNCU+BANKER SİNYAL GÖNDERME
async def send_player_banker_signal(game_num, tahmin, reason, game_info=None):
    global is_signal_active, daily_signal_count
        
    try:
        tahmin_emoji = "⬇️ ALT" if tahmin == "alt" else "⬆️ ÜST"
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        
        signal_text = f"""🎯 **10.5 ALT/UST SİNYALİ** 🎯

#N{game_num} - {tahmin_emoji}
📊 Sebep: {reason}
🎮 Strateji: Martingale {OYUNCU_BANKER_MARTINGALE_STEPS} Seviye
🕒 {gmt3_time} (GMT+3)

🔮 SONUÇ: BEKLENİYOR... ⏳"""
        
        sent_message = await client.send_message(KANAL_HEDEF, signal_text)
        print(f"📢 10.5 Alt/Üst sinyal gönderildi: #N{game_num} - {tahmin_emoji}")
        
        tracker_key = f"{game_num}_oyuncu_banker"
        martingale_trackers[tracker_key] = {
            'message_obj': sent_message, 
            'step': 0, 
            'signal_type': 'oyuncu_banker',
            'signal_tahmin': tahmin,
            'sent_game_number': game_num, 
            'expected_game_number_for_check': game_num, 
            'start_time': datetime.now(GMT3), 
            'reason': reason,
            'results': []
        }
        
        is_signal_active = True
        daily_signal_count += 1
        
    except Exception as e: 
        print(f"❌ 10.5 Alt/Üst sinyal gönderme hatası: {e}")

# 🔍 5.5 ALT/ÜST KONTROL SİSTEMİ
async def check_alt_ust_tracker(tracker_info):
    current_step = tracker_info['step']
    game_to_check = tracker_info['expected_game_number_for_check']
    tahmin = tracker_info['signal_tahmin']
    
    if game_to_check not in game_results:
        return False
    
    result_info = game_results[game_to_check]
    if not result_info['is_final']:
        return False
    
    gercek_tahmin, gercek_deger = predict_alt_ust(result_info['player_cards'], 
                                                 result_info['banker_cards'])
    
    kazandi = (gercek_tahmin == tahmin)
    
    print(f"🔍 5.5 Alt/Üst kontrol: #{tracker_info['sent_game_number']} → #{game_to_check} | Tahmin: {tahmin} | Gerçek: {gercek_tahmin} | Değer: {gercek_deger} | Kazandı: {kazandi}")
    
    if kazandi:
        result_details = f"#{game_to_check} ✅ Kazanç - {current_step}. seviye | Değer: {gercek_deger}"
        await update_alt_ust_message(tracker_info, 'step_result', current_step, result_details)
        await asyncio.sleep(1)
        await update_alt_ust_message(tracker_info, 'win', current_step)
        
        update_alt_ust_stats(tahmin, 'win', current_step)
        
        print(f"🎉 5.5 Alt/Üst #{tracker_info['sent_game_number']} KAZANDI! Seviye: {current_step}")
        return True
    else:
        result_details = f"#{game_to_check} ❌ Kayıp - {current_step}. seviye | Değer: {gercek_deger}"
        await update_alt_ust_message(tracker_info, 'step_result', current_step, result_details)
        await asyncio.sleep(1)
        
        if current_step < ALT_UST_MARTINGALE_STEPS:
            next_step = current_step + 1
            next_game_num = get_next_game_number(game_to_check)
            
            tracker_info['step'] = next_step
            tracker_info['expected_game_number_for_check'] = next_game_num
            
            await update_alt_ust_message(tracker_info, 'progress', next_step)
            print(f"🔄 5.5 Alt/Üst #{tracker_info['sent_game_number']} → {next_step}. seviye → #{next_game_num}")
            return False
        else:
            await update_alt_ust_message(tracker_info, 'loss', current_step)
            
            update_alt_ust_stats(tahmin, 'loss', current_step)
            
            print(f"💥 5.5 Alt/Üst #{tracker_info['sent_game_number']} KAYBETTİ! Son seviye: {current_step}")
            return True

# 🔍 10.5 OYUNCU+BANKER KONTROL SİSTEMİ
async def check_player_banker_tracker(tracker_info):
    current_step = tracker_info['step']
    game_to_check = tracker_info['expected_game_number_for_check']
    tahmin = tracker_info['signal_tahmin']
    
    if game_to_check not in game_results:
        return False
    
    result_info = game_results[game_to_check]
    if not result_info['is_final']:
        return False
    
    gercek_tahmin, gercek_deger = calculate_player_banker_total(
        result_info['player_cards'], 
        result_info['banker_cards']
    )
    
    kazandi = (gercek_tahmin == tahmin)
    
    print(f"🔍 10.5 Alt/Üst kontrol: #{tracker_info['sent_game_number']} → #{game_to_check} | Tahmin: {tahmin} | Gerçek: {gercek_tahmin} | Değer: {gercek_deger} | Kazandı: {kazandi}")
    
    if kazandi:
        result_details = f"#{game_to_check} ✅ Kazanç - {current_step}. seviye | Toplam: {gercek_deger}"
        await update_player_banker_message(tracker_info, 'step_result', current_step, result_details)
        await asyncio.sleep(1)
        await update_player_banker_message(tracker_info, 'win', current_step)
        
        update_player_banker_stats(tahmin, 'win', current_step)
        
        print(f"🎉 10.5 Alt/Üst #{tracker_info['sent_game_number']} KAZANDI! Seviye: {current_step}")
        return True
    else:
        result_details = f"#{game_to_check} ❌ Kayıp - {current_step}. seviye | Toplam: {gercek_deger}"
        await update_player_banker_message(tracker_info, 'step_result', current_step, result_details)
        await asyncio.sleep(1)
        
        if current_step < OYUNCU_BANKER_MARTINGALE_STEPS:
            next_step = current_step + 1
            next_game_num = get_next_game_number(game_to_check)
            
            tracker_info['step'] = next_step
            tracker_info['expected_game_number_for_check'] = next_game_num
            
            await update_player_banker_message(tracker_info, 'progress', next_step)
            print(f"🔄 10.5 Alt/Üst #{tracker_info['sent_game_number']} → {next_step}. seviye → #{next_game_num}")
            return False
        else:
            await update_player_banker_message(tracker_info, 'loss', current_step)
            
            update_player_banker_stats(tahmin, 'loss', current_step)
            
            print(f"💥 10.5 Alt/Üst #{tracker_info['sent_game_number']} KAYBETTİ! Son seviye: {current_step}")
            return True

# ✏️ 5.5 ALT/ÜST MESAJ GÜNCELLEME
async def update_alt_ust_message(tracker_info, result_type, current_step=None, result_details=None):
    try:
        game_num = tracker_info['sent_game_number']
        tahmin = tracker_info['signal_tahmin']
        reason = tracker_info['reason']
        message_obj = tracker_info['message_obj']
        
        if current_step is None:
            current_step = tracker_info.get('step', 0)
        
        tahmin_emoji = "⬇️ ALT" if tahmin == "alt" else "⬆️ ÜST"
        
        duration = datetime.now(GMT3) - tracker_info['start_time']
        duration_str = f"{duration.seconds // 60}d {duration.seconds % 60}s"
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        
        if result_details:
            tracker_info['results'].append(result_details)
        
        if result_type == 'win':
            new_text = f"""🎉 **5.5 ALT/UST KAZANÇ** 🎉

#N{game_num} - {tahmin_emoji}
📊 Sebep: {reason}
🎮 Seviye: {current_step}. Seviye
⏱️ Süre: {duration_str}
🕒 Bitiş: {gmt3_time}

✨ **SONUÇ: KAZANDINIZ!** 💰"""
        elif result_type == 'loss':
            new_text = f"""💥 **5.5 ALT/UST KAYIP** 💥

#N{game_num} - {tahmin_emoji}
📊 Sebep: {reason}
🎮 Seviye: {current_step}. Seviye
⏱️ Süre: {duration_str}
🕒 Bitiş: {gmt3_time}

😔 **SONUÇ: KAYBETTİNİZ** 📉"""
        elif result_type == 'progress':
            step_details = f"{current_step}. seviye → #{tracker_info['expected_game_number_for_check']}"
            results_history = "\n".join([f"• {r}" for r in tracker_info['results']]) if tracker_info['results'] else "• 🎯 İlk deneme"
            new_text = f"""🔄 **5.5 ALT/UST MARTINGALE** 🔄

#N{game_num} - {tahmin_emoji}
📊 Sebep: {reason}
🎯 Adım: {step_details}
⏱️ Süre: {duration_str}
🕒 Son Güncelleme: {gmt3_time}

📈 Geçmiş:
{results_history}

🎮 **SONRAKİ: #{tracker_info['expected_game_number_for_check']}**"""
        elif result_type == 'step_result':
            new_text = f"""📊 **5.5 ALT/UST ADIM SONUCU** 📊

#N{game_num} - {tahmin_emoji}
🎯 Adım: {current_step}. seviye
📋 Sonuç: {result_details}
⏱️ Süre: {duration_str}
🕒 Zaman: {gmt3_time}

🔄 **DEVAM EDİYOR...** ⏳"""
        
        await message_obj.edit(new_text)
        print(f"✏️ 5.5 Alt/Üst sinyal güncellendi: #{game_num} - {result_type} - Seviye: {current_step}")
        
    except MessageNotModifiedError: 
        pass
    except Exception as e: 
        print(f"❌ 5.5 Alt/Üst mesaj düzenleme hatası: {e}")

# ✏️ 10.5 OYUNCU+BANKER MESAJ GÜNCELLEME
async def update_player_banker_message(tracker_info, result_type, current_step=None, result_details=None):
    try:
        game_num = tracker_info['sent_game_number']
        tahmin = tracker_info['signal_tahmin']
        reason = tracker_info['reason']
        message_obj = tracker_info['message_obj']
        
        if current_step is None:
            current_step = tracker_info.get('step', 0)
        
        tahmin_emoji = "⬇️ ALT" if tahmin == "alt" else "⬆️ ÜST"
        
        duration = datetime.now(GMT3) - tracker_info['start_time']
        duration_str = f"{duration.seconds // 60}d {duration.seconds % 60}s"
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        
        if result_details:
            tracker_info['results'].append(result_details)
        
        if result_type == 'win':
            new_text = f"""🎉 **10.5 ALT/UST KAZANÇ** 🎉

#N{game_num} - {tahmin_emoji}
📊 Sebep: {reason}
🎮 Seviye: {current_step}. Seviye
⏱️ Süre: {duration_str}
🕒 Bitiş: {gmt3_time}

✨ **SONUÇ: KAZANDINIZ!** 💰"""
        elif result_type == 'loss':
            new_text = f"""💥 **10.5 ALT/UST KAYIP** 💥

#N{game_num} - {tahmin_emoji}
📊 Sebep: {reason}
🎮 Seviye: {current_step}. Seviye
⏱️ Süre: {duration_str}
🕒 Bitiş: {gmt3_time}

😔 **SONUÇ: KAYBETTİNİZ** 📉"""
        elif result_type == 'progress':
            step_details = f"{current_step}. seviye → #{tracker_info['expected_game_number_for_check']}"
            results_history = "\n".join([f"• {r}" for r in tracker_info['results']]) if tracker_info['results'] else "• 🎯 İlk deneme"
            new_text = f"""🔄 **10.5 ALT/UST MARTINGALE** 🔄

#N{game_num} - {tahmin_emoji}
📊 Sebep: {reason}
🎯 Adım: {step_details}
⏱️ Süre: {duration_str}
🕒 Son Güncelleme: {gmt3_time}

📈 Geçmiş:
{results_history}

🎮 **SONRAKİ: #{tracker_info['expected_game_number_for_check']}**"""
        elif result_type == 'step_result':
            new_text = f"""📊 **10.5 ALT/UST ADIM SONUCU** 📊

#N{game_num} - {tahmin_emoji}
🎯 Adım: {current_step}. seviye
📋 Sonuç: {result_details}
⏱️ Süre: {duration_str}
🕒 Zaman: {gmt3_time}

🔄 **DEVAM EDİYOR...** ⏳"""
        
        await message_obj.edit(new_text)
        print(f"✏️ 10.5 Alt/Üst sinyal güncellendi: #{game_num} - {result_type} - Seviye: {current_step}")
        
    except MessageNotModifiedError: 
        pass
    except Exception as e: 
        print(f"❌ 10.5 Alt/Üst mesaj düzenleme hatası: {e}")

# 📈 5.5 ALT/ÜST İSTATİSTİK GÜNCELLEME
def update_alt_ust_stats(tahmin, result_type, steps=0):
    stats = alt_ust_stats[tahmin]
    stats['total'] += 1
    
    if result_type == 'win':
        stats['wins'] += 1
        stats['profit'] += 1
    else:
        stats['losses'] += 1
        stats['profit'] -= (2**steps - 1)

# 📈 10.5 OYUNCU+BANKER İSTATİSTİK GÜNCELLEME
def update_player_banker_stats(tahmin, result_type, steps=0):
    stats = oyuncu_banker_stats[tahmin]
    stats['total'] += 1
    
    if result_type == 'win':
        stats['wins'] += 1
        stats['profit'] += 1
    else:
        stats['losses'] += 1
        stats['profit'] -= (2**steps - 1)

# 🔄 TAKİPÇİ KONTROL SİSTEMİ
async def check_martingale_trackers():
    global martingale_trackers, is_signal_active
    trackers_to_remove = []
    
    for signal_key, tracker_info in list(martingale_trackers.items()):
        if 'signal_type' in tracker_info and tracker_info['signal_type'] == 'alt_ust':
            completed = await check_alt_ust_tracker(tracker_info)
            if completed:
                trackers_to_remove.append(signal_key)
                is_signal_active = False
        
        elif 'signal_type' in tracker_info and tracker_info['signal_type'] == 'oyuncu_banker':
            completed = await check_player_banker_tracker(tracker_info)
            if completed:
                trackers_to_remove.append(signal_key)
                is_signal_active = False
    
    for key_to_remove in trackers_to_remove:
        if key_to_remove in martingale_trackers: 
            del martingale_trackers[key_to_remove]
            print(f"🧹 Takipçi temizlendi: {key_to_remove}")

# 📩 ANA MESAJ İŞLEYİCİ
@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_source_channel_message(event):
    try:
        message = event.message
        text = message.text or ""
        cleaned_text = re.sub(r'\*\*', '', text).strip()
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        print(f"📩 [{gmt3_time}] Mesaj: #{len(cleaned_text)} karakter")
        game_info = extract_game_info_from_message(cleaned_text)
        if game_info['game_number'] is None: return
        game_results[game_info['game_number']] = game_info
        await check_martingale_trackers()
        if not is_signal_active:
            if game_info['is_final'] and game_info.get('is_c2_3'):
                trigger_game_num, c2_3_type, c2_3_desc = game_info['game_number'], game_info['c2_3_type'], game_info['c2_3_description']
                print(f"🎯 {c2_3_desc} tespit edildi: #{trigger_game_num} - {c2_3_type}")
                
                # 2 BAĞIMSIZ SİSTEM AYNI ANDA ÇALIŞACAK
                await alt_ust_hibrit_sistemi(game_info)      # 🎯 5.5 Alt/Üst
                await oyuncu_banker_hibrit_sistemi(game_info) # 🃏 10.5 Alt/Üst
                    
    except Exception as e: 
        print(f"❌ Mesaj işleme hatası: {e}")

# 🎮 KOMUT SİSTEMİ
@client.on(events.NewMessage(pattern='(?i)/basla'))
async def handle_start(event): 
    await event.reply("🎉 Royal Baccarat Bot Aktif! 🚀")

@client.on(events.NewMessage(pattern='(?i)/durum'))
async def handle_durum(event):
    aktif_sinyal = "✅ Evet" if is_signal_active else "❌ Hayır"
    gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
    aktif_takipciler = "\n".join([f"• #{num.split('_')[0]} (Seviye {info['step']}) - {info['signal_type']}" for num, info in martingale_trackers.items()])
    if not aktif_takipciler: 
        aktif_takipciler = "• 📭 Aktif sinyal yok"
    
    durum_mesaji = f"""🏰 **ROYAL BACCARAT BOT** 🏰

📊 **Durum:** 🟢 Çalışıyor
🎯 **Aktif Sinyal:** {aktif_sinyal}
📋 **Aktif Takipçiler:**
{aktif_takipciler}
🔄 **Trend:** {color_trend[-5:] if color_trend else '📭 Yok'}
🎮 **Mod:** {SISTEM_MODU}
🕒 **Saat:** {gmt3_time} (GMT+3)
📈 **Günlük Sinyal:** {daily_signal_count}

🚀 **Sistemler:** 
• 🎯 5.5 Alt/Üst 
• 🃏 10.5 Alt/Üst
• 🔥 C2-3 Trigger

💎 **Royal Baccarat - Kazanmanın Yeni Yolu!** 💰
"""
    await event.reply(durum_mesaji)

# 🛑 GRACEFUL SHUTDOWN İŞLEMLERİ
async def shutdown():
    """Botu güvenli şekilde kapat"""
    print("🛑 Bot kapatılıyor...")
    try:
        await client.disconnect()
        print("✅ Bot bağlantısı kesildi")
    except Exception as e:
        print(f"❌ Kapatma hatası: {e}")
    finally:
        # Tüm asenkron görevleri iptal et
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        # İptal edilen görevleri bekle
        await asyncio.gather(*tasks, return_exceptions=True)
        print("🎪 Royal Baccarat Bot kapandı!")

def signal_handler(signum, frame):
    """Sinyal yakalayıcı"""
    print(f"🛑 {signum} sinyali alındı, bot kapatılıyor...")
    asyncio.create_task(shutdown())

# 🎪 BAŞLANGIÇ - GÜNCELLENMİŞ
async def main():
    """Ana bot fonksiyonu"""
    print("🎪 ROYAL BACCARAT BOT BAŞLIYOR...")
    print(f"🔐 API_ID: {API_ID}")
    print(f"📥 Kaynak Kanal: {KANAL_KAYNAK_ID}")
    print(f"📤 Hedef Kanal: {KANAL_HEDEF}")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"🎮 Varsayılan Mod: {SISTEM_MODU}")
    print(f"🎯 5.5 Alt/Üst Sistemi: 🟢 AKTİF")
    print(f"🃏 10.5 Alt/Üst Sistemi: 🟢 AKTİF")
    print(f"🔥 C2-3 Analiz Sistemi: 🟢 AKTİF")
    print(f"🕒 Saat Dilimi: GMT+3")
    
    # Sinyal işleyicileri
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        print("🔗 Bağlanıyor...")
        await client.start(bot_token=BOT_TOKEN)
        print("✅ Bağlantı başarılı!")
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        print("🛑 Kullanıcı tarafından durduruldu...")
    except Exception as e:
        print(f"❌ Bot başlangıç hatası: {e}")
    finally:
        await shutdown()

if __name__ == '__main__':
    # Asenkron main fonksiyonunu çalıştır
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🎪 Royal Baccarat Bot sonlandırıldı!")
