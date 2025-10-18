# -*- coding: utf-8 -*-
import re, json, os, asyncio, sys, pytz
from datetime import datetime, timedelta
from collections import defaultdict, deque

SISTEM_MODU = "normal_hibrit"
GMT3 = pytz.timezone('Europe/Istanbul')

# Global değişkenler
game_results, martingale_trackers, color_trend, recent_games = {}, {}, [], []
MAX_MARTINGALE_STEPS, MAX_GAME_NUMBER, is_signal_active, daily_signal_count = 3, 1440, False, 0

# Strateji Performans Takip Sistemi
strategy_performance = {
    "🎯 GÜÇLÜ EL": {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    "🏆 DOĞAL KAZANÇ": {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    "📊 5+ KART": {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    "🚨 3x TEKRAR": {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    "📈 STANDART SİNYAL": {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    "✅ 5-Lİ ONAY": {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    "🚀 SÜPER HİBRİT": {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    "🎯 KLASİK #C2_3": {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0}
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
    'signal_history': deque(maxlen=1000)
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
        
        # Strateji tespiti
        if sum(player_values) >= 8 and len(player_values) >= 3: 
            return signal_color, "🎯 GÜÇLÜ EL"
        elif sum(player_values) in [8, 9]: 
            return signal_color, "🏆 DOĞAL KAZANÇ"
        elif total_cards >= 5: 
            return signal_color, "📊 5+ KART"
        elif len(color_trend) >= 3 and color_trend[-3:] == [signal_color] * 3: 
            return signal_color, "🚨 3x TEKRAR"
        else: 
            return signal_color, "📈 STANDART SİNYAL"
    except Exception as e:
        print(f"❌ Pattern analysis error: {e}")
        return None, f"Hata: {e}"

def besli_onay_sistemi(player_cards, banker_cards, game_number):
    onaylar = []
    temel_renk = extract_largest_value_suit(player_cards)
    if temel_renk: 
        onaylar.append(("C2_3", temel_renk))
    pattern_renk, pattern_sebep = analyze_simple_pattern(player_cards, banker_cards, game_number)
    if pattern_renk and "STANDART" not in pattern_sebep:
        onaylar.append(("PATTERN", pattern_renk))
    if color_trend:
        trend_renk = color_trend[-1] if color_trend else None
        if trend_renk: onaylar.append(("TREND", trend_renk))
    if len(color_trend) >= 3:
        son_uc = color_trend[-3:]
        if son_uc.count(temel_renk) >= 2: onaylar.append(("REPEAT", temel_renk))
    
    renk_oyları = {}
    for yontem, renk in onaylar: 
        renk_oyları[renk] = renk_oyları.get(renk, 0) + 1
    
    if renk_oyları:
        kazanan_renk = max(renk_oyları, key=renk_oyları.get)
        oy_sayisi = renk_oyları[kazanan_renk]
        güven = oy_sayisi / 5
        if oy_sayisi >= 3 and güven >= 0.6: 
            return kazanan_renk, f"✅ 5-Lİ ONAY ({oy_sayisi}/5) - %{güven*100:.1f}"
    return None, "❌ 5'li onay sağlanamadı"

def super_hibrit_sistemi(player_cards, banker_cards, game_number):
    signal_color, onay_sebep = besli_onay_sistemi(player_cards, banker_cards, game_number)
    if signal_color:
        return signal_color, "🚀 SÜPER HİBRİT"
    return None, "❌ Süper hibrit sinyal yok"

def update_strategy_stats(strategy_type, result_type, steps=0):
    """Strateji performans istatistiklerini günceller"""
    if strategy_type not in strategy_performance:
        strategy_type = "📈 STANDART SİNYAL"
    
    stats = strategy_performance[strategy_type]
    stats['total'] += 1
    
    if result_type == 'win':
        stats['wins'] += 1
        stats['profit'] += 1
        if stats['wins'] > 0:
            stats['avg_steps'] = (stats['avg_steps'] * (stats['wins'] - 1) + steps) / stats['wins']
    else:
        stats['losses'] += 1
        stats['profit'] -= (2**steps - 1)

def update_performance_stats(result_type, steps=0, strategy_type=None):
    today = datetime.now(GMT3).strftime('%Y-%m-%d')
    week = datetime.now(GMT3).strftime('%Y-%W')
    performance_stats['total_signals'] += 1
    performance_stats['signal_history'].append({
        'timestamp': datetime.now(GMT3),
        'result': result_type,
        'steps': steps,
        'strategy_type': strategy_type
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
    
    # Strateji istatistiklerini de güncelle
    if strategy_type:
        update_strategy_stats(strategy_type, result_type, steps)

def generate_strategy_report():
    """Strateji performans raporu oluşturur"""
    report = "🎯 **STRATEJİ PERFORMANS TABLOSU** 🎯\n\n"
    
    # Başarı oranına göre sırala
    sorted_strategies = sorted(
        strategy_performance.items(),
        key=lambda x: (x[1]['wins'] / x[1]['total']) if x[1]['total'] > 0 else 0,
        reverse=True
    )
    
    for strategy, data in sorted_strategies:
        if data['total'] > 0:
            win_rate = (data['wins'] / data['total']) * 100
            avg_profit_per_signal = data['profit'] / data['total']
            
            report += f"**{strategy}**\n"
            report += f"   📊 Sinyal: {data['total']} | ✅: {data['wins']} | ❌: {data['losses']}\n"
            report += f"   🎯 Başarı: %{win_rate:.1f} | 💰 Net Kâr: {data['profit']} birim\n"
            report += f"   📈 Ort. Kazanç: {avg_profit_per_signal:.2f} | ⚡ Ort. Adım: {data['avg_steps']:.1f}\n\n"
        else:
            report += f"**{strategy}**\n"
            report += f"   📊 Henüz veri yok\n\n"
    
    # En iyi stratejiyi bul
    active_strategies = {k: v for k, v in strategy_performance.items() if v['total'] > 0}
    if active_strategies:
        best_strategy = max(active_strategies.items(), key=lambda x: x[1]['profit'])
        report += f"🏆 **EN KARLI STRATEJİ:** {best_strategy[0]}\n"
        report += f"💰 **Toplam Kâr:** {best_strategy[1]['profit']} birim\n"
        report += f"🎯 **Başarı Oranı:** %{(best_strategy[1]['wins']/best_strategy[1]['total'])*100:.1f}"
    else:
        report += "🏆 Henüz yeterli veri yok"
    
    return report

def get_smart_strategy_advice():
    """Akıllı strateji tavsiyesi oluşturur"""
    active_strategies = {k: v for k, v in strategy_performance.items() if v['total'] > 0}
    
    if not active_strategies:
        return "🤖 **AKILLI STRATEJİ TAVSİYESİ**\n\n📊 Henüz yeterli veri yok"
    
    best_profit = max(active_strategies.items(), key=lambda x: x[1]['profit'])
    best_win_rate = max(active_strategies.items(), 
                       key=lambda x: (x[1]['wins'] / x[1]['total']))
    most_stable = min(active_strategies.items(), 
                     key=lambda x: x[1]['avg_steps'] if x[1]['wins'] > 0 else 999)
    
    advice = f"""🤖 **AKILLI STRATEJİ TAVSİYESİ** 🤖

🎯 **AGRESİF OYUNCU İÇİN:**
   {best_profit[0]}
   💰 Maksimum kâr: {best_profit[1]['profit']} birim
   📈 Ortalama kazanç: {best_profit[1]['profit']/best_profit[1]['total']:.2f} birim/sinyal

🛡️ **KONSERVATİF OYUNCU İÇİN:**
   {best_win_rate[0]}
   ✅ Başarı oranı: %{(best_win_rate[1]['wins']/best_win_rate[1]['total'])*100:.1f}
   ⚡ Ortalama adım: {best_win_rate[1]['avg_steps']:.1f}

⚡ **HIZLI KAZANÇ İÇİN:**
   {most_stable[0]}
   🚀 Ortalama adım: {most_stable[1]['avg_steps']:.1f}
   ⏱️ Hızlı sonuç: daha az martingale
"""
    return advice

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
    
    report = f"""🎯 **DETAYLI PERFORMANS RAPORU** 🎯

📊 **GENEL İSTATİSTİKLER:**
• Toplam Sinyal: {performance_stats['total_signals']}
• Kazanç: {performance_stats['win_signals']} | Kayıp: {performance_stats['loss_signals']}
• Kazanç Oranı: %{win_rate:.1f}
• Toplam Kâr: {performance_stats['total_profit']} birim
• Mevcut Seri: {performance_stats['current_streak']} kazanç
• En Uzun Seri: {performance_stats['max_streak']} kazanç

📅 **GÜNLÜK RAPOR ({datetime.now(GMT3).strftime('%d.%m.%Y')}):**
• Sinyal: {daily['signals']}
• Kazanç: {daily['wins']} | Kayıp: {daily['losses']}
• Günlük Kâr: {daily['profit']} birim

📈 **HAFTALIK RAPOR:**
• Sinyal: {weekly['signals']}
• Kazanç: {weekly['wins']} | Kayıp: {weekly['losses']}
• Haftalık Kâr: {weekly['profit']} birim

🎛️ **SİSTEM BİLGİSİ:**
• Aktif Mod: {SISTEM_MODU}
• Martingale: {MAX_MARTINGALE_STEPS} seviye
• Trend Uzunluğu: {len(color_trend)}
• Aktif Takipçi: {len(martingale_trackers)}
"""
    return report

# TEST VERİSİ EKLEME FONKSİYONLARI
def add_test_signal(strategy_type, result_type, steps=0):
    """Test için sinyal ekle"""
    update_performance_stats(result_type, steps, strategy_type)
    print(f"✅ Test sinyali eklendi: {strategy_type} - {result_type} - {steps} adım")

def simulate_test_data():
    """Test verileri simüle et"""
    test_cases = [
        ("🎯 GÜÇLÜ EL", "win", 0),
        ("🎯 GÜÇLÜ EL", "win", 1),
        ("🎯 GÜÇLÜ EL", "loss", 3),
        ("🏆 DOĞAL KAZANÇ", "win", 0),
        ("🏆 DOĞAL KAZANÇ", "win", 0),
        ("📊 5+ KART", "win", 2),
        ("📊 5+ KART", "loss", 3),
        ("🚨 3x TEKRAR", "win", 1),
        ("📈 STANDART SİNYAL", "win", 0),
        ("📈 STANDART SİNYAL", "loss", 3),
        ("✅ 5-Lİ ONAY", "win", 0),
        ("🚀 SÜPER HİBRİT", "win", 1),
        ("🎯 KLASİK #C2_3", "win", 0),
        ("🎯 KLASİK #C2_3", "loss", 2),
    ]
    
    for strategy, result, steps in test_cases:
        add_test_signal(strategy, result, steps)
    
    print("✅ Test verileri eklendi!")

# ANA PROGRAM
def main():
    print("🤖 ROYAL BACCARAT STRATEJİ PERFORMANS SİSTEMİ")
    print("=============================================")
    
    while True:
        print("\n🎯 **MENÜ** 🎯")
        print("1. Strateji Performans Raporu")
        print("2. Akıllı Strateji Tavsiyesi")
        print("3. Detaylı Performans Raporu")
        print("4. Test Verileri Ekle")
        print("5. Manuel Sinyal Ekle")
        print("6. Çıkış")
        
        choice = input("\nSeçiminiz (1-6): ").strip()
        
        if choice == "1":
            print("\n" + "="*50)
            print(generate_strategy_report())
            print("="*50)
            
        elif choice == "2":
            print("\n" + "="*50)
            print(get_smart_strategy_advice())
            print("="*50)
            
        elif choice == "3":
            print("\n" + "="*50)
            print(generate_performance_report())
            print("="*50)
            
        elif choice == "4":
            simulate_test_data()
            
        elif choice == "5":
            print("\n🎯 Manuel Sinyal Ekleme")
            print("Mevcut Stratejiler:")
            for i, strategy in enumerate(strategy_performance.keys(), 1):
                print(f"{i}. {strategy}")
            
            try:
                strat_choice = int(input("Strateji numarası: ")) - 1
                strategy_list = list(strategy_performance.keys())
                if 0 <= strat_choice < len(strategy_list):
                    strategy_type = strategy_list[strat_choice]
                    result = input("Sonuç (win/loss): ").strip().lower()
                    steps = int(input("Adım sayısı (0-3): "))
                    
                    if result in ['win', 'loss'] and 0 <= steps <= 3:
                        add_test_signal(strategy_type, result, steps)
                        print("✅ Sinyal başarıyla eklendi!")
                    else:
                        print("❌ Geçersiz sonuç veya adım sayısı!")
                else:
                    print("❌ Geçersiz strateji numarası!")
            except ValueError:
                print("❌ Geçersiz giriş!")
                
        elif choice == "6":
            print("👋 Çıkış yapılıyor...")
            break
            
        else:
            print("❌ Geçersiz seçim!")

if __name__ == '__main__':
    main()