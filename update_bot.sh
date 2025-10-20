#!/bin/bash

# screen.py dosyasını güncelle
cat > /root/0zctn/screen.py << 'EOF'
# -*- coding: utf-8 -*-
import re, json, os, asyncio, sys, pytz
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
from collections import defaultdict, deque

API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
BOT_TOKEN = ''
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"
ADMIN_ID = 1136442929
SISTEM_MODU = "normal_hibrit_ultra"
GMT3 = pytz.timezone('Europe/Istanbul')
client = TelegramClient('screen_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

game_results, martingale_trackers, color_trend, recent_games = {}, {}, [], []
MAX_MARTINGALE_STEPS, MAX_GAME_NUMBER, is_signal_active, daily_signal_count = 3, 1440, False, 0

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
    '📊 4+ KART': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '🚨 3x TEKRAR': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '📈 STANDART SİNYAL': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '📈 İYİ EL': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '✅ 5-Lİ ONAY': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '🚀 SÜPER HİBRİT': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '🎯 KLASİK #C2_3': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '🛡️ ULTRA ONAY': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '💎 QUANTUM ELITE': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '👑 MASTER PERFECT': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0}
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

def analyze_simple_pattern(player_cards, banker_cards, game_number):
    try:
        signal_color = extract_largest_value_suit(player_cards)
        if not signal_color: return None, "Renk tespit edilemedi"
        color_trend.append(signal_color)
        if len(color_trend) > 10: color_trend.pop(0)
        player_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
        player_values = [get_baccarat_value(card[0]) for card in player_card_data]
        banker_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)
        banker_values = [get_baccarat_value(card[0]) for card in banker_card_data]
        total_cards = len(player_values) + len(banker_values)
        
        # Daha geniş pattern kabulü
        if sum(player_values) >= 7 and len(player_values) >= 2:  # 8'den 7'ye, 3'ten 2'ye
            return signal_color, "🎯 GÜÇLÜ EL"
        elif sum(player_values) in [8, 9]: 
            return signal_color, "🏆 DOĞAL KAZANÇ"
        elif total_cards >= 4:  # 5'ten 4'e
            return signal_color, "📊 4+ KART"
        elif len(color_trend) >= 3 and color_trend[-3:] == [signal_color] * 3: 
            return signal_color, "🚨 3x TEKRAR"
        elif sum(player_values) >= 6:  # Yeni pattern ekle
            return signal_color, "📈 İYİ EL"
        else: 
            return signal_color, "📈 STANDART SİNYAL"
    except Exception as e:
        print(f"❌ Pattern analysis error: {e}")
        return None, f"Hata: {e}"

def super_risk_analizi():
    """OPTİMUM RİSK ANALİZİ - Daha esnek"""
    risk_puan = 0
    uyarılar = []
    
    # 1. Trend riski (daha esnek)
    if len(color_trend) >= 8:  # 10'dan 8'e düşür
        son_trend = color_trend[-8:]
        renk_frekans = {renk: son_trend.count(renk) for renk in set(son_trend)}
        max_frekans = max(renk_frekans.values())
        
        if max_frekans >= 7:  # 8'den 7'ye
            risk_puan += 15   # 30'dan 15'e
            uyarılar.append("⚠️ YÜKSEK TREND DOMINANCE")
        elif max_frekans >= 5:  # 6'dan 5'e
            risk_puan += 8     # 15'ten 8'e
            uyarılar.append("📊 ORTA TREND DOMINANCE")
    
    # 2. Kayıp zinciri (daha esnek)
    if len(recent_games) >= 5:  # 6'dan 5'e
        son_kayiplar = sum(1 for oyun in recent_games[-5:] if not oyun.get('kazanç', True))
        if son_kayiplar >= 3:   # 3/5 kayıp
            risk_puan += 15     # 25'ten 15'e
            uyarılar.append("🔴 3/5 KAYIP ZİNCİRİ")
        elif son_kayiplar >= 2: # 2/5 kayıp
            risk_puan += 5      # 10'dan 5'e
            uyarılar.append("🟡 2/5 KAYIP ZİNCİRİ")
    
    # 3. Günlük performans (daha esnek)
    daily = get_daily_stats()
    if daily['profit'] <= -12:  # -8'den -12'ye
        risk_puan += 10         # 20'den 10'a
        uyarılar.append("💸 YÜKSEK ZARAR")
    elif daily['profit'] <= -6: # -3'ten -6'ya
        risk_puan += 5          # 10'dan 5'e
        uyarılar.append("📉 ORTA ZARAR")
    
    # Risk seviyesi (eşikleri düşür)
    if risk_puan >= 20: return "🔴 YÜKSEK RİSK", uyarılar  # 30'dan 20'ye
    elif risk_puan >= 10: return "🟡 ORTA RİSK", uyarılar   # 15'ten 10'a
    else: return "🟢 DÜŞÜK RİSK", uyarılar

def get_next_game_number(current_game_num):
    next_num = current_game_num + 1
    return 1 if next_num > MAX_GAME_NUMBER else next_num

def update_c2_3_stats(c2_3_type, result_type, steps=0):
    if c2_3_type in performance_stats['c2_3_performance']:
        stats = performance_stats['c2_3_performance'][c2_3_type]['stats']
        stats['total'] += 1
        if result_type == 'win':
            stats['wins'] += 1
            stats['profit'] += 1
        else:
            stats['losses'] += 1
            stats['profit'] -= (2**steps - 1)

def update_pattern_stats(pattern_type, result_type, steps=0):
    if pattern_type in pattern_stats:
        stats = pattern_stats[pattern_type]
        stats['total'] += 1
        if result_type == 'win':
            stats['wins'] += 1
            stats['profit'] += 1
            if stats['wins'] > 0:
                stats['avg_steps'] = ((stats['avg_steps'] * (stats['wins'] - 1)) + steps) / stats['wins']
        else:
            stats['losses'] += 1
            stats['profit'] -= (2**steps - 1)

def update_performance_stats(result_type, steps=0, c2_3_type=None, pattern_type=None):
    today = datetime.now(GMT3).strftime('%Y-%m-%d')
    week = datetime.now(GMT3).strftime('%Y-%W')
    
    performance_stats['total_signals'] += 1
    performance_stats['signal_history'].append({
        'timestamp': datetime.now(GMT3),
        'result': result_type,
        'steps': steps,
        'c2_3_type': c2_3_type,
        'pattern_type': pattern_type
    })
    
    if result_type == 'win':
        performance_stats['win_signals'] += 1
        performance_stats['current_streak'] += 1
        performance_stats['max_streak'] = max(performance_stats['max_streak'], performance_stats['current_streak'])
        performance_stats['total_profit'] += 1
        performance_stats['daily_stats'][today]['wins'] += 1
        performance_stats['daily_stats'][today]['profit'] += 1
        performance_stats['weekly_stats'][week]['wins'] += 1
        performance_stats['weekly_stats'][week]['profit'] += 1
    else:
        performance_stats['loss_signals'] += 1
        performance_stats['current_streak'] = 0
        performance_stats['total_profit'] -= (2**steps - 1)
        performance_stats['daily_stats'][today]['losses'] += 1
        performance_stats['daily_stats'][today]['profit'] -= (2**steps - 1)
        performance_stats['weekly_stats'][week]['losses'] += 1
        performance_stats['weekly_stats'][week]['profit'] -= (2**steps - 1)
    
    performance_stats['daily_stats'][today]['signals'] += 1
    performance_stats['weekly_stats'][week]['signals'] += 1
    
    if c2_3_type:
        update_c2_3_stats(c2_3_type, result_type, steps)
    if pattern_type:
        update_pattern_stats(pattern_type, result_type, steps)

def get_c2_3_performance():
    performance_text = "🎯 **C2-3 TİP PERFORMANSLARI** 🎯\n\n"
    sorted_types = sorted(
        performance_stats['c2_3_performance'].items(),
        key=lambda x: (x[1]['stats']['wins'] / x[1]['stats']['total']) if x[1]['stats']['total'] > 0 else 0,
        reverse=True
    )
    
    for c2_3_type, data in sorted_types:
        stats = data['stats']
        emoji = data['emoji']
        name = data['name']
        
        if stats['total'] > 0:
            win_rate = (stats['wins'] / stats['total']) * 100
            performance_text += f"{emoji} **{name}**\n"
            performance_text += f"   📊 Toplam: {stats['total']} | ⭕: {stats['wins']} | ❌: {stats['losses']}\n"
            performance_text += f"   🎯 Başarı: %{win_rate:.1f} | 💰 Kâr: {stats['profit']} birim\n\n"
        else:
            performance_text += f"{emoji} **{name}**\n"
            performance_text += f"   📊 Henüz veri yok\n\n"
    
    return performance_text

def get_pattern_performance():
    performance_text = "🎯 **PATTERN PERFORMANS TABLOSU** 🎯\n\n"
    sorted_patterns = sorted(
        pattern_stats.items(),
        key=lambda x: (x[1]['wins'] / x[1]['total']) if x[1]['total'] > 0 else 0,
        reverse=True
    )
    
    for pattern_type, stats in sorted_patterns:
        if stats['total'] > 0:
            win_rate = (stats['wins'] / stats['total']) * 100
            performance_text += f"{pattern_type}\n"
            performance_text += f"   📊 Toplam: {stats['total']} | ⭕: {stats['wins']} | ❌: {stats['losses']}\n"
            performance_text += f"   🎯 Başarı: %{win_rate:.1f} | 💰 Kâr: {stats['profit']} birim\n"
            performance_text += f"   ⚡ Ort. Adım: {stats['avg_steps']:.1f}\n\n"
        else:
            performance_text += f"{pattern_type}\n"
            performance_text += f"   📊 Henüz veri yok\n\n"
    
    return performance_text

def get_best_performing_type():
    best_type = None
    best_win_rate = 0
    for c2_3_type, data in performance_stats['c2_3_performance'].items():
        stats = data['stats']
        if stats['total'] >= 5:
            win_rate = (stats['wins'] / stats['total']) * 100
            if win_rate > best_win_rate:
                best_win_rate = win_rate
                best_type = c2_3_type
    return best_type, best_win_rate

def get_worst_performing_type():
    worst_type = None
    worst_win_rate = 100
    for c2_3_type, data in performance_stats['c2_3_performance'].items():
        stats = data['stats']
        if stats['total'] >= 5:
            win_rate = (stats['wins'] / stats['total']) * 100
            if win_rate < worst_win_rate:
                worst_win_rate = win_rate
                worst_type = c2_3_type
    return worst_type, worst_win_rate

def calculate_win_rate():
    if performance_stats['total_signals'] == 0:
        return 0
    return (performance_stats['win_signals'] / performance_stats['total_signals']) * 100

def get_daily_stats():
    today = datetime.now(GMT3).strftime('%Y-%m-%d')
    return performance_stats['daily_stats'].get(today, {'signals': 0, 'wins': 0, 'losses': 0, 'profit': 0})

def get_weekly_stats():
    week = datetime.now(GMT3).strftime('%Y-%W')
    return performance_stats['weekly_stats'].get(week, {'signals': 0, 'wins': 0, 'losses': 0, 'profit': 0})

def generate_performance_report():
    win_rate = calculate_win_rate()
    daily = get_daily_stats()
    weekly = get_weekly_stats()
    best_type, best_rate = get_best_performing_type()
    worst_type, worst_rate = get_worst_performing_type()
    pattern_analysis = get_pattern_performance()
    
    best_type_name = performance_stats['c2_3_performance'][best_type]['name'] if best_type else "Yok"
    worst_type_name = performance_stats['c2_3_performance'][worst_type]['name'] if worst_type else "Yok"
    
    report = f"""🎯 **DETAYLI PERFORMANS RAPORU** 🎯

📊 **GENEL İSTATİSTİKLER:**
• Toplam Sinyal: {performance_stats['total_signals']}
• Kazanç: {performance_stats['win_signals']} | Kayıp: {performance_stats['loss_signals']}
• Kazanç Oranı: %{win_rate:.1f}
• Toplam Kâr: {performance_stats['total_profit']} birim
• Mevcut Seri: {performance_stats['current_streak']} kazanç
• En Uzun Seri: {performance_stats['max_streak']} kazanç

🏆 **PERFORMANS ANALİZİ:**
• En İyi Tip: {best_type_name} (%{best_rate:.1f})
• En Kötü Tip: {worst_type_name} (%{worst_rate:.1f})

{pattern_analysis}
"""
    return report

def generate_trend_analysis():
    if not color_trend:
        return "📊 Trend verisi bulunmuyor"
    
    trend_counts = {
        '♠': color_trend.count('♠'),
        '♥': color_trend.count('♥'), 
        '♦': color_trend.count('♦'),
        '♣': color_trend.count('♣')
    }
    
    most_common = max(trend_counts.items(), key=lambda x: x[1])
    
    analysis = f"""📈 **TREND ANALİZİ** 📈

Son {len(color_trend)} oyun dağılımı:
♠️ Maça: {trend_counts['♠']} (%{trend_counts['♠']/len(color_trend)*100:.1f})
❤️ Kalp: {trend_counts['♥']} (%{trend_counts['♥']/len(color_trend)*100:.1f})
♦️ Karo: {trend_counts['♦']} (%{trend_counts['♦']/len(color_trend)*100:.1f})
♣️ Sinek: {trend_counts['♣']} (%{trend_counts['♣']/len(color_trend)*100:.1f})

🔥 **DOMİNANT RENK:** {get_suit_display_name(most_common[0])} ({most_common[1]} kez)
"""
    return analysis

# QUANTUM HİBRİT SİSTEMİ - OPTİMUM GÜVENLİK
def quantum_pattern_analizi(game_info):
    player_cards = game_info['player_cards']
    banker_cards = game_info['banker_cards']
    
    player_kartlar = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
    banker_kartlar = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)
    
    player_degerler = [get_baccarat_value(kart[0]) for kart in player_kartlar]
    banker_degerler = [get_baccarat_value(kart[0]) for kart in banker_kartlar]
    
    player_toplam = sum(player_degerler) % 10
    banker_toplam = sum(banker_degerler) % 10
    
    renk = extract_largest_value_suit(player_cards)
    if not renk:
        return None, None
    
    if player_toplam in [8, 9]:
        return renk, "🏆 DOĞAL KAZANÇ"
    
    if sum(player_degerler) >= 6 and len(player_kartlar) >= 2:  # 8'den 6'ya, 3'ten 2'ye
        return renk, "🎯 GÜÇLÜ EL"
    
    if (len(player_kartlar) + len(banker_kartlar)) >= 4:  # 5'ten 4'e
        return renk, "📊 4+ KART"
    
    if player_toplam >= 6 and banker_toplam <= 5:  # 7'den 6'ya, 4'ten 5'e
        return renk, "💎 YÜKSEK DEĞER"
    
    if len(player_kartlar) >= 3:  # Yeni pattern
        return renk, "🃏 ÇOKLU KART"
    
    return None, None

def quantum_trend_analizi():
    if len(color_trend) < 6:  # 8'den 6'ya
        return None, None
    
    son_trend = color_trend[-6:]
    renk_frekans = {renk: son_trend.count(renk) for renk in set(son_trend)}
    
    for renk, sayi in renk_frekans.items():
        if sayi >= 4:  # 6'dan 4'e
            return renk, f"📈 TREND DOMINANCE ({sayi}/6)"
        elif sayi >= 3:  # Yeni kriter
            return renk, f"📊 GÜÇLÜ TREND ({sayi}/6)"
    
    if len(set(son_trend[-3:])) == 1:  # 4'ten 3'e
        return son_trend[-1], "🔥 TREND MASTER 3x"
    
    return None, None

def quantum_kart_analizi(game_info):
    player_cards = game_info['player_cards']
    banker_cards = game_info['banker_cards']
    
    player_kartlar = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
    banker_kartlar = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)
    
    renk = extract_largest_value_suit(player_cards)
    if not renk:
        return None, None
    
    yuksek_kartlar = [v for v in [get_baccarat_value(k[0]) for k in player_kartlar] if v >= 6]  # 7'den 6'ya
    if len(yuksek_kartlar) >= 1:  # 2'den 1'e
        return renk, "🃏 YÜKSEK KART"
    
    degerler = [get_baccarat_value(k[0]) for k in player_kartlar]
    if len(set(degerler)) >= 2:  # 3'ten 2'ye
        return renk, "🎲 KARIŞIK DEĞER"
    
    if len(player_kartlar) >= 2:  # Yeni kriter
        return renk, "📊 İKİLİ KART"
    
    return None, None

# ULTRA GÜVENLİ SİSTEM FONKSİYONLARI
async def normal_hibrit_sistemi(game_info):
    """OPTİMUM GÜVENLİK - Geniş pattern kabulü"""
    print("🛡️ NORMAL HİBRİT OPTİMUM analiz...")
    
    signal_color, reason = analyze_simple_pattern(game_info['player_cards'], game_info['banker_cards'], game_info['game_number'])
    
    if not signal_color:
        print(f"🚫 Normal Optimum: Renk tespit edilemedi")
        return
    
    # Tüm patternleri kabul et
    ALL_PATTERNS = ['🎯 GÜÇLÜ EL', '🏆 DOĞAL KAZANÇ', '📊 4+ KART', '🚨 3x TEKRAR', '📈 STANDART SİNYAL', '📈 İYİ EL']
    if reason not in ALL_PATTERNS:
        print(f"🚫 Normal Optimum: {reason} kabul edilmiyor")
        return
    
    # Pattern istatistik kontrolü (%60+ başarı yeterli)
    pattern_data = pattern_stats.get(reason, {'total': 0, 'wins': 0})
    if pattern_data['total'] > 2:  # 5'ten 2'ye
        success_rate = pattern_data['wins'] / pattern_data['total']
        if success_rate < 0.60:    # 0.85'ten 0.60'a
            print(f"🚫 Normal Optimum: {reason} başarı oranı düşük: %{success_rate*100:.1f}")
            return
    
    # Risk kontrolü (orta riskte de çalışsın)
    risk_seviye, _ = super_risk_analizi()
    if risk_seviye == "🔴 YÜKSEK RİSK":  # Sadece yüksek riskte dur
        print(f"🚫 Normal Optimum: Risk yüksek - {risk_seviye}")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    await send_new_signal(next_game_num, signal_color, f"🛡️ NORMAL OPTİMUM - {reason}", game_info)

async def super_hibrit_sistemi(game_info):
    """OPTİMUM GÜVENLİK - 2/5+ onay"""
    print("🛡️ SÜPER HİBRİT OPTİMUM analiz...")
    
    signal_color, onay_sebep = besli_onay_sistemi_optimum(game_info['player_cards'], game_info['banker_cards'], game_info['game_number'])
    if not signal_color:
        print(f"🚫 Süper Optimum: Onay reddedildi - {onay_sebep}")
        return
    
    # Risk kontrolü (orta riskte de çalışsın)
    risk_seviye, _ = super_risk_analizi()
    if risk_seviye == "🔴 YÜKSEK RİSK":  # Sadece yüksek riskte dur
        print(f"🚫 Süper Optimum: Risk yüksek - {risk_seviye}")
        return
    
    # Günlük performans kontrolü (daha esnek)
    daily = get_daily_stats()
    if daily['profit'] < -10:  # -5'ten -10'a
        print(f"🚫 Süper Optimum: Günlük zarar - {daily['profit']}")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    await send_new_signal(next_game_num, signal_color, f"🛡️ SÜPER OPTİMUM - {onay_sebep}", game_info)

def besli_onay_sistemi_optimum(player_cards, banker_cards, game_number):
    """OPTİMUM GÜVENLİK - 2/5 onay"""
    onaylar = []
    temel_renk = extract_largest_value_suit(player_cards)
    
    if temel_renk: 
        onaylar.append(("C2_3", temel_renk))
        print(f"✅ C2_3 onay: {temel_renk}")
    
    # Pattern onayı (daha geniş)
    pattern_renk, pattern_sebep = analyze_simple_pattern(player_cards, banker_cards, game_number)
    if pattern_renk and pattern_sebep in ['🎯 GÜÇLÜ EL', '🏆 DOĞAL KAZANÇ', '📊 4+ KART', '🚨 3x TEKRAR', '📈 STANDART SİNYAL', '📈 İYİ EL']:
        onaylar.append(("PATTERN", pattern_renk))
        print(f"✅ Pattern onay: {pattern_renk} - {pattern_sebep}")
    
    # Trend onayı (daha esnek)
    if len(color_trend) >= 5:
        son_trend = color_trend[-5:]
        if son_trend.count(temel_renk) >= 2:  # 3'ten 2'ye
            onaylar.append(("TREND", temel_renk))
            print(f"✅ Trend onay: {temel_renk}")
    
    # Quantum onayı
    quantum_renk, quantum_sebep = quantum_pattern_analizi({'player_cards': player_cards, 'banker_cards': banker_cards, 'game_number': game_number})
    if quantum_renk:
        onaylar.append(("QUANTUM", quantum_renk))
        print(f"✅ Quantum onay: {quantum_renk} - {quantum_sebep}")
    
    # Kart onayı
    kart_renk, kart_sebep = quantum_kart_analizi({'player_cards': player_cards, 'banker_cards': banker_cards, 'game_number': game_number})
    if kart_renk:
        onaylar.append(("KART", kart_renk))
        print(f"✅ Kart onay: {kart_renk} - {kart_sebep}")
    
    renk_oyları = {}
    for yontem, renk in onaylar: 
        renk_oyları[renk] = renk_oyları.get(renk, 0) + 1
    
    if renk_oyları:
        kazanan_renk = max(renk_oyları, key=renk_oyları.get)
        oy_sayisi = renk_oyları[kazanan_renk]
        
        # OPTİMUM: 2/5 onay
        if oy_sayisi >= 2:  # 4'ten 2'ye
            return kazanan_renk, f"🛡️ OPTİMUM ONAY ({oy_sayisi}/{len(onaylar)})"
    
    return None, f"❌ Onay sağlanamadı (Mevcut: {len(onaylar)}/5)"

async def quantum_hibrit_sistemi(game_info):
    """OPTİMUM GÜVENLİK - 1 pattern yeterli"""
    print("🛡️ QUANTUM HİBRİT OPTİMUM analiz...")
    
    pattern_sonuclari = []
    
    # Tüm patternleri kabul et
    signal_color, reason = analyze_simple_pattern(game_info['player_cards'], game_info['banker_cards'], game_info['game_number'])
    if signal_color and reason in ['🎯 GÜÇLÜ EL', '🏆 DOĞAL KAZANÇ', '📊 4+ KART', '🚨 3x TEKRAR', '📈 STANDART SİNYAL', '📈 İYİ EL']:
        pattern_sonuclari.append((signal_color, reason, "ELITE", 1.0))
    
    quantum_renk, quantum_sebep = quantum_pattern_analizi(game_info)
    if quantum_renk:
        pattern_sonuclari.append((quantum_renk, quantum_sebep, "QUANTUM", 0.8))
    
    trend_renk, trend_sebep = quantum_trend_analizi()
    if trend_renk:
        pattern_sonuclari.append((trend_renk, trend_sebep, "TREND", 0.7))
    
    # 1 pattern yeterli
    if len(pattern_sonuclari) < 1:  # 2'den 1'e
        print(f"🚫 Quantum Optimum: Yetersiz pattern ({len(pattern_sonuclari)}/1)")
        return
    
    # Ağırlık kontrolü (daha düşük)
    renk_agirliklari = {}
    for renk, sebep, tip, agirlik in pattern_sonuclari:
        renk_agirliklari[renk] = renk_agirliklari.get(renk, 0) + agirlik
    
    kazanan_renk = max(renk_agirliklari, key=renk_agirliklari.get)
    toplam_agirlik = renk_agirliklari[kazanan_renk]
    
    if toplam_agirlik < 0.5:  # 2.5'ten 0.5'e
        print(f"🚫 Quantum Optimum: Ağırlık yetersiz {toplam_agirlik:.1f}")
        return
    
    # Risk kontrolü (orta riskte de çalışsın)
    risk_seviye, _ = super_risk_analizi()
    if risk_seviye == "🔴 YÜKSEK RİSK":
        print(f"🚫 Quantum Optimum: Risk yüksek - {risk_seviye}")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    sebep_metin = " + ".join([sebep for _, sebep, _, _ in pattern_sonuclari])
    
    await send_new_signal(next_game_num, kazanan_renk, f"🛡️ QUANTUM OPTİMUM - {sebep_metin}", game_info)

async def quantum_pro_sistemi(game_info):
    """OPTİMUM GÜVENLİK - 2 pattern yeterli"""
    print("🛡️ QUANTUM PRO OPTİMUM analiz...")
    
    pattern_sonuclari = []
    
    # Patternler (daha geniş kabul)
    signal_color, reason = analyze_simple_pattern(game_info['player_cards'], game_info['banker_cards'], game_info['game_number'])
    if signal_color and reason in ['🎯 GÜÇLÜ EL', '🏆 DOĞAL KAZANÇ', '📊 4+ KART', '🚨 3x TEKRAR', '📈 İYİ EL']:
        pattern_data = pattern_stats.get(reason, {'total': 0, 'wins': 0})
        if pattern_data['total'] > 3 and pattern_data['wins'] / pattern_data['total'] >= 0.70:  # 0.9'dan 0.7'ye
            pattern_sonuclari.append((signal_color, reason, "ELITE", 1.2))
        else:
            pattern_sonuclari.append((signal_color, reason, "ELITE", 1.0))
    
    # Diğer quantum patternler
    quantum_renk, quantum_sebep = quantum_pattern_analizi(game_info)
    if quantum_renk:
        pattern_sonuclari.append((quantum_renk, quantum_sebep, "QUANTUM", 0.9))
    
    trend_renk, trend_sebep = quantum_trend_analizi()
    if trend_renk:
        pattern_sonuclari.append((trend_renk, trend_sebep, "TREND", 0.8))
    
    kart_renk, kart_sebep = quantum_kart_analizi(game_info)
    if kart_renk:
        pattern_sonuclari.append((kart_renk, kart_sebep, "KART", 0.7))
    
    if len(pattern_sonuclari) < 2:  # 3'ten 2'ye
        print(f"🚫 Quantum Pro Optimum: Yetersiz pattern ({len(pattern_sonuclari)}/2)")
        return
    
    # Ağırlık kontrolü (daha düşük)
    renk_agirliklari = {}
    for renk, sebep, tip, agirlik in pattern_sonuclari:
        renk_agirliklari[renk] = renk_agirliklari.get(renk, 0) + agirlik
    
    kazanan_renk = max(renk_agirliklari, key=renk_agirliklari.get)
    toplam_agirlik = renk_agirliklari[kazanan_renk]
    
    if toplam_agirlik < 1.5:  # 4.0'dan 1.5'e
        print(f"🚫 Quantum Pro Optimum: Ağırlık yetersiz {toplam_agirlik:.1f}")
        return
    
    # Risk kontrolü (orta riskte de çalışsın)
    risk_seviye, _ = super_risk_analizi()
    if risk_seviye == "🔴 YÜKSEK RİSK":
        print(f"🚫 Quantum Pro Optimum: Risk yüksek - {risk_seviye}")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    sebep_metin = " + ".join([sebep for _, sebep, _, _ in pattern_sonuclari])
    
    await send_new_signal(next_game_num, kazanan_renk, f"🛡️ QUANTUM PRO OPTİMUM - {sebep_metin}", game_info)

async def master_elite_sistemi(game_info):
    """OPTİMUM GÜVENLİK - %70+ başarılı patternler"""
    print("🛡️ MASTER ELITE OPTİMUM analiz...")
    
    # Elite patternler (daha geniş)
    ELITE_PATTERNS = ['🎯 GÜÇLÜ EL', '🚨 3x TEKRAR', '📊 4+ KART', '🏆 DOĞAL KAZANÇ', '📈 İYİ EL']
    
    signal_color, reason = analyze_simple_pattern(game_info['player_cards'], game_info['banker_cards'], game_info['game_number'])
    
    if reason not in ELITE_PATTERNS:
        print(f"🚫 Master Elite Optimum: {reason} elite değil")
        return
    
    # Pattern istatistik kontrolü (%70+ başarı)
    pattern_data = pattern_stats.get(reason, {'total': 0, 'wins': 0})
    if pattern_data['total'] < 2:  # 5'ten 2'ye
        print(f"🚫 Master Elite Optimum: {reason} yeterli veri yok")
        return
        
    success_rate = pattern_data['wins'] / pattern_data['total']
    if success_rate < 0.70:  # 1.0'dan 0.70'e
        print(f"🚫 Master Elite Optimum: {reason} başarı oranı düşük: %{success_rate*100:.1f}")
        return
    
    # Koşul filtreleri (daha esnek)
    filtre_gecen = 0
    toplam_filtre = 3  # 5'ten 3'e
    
    # 1. Risk seviyesi
    risk_seviye, _ = super_risk_analizi()
    if risk_seviye in ["🟢 DÜŞÜK RİSK", "🟡 ORTA RİSK"]:  # Orta riski de kabul et
        filtre_gecen += 1
    
    # 2. Trend desteği
    if len(color_trend) >= 6:  # 10'dan 6'ya
        son_trend = color_trend[-6:]
        if son_trend.count(signal_color) >= 2:  # 4'ten 2'ye
            filtre_gecen += 1
    
    # 3. Aktif sinyal kontrolü
    if not is_signal_active:
        filtre_gecen += 1
    
    print(f"📊 Master Elite Optimum Filtre: {filtre_gecen}/{toplam_filtre}")
    
    if filtre_gecen < 2:  # 4'ten 2'ye
        print(f"🚫 Master Elite Optimum: Yetersiz filtre ({filtre_gecen}/{toplam_filtre})")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    await send_new_signal(next_game_num, signal_color, f"🛡️ MASTER ELITE OPTİMUM - {reason}", game_info)

async def send_new_signal(game_num, signal_suit, reason, c2_3_info=None):
    global is_signal_active, daily_signal_count
    try:
        suit_display = get_suit_display_name(signal_suit)
        if c2_3_info:
            c2_3_type, c2_3_desc = c2_3_info.get('c2_3_type', ''), c2_3_info.get('c2_3_description', '')
            trigger_info = f"{c2_3_desc} {c2_3_type}"
        else: 
            c2_3_type, c2_3_desc = '#C2_3', 'KLASİK'
            trigger_info = "KLASİK #C2_3"
        
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        signal_text = f"🎯 **SİNYAL BAŞLADI** 🎯\n#N{game_num} - {suit_display}\n📊 Tetikleyici: {trigger_info}\n🎯 Sebep: {reason}\n⚡ Strateji: Martingale {MAX_MARTINGALE_STEPS} Seviye\n🕒 {gmt3_time} (GMT+3)\n🔴 SONUÇ: BEKLENİYOR..."
        sent_message = await client.send_message(KANAL_HEDEF, signal_text)
        print(f"🚀 Sinyal gönderildi: #N{game_num} - {suit_display} - {trigger_info}")
        daily_signal_count += 1
        martingale_trackers[game_num] = {
            'message_obj': sent_message, 
            'step': 0, 
            'signal_suit': signal_suit, 
            'sent_game_number': game_num, 
            'expected_game_number_for_check': game_num, 
            'start_time': datetime.now(GMT3), 
            'reason': reason, 
            'c2_3_type': c2_3_type,
            'c2_3_description': c2_3_desc,
            'results': []
        }
        is_signal_active = True
    except Exception as e: 
        print(f"❌ Sinyal gönderme hatası: {e}")

async def update_signal_message(tracker_info, result_type, current_step=None, result_details=None):
    try:
        signal_game_num, signal_suit = tracker_info['sent_game_number'], tracker_info['signal_suit']
        suit_display, message_obj, reason = get_suit_display_name(signal_suit), tracker_info['message_obj'], tracker_info.get('reason', '')
        c2_3_type = tracker_info.get('c2_3_type', '#C2_3')
        
        pattern_type = None
        for pattern in pattern_stats.keys():
            if pattern in reason:
                pattern_type = pattern
                break
        
        duration = datetime.now(GMT3) - tracker_info['start_time']
        duration_str = f"{duration.seconds // 60}d {duration.seconds % 60}s"
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        
        if result_details: 
            tracker_info['results'].append(result_details)
        
        if result_type == 'win':
            new_text = f"✅ **KAZANÇ** ✅\n#N{signal_game_num} - {suit_display}\n📊 Sebep: {reason}\n🎯 Seviye: {current_step if current_step else 0}. Seviye\n⏱️ Süre: {duration_str}\n🕒 Bitiş: {gmt3_time}\n🏆 **SONUÇ: KAZANDINIZ!**"
            update_performance_stats('win', current_step if current_step else 0, c2_3_type, pattern_type)
        elif result_type == 'loss':
            new_text = f"❌ **KAYIP** ❌\n#N{signal_game_num} - {suit_display}\n📊 Sebep: {reason}\n🎯 Seviye: {current_step if current_step else MAX_MARTINGALE_STEPS}. Seviye\n⏱️ Süre: {duration_str}\n🕒 Bitiş: {gmt3_time}\n💔 **SONUÇ: KAYBETTİNİZ**"
            update_performance_stats('loss', current_step if current_step else MAX_MARTINGALE_STEPS, c2_3_type, pattern_type)
        elif result_type == 'progress':
            step_details = f"{current_step}. seviye → #{tracker_info['expected_game_number_for_check']}"
            results_history = "\n".join([f"• {r}" for r in tracker_info['results']]) if tracker_info['results'] else "• İlk deneme"
            new_text = f"🔄 **MARTINGALE İLERLİYOR** 🔄\n#N{signal_game_num} - {suit_display}\n📊 Sebep: {reason}\n🎯 Adım: {step_details}\n⏱️ Süre: {duration_str}\n🕒 Son Güncelleme: {gmt3_time}\n📈 Geçmiş:\n{results_history}\n🎲 **SONRAKİ: #{tracker_info['expected_game_number_for_check']}**"
        elif result_type == 'step_result':
            new_text = f"📊 **ADIM SONUCU** 📊\n#N{signal_game_num} - {suit_display}\n🎯 Adım: {current_step}. seviye\n📋 Sonuç: {result_details}\n⏱️ Süre: {duration_str}\n🕒 Zaman: {gmt3_time}\n🔄 **DEVAM EDİYOR...**"
        
        await message_obj.edit(new_text)
        print(f"✏️ Sinyal güncellendi: #{signal_game_num} - {result_type}")
    except MessageNotModifiedError: 
        pass
    except Exception as e: 
        print(f"❌ Mesaj düzenleme hatası: {e}")

async def check_martingale_trackers():
    global martingale_trackers, is_signal_active
    trackers_to_remove = []
    for signal_game_num, tracker_info in list(martingale_trackers.items()):
        current_step, signal_suit, game_to_check = tracker_info['step'], tracker_info['signal_suit'], tracker_info['expected_game_number_for_check']
        if game_to_check not in game_results: continue
        result_info = game_results.get(game_to_check)
        if not result_info['is_final']: continue
        player_cards_str = result_info['player_cards']
        signal_won_this_step = bool(re.search(re.escape(signal_suit), player_cards_str))
        print(f"🔍 Sinyal kontrol: #{signal_game_num} (Seviye {current_step}) → #{game_to_check}")
        if signal_won_this_step:
            result_details = f"#{game_to_check} ✅ Kazanç - {current_step}. seviye"
            await update_signal_message(tracker_info, 'step_result', current_step, result_details)
            await asyncio.sleep(1)
            await update_signal_message(tracker_info, 'win', current_step)
            trackers_to_remove.append(signal_game_num)
            is_signal_active = False
            recent_games.append({'kazanç': True, 'adim': current_step})
            if len(recent_games) > 20: recent_games.pop(0)
            print(f"🎉 Sinyal #{signal_game_num} KAZANDI! Seviye: {current_step}")
        else:
            result_details = f"#{game_to_check} ❌ Kayıp - {current_step}. seviye"
            await update_signal_message(tracker_info, 'step_result', current_step, result_details)
            await asyncio.sleep(1)
            if current_step < MAX_MARTINGALE_STEPS:
                next_step, next_game_num = current_step + 1, get_next_game_number(game_to_check)
                martingale_trackers[signal_game_num]['step'], martingale_trackers[signal_game_num]['expected_game_number_for_check'] = next_step, next_game_num
                await update_signal_message(tracker_info, 'progress', next_step)
                print(f"📈 Sinyal #{signal_game_num} → {next_step}. seviye → #{next_game_num}")
            else:
                await update_signal_message(tracker_info, 'loss', current_step)
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False
                recent_games.append({'kazanç': False, 'adim': current_step})
                if len(recent_games) > 20: recent_games.pop(0)
                print(f"💔 Sinyal #{signal_game_num} KAYBETTİ! Son seviye: {current_step}")
    for game_num_to_remove in trackers_to_remove:
        if game_num_to_remove in martingale_trackers: 
            del martingale_trackers[game_num_to_remove]

def extract_game_info_from_message(text):
    game_info = {'game_number': None, 'player_cards': '', 'banker_cards': '', 'is_final': False, 'is_player_drawing': False, 'is_c2_3': False, 'c2_3_type': None, 'c2_3_description': ''}
    try:
        game_match = re.search(r'#N(\d+)', text)
        if game_match: game_info['game_number'] = int(game_match.group(1))
        player_match = re.search(r'\((.*?)\)', text)
        if player_match: game_info['player_cards'] = player_match.group(1)
        banker_match = re.search(r'\d+\s+\((.*?)\)', text)
        if banker_match: game_info['banker_cards'] = banker_match.group(1)
        
        # C2_3 TİPLERİNİ TESPİT ET
        for trigger_type, trigger_data in C2_3_TYPES.items():
            if trigger_type in text:
                game_info['is_c2_3'], game_info['c2_3_type'], game_info['c2_3_description'] = True, trigger_type, trigger_data['name']
                break
        
        # FİNAL MESAJI KONTROLÜ (TÜM MODLAR İÇİN)
        if ('✅' in text or '🔰' in text or '#X' in text or 'SONUÇ' in text): 
            game_info['is_final'] = True
            
    except Exception as e: print(f"❌ Oyun bilgisi çıkarma hatası: {e}")
    return game_info

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
            # TÜM MODLAR İÇİN FİNAL MESAJLARINI İŞLE
            if game_info['is_final']:
                trigger_game_num = game_info['game_number']
                print(f"🎯 Final mesajı tespit edildi: #{trigger_game_num}")
                
                if SISTEM_MODU == "normal_hibrit_ultra": 
                    await normal_hibrit_sistemi(game_info)
                elif SISTEM_MODU == "super_hibrit_ultra": 
                    await super_hibrit_sistemi(game_info)
                elif SISTEM_MODU == "quantum_hibrit_ultra":
                    await quantum_hibrit_sistemi(game_info)
                elif SISTEM_MODU == "quantum_pro_ultra":
                    await quantum_pro_sistemi(game_info)
                elif SISTEM_MODU == "master_elite_ultra":
                    await master_elite_sistemi(game_info)
                    
    except Exception as e: print(f"❌ Mesaj işleme hatası: {e}")

# KOMUTLAR
@client.on(events.NewMessage(pattern='(?i)/basla'))
async def handle_start(event): 
    await event.reply("🤖 Royal Baccarat Bot Aktif! 🎯")

@client.on(events.NewMessage(pattern='(?i)/durum'))
async def handle_durum(event):
    aktif_sinyal = "✅ Evet" if is_signal_active else "❌ Hayır"
    gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
    aktif_takipciler = "\n".join([f"• #{num} (Seviye {info['step']})" for num, info in martingale_trackers.items()])
    if not aktif_takipciler: 
        aktif_takipciler = "• Aktif sinyal yok"
    
    best_type, best_rate = get_best_performing_type()
    best_name = performance_stats['c2_3_performance'][best_type]['name'] if best_type else "Belirsiz"
    
    durum_mesaji = f"""🤖 **ROYAL BACCARAT BOT** 🤖

🟢 **Durum:** Çalışıyor
🎯 **Aktif Sinyal:** {aktif_sinyal}
📊 **Aktif Takipçiler:**
{aktif_takipciler}
📈 **Trend:** {color_trend[-5:] if color_trend else 'Yok'}
🎛️ **Mod:** {SISTEM_MODU}
🏆 **En İyi Tip:** {best_name} (%{best_rate:.1f})
🕒 **Saat:** {gmt3_time} (GMT+3)
📨 **Günlük Sinyal:** {daily_signal_count}

⚡ **Sistem:** OPTİMUM GÜVENLİK + Martingale {MAX_MARTINGALE_STEPS} Seviye
"""
    await event.reply(durum_mesaji)

@client.on(events.NewMessage(pattern='(?i)/istatistik'))
async def handle_istatistik(event):
    report = generate_performance_report()
    await event.reply(report)

@client.on(events.NewMessage(pattern='(?i)/performans'))
async def handle_performans(event):
    report = generate_performance_report()
    await event.reply(report)

@client.on(events.NewMessage(pattern='(?i)/rapor'))
async def handle_rapor(event):
    daily = get_daily_stats()
    weekly = get_weekly_stats()
    win_rate = calculate_win_rate()
    c2_analysis = get_c2_3_performance()
    
    report = f"""📊 **DETAYLI GÜNLÜK/HAFTALIK RAPOR** 📊

🎯 **BUGÜN ({datetime.now(GMT3).strftime('%d.%m.%Y')}):**
• Sinyal: {daily['signals']}
• Kazanç: {daily['wins']} 
• Kayıp: {daily['losses']}
• Kâr/Zarar: {daily['profit']} birim
• Başarı Oranı: %{(daily['wins']/daily['signals']*100) if daily['signals'] > 0 else 0:.1f}

📈 **BU HAFTA:**
• Sinyal: {weekly['signals']}
• Kazanç: {weekly['wins']}
• Kayıp: {weekly['losses']} 
• Kâr/Zarar: {weekly['profit']} birim
• Başarı Oranı: %{(weekly['wins']/weekly['signals']*100) if weekly['signals'] > 0 else 0:.1f}

🏆 **GENEL:**
• Toplam Sinyal: {performance_stats['total_signals']}
• Kazanç Oranı: %{win_rate:.1f}
• Toplam Kâr: {performance_stats['total_profit']} birim
• Mevcut Seri: {performance_stats['current_streak']} kazanç

{c2_analysis}
"""
    await event.reply(report)

@client.on(events.NewMessage(pattern='(?i)/c2analiz'))
async def handle_c2_analiz(event):
    analysis = get_c2_3_performance()
    await event.reply(analysis)

@client.on(events.NewMessage(pattern='(?i)/pattern'))
async def handle_pattern(event):
    analysis = get_pattern_performance()
    await event.reply(analysis)

@client.on(events.NewMessage(pattern='(?i)/trend'))
async def handle_trend(event):
    analysis = generate_trend_analysis()
    await event.reply(analysis)

@client.on(events.NewMessage(pattern='(?i)/eniyi'))
async def handle_eniyi(event):
    best_type, best_rate = get_best_performing_type()
    if best_type:
        best_data = performance_stats['c2_3_performance'][best_type]
        await event.reply(
            f"🏆 **EN İYİ PERFORMANS** 🏆\n\n"
            f"{best_data['emoji']} **{best_data['name']}**\n"
            f"📊 Başarı Oranı: %{best_rate:.1f}\n"
            f"✅ Kazanç: {best_data['stats']['wins']} | ❌ Kayıp: {best_data['stats']['losses']}\n"
            f"💰 Toplam Kâr: {best_data['stats']['profit']} birim\n"
            f"🎯 Güven Skoru: {best_data['confidence']}"
        )
    else:
        await event.reply("📊 Henüz yeterli veri yok")

@client.on(events.NewMessage(pattern='(?i)/enkotu'))
async def handle_enkotu(event):
    worst_type, worst_rate = get_worst_performing_type()
    if worst_type:
        worst_data = performance_stats['c2_3_performance'][worst_type]
        await event.reply(
            f"📉 **EN KÖTÜ PERFORMANS** 📉\n\n"
            f"{worst_data['emoji']} **{worst_data['name']}**\n"
            f"📊 Başarı Oranı: %{worst_rate:.1f}\n"
            f"✅ Kazanç: {worst_data['stats']['wins']} | ❌ Kayıp: {worst_data['stats']['losses']}\n"
            f"💰 Toplam Kâr: {worst_data['stats']['profit']} birim\n"
            f"⚡ Öneri: Bu tipi dikkatle kullanın"
        )
    else:
        await event.reply("📊 Henüz yeterli veri yok")

@client.on(events.NewMessage(pattern='(?i)/tavsiye'))
async def handle_tavsiye(event):
    best_type, best_rate = get_best_performing_type()
    worst_type, worst_rate = get_worst_performing_type()
    
    if best_type and worst_type:
        best_data = performance_stats['c2_3_performance'][best_type]
        worst_data = performance_stats['c2_3_performance'][worst_type]
        
        tavsiye = f"🎯 **TRADING TAVSİYESİ** 🎯\n\n"
        tavsiye += f"🏆 **TERCIH EDİLEN:** {best_data['emoji']} {best_data['name']}\n"
        tavsiye += f"   📈 Başarı: %{best_rate:.1f} | 💰 Kâr: {best_data['stats']['profit']} birim\n\n"
        tavsiye += f"⚠️ **DİKKATLİ KULLAN:** {worst_data['emoji']} {worst_data['name']}\n"
        tavsiye += f"   📉 Başarı: %{worst_rate:.1f} | 💸 Zarar: {abs(worst_data['stats']['profit'])} birim\n\n"
        tavsiye += f"💡 **STRATEJİ:** {best_data['name']} tipine odaklanın, {worst_data['name']} tipinde daha seçici olun."
        
        await event.reply(tavsiye)
    else:
        await event.reply("📊 Henüz yeterli veri yok. Daha fazla sinyal bekleyin.")

# OPTİMUM GÜVENLİK MOD KOMUTLARI
@client.on(events.NewMessage(pattern='(?i)/mod_normal'))
async def handle_mod_normal(event):
    global SISTEM_MODU
    SISTEM_MODU = "normal_hibrit_ultra"
    await event.reply("🛡️ NORMAL OPTİMUM modu aktif! • Geniş Patternler • %60+ Başarı")

@client.on(events.NewMessage(pattern='(?i)/mod_super'))
async def handle_mod_super(event):
    global SISTEM_MODU
    SISTEM_MODU = "super_hibrit_ultra"
    await event.reply("🛡️ SÜPER OPTİMUM modu aktif! • 2/5+ Onay • Esnek Filtreler")

@client.on(events.NewMessage(pattern='(?i)/mod_quantum'))
async def handle_mod_quantum(event):
    global SISTEM_MODU
    SISTEM_MODU = "quantum_hibrit_ultra"
    await event.reply("🛡️ QUANTUM OPTİMUM modu aktif! • 1 Pattern Yeterli • Ağırlık 0.5+")

@client.on(events.NewMessage(pattern='(?i)/mod_quantumpro'))
async def handle_mod_quantumpro(event):
    global SISTEM_MODU
    SISTEM_MODU = "quantum_pro_ultra"
    await event.reply("🛡️ QUANTUM PRO OPTİMUM modu aktif! • 2 Pattern • Ağırlık 1.5+")

@client.on(events.NewMessage(pattern='(?i)/mod_masterelite'))
async def handle_mod_masterelite(event):
    global SISTEM_MODU
    SISTEM_MODU = "master_elite_ultra"
    await event.reply("🛡️ MASTER ELITE OPTİMUM modu aktif! • %70+ Patternler • Esnek Koşullar")

@client.on(events.NewMessage(pattern='(?i)/mod_durum'))
async def handle_mod_status(event): 
    await event.reply(f"🎛️ Aktif Mod: {SISTEM_MODU}")

@client.on(events.NewMessage(pattern='(?i)/temizle'))
async def handle_temizle(event):
    if event.sender_id != ADMIN_ID: 
        return await event.reply("❌ Yetkiniz yok!")
    global color_trend, recent_games, daily_signal_count
    color_trend, recent_games, daily_signal_count = [], [], 0
    await event.reply("✅ Trend verileri temizlendi! Sinyal sayacı sıfırlandı.")

@client.on(events.NewMessage(pattern='(?i)/acil_durdur'))
async def handle_emergency_stop(event):
    global is_signal_active
    if event.sender_id != ADMIN_ID: 
        return await event.reply("❌ Yetkiniz yok!")
    is_signal_active = False
    martingale_trackers.clear()
    await event.reply("🚨 **ACİL DURDURMA** 🚨\n✅ Tüm sinyaller durduruldu\n✅ Takipçiler temizlendi\n✅ Sistem duraklatıldı\nDevam etmek için /aktif_et komutunu kullan")

@client.on(events.NewMessage(pattern='(?i)/aktif_et'))
async def handle_activate(event):
    global is_signal_active
    if event.sender_id != ADMIN_ID: 
        return await event.reply("❌ Yetkiniz yok!")
    is_signal_active = False
    await event.reply(f"✅ **SİSTEM AKTİF** ✅\n🟢 Yeni sinyaller için hazır\n🎛️ Mod: {SISTEM_MODU}\n📊 Bugün: {daily_signal_count} sinyal")

@client.on(events.NewMessage(pattern='(?i)/yardim'))
async def handle_yardim(event):
    yardim_mesaji = """🤖 **ROYAL BACCARAT BOT - YARDIM MENÜSÜ** 🤖

🎯 **OPTİMUM GÜVENLİK MODLAR:**
• /mod_normal - Normal Optimum (geniş patternler)
• /mod_super - Süper Optimum (2/5+ onay)
• /mod_quantum - Quantum Optimum (1 pattern yeterli)
• /mod_quantumpro - Quantum Pro Optimum (2 pattern)
• /mod_masterelite - Master Elite Optimum (%70+ patternler)
• /mod_durum - Aktif modu göster

📊 **ANALİZ KOMUTLARI:**
• /durum - Sistem durumu
• /istatistik - Detaylı istatistikler
• /performans - Performans raporu
• /rapor - Günlük/haftalık rapor
• /c2analiz - C2-3 tip performansları
• /pattern - Pattern performans tablosu
• /trend - Trend analizi

⚡ **SİSTEM ÖZELLİKLERİ:**
• 🛡️ Optimum Güvenlik Modları
• 🎯 Yüksek Sinyal Sıklığı
• ⚠️ Düşük Risk
• 🔒 Martingale 2 Seviye

🔧 **Sistem:** Optimum Güvenlik + Martingale {MAX_MARTINGALE_STEPS} Seviye
🕒 **Saat Dilimi:** GMT+3 (İstanbul)
""".format(MAX_MARTINGALE_STEPS=MAX_MARTINGALE_STEPS)
    await event.reply(yardim_mesaji)

if __name__ == '__main__':
    print("🤖 ROYAL BACCARAT BOT BAŞLIYOR...")
    print(f"🔧 API_ID: {API_ID}")
    print(f"🎯 Kaynak Kanal: {KANAL_KAYNAK_ID}")
    print(f"📤 Hedef Kanal: {KANAL_HEDEF}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"🎛️ Varsayılan Mod: {SISTEM_MODU}")
    print(f"🛡️ Optimum Güvenlik Sistemleri: AKTİF")
    print(f"⚡ Martingale Seviyesi: {MAX_MARTINGALE_STEPS}")
    print(f"📊 Pattern Performans Takibi: AKTİF")
    print(f"🕒 Saat Dilimi: GMT+3")
    print("⏳ Bağlanıyor...")
    try:
        with client: 
            client.run_until_disconnected()
    except KeyboardInterrupt: 
        print("\n👋 Bot durduruluyor...")
    except Exception as e: 
        print(f"❌ Bot başlangıç hatası: {e}")
EOF

echo "✅ screen.py dosyası güncellendi!"

# Botu yeniden başlat
echo "🔄 Bot yeniden başlatılıyor..."
sudo systemctl restart screen_bot

echo "✅ Bot güncellendi ve yeniden başlatıldı!"
echo "📊 Logları kontrol et: sudo journalctl -u screen_bot -f"
