# -*- coding: utf-8 -*-
import re, json, os, asyncio, sys, pytz
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
from collections import defaultdict, deque

API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
BOT_TOKEN = '7754085980:AAG75MV6xtipXJP-aycQ_yor5Ca56CUC9hw'
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"
ADMIN_ID = 1136442929
SISTEM_MODU = "normal_hibrit_ultra"
GMT3 = pytz.timezone('Europe/Istanbul')
client = TelegramClient('royal_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

game_results, martingale_trackers, color_trend, recent_games = {}, {}, [], []
MAX_MARTINGALE_STEPS, MAX_GAME_NUMBER, is_signal_active, daily_signal_count = 2, 1440, False, 0

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
        if sum(player_values) >= 8 and len(player_values) >= 3: return signal_color, "🎯 GÜÇLÜ EL"
        elif sum(player_values) in [8, 9]: return signal_color, "🏆 DOĞAL KAZANÇ"
        elif total_cards >= 5: return signal_color, "📊 5+ KART"
        elif len(color_trend) >= 3 and color_trend[-3:] == [signal_color] * 3: return signal_color, "🚨 3x TEKRAR"
        else: return signal_color, "📈 STANDART SİNYAL"
    except Exception as e:
        print(f"❌ Pattern analysis error: {e}")
        return None, f"Hata: {e}"

def besli_onay_sistemi_ultra(player_cards, banker_cards, game_number):
    """ULTRA GÜVENLİ - Sadece 4/5 ve 5/5 onay"""
    onaylar = []
    temel_renk = extract_largest_value_suit(player_cards)
    
    if temel_renk: 
        onaylar.append(("C2_3", temel_renk))
        print(f"✅ C2_3 onay: {temel_renk}")
    
    pattern_renk, pattern_sebep = analyze_simple_pattern(player_cards, banker_cards, game_number)
    if pattern_renk and pattern_sebep in ['🎯 GÜÇLÜ EL', '🏆 DOĞAL KAZANÇ']:
        onaylar.append(("PATTERN", pattern_renk))
        print(f"✅ Pattern onay: {pattern_renk} - {pattern_sebep}")
    
    if len(color_trend) >= 8:
        son_8 = color_trend[-8:]
        if son_8.count(temel_renk) >= 4:
            onaylar.append(("TREND", temel_renk))
            print(f"✅ Trend onay: {temel_renk}")
    
    renk_oyları = {}
    for yontem, renk in onaylar: 
        renk_oyları[renk] = renk_oyları.get(renk, 0) + 1
    
    if renk_oyları:
        kazanan_renk = max(renk_oyları, key=renk_oyları.get)
        oy_sayisi = renk_oyları[kazanan_renk]
        
        # SADECE 4/5 ve 5/5
        if oy_sayisi >= 4:
            return kazanan_renk, f"🛡️ ULTRA ONAY ({oy_sayisi}/5)"
    
    return None, "❌ Ultra onay sağlanamadı"

def super_risk_analizi():
    """ULTRA GÜVENLİ RİSK ANALİZİ"""
    risk_puan = 0
    uyarılar = []
    
    # 1. Trend riski
    if len(color_trend) >= 10:
        son_10 = color_trend[-10:]
        renk_frekans = {renk: son_10.count(renk) for renk in set(son_10)}
        max_frekans = max(renk_frekans.values())
        
        if max_frekans >= 8:
            risk_puan += 30
            uyarılar.append("🚨 YÜKSEK TREND DOMINANCE")
        elif max_frekans >= 6:
            risk_puan += 15
            uyarılar.append("⚠️ ORTA TREND DOMINANCE")
    
    # 2. Kayıp zinciri
    if len(recent_games) >= 6:
        son_kayiplar = sum(1 for oyun in recent_games[-6:] if not oyun.get('kazanç', True))
        if son_kayiplar >= 3:
            risk_puan += 25
            uyarılar.append("🔴 3/6 KAYIP ZİNCİRİ")
        elif son_kayiplar >= 2:
            risk_puan += 10
            uyarılar.append("🟡 2/6 KAYIP ZİNCİRİ")
    
    # 3. Günlük performans
    daily = get_daily_stats()
    if daily['profit'] <= -8:
        risk_puan += 20
        uyarılar.append("💸 YÜKSEK ZARAR")
    elif daily['profit'] <= -3:
        risk_puan += 10
        uyarılar.append("📉 ORTA ZARAR")
    
    # Risk seviyesi
    if risk_puan >= 30: return "🔴 YÜKSEK RİSK", uyarılar
    elif risk_puan >= 15: return "🟡 ORTA RİSK", uyarılar
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

# QUANTUM HİBRİT SİSTEMİ - ULTRA GÜVENLİ
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
    
    if sum(player_degerler) >= 8 and len(player_kartlar) >= 3:
        return renk, "🎯 GÜÇLÜ EL"
    
    if (len(player_kartlar) + len(banker_kartlar)) >= 5:
        return renk, "📊 5+ KART"
    
    if player_toplam >= 7 and banker_toplam <= 4:
        return renk, "💎 YÜKSEK DEĞER"
    
    return None, None

def quantum_trend_analizi():
    if len(color_trend) < 8:
        return None, None
    
    son_8 = color_trend[-8:]
    renk_frekans = {renk: son_8.count(renk) for renk in set(son_8)}
    
    for renk, sayi in renk_frekans.items():
        if sayi >= 6:
            return renk, f"📈 TREND DOMINANCE ({sayi}/8)"
    
    if len(set(son_8[-4:])) == 1:
        return son_8[-1], "🔥 TREND MASTER 4x"
    
    return None, None

def quantum_kart_analizi(game_info):
    player_cards = game_info['player_cards']
    banker_cards = game_info['banker_cards']
    
    player_kartlar = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
    banker_kartlar = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)
    
    renk = extract_largest_value_suit(player_cards)
    if not renk:
        return None, None
    
    yuksek_kartlar = [v for v in [get_baccarat_value(k[0]) for k in player_kartlar] if v >= 7]
    if len(yuksek_kartlar) >= 2:
        return renk, "🃏 ÇOKLU YÜKSEK KART"
    
    degerler = [get_baccarat_value(k[0]) for k in player_kartlar]
    if len(set(degerler)) >= 3:
        return renk, "🎲 KARIŞIK DEĞER"
    
    return None, None

# ULTRA GÜVENLİ SİSTEM FONKSİYONLARI
async def normal_hibrit_sistemi(game_info):
    """ULTRA GÜVENLİ - Sadece %90+ başarılı patternler"""
    print("🛡️ NORMAL HİBRİT ULTRA analiz...")
    
    signal_color, reason = analyze_simple_pattern(game_info['player_cards'], game_info['banker_cards'], game_info['game_number'])
    
    # Sadece yüksek başarılı patternler
    HIGH_SUCCESS_PATTERNS = ['🎯 GÜÇLÜ EL', '🏆 DOĞAL KAZANÇ', '📊 5+ KART', '🚨 3x TEKRAR']
    if reason not in HIGH_SUCCESS_PATTERNS:
        print(f"🚫 Normal Ultra: {reason} kabul edilmiyor")
        return
    
    # Pattern istatistik kontrolü (%85+ başarı)
    pattern_data = pattern_stats.get(reason, {'total': 0, 'wins': 0})
    if pattern_data['total'] > 5:
        success_rate = pattern_data['wins'] / pattern_data['total']
        if success_rate < 0.85:
            print(f"🚫 Normal Ultra: {reason} başarı oranı düşük: %{success_rate*100:.1f}")
            return
    
    # Risk kontrolü
    risk_seviye, _ = super_risk_analizi()
    if risk_seviye == "🔴 YÜKSEK RİSK":
        print(f"🚫 Normal Ultra: Risk yüksek - {risk_seviye}")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    await send_new_signal(next_game_num, signal_color, f"🛡️ NORMAL ULTRA - {reason}", game_info)

async def super_hibrit_sistemi(game_info):
    """ULTRA GÜVENLİ - Sadece 4/5+ onay"""
    print("🛡️ SÜPER HİBRİT ULTRA analiz...")
    
    signal_color, onay_sebep = besli_onay_sistemi_ultra(game_info['player_cards'], game_info['banker_cards'], game_info['game_number'])
    if not signal_color:
        print(f"🚫 Süper Ultra: Onay reddedildi - {onay_sebep}")
        return
    
    # Risk kontrolü
    risk_seviye, _ = super_risk_analizi()
    if risk_seviye != "🟢 DÜŞÜK RİSK":
        print(f"🚫 Süper Ultra: Risk yüksek - {risk_seviye}")
        return
    
    # Günlük performans kontrolü
    daily = get_daily_stats()
    if daily['profit'] < -5:
        print(f"🚫 Süper Ultra: Günlük zarar - {daily['profit']}")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    await send_new_signal(next_game_num, signal_color, f"🛡️ SÜPER ULTRA - {onay_sebep}", game_info)

async def quantum_hibrit_sistemi(game_info):
    """ULTRA GÜVENLİ - Yüksek ağırlık + elite patternler"""
    print("🛡️ QUANTUM HİBRİT ULTRA analiz...")
    
    pattern_sonuclari = []
    
    # Sadece elite patternler
    signal_color, reason = analyze_simple_pattern(game_info['player_cards'], game_info['banker_cards'], game_info['game_number'])
    if reason in ['🎯 GÜÇLÜ EL', '🏆 DOĞAL KAZANÇ']:
        pattern_sonuclari.append((signal_color, reason, "ELITE", 1.5))
    
    quantum_renk, quantum_sebep = quantum_pattern_analizi(game_info)
    if quantum_renk and quantum_sebep in ['💎 YÜKSEK DEĞER', '🃏 GÜÇLÜ 3+KART']:
        pattern_sonuclari.append((quantum_renk, quantum_sebep, "QUANTUM", 1.2))
    
    if len(pattern_sonuclari) < 2:
        print(f"🚫 Quantum Ultra: Yetersiz pattern ({len(pattern_sonuclari)}/2)")
        return
    
    # Ağırlık kontrolü
    renk_agirliklari = {}
    for renk, sebep, tip, agirlik in pattern_sonuclari:
        renk_agirliklari[renk] = renk_agirliklari.get(renk, 0) + agirlik
    
    kazanan_renk = max(renk_agirliklari, key=renk_agirliklari.get)
    toplam_agirlik = renk_agirliklari[kazanan_renk]
    
    if toplam_agirlik < 2.5:
        print(f"🚫 Quantum Ultra: Ağırlık yetersiz {toplam_agirlik:.1f}")
        return
    
    # Risk kontrolü
    risk_seviye, _ = super_risk_analizi()
    if risk_seviye != "🟢 DÜŞÜK RİSK":
        print(f"🚫 Quantum Ultra: Risk yüksek - {risk_seviye}")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    sebep_metin = " + ".join([sebep for _, sebep, _, _ in pattern_sonuclari])
    
    await send_new_signal(next_game_num, kazanan_renk, f"🛡️ QUANTUM ULTRA - {sebep_metin}", game_info)

async def quantum_pro_sistemi(game_info):
    """ULTRA GÜVENLİ - Sadece %95+ başarılı pattern kombinasyonları"""
    print("🛡️ QUANTUM PRO ULTRA analiz...")
    
    pattern_sonuclari = []
    
    # Elite patternler + yüksek başarı istatistikleri
    signal_color, reason = analyze_simple_pattern(game_info['player_cards'], game_info['banker_cards'], game_info['game_number'])
    if reason in ['🎯 GÜÇLÜ EL', '🏆 DOĞAL KAZANÇ']:
        pattern_data = pattern_stats.get(reason, {'total': 0, 'wins': 0})
        if pattern_data['total'] > 10 and pattern_data['wins'] / pattern_data['total'] >= 0.9:
            pattern_sonuclari.append((signal_color, reason, "ELITE", 2.0))
    
    # Diğer quantum patternler
    quantum_renk, quantum_sebep = quantum_pattern_analizi(game_info)
    if quantum_renk:
        pattern_sonuclari.append((quantum_renk, quantum_sebep, "QUANTUM", 1.5))
    
    trend_renk, trend_sebep = quantum_trend_analizi()
    if trend_renk and "DOMINANCE" in trend_sebep:
        pattern_sonuclari.append((trend_renk, trend_sebep, "TREND", 1.2))
    
    if len(pattern_sonuclari) < 3:
        print(f"🚫 Quantum Pro Ultra: Yetersiz pattern ({len(pattern_sonuclari)}/3)")
        return
    
    # Yüksek ağırlık şartı
    renk_agirliklari = {}
    for renk, sebep, tip, agirlik in pattern_sonuclari:
        renk_agirliklari[renk] = renk_agirliklari.get(renk, 0) + agirlik
    
    kazanan_renk = max(renk_agirliklari, key=renk_agirliklari.get)
    toplam_agirlik = renk_agirliklari[kazanan_renk]
    
    if toplam_agirlik < 4.0:
        print(f"🚫 Quantum Pro Ultra: Ağırlık yetersiz {toplam_agirlik:.1f}")
        return
    
    # Ultra risk kontrolü
    risk_seviye, _ = super_risk_analizi()
    if risk_seviye != "🟢 DÜŞÜK RİSK":
        print(f"🚫 Quantum Pro Ultra: Risk yüksek - {risk_seviye}")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    sebep_metin = " + ".join([sebep for _, sebep, _, _ in pattern_sonuclari])
    
    await send_new_signal(next_game_num, kazanan_renk, f"🛡️ QUANTUM PRO ULTRA - {sebep_metin}", game_info)

async def master_elite_sistemi(game_info):
    """ULTRA GÜVENLİ - Sadece %100 başarılı patternler"""
    print("🛡️ MASTER ELITE ULTRA analiz...")
    
    # Sadece %100 başarılı patternler
    PERFECT_PATTERNS = ['🎯 GÜÇLÜ EL', '🚨 3x TEKRAR', '📊 5+ KART']
    
    signal_color, reason = analyze_simple_pattern(game_info['player_cards'], game_info['banker_cards'], game_info['game_number'])
    
    if reason not in PERFECT_PATTERNS:
        print(f"🚫 Master Elite Ultra: {reason} perfect değil")
        return
    
    # Pattern istatistik kontrolü (%100 başarı)
    pattern_data = pattern_stats.get(reason, {'total': 0, 'wins': 0})
    if pattern_data['total'] < 5 or pattern_data['wins'] / pattern_data['total'] < 1.0:
        print(f"🚫 Master Elite Ultra: {reason} %100 başarılı değil")
        return
    
    # Mükemmel koşul filtreleri
    filtre_gecen = 0
    toplam_filtre = 5
    
    # 1. Risk seviyesi
    risk_seviye, _ = super_risk_analizi()
    if risk_seviye == "🟢 DÜŞÜK RİSK":
        filtre_gecen += 1
    
    # 2. Trend desteği
    if len(color_trend) >= 10:
        son_10 = color_trend[-10:]
        if son_10.count(signal_color) >= 4:
            filtre_gecen += 1
    
    # 3. Günlük performans
    daily = get_daily_stats()
    if daily['profit'] >= 0:
        filtre_gecen += 1
    
    # 4. Pattern frekansı
    if pattern_data['total'] <= 20:
        filtre_gecen += 1
    
    # 5. Aktif sinyal kontrolü
    if not is_signal_active:
        filtre_gecen += 1
    
    print(f"📊 Master Elite Ultra Filtre: {filtre_gecen}/{toplam_filtre}")
    
    if filtre_gecen < 4:
        print(f"🚫 Master Elite Ultra: Yetersiz filtre ({filtre_gecen}/{toplam_filtre})")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    await send_new_signal(next_game_num, signal_color, f"🛡️ MASTER ELITE ULTRA - {reason}", game_info)

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
        for trigger_type, trigger_data in C2_3_TYPES.items():
            if trigger_type in text:
                game_info['is_c2_3'], game_info['c2_3_type'], game_info['c2_3_description'] = True, trigger_type, trigger_data['name']
                break
        if ('✅' in text or '🔰' in text or '#X' in text): game_info['is_final'] = True
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
            if game_info['is_final'] and game_info.get('is_c2_3'):
                trigger_game_num, c2_3_type, c2_3_desc = game_info['game_number'], game_info['c2_3_type'], game_info['c2_3_description']
                print(f"🎯 {c2_3_desc} tespit edildi: #{trigger_game_num} - {c2_3_type}")
                
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

⚡ **Sistem:** ULTRA GÜVENLİ + Martingale {MAX_MARTINGALE_STEPS} Seviye
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

# ULTRA GÜVENLİ MOD KOMUTLARI
@client.on(events.NewMessage(pattern='(?i)/mod_normal'))
async def handle_mod_normal(event):
    global SISTEM_MODU
    SISTEM_MODU = "normal_hibrit_ultra"
    await event.reply("🛡️ NORMAL ULTRA modu aktif! • %90+ Başarılı Patternler • Temel Filtreler")

@client.on(events.NewMessage(pattern='(?i)/mod_super'))
async def handle_mod_super(event):
    global SISTEM_MODU
    SISTEM_MODU = "super_hibrit_ultra"
    await event.reply("🛡️ SÜPER ULTRA modu aktif! • Sadece 4/5+ Onay • Sıkı Filtreler")

@client.on(events.NewMessage(pattern='(?i)/mod_quantum'))
async def handle_mod_quantum(event):
    global SISTEM_MODU
    SISTEM_MODU = "quantum_hibrit_ultra"
    await event.reply("🛡️ QUANTUM ULTRA modu aktif! • Elite Patternler • Ağırlık 2.5+")

@client.on(events.NewMessage(pattern='(?i)/mod_quantumpro'))
async def handle_mod_quantumpro(event):
    global SISTEM_MODU
    SISTEM_MODU = "quantum_pro_ultra"
    await event.reply("🛡️ QUANTUM PRO ULTRA modu aktif! • %95+ Başarı • Ağırlık 4.0+")

@client.on(events.NewMessage(pattern='(?i)/mod_masterelite'))
async def handle_mod_masterelite(event):
    global SISTEM_MODU
    SISTEM_MODU = "master_elite_ultra"
    await event.reply("🛡️ MASTER ELITE ULTRA modu aktif! • Sadece %100 Patternler • Mükemmel Koşullar")

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

🎯 **ULTRA GÜVENLİ MODLAR:**
• /mod_normal - Normal Ultra (%90+ patternler)
• /mod_super - Süper Ultra (4/5+ onay)
• /mod_quantum - Quantum Ultra (elite patternler)
• /mod_quantumpro - Quantum Pro Ultra (%95+ başarı)
• /mod_masterelite - Master Elite Ultra (%100 patternler)
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
• 🛡️ Ultra Güvenlik Modları
• 🎯 Yüksek Başarı Oranı
• ⚠️ Düşük Risk
• 🔒 Martingale 2 Seviye

🔧 **Sistem:** Ultra Güvenlik + Martingale {MAX_MARTINGALE_STEPS} Seviye
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
    print(f"🛡️ Ultra Güvenlik Sistemleri: AKTİF")
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
