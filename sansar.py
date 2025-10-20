# -*- coding: utf-8 -*-
import re, json, os, asyncio, sys, pytz
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
from collections import defaultdict, deque

API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
BOT_TOKEN = ''  # 🔑 Buraya bot tokenınızı yazın
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"  # 📢 Hedef kanal
ADMIN_ID = 1136442929  # 👑 Admin ID
SISTEM_MODU = "normal_hibrit"
GMT3 = pytz.timezone('Europe/Istanbul')
client = TelegramClient('/root/0zctn/royal_bot.session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

game_results, martingale_trackers, color_trend, recent_games = {}, {}, [], []
MAX_MARTINGALE_STEPS, MAX_GAME_NUMBER, is_signal_active, daily_signal_count = 3, 1440, False, 0

# 5.5 Alt/Üst tahmin sistemi için yeni değişkenler
alt_ust_stats = {
    'alt': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0},
    'ust': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0}
}

alt_ust_trend = []
ALT_UST_MARTINGALE_STEPS = 3

# 10.5 ALT/ÜST istatistikleri
onbes_stats = {
    'alt': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0},
    'ust': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0}
}

onbes_trend = []
ONBES_MARTINGALE_STEPS = 3

# Güncellenmiş C2_3 istatistik yapısı
C2_3_TYPES = {
    '#C2_3': {'emoji': '🔴', 'name': 'KLASİK', 'confidence': 0.9, 'stats': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0}},
    '#C2_2': {'emoji': '🔵', 'name': 'ALTERNATİF', 'confidence': 0.7, 'stats': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0}},
    '#C3_2': {'emoji': '🟢', 'name': 'VARYANT', 'confidence': 0.6, 'stats': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0}},
    '#C3_3': {'emoji': '🟡', 'name': 'ÖZEL', 'confidence': 0.7, 'stats': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0}}
}

# İstatistik veri yapıları
performance_stats = {
    'total_signals': 0,
    'win_signals': 0,
    'loss_signals': 0,
    'total_profit': 0,
    'current_streak': 0,
    'max_streak': 0,
    'daily_stats': defaultdict(lambda: {'signals': 0, 'wins': 0, 'losses': 0, 'profit': 0}),
    'weekly_stats': defaultdict(lambda: {'signals': 0, 'wins': 0, 'losses': 0, 'profit': 0}),
    'signal_history': deque(maxlen=1000),
    'c2_3_performance': C2_3_TYPES.copy()
}

# PATTERN İSTATİSTİKLERİ
pattern_stats = {
    '🎯 GÜÇLÜ EL': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '🏆 DOĞAL KAZANÇ': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '📊 5+ KART': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '🚨 3x TEKRAR': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '📈 STANDART SİNYAL': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '✅ 5-Lİ ONAY': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '🚀 SÜPER HİBRİT': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '🎯 KLASİK #C2_3': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0}
}

def get_suit_display_name(suit_symbol):
    suit_names = {'♠': '♠️ MAÇA', '♥': '❤️ KALP', '♦': '♦️ KARO', '♣': '♣️ SİNEK'}
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
        print(f"❌ extract_largest_value_suit hatası: {e}")
        return None

# 5.5 Alt/Üst tahmin fonksiyonu
def predict_alt_ust(player_cards, banker_cards):
    try:
        # Kart değerlerini hesapla
        player_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
        banker_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)
        
        player_values = [get_baccarat_value(card[0]) for card in player_card_data]
        banker_values = [get_baccarat_value(card[0]) for card in banker_card_data]
        
        # Toplam değeri hesapla
        total_value = sum(player_values) + sum(banker_values)
        
        # 5.5 tahmini
        if total_value <= 5.5:
            return "alt", total_value
        else:
            return "ust", total_value
            
    except Exception as e:
        print(f"❌ Alt/Üst tahmin hatası: {e}")
        return None, 0

# 10.5 ALT/ÜST tahmin fonksiyonu
def calculate_onbes_total(player_cards, banker_cards):
    try:
        # Oyuncu el değerini hesapla (0-9)
        player_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
        player_values = [get_baccarat_value(card[0]) for card in player_card_data]
        player_total = sum(player_values) % 10
        
        # Banker el değerini hesapla (0-9)
        banker_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)
        banker_values = [get_baccarat_value(card[0]) for card in banker_card_data]
        banker_total = sum(banker_values) % 10
        
        # Toplam el değerleri (0-18 arası)
        total_hand_value = player_total + banker_total
        
        # 10.5 ALT/ÜST tahmini - 10 ve altı ALT, 11 ve üstü ÜST
        if total_hand_value <= 10:
            return "alt", total_hand_value
        else:
            return "ust", total_hand_value
            
    except Exception as e:
        print(f"❌ 10.5 ALT/ÜST toplam hatası: {e}")
        return None, 0

# 5.5 Alt/Üst pattern analizi
def analyze_alt_ust_pattern(player_cards, banker_cards, game_number):
    try:
        tahmin, deger = predict_alt_ust(player_cards, banker_cards)
        if not tahmin:
            return None, "Hesaplama hatası"
        
        alt_ust_trend.append(tahmin)
        if len(alt_ust_trend) > 10:
            alt_ust_trend.pop(0)
        
        # Pattern analizleri
        player_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
        banker_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)
        
        total_cards = len(player_card_data) + len(banker_card_data)
        total_value = sum([get_baccarat_value(card[0]) for card in player_card_data]) + \
                     sum([get_baccarat_value(card[0]) for card in banker_card_data])
        
        if total_cards >= 5:
            return tahmin, "📊 5+ KART - ALT/ÜST"
        elif total_value <= 3:
            return "alt", "🎯 DÜŞÜK DEĞER - ALT"
        elif total_value >= 8:
            return "ust", "🚀 YÜKSEK DEĞER - ÜST"
        elif len(alt_ust_trend) >= 3 and alt_ust_trend[-3:] == [tahmin] * 3:
            return tahmin, "🔄 3x TEKRAR - ALT/ÜST"
        else:
            return tahmin, "📈 STANDART - ALT/ÜST"
            
    except Exception as e:
        print(f"❌ Alt/Üst pattern analiz hatası: {e}")
        return None, f"Hata: {e}"

# 10.5 ALT/ÜST pattern analizi
def analyze_onbes_pattern(player_cards, banker_cards, game_number):
    try:
        tahmin, deger = calculate_onbes_total(player_cards, banker_cards)
        if not tahmin:
            return None, "Hesaplama hatası"
        
        onbes_trend.append(tahmin)
        if len(onbes_trend) > 10:
            onbes_trend.pop(0)
        
        # Pattern analizleri
        player_total = sum([get_baccarat_value(card[0]) for card in re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)]) % 10
        banker_total = sum([get_baccarat_value(card[0]) for card in re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)]) % 10
        
        total_hand_value = player_total + banker_total
        
        if total_hand_value <= 8:
            return "alt", "🎯 DÜŞÜK EL TOPLAM"
        elif total_hand_value >= 13:
            return "ust", "🚀 YÜKSEK EL TOPLAM"
        elif player_total >= 7 and banker_total >= 7:
            return "ust", "💎 ÇİFT YÜKSEK EL"
        elif len(onbes_trend) >= 3 and onbes_trend[-3:] == [tahmin] * 3:
            return tahmin, "🔄 3x TEKRAR - 10.5"
        else:
            return tahmin, "📈 STANDART - 10.5"
            
    except Exception as e:
        print(f"❌ 10.5 ALT/ÜST pattern analiz hatası: {e}")
        return None, f"Hata: {e}"

# 5.5 Alt/Üst hibrit sistem
async def alt_ust_hibrit_sistemi(game_info):
    print("🎯 5.5 ALT/ÜST analiz başlıyor...")
    
    tahmin, sebep = analyze_alt_ust_pattern(game_info['player_cards'], 
                                          game_info['banker_cards'], 
                                          game_info['game_number'])
    
    if not tahmin:
        print(f"🚫 Alt/Üst: Tahmin yapılamadı - {sebep}")
        return
    
    # Risk analizi
    risk_seviye, risk_uyarilar = super_risk_analizi()
    if risk_seviye == "🔴 YÜKSEK RİSK":
        print(f"🚫 Alt/Üst: Yüksek risk - {risk_uyarilar}")
        return
    
    # Trend kontrolü
    if len(alt_ust_trend) >= 5:
        son_5 = alt_ust_trend[-5:]
        if son_5.count(tahmin) >= 4:
            print("🎯 Alt/Üst: Trend destekliyor")
    
    next_game_num = get_next_game_number(game_info['game_number'])
    await send_alt_ust_signal(next_game_num, tahmin, sebep, game_info)

# 10.5 ALT/ÜST hibrit sistem
async def onbes_hibrit_sistemi(game_info):
    print("🎯 10.5 ALT/ÜST analiz başlıyor...")
    
    tahmin, sebep = analyze_onbes_pattern(game_info['player_cards'], 
                                          game_info['banker_cards'], 
                                          game_info['game_number'])
    
    if not tahmin:
        print(f"🚫 10.5 ALT/ÜST: Tahmin yapılamadı - {sebep}")
        return
    
    # Risk analizi
    risk_seviye, risk_uyarilar = super_risk_analizi()
    if risk_seviye == "🔴 YÜKSEK RİSK":
        print(f"🚫 10.5 ALT/ÜST: Yüksek risk - {risk_uyarilar}")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    await send_onbes_signal(next_game_num, tahmin, sebep, game_info)

# 5.5 Alt/Üst sinyal gönderme
async def send_alt_ust_signal(game_num, tahmin, reason, game_info=None):
    global is_signal_active, daily_signal_count
        
    try:
        tahmin_emoji = "⬇️ ALT" if tahmin == "alt" else "⬆️ ÜST"
        tahmin_text = "5.5 ALT" if tahmin == "alt" else "5.5 ÜST"
        
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        
        signal_text = f"🎯 **5.5 ALT/ÜST SİNYALİ** 🎯\n#N{game_num} - {tahmin_emoji}\n📊 Sebep: {reason}\n⚡ Strateji: Martingale {ALT_UST_MARTINGALE_STEPS} Seviye\n🕒 {gmt3_time} (GMT+3)\n🔴 SONUÇ: BEKLENİYOR..."
        
        sent_message = await client.send_message(KANAL_HEDEF, signal_text)
        print(f"🚀 5.5 Alt/Üst sinyal gönderildi: #N{game_num} - {tahmin_text}")
        
        # Takipçiye ekle - benzersiz key için game_num + "alt_ust" ekliyoruz
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

# 10.5 ALT/ÜST sinyal gönderme
async def send_onbes_signal(game_num, tahmin, reason, game_info=None):
    global is_signal_active, daily_signal_count
        
    try:
        tahmin_emoji = "⬇️ ALT" if tahmin == "alt" else "⬆️ ÜST"
        
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        
        signal_text = f"🎯 **10.5 ALT/ÜST SİNYALİ** 🎯\n#N{game_num} - {tahmin_emoji}\n📊 Sebep: {reason}\n⚡ Strateji: Martingale {ONBES_MARTINGALE_STEPS} Seviye\n🕒 {gmt3_time} (GMT+3)\n🔴 SONUÇ: BEKLENİYOR..."
        
        sent_message = await client.send_message(KANAL_HEDEF, signal_text)
        print(f"🚀 10.5 ALT/ÜST sinyal gönderildi: #N{game_num} - {tahmin_emoji}")
        
        # Takipçiye ekle
        tracker_key = f"{game_num}_onbes"
        martingale_trackers[tracker_key] = {
            'message_obj': sent_message, 
            'step': 0, 
            'signal_type': 'onbes',
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
        print(f"❌ 10.5 ALT/ÜST sinyal gönderme hatası: {e}")

# 5.5 Alt/Üst kontrol fonksiyonu
async def check_alt_ust_tracker(tracker_info):
    current_step = tracker_info['step']
    game_to_check = tracker_info['expected_game_number_for_check']
    tahmin = tracker_info['signal_tahmin']
    
    if game_to_check not in game_results:
        return False
    
    result_info = game_results[game_to_check]
    if not result_info['is_final']:
        return False
    
    # Gerçek değeri hesapla
    gercek_tahmin, gercek_deger = predict_alt_ust(result_info['player_cards'], 
                                                 result_info['banker_cards'])
    
    kazandi = (gercek_tahmin == tahmin)
    
    print(f"🔍 5.5 Alt/Üst kontrol: #{tracker_info['sent_game_number']} → #{game_to_check} | Tahmin: {tahmin} | Gerçek: {gercek_tahmin} | Değer: {gercek_deger} | Kazandı: {kazandi}")
    
    if kazandi:
        result_details = f"#{game_to_check} ✅ Kazanç - {current_step}. seviye | Değer: {gercek_deger}"
        await update_alt_ust_message(tracker_info, 'step_result', current_step, result_details)
        await asyncio.sleep(1)
        await update_alt_ust_message(tracker_info, 'win', current_step)
        
        # İstatistik güncelle
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
            print(f"📈 5.5 Alt/Üst #{tracker_info['sent_game_number']} → {next_step}. seviye → #{next_game_num}")
            return False
        else:
            await update_alt_ust_message(tracker_info, 'loss', current_step)
            
            # İstatistik güncelle
            update_alt_ust_stats(tahmin, 'loss', current_step)
            
            print(f"💔 5.5 Alt/Üst #{tracker_info['sent_game_number']} KAYBETTİ! Son seviye: {current_step}")
            return True

# 10.5 ALT/ÜST takipçi kontrolü
async def check_onbes_tracker(tracker_info):
    current_step = tracker_info['step']
    game_to_check = tracker_info['expected_game_number_for_check']
    tahmin = tracker_info['signal_tahmin']
    
    if game_to_check not in game_results:
        return False
    
    result_info = game_results[game_to_check]
    if not result_info['is_final']:
        return False
    
    # Gerçek değeri hesapla
    gercek_tahmin, gercek_deger = calculate_onbes_total(
        result_info['player_cards'], 
        result_info['banker_cards']
    )
    
    kazandi = (gercek_tahmin == tahmin)
    
    print(f"🔍 10.5 ALT/ÜST kontrol: #{tracker_info['sent_game_number']} → #{game_to_check} | Tahmin: {tahmin} | Gerçek: {gercek_tahmin} | Değer: {gercek_deger} | Kazandı: {kazandi}")
    
    if kazandi:
        result_details = f"#{game_to_check} ✅ Kazanç - {current_step}. seviye | Toplam: {gercek_deger}"
        await update_onbes_message(tracker_info, 'step_result', current_step, result_details)
        await asyncio.sleep(1)
        await update_onbes_message(tracker_info, 'win', current_step)
        
        # İstatistik güncelle
        update_onbes_stats(tahmin, 'win', current_step)
        
        print(f"🎉 10.5 ALT/ÜST #{tracker_info['sent_game_number']} KAZANDI! Seviye: {current_step}")
        return True
    else:
        result_details = f"#{game_to_check} ❌ Kayıp - {current_step}. seviye | Toplam: {gercek_deger}"
        await update_onbes_message(tracker_info, 'step_result', current_step, result_details)
        await asyncio.sleep(1)
        
        if current_step < ONBES_MARTINGALE_STEPS:
            next_step = current_step + 1
            next_game_num = get_next_game_number(game_to_check)
            
            tracker_info['step'] = next_step
            tracker_info['expected_game_number_for_check'] = next_game_num
            
            await update_onbes_message(tracker_info, 'progress', next_step)
            print(f"📈 10.5 ALT/ÜST #{tracker_info['sent_game_number']} → {next_step}. seviye → #{next_game_num}")
            return False
        else:
            await update_onbes_message(tracker_info, 'loss', current_step)
            
            # İstatistik güncelle
            update_onbes_stats(tahmin, 'loss', current_step)
            
            print(f"💔 10.5 ALT/ÜST #{tracker_info['sent_game_number']} KAYBETTİ! Son seviye: {current_step}")
            return True

# 5.5 Alt/Üst mesaj güncelleme
async def update_alt_ust_message(tracker_info, result_type, current_step=None, result_details=None):
    try:
        game_num = tracker_info['sent_game_number']
        tahmin = tracker_info['signal_tahmin']
        reason = tracker_info['reason']
        message_obj = tracker_info['message_obj']
        
        tahmin_emoji = "⬇️ ALT" if tahmin == "alt" else "⬆️ ÜST"
        tahmin_text = "5.5 ALT" if tahmin == "alt" else "5.5 ÜST"
        
        duration = datetime.now(GMT3) - tracker_info['start_time']
        duration_str = f"{duration.seconds // 60}d {duration.seconds % 60}s"
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        
        if result_details:
            tracker_info['results'].append(result_details)
        
        if result_type == 'win':
            new_text = f"✅ **5.5 ALT/ÜST KAZANÇ** ✅\n#N{game_num} - {tahmin_emoji}\n📊 Sebep: {reason}\n🎯 Seviye: {current_step}. Seviye\n⏱️ Süre: {duration_str}\n🕒 Bitiş: {gmt3_time}\n🏆 **SONUÇ: KAZANDINIZ!**"
        elif result_type == 'loss':
            new_text = f"❌ **5.5 ALT/ÜST KAYIP** ❌\n#N{game_num} - {tahmin_emoji}\n📊 Sebep: {reason}\n🎯 Seviye: {current_step}. Seviye\n⏱️ Süre: {duration_str}\n🕒 Bitiş: {gmt3_time}\n💔 **SONUÇ: KAYBETTİNİZ**"
        elif result_type == 'progress':
            step_details = f"{current_step}. seviye → #{tracker_info['expected_game_number_for_check']}"
            results_history = "\n".join([f"• {r}" for r in tracker_info['results']]) if tracker_info['results'] else "• İlk deneme"
            new_text = f"🔄 **5.5 ALT/ÜST MARTINGALE** 🔄\n#N{game_num} - {tahmin_emoji}\n📊 Sebep: {reason}\n🎯 Adım: {step_details}\n⏱️ Süre: {duration_str}\n🕒 Son Güncelleme: {gmt3_time}\n📈 Geçmiş:\n{results_history}\n🎲 **SONRAKİ: #{tracker_info['expected_game_number_for_check']}**"
        elif result_type == 'step_result':
            new_text = f"📊 **5.5 ALT/ÜST ADIM SONUCU** 📊\n#N{game_num} - {tahmin_emoji}\n🎯 Adım: {current_step}. seviye\n📋 Sonuç: {result_details}\n⏱️ Süre: {duration_str}\n🕒 Zaman: {gmt3_time}\n🔄 **DEVAM EDİYOR...**"
        
        await message_obj.edit(new_text)
        print(f"✏️ 5.5 Alt/Üst sinyal güncellendi: #{game_num} - {result_type}")
        
    except MessageNotModifiedError: 
        pass
    except Exception as e: 
        print(f"❌ 5.5 Alt/Üst mesaj düzenleme hatası: {e}")

# 10.5 ALT/ÜST mesaj güncelleme
async def update_onbes_message(tracker_info, result_type, current_step=None, result_details=None):
    try:
        game_num = tracker_info['sent_game_number']
        tahmin = tracker_info['signal_tahmin']
        reason = tracker_info['reason']
        message_obj = tracker_info['message_obj']
        
        tahmin_emoji = "⬇️ ALT" if tahmin == "alt" else "⬆️ ÜST"
        
        duration = datetime.now(GMT3) - tracker_info['start_time']
        duration_str = f"{duration.seconds // 60}d {duration.seconds % 60}s"
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        
        if result_details:
            tracker_info['results'].append(result_details)
        
        if result_type == 'win':
            new_text = f"✅ **10.5 ALT/ÜST KAZANÇ** ✅\n#N{game_num} - {tahmin_emoji}\n📊 Sebep: {reason}\n🎯 Seviye: {current_step}. Seviye\n⏱️ Süre: {duration_str}\n🕒 Bitiş: {gmt3_time}\n🏆 **SONUÇ: KAZANDINIZ!**"
        elif result_type == 'loss':
            new_text = f"❌ **10.5 ALT/ÜST KAYIP** ❌\n#N{game_num} - {tahmin_emoji}\n📊 Sebep: {reason}\n🎯 Seviye: {current_step}. Seviye\n⏱️ Süre: {duration_str}\n🕒 Bitiş: {gmt3_time}\n💔 **SONUÇ: KAYBETTİNİZ**"
        elif result_type == 'progress':
            step_details = f"{current_step}. seviye → #{tracker_info['expected_game_number_for_check']}"
            results_history = "\n".join([f"• {r}" for r in tracker_info['results']]) if tracker_info['results'] else "• İlk deneme"
            new_text = f"🔄 **10.5 ALT/ÜST MARTINGALE** 🔄\n#N{game_num} - {tahmin_emoji}\n📊 Sebep: {reason}\n🎯 Adım: {step_details}\n⏱️ Süre: {duration_str}\n🕒 Son Güncelleme: {gmt3_time}\n📈 Geçmiş:\n{results_history}\n🎲 **SONRAKİ: #{tracker_info['expected_game_number_for_check']}**"
        elif result_type == 'step_result':
            new_text = f"📊 **10.5 ALT/ÜST ADIM SONUCU** 📊\n#N{game_num} - {tahmin_emoji}\n🎯 Adım: {current_step}. seviye\n📋 Sonuç: {result_details}\n⏱️ Süre: {duration_str}\n🕒 Zaman: {gmt3_time}\n🔄 **DEVAM EDİYOR...**"
        
        await message_obj.edit(new_text)
        print(f"✏️ 10.5 ALT/ÜST sinyal güncellendi: #{game_num} - {result_type}")
        
    except MessageNotModifiedError: 
        pass
    except Exception as e: 
        print(f"❌ 10.5 ALT/ÜST mesaj düzenleme hatası: {e}")

# 5.5 Alt/Üst istatistik güncelleme
def update_alt_ust_stats(tahmin, result_type, steps=0):
    stats = alt_ust_stats[tahmin]
    stats['total'] += 1
    
    if result_type == 'win':
        stats['wins'] += 1
        stats['profit'] += 1
    else:
        stats['losses'] += 1
        stats['profit'] -= (2**steps - 1)

# 10.5 ALT/ÜST istatistik güncelleme
def update_onbes_stats(tahmin, result_type, steps=0):
    stats = onbes_stats[tahmin]
    stats['total'] += 1
    
    if result_type == 'win':
        stats['wins'] += 1
        stats['profit'] += 1
    else:
        stats['losses'] += 1
        stats['profit'] -= (2**steps - 1)

# 5.5 Alt/Üst performans raporu
def get_alt_ust_performance():
    performance_text = "📊 **5.5 ALT/ÜST PERFORMANSI** 📊\n\n"
    
    for tahmin, stats in alt_ust_stats.items():
        tahmin_adi = "ALT" if tahmin == "alt" else "ÜST"
        emoji = "⬇️" if tahmin == "alt" else "⬆️"
        
        if stats['total'] > 0:
            win_rate = (stats['wins'] / stats['total']) * 100
            performance_text += f"{emoji} **{tahmin_adi}**\n"
            performance_text += f"   📊 Toplam: {stats['total']} | ⭕: {stats['wins']} | ❌: {stats['losses']}\n"
            performance_text += f"   🎯 Başarı: %{win_rate:.1f} | 💰 Kâr: {stats['profit']} birim\n\n"
        else:
            performance_text += f"{emoji} **{tahmin_adi}**\n"
            performance_text += f"   📊 Henüz veri yok\n\n"
    
    return performance_text

# 10.5 ALT/ÜST performans raporu
def get_onbes_performance():
    performance_text = "📊 **10.5 ALT/ÜST PERFORMANSI** 📊\n\n"
    
    for tahmin, stats in onbes_stats.items():
        tahmin_adi = "ALT" if tahmin == "alt" else "ÜST"
        emoji = "⬇️" if tahmin == "alt" else "⬆️"
        
        if stats['total'] > 0:
            win_rate = (stats['wins'] / stats['total']) * 100
            performance_text += f"{emoji} **{tahmin_adi}**\n"
            performance_text += f"   📊 Toplam: {stats['total']} | ⭕: {stats['wins']} | ❌: {stats['losses']}\n"
            performance_text += f"   🎯 Başarı: %{win_rate:.1f} | 💰 Kâr: {stats['profit']} birim\n\n"
        else:
            performance_text += f"{emoji} **{tahmin_adi}**\n"
            performance_text += f"   📊 Henüz veri yok\n\n"
    
    return performance_text

# ... (diğer mevcut fonksiyonlar aynen kalacak: analyze_simple_pattern, besli_onay_sistemi, super_filtre_kontrol, super_risk_analizi, get_next_game_number, update_c2_3_stats, update_pattern_stats, update_performance_stats, get_c2_3_performance, get_pattern_performance, get_best_performing_type, get_worst_performing_type, calculate_win_rate, get_daily_stats, get_weekly_stats, generate_performance_report, generate_trend_analysis, quantum_pattern_analizi, quantum_trend_analizi, quantum_kart_analizi, quantum_hibrit_sistemi, elite_trend_analizi, kart_deger_analizi, pattern_zincir_analizi, performans_bazli_analiz, quantum_pro_sistemi, master_elite_sistemi, send_new_signal, update_signal_message, check_martingale_trackers, extract_game_info_from_message, normal_hibrit_sistemi, super_hibrit_sistemi)

# Takipçi kontrol fonksiyonunu güncelle
async def check_martingale_trackers():
    global martingale_trackers, is_signal_active
    trackers_to_remove = []
    
    for signal_key, tracker_info in list(martingale_trackers.items()):
        # Renk tabanlı sinyaller
        if 'signal_suit' in tracker_info:
            current_step, signal_suit, game_to_check = tracker_info['step'], tracker_info['signal_suit'], tracker_info['expected_game_number_for_check']
            
            # Oyun sonucu henüz gelmemişse devam et
            if game_to_check not in game_results:
                continue
                
            result_info = game_results.get(game_to_check)
            if not result_info['is_final']:
                continue
                
            player_cards_str = result_info['player_cards']
            
            # Sinyal kontrolü
            signal_won_this_step = False
            try:
                # Oyundaki tüm renkleri kontrol et
                suits_in_game = re.findall(r'[♣♦♥♠]', player_cards_str)
                signal_won_this_step = signal_suit in suits_in_game
                print(f"🔍 Renk kontrol: #{tracker_info['sent_game_number']} → #{game_to_check} | Aranan: {signal_suit} | Bulunan: {suits_in_game} | Sonuç: {signal_won_this_step}")
            except Exception as e:
                print(f"❌ Renk kontrol hatası: {e}")
                continue
            
            if signal_won_this_step:
                result_details = f"#{game_to_check} ✅ Kazanç - {current_step}. seviye"
                await update_signal_message(tracker_info, 'step_result', current_step, result_details)
                await asyncio.sleep(1)
                await update_signal_message(tracker_info, 'win', current_step)
                trackers_to_remove.append(signal_key)
                is_signal_active = False
                recent_games.append({'kazanç': True, 'adim': current_step})
                if len(recent_games) > 20: recent_games.pop(0)
                print(f"🎉 Renk Sinyali #{tracker_info['sent_game_number']} KAZANDI! Seviye: {current_step}")
            else:
                result_details = f"#{game_to_check} ❌ Kayıp - {current_step}. seviye"
                await update_signal_message(tracker_info, 'step_result', current_step, result_details)
                await asyncio.sleep(1)
                
                if current_step < MAX_MARTINGALE_STEPS:
                    next_step, next_game_num = current_step + 1, get_next_game_number(game_to_check)
                    tracker_info['step'] = next_step
                    tracker_info['expected_game_number_for_check'] = next_game_num
                    await update_signal_message(tracker_info, 'progress', next_step)
                    print(f"📈 Renk Sinyali #{tracker_info['sent_game_number']} → {next_step}. seviye → #{next_game_num}")
                else:
                    await update_signal_message(tracker_info, 'loss', current_step)
                    trackers_to_remove.append(signal_key)
                    is_signal_active = False
                    recent_games.append({'kazanç': False, 'adim': current_step})
                    if len(recent_games) > 20: recent_games.pop(0)
                    print(f"💔 Renk Sinyali #{tracker_info['sent_game_number']} KAYBETTİ! Son seviye: {current_step}")
        
        # 5.5 Alt/Üst sinyaller
        elif 'signal_type' in tracker_info and tracker_info['signal_type'] == 'alt_ust':
            completed = await check_alt_ust_tracker(tracker_info)
            if completed:
                trackers_to_remove.append(signal_key)
                is_signal_active = False
        
        # YENİ: 10.5 ALT/ÜST sinyaller
        elif 'signal_type' in tracker_info and tracker_info['signal_type'] == 'onbes':
            completed = await check_onbes_tracker(tracker_info)
            if completed:
                trackers_to_remove.append(signal_key)
                is_signal_active = False
    
    for key_to_remove in trackers_to_remove:
        if key_to_remove in martingale_trackers: 
            del martingale_trackers[key_to_remove]
            print(f"🧹 Takipçi temizlendi: {key_to_remove}")

# Ana mesaj işleyiciyi güncelle
@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_source_channel_message(event):
    try:
        message = event.message
        text = message.text or ""
        cleaned_text = re.sub(r'\*\*', '', text).strip()
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        print(f"[{gmt3_time}] 📥 Mesaj: #{len(cleaned_text)} karakter")
        game_info = extract_game_info_from_message(cleaned_text)
        if game_info['game_number'] is None: return
        game_results[game_info['game_number']] = game_info
        await check_martingale_trackers()
        if not is_signal_active:
            if game_info['is_final'] and game_info.get('is_c2_3'):
                trigger_game_num, c2_3_type, c2_3_desc = game_info['game_number'], game_info['c2_3_type'], game_info['c2_3_description']
                print(f"🎯 {c2_3_desc} tespit edildi: #{trigger_game_num} - {c2_3_type}")
                
                if SISTEM_MODU == "normal_hibrit": 
                    await normal_hibrit_sistemi(game_info)
                elif SISTEM_MODU == "super_hibrit": 
                    await super_hibrit_sistemi(game_info)
                elif SISTEM_MODU == "quantum_hibrit":
                    await quantum_hibrit_sistemi(game_info)
                elif SISTEM_MODU == "quantum_pro":
                    await quantum_pro_sistemi(game_info)
                elif SISTEM_MODU == "master_elite":
                    await master_elite_sistemi(game_info)
                
                # 3 BAĞIMSIZ SİSTEM AYNI ANDA ÇALIŞACAK
                await alt_ust_hibrit_sistemi(game_info)      # 5.5 Alt/Üst
                await onbes_hibrit_sistemi(game_info)        # 10.5 ALT/ÜST
                    
    except Exception as e: print(f"❌ Mesaj işleme hatası: {e}")

# YENİ KOMUTLAR EKLE
@client.on(events.NewMessage(pattern='(?i)/10_5'))
async def handle_10_5(event):
    analysis = get_onbes_performance()
    await event.reply(analysis)

@client.on(events.NewMessage(pattern='(?i)/10_5_trend'))
async def handle_10_5_trend(event):
    if not onbes_trend:
        await event.reply("📊 10.5 ALT/ÜST trend verisi bulunmuyor")
        return
    
    alt_count = onbes_trend.count('alt')
    ust_count = onbes_trend.count('ust')
    total = len(onbes_trend)
    
    analysis = f"📊 **10.5 ALT/ÜST TREND ANALİZİ** 📊\n\n"
    analysis += f"Son {total} oyun dağılımı:\n"
    analysis += f"⬇️ ALT: {alt_count} (%{alt_count/total*100:.1f})\n"
    analysis += f"⬆️ ÜST: {ust_count} (%{ust_count/total*100:.1f})\n\n"
    
    if alt_count > ust_count:
        analysis += f"🔥 **DOMINANT TAHMİN:** ⬇️ ALT ({alt_count} kez)"
    elif ust_count > alt_count:
        analysis += f"🔥 **DOMINANT TAHMİN:** ⬆️ ÜST ({ust_count} kez)"
    else:
        analysis += "⚖️ **DENGE:** Eşit dağılım"
    
    await event.reply(analysis)

@client.on(events.NewMessage(pattern='(?i)/mod_10_5'))
async def handle_mod_10_5(event):
    global SISTEM_MODU
    SISTEM_MODU = "10_5"
    await event.reply("🎯 10.5 ALT/ÜST modu aktif! Oyuncu ve Banker el değerleri toplamı bazlı tahmin. 3 martingale seviye.")

# /temizle komutunu güncelle
@client.on(events.NewMessage(pattern='(?i)/temizle'))
async def handle_temizle(event):
    global color_trend, recent_games, daily_signal_count, alt_ust_trend, onbes_trend
    color_trend, recent_games, daily_signal_count, alt_ust_trend, onbes_trend = [], [], 0, [], []
    await event.reply("✅ Trend verileri temizlendi! Sinyal sayacı sıfırlandı.")

# ... (diğer mevcut komutlar aynen kalacak)

if __name__ == '__main__':
    print("🤖 ROYAL BACCARAT BOT BAŞLIYOR...")
    print(f"🔧 API_ID: {API_ID}")
    print(f"🎯 Kaynak Kanal: {KANAL_KAYNAK_ID}")
    print(f"📤 Hedef Kanal: {KANAL_HEDEF}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"🎛️ Varsayılan Mod: {SISTEM_MODU}")
    print(f"📊 C2-3 Analiz Sistemi: AKTİF")
    print(f"📈 Pattern Performans Takibi: AKTİF")
    print(f"⚛️ Quantum Hibrit Sistem: AKTİF")
    print(f"🚀 Quantum PRO Sistem: AKTİF")
    print(f"🏆 Master Elite Sistem: AKTİF")
    print(f"🎯 5.5 Alt/Üst Sistemi: AKTİF")
    print(f"🆕 10.5 ALT/ÜST Sistemi: AKTİF")
    print(f"🕒 Saat Dilimi: GMT+3")
    print("⏳ Bağlanıyor...")
    try:
        with client: 
            client.run_until_disconnected()
    except KeyboardInterrupt: 
        print("\n👋 Bot durduruluyor...")
    except Exception as e: 
        print(f"❌ Bot başlangıç hatası: {e}")
