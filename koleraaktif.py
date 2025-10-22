# -*- coding: utf-8 -*-
import re, json, os, asyncio, sys, pytz
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
from collections import defaultdict, deque
import pandas as pd
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font

API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
BOT_TOKEN = ''  # 🔑 Buraya bot tokenınızı yazın
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"  # 📢 Hedef kanal
ADMIN_ID = 1136442929  # 👑 Admin ID
SISTEM_MODU = "normal_hibrit"
GMT3 = pytz.timezone('Europe/Istanbul')
client = TelegramClient('kolera_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

game_results, martingale_trackers, color_trend, recent_games = {}, {}, [], []
MAX_MARTINGALE_STEPS, MAX_GAME_NUMBER, is_signal_active, daily_signal_count = 3, 1440, False, 0

# Excel dosyası için renk tanımlamaları
EXCEL_FILE = "royal_baccarat_data.xlsx"
RED_FILL = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
BLUE_FILL = PatternFill(start_color="0000FF", end_color="0000FF", fill_type="solid")
GREEN_FILL = PatternFill(start_color="00FF00", end_color="00FF00", fill_type="solid")
BLACK_FILL = PatternFill(start_color="000000", end_color="000000", fill_type="solid")

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

# Excel dosyasını başlat
def init_excel_file():
    try:
        if not os.path.exists(EXCEL_FILE):
            wb = Workbook()
            ws = wb.active
            ws.title = "Baccarat Data"
            
            # Başlıkları oluştur
            headers = [
                "Oyun No", "Tarih", "Saat", "Player Kartları", "Banker Kartları", 
                "Player Toplam", "Banker Toplam", "Kazanan", "C2 Tipi", "Renk Tahmini",
                "Pattern Tipi", "Sinyal Seviyesi", "Sonuç", "Kazanç/Kayıp", "Toplam Kâr"
            ]
            
            for col, header in enumerate(headers, 1):
                ws.cell(row=1, column=col, value=header).font = Font(bold=True)
            
            wb.save(EXCEL_FILE)
            print(f"✅ Excel dosyası oluşturuldu: {EXCEL_FILE}")
        else:
            print(f"✅ Excel dosyası zaten mevcut: {EXCEL_FILE}")
    except Exception as e:
        print(f"❌ Excel dosyası oluşturma hatası: {e}")

# Excel'e veri kaydet
def save_to_excel(game_data):
    try:
        wb = openpyxl.load_workbook(EXCEL_FILE)
        ws = wb.active
        
        # Yeni satır ekle
        row = ws.max_row + 1
        
        # Verileri yaz
        ws.cell(row=row, column=1, value=game_data.get('game_number'))
        ws.cell(row=row, column=2, value=game_data.get('date'))
        ws.cell(row=row, column=3, value=game_data.get('time'))
        ws.cell(row=row, column=4, value=game_data.get('player_cards'))
        ws.cell(row=row, column=5, value=game_data.get('banker_cards'))
        ws.cell(row=row, column=6, value=game_data.get('player_total'))
        ws.cell(row=row, column=7, value=game_data.get('banker_total'))
        ws.cell(row=row, column=8, value=game_data.get('winner'))
        ws.cell(row=row, column=9, value=game_data.get('c2_type'))
        
        # Renk tahmini hücresini renklendir
        color_cell = ws.cell(row=row, column=10, value=game_data.get('color_prediction'))
        color_pred = game_data.get('color_prediction', '')
        if '🔴' in color_pred or 'MAÇA' in color_pred:
            color_cell.fill = RED_FILL
            color_cell.value = "🔴 MAÇA"
        elif '🔵' in color_pred or 'KALP' in color_pred:
            color_cell.fill = BLUE_FILL  
            color_cell.value = "🔵 KALP"
        elif '🟢' in color_pred or 'KARO' in color_pred:
            color_cell.fill = GREEN_FILL
            color_cell.value = "🟢 KARO"
        elif '⚫' in color_pred or 'SİNEK' in color_pred:
            color_cell.fill = BLACK_FILL
            color_cell.value = "⚫ SİNEK"
        
        ws.cell(row=row, column=11, value=game_data.get('pattern_type'))
        ws.cell(row=row, column=12, value=game_data.get('signal_level'))
        
        # Sonuç hücresini renklendir
        result_cell = ws.cell(row=row, column=13, value=game_data.get('result'))
        if game_data.get('result') == 'KAZANÇ':
            result_cell.fill = GREEN_FILL
        elif game_data.get('result') == 'KAYIP':
            result_cell.fill = RED_FILL
            
        ws.cell(row=row, column=14, value=game_data.get('profit_loss'))
        ws.cell(row=row, column=15, value=game_data.get('total_profit'))
        
        wb.save(EXCEL_FILE)
        print(f"✅ Excel'e kaydedildi: #{game_data.get('game_number')}")
        
    except Exception as e:
        print(f"❌ Excel kaydetme hatası: {e}")

# Excel'den C2 tipi analizi yapan gelişmiş fonksiyonlar
def analyze_c2_from_excel():
    """Excel'deki C2 tiplerini detaylı analiz eder"""
    try:
        if not os.path.exists(EXCEL_FILE):
            return "❌ Excel dosyası bulunamadı"
        
        wb = openpyxl.load_workbook(EXCEL_FILE)
        ws = wb.active
        
        if ws.max_row <= 1:
            return "📊 Excel'de henüz veri yok"
        
        # C2 tipi istatistikleri
        c2_stats = {}
        c2_color_stats = {}
        c2_time_stats = {}
        
        for row in range(2, ws.max_row + 1):
            c2_type = ws.cell(row=row, column=9).value  # C2 tipi
            result = ws.cell(row=row, column=13).value  # Sonuç
            color_pred = ws.cell(row=row, column=10).value  # Renk tahmini
            time_str = ws.cell(row=row, column=3).value  # Saat
            
            if c2_type and c2_type != 'N/A':
                # C2 tipi istatistikleri
                if c2_type not in c2_stats:
                    c2_stats[c2_type] = {'total': 0, 'wins': 0, 'profit': 0}
                
                c2_stats[c2_type]['total'] += 1
                if result == 'KAZANÇ':
                    c2_stats[c2_type]['wins'] += 1
                    c2_stats[c2_type]['profit'] += 1
                elif result == 'KAYIP':
                    c2_stats[c2_type]['profit'] -= 1
                
                # C2 tipine göre renk başarısı
                if c2_type not in c2_color_stats:
                    c2_color_stats[c2_type] = {}
                
                if color_pred:
                    for color in ['🔴', '🔵', '🟢', '⚫']:
                        if color in str(color_pred):
                            if color not in c2_color_stats[c2_type]:
                                c2_color_stats[c2_type][color] = {'total': 0, 'wins': 0}
                            
                            c2_color_stats[c2_type][color]['total'] += 1
                            if result == 'KAZANÇ':
                                c2_color_stats[c2_type][color]['wins'] += 1
                            break
                
                # Zaman bazlı analiz
                if time_str:
                    hour = int(time_str.split(':')[0])
                    time_slot = get_time_slot(hour)
                    
                    if c2_type not in c2_time_stats:
                        c2_time_stats[c2_type] = {}
                    
                    if time_slot not in c2_time_stats[c2_type]:
                        c2_time_stats[c2_type][time_slot] = {'total': 0, 'wins': 0}
                    
                    c2_time_stats[c2_type][time_slot]['total'] += 1
                    if result == 'KAZANÇ':
                        c2_time_stats[c2_type][time_slot]['wins'] += 1
        
        return generate_c2_excel_analysis(c2_stats, c2_color_stats, c2_time_stats)
        
    except Exception as e:
        return f"❌ C2 Excel analiz hatası: {e}"

def get_time_slot(hour):
    """Saat dilimine göre zaman slotu belirler"""
    if 6 <= hour < 12:
        return "⛅ SABAH (06-12)"
    elif 12 <= hour < 18:
        return "☀️ ÖĞLEN (12-18)"
    elif 18 <= hour < 24:
        return "🌙 AKŞAM (18-24)"
    else:
        return "🌜 GECE (00-06)"

def generate_c2_excel_analysis(c2_stats, c2_color_stats, c2_time_stats):
    """C2 analiz raporu oluşturur"""
    if not c2_stats:
        return "📊 C2 verisi bulunamadı"
    
    analysis = "🎯 **EXCEL C2 TİP ANALİZİ** 🎯\n\n"
    
    # C2 tipi performansı
    analysis += "📈 **C2 TİP PERFORMANSI:**\n"
    sorted_c2 = sorted(c2_stats.items(), 
                      key=lambda x: (x[1]['wins']/x[1]['total']) if x[1]['total'] > 0 else 0, 
                      reverse=True)
    
    for c2_type, stats in sorted_c2:
        if stats['total'] > 0:
            win_rate = (stats['wins'] / stats['total']) * 100
            analysis += f"• {c2_type}: %{win_rate:.1f} ({stats['wins']}/{stats['total']}) | 💰 {stats['profit']} birim\n"
    
    analysis += "\n🎨 **C2 TİPİNE GÖRE RENK BAŞARISI:**\n"
    
    for c2_type, color_data in c2_color_stats.items():
        if color_data:
            analysis += f"\n{c2_type}:\n"
            for color, c_stats in color_data.items():
                if c_stats['total'] > 0:
                    color_win_rate = (c_stats['wins'] / c_stats['total']) * 100
                    analysis += f"  {color}: %{color_win_rate:.1f} ({c_stats['wins']}/{c_stats['total']})\n"
    
    analysis += "\n⏰ **ZAMAN BAZLI C2 PERFORMANSI:**\n"
    
    for c2_type, time_data in c2_time_stats.items():
        if time_data:
            analysis += f"\n{c2_type}:\n"
            best_slot = None
            best_rate = 0
            
            for time_slot, t_stats in time_data.items():
                if t_stats['total'] > 0:
                    time_win_rate = (t_stats['wins'] / t_stats['total']) * 100
                    analysis += f"  {time_slot}: %{time_win_rate:.1f} ({t_stats['wins']}/{t_stats['total']})\n"
                    
                    if time_win_rate > best_rate and t_stats['total'] >= 3:
                        best_rate = time_win_rate
                        best_slot = time_slot
            
            if best_slot:
                analysis += f"  ✅ EN İYİ: {best_slot} (%{best_rate:.1f})\n"
    
    # Tavsiyeler
    analysis += "\n💡 **EXCEL VERİLERİNE GÖRE TAVSİYELER:**\n"
    
    if sorted_c2:
        best_c2 = sorted_c2[0]
        worst_c2 = sorted_c2[-1]
        
        best_c2_type, best_stats = best_c2
        worst_c2_type, worst_stats = worst_c2
        
        best_win_rate = (best_stats['wins'] / best_stats['total']) * 100 if best_stats['total'] > 0 else 0
        worst_win_rate = (worst_stats['wins'] / worst_stats['total']) * 100 if worst_stats['total'] > 0 else 0
        
        analysis += f"✅ **TERCIH ET:** {best_c2_type} (%{best_win_rate:.1f} başarı)\n"
        analysis += f"⚠️ **DİKKAT ET:** {worst_c2_type} (%{worst_win_rate:.1f} başarı)\n"
        
        # En iyi C2 tipi için renk tavsiyesi
        if best_c2_type in c2_color_stats:
            best_colors = c2_color_stats[best_c2_type]
            if best_colors:
                best_color = max(best_colors.items(), 
                               key=lambda x: (x[1]['wins']/x[1]['total']) if x[1]['total'] > 0 else 0)
                color_name = best_color[0]
                color_stats = best_color[1]
                color_win_rate = (color_stats['wins'] / color_stats['total']) * 100 if color_stats['total'] > 0 else 0
                analysis += f"🎨 **RENK TAVSİYESİ:** {best_c2_type} için {color_name} (%{color_win_rate:.1f})\n"
        
        # Zaman tavsiyesi
        if best_c2_type in c2_time_stats:
            best_times = c2_time_stats[best_c2_type]
            if best_times:
                best_time = max(best_times.items(), 
                              key=lambda x: (x[1]['wins']/x[1]['total']) if x[1]['total'] > 0 else 0)
                time_slot = best_time[0]
                time_stats = best_time[1]
                time_win_rate = (time_stats['wins'] / time_stats['total']) * 100 if time_stats['total'] > 0 else 0
                analysis += f"⏰ **ZAMAN TAVSİYESİ:** {best_c2_type} için {time_slot} (%{time_win_rate:.1f})\n"
    
    return analysis

def get_c2_recommendation_from_excel():
    """Excel verilerine göre anlık C2 tavsiyesi verir"""
    try:
        if not os.path.exists(EXCEL_FILE):
            return "#C2_3", "Excel dosyası bulunamadı"
        
        wb = openpyxl.load_workbook(EXCEL_FILE)
        ws = wb.active
        
        if ws.max_row <= 10:
            return "#C2_3", "Yeterli veri yok, varsayılan kullanılıyor"
        
        # Son 30 oyunu analiz et
        recent_games = min(30, ws.max_row - 1)
        c2_recent_stats = {}
        
        for row in range(ws.max_row - recent_games + 1, ws.max_row + 1):
            c2_type = ws.cell(row=row, column=9).value
            result = ws.cell(row=row, column=13).value
            
            if c2_type and c2_type != 'N/A':
                if c2_type not in c2_recent_stats:
                    c2_recent_stats[c2_type] = {'total': 0, 'wins': 0}
                
                c2_recent_stats[c2_type]['total'] += 1
                if result == 'KAZANÇ':
                    c2_recent_stats[c2_type]['wins'] += 1
        
        if not c2_recent_stats:
            return "#C2_3", "C2 verisi yok, varsayılan kullanılıyor"
        
        # En başarılı C2 tipini bul
        best_c2 = max(c2_recent_stats.items(), 
                     key=lambda x: (x[1]['wins']/x[1]['total']) if x[1]['total'] > 0 else 0)
        
        c2_type, stats = best_c2
        win_rate = (stats['wins'] / stats['total']) * 100 if stats['total'] > 0 else 0
        
        reason = f"Son {recent_games} oyunda %{win_rate:.1f} başarı"
        
        return c2_type, reason
        
    except Exception as e:
        print(f"❌ C2 tavsiye hatası: {e}")
        return "#C2_3", f"Hata: {e}"

def predict_color_by_c2_excel(c2_type, player_cards):
    """Excel verilerine göre C2 tipi bazlı renk tahmini"""
    try:
        if not os.path.exists(EXCEL_FILE):
            return predict_color_by_c2_type(c2_type, player_cards)
        
        wb = openpyxl.load_workbook(EXCEL_FILE)
        ws = wb.active
        
        if ws.max_row <= 5:
            return predict_color_by_c2_type(c2_type, player_cards)
        
        # Bu C2 tipi için Excel'deki renk başarısını bul
        c2_color_stats = {}
        
        for row in range(2, ws.max_row + 1):
            row_c2_type = ws.cell(row=row, column=9).value
            color_pred = ws.cell(row=row, column=10).value
            result = ws.cell(row=row, column=13).value
            
            if row_c2_type == c2_type and color_pred and result in ['KAZANÇ', 'KAYIP']:
                for color in ['🔴', '🔵', '🟢', '⚫']:
                    if color in str(color_pred):
                        if color not in c2_color_stats:
                            c2_color_stats[color] = {'total': 0, 'wins': 0}
                        
                        c2_color_stats[color]['total'] += 1
                        if result == 'KAZANÇ':
                            c2_color_stats[color]['wins'] += 1
                        break
        
        # Excel'de bu C2 tipi için veri varsa, en başarılı rengi kullan
        if c2_color_stats:
            best_color = max(c2_color_stats.items(), 
                           key=lambda x: (x[1]['wins']/x[1]['total']) if x[1]['total'] > 0 else 0)
            
            color_emoji = best_color[0]
            color_stats = best_color[1]
            win_rate = (color_stats['wins'] / color_stats['total']) * 100 if color_stats['total'] > 0 else 0
            
            base_color = extract_largest_value_suit(player_cards)
            suit_display = get_suit_display_name(base_color) if base_color else "MAÇA"
            
            return f"{color_emoji} {suit_display}", f"Excel C2 Optimize: %{win_rate:.1f} başarı"
        
        # Excel verisi yoksa normal tahmin
        return predict_color_by_c2_type(c2_type, player_cards)
        
    except Exception as e:
        print(f"❌ Excel C2 renk tahmin hatası: {e}")
        return predict_color_by_c2_type(c2_type, player_cards)

# Renk oyunu tahmini fonksiyonu
def predict_color_game(player_cards, banker_cards, game_number):
    try:
        # Kart değerlerini analiz et
        player_values = [get_baccarat_value(card[0]) for card in re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)]
        banker_values = [get_baccarat_value(card[0]) for card in re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)]
        
        player_total = sum(player_values) % 10
        banker_total = sum(banker_values) % 10
        
        # Renk dağılımını analiz et
        player_suits = [card[1] for card in re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)]
        banker_suits = [card[1] for card in re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)]
        all_suits = player_suits + banker_suits
        
        suit_counts = {
            '♠': all_suits.count('♠'),
            '♥': all_suits.count('♥'),
            '♦': all_suits.count('♦'), 
            '♣': all_suits.count('♣')
        }
        
        # En çok görülen rengi bul
        most_common_suit = max(suit_counts, key=suit_counts.get)
        suit_display = get_suit_display_name(most_common_suit)
        
        # Oyun sonucuna göre tahmin yap
        if player_total > banker_total:
            return f"🔴 {suit_display}", "PLAYER kazandı - KIRMIZI önerilir"
        elif banker_total > player_total:
            return f"🔵 {suit_display}", "BANKER kazandı - MAVİ önerilir"
        else:
            return f"🟢 {suit_display}", "BERABERE - YEŞİL önerilir"
            
    except Exception as e:
        print(f"❌ Renk oyunu tahmin hatası: {e}")
        return "🔴 MAÇA", "Varsayılan tahmin"

# C2 tipine göre renk tahmini
def predict_color_by_c2_type(c2_type, player_cards):
    try:
        base_color = extract_largest_value_suit(player_cards)
        if not base_color:
            return "🔴 MAÇA", "Varsayılan"
            
        suit_display = get_suit_display_name(base_color)
        
        # C2 tipine göre özel tahminler
        if c2_type == '#C2_3':
            return f"🔴 {suit_display}", "KLASİK C2_3 - KIRMIZI agresif"
        elif c2_type == '#C2_2':
            return f"🔵 {suit_display}", "ALTERNATİF C2_2 - MAVİ dengeli"
        elif c2_type == '#C3_2':
            return f"🟢 {suit_display}", "VARYANT C3_2 - YEŞIL riskli"
        elif c2_type == '#C3_3':
            return f"🟡 {suit_display}", "ÖZEL C3_3 - SARI özel"
        else:
            return f"🔴 {suit_display}", "Varsayılan tahmin"
            
    except Exception as e:
        print(f"❌ C2 tipi tahmin hatası: {e}")
        return "🔴 MAÇA", "Hata"

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

# Oyun sonucunu Excel'e kaydetmek için fonksiyon
async def save_game_result_to_excel(game_info, signal_info=None, result_type=None):
    try:
        # Oyun bilgilerini hazırla
        player_cards = game_info['player_cards']
        banker_cards = game_info['banker_cards']
        
        # Kart değerlerini hesapla
        player_values = [get_baccarat_value(card[0]) for card in re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)]
        banker_values = [get_baccarat_value(card[0]) for card in re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)]
        
        player_total = sum(player_values) % 10
        banker_total = sum(banker_values) % 10
        
        # Kazananı belirle
        if player_total > banker_total:
            winner = "PLAYER"
        elif banker_total > player_total:
            winner = "BANKER"
        else:
            winner = "TIE"
        
        # Gelişmiş renk tahminleri
        recommended_c2, c2_reason = get_c2_recommendation_from_excel()
        smart_color, smart_reason = predict_color_by_c2_excel(recommended_c2, player_cards)
        normal_color, normal_reason = predict_color_game(player_cards, banker_cards, game_info['game_number'])
        
        # Excel verisini oluştur
        excel_data = {
            'game_number': game_info['game_number'],
            'date': datetime.now(GMT3).strftime('%Y-%m-%d'),
            'time': datetime.now(GMT3).strftime('%H:%M:%S'),
            'player_cards': player_cards,
            'banker_cards': banker_cards,
            'player_total': player_total,
            'banker_total': banker_total,
            'winner': winner,
            'c2_type': game_info.get('c2_3_type', 'N/A'),
            'color_prediction': f"{smart_color} | {normal_color}",
            'pattern_type': signal_info.get('reason', 'N/A') if signal_info else 'N/A',
            'signal_level': signal_info.get('step', 0) if signal_info else 0,
            'result': result_type if result_type else 'BEKLİYOR',
            'profit_loss': 1 if result_type == 'KAZANÇ' else -1 if result_type == 'KAYIP' else 0,
            'total_profit': performance_stats['total_profit']
        }
        
        # Excel'e kaydet
        save_to_excel(excel_data)
        
        # Gelişmiş analizleri konsola yazdır
        print(f"🎯 Akıllı Tahmin: {smart_color} - {smart_reason}")
        print(f"📊 Önerilen C2: {recommended_c2} - {c2_reason}")
        
    except Exception as e:
        print(f"❌ Excel kayıt hatası: {e}")

# Excel'den veri okuyup analiz yapan fonksiyonlar
def analyze_excel_data():
    """Excel'deki geçmiş verileri analiz eder"""
    try:
        if not os.path.exists(EXCEL_FILE):
            return "❌ Excel dosyası bulunamadı"
        
        wb = openpyxl.load_workbook(EXCEL_FILE)
        ws = wb.active
        
        if ws.max_row <= 1:
            return "📊 Excel'de henüz veri yok"
        
        # İstatistikleri hesapla
        total_games = ws.max_row - 1
        wins = 0
        losses = 0
        color_predictions = []
        c2_types = []
        
        for row in range(2, ws.max_row + 1):
            result = ws.cell(row=row, column=13).value  # Sonuç sütunu
            color_pred = ws.cell(row=row, column=10).value  # Renk tahmini
            c2_type = ws.cell(row=row, column=9).value  # C2 tipi
            
            if result == 'KAZANÇ':
                wins += 1
            elif result == 'KAYIP':
                losses += 1
                
            if color_pred:
                color_predictions.append(color_pred)
            if c2_type and c2_type != 'N/A':
                c2_types.append(c2_type)
        
        # Renk tahmini başarısını analiz et
        color_success = analyze_color_predictions(ws)
        
        # C2 tipi başarısını analiz et
        c2_success = analyze_c2_performance(ws)
        
        win_rate = (wins / total_games * 100) if total_games > 0 else 0
        
        analysis = f"""📈 **EXCEL VERİ ANALİZİ** 📈

🎯 **GENEL İSTATİSTİKLER:**
• Toplam Oyun: {total_games}
• Kazanç: {wins} | Kayıp: {losses}
• Başarı Oranı: %{win_rate:.1f}

{color_success}

{c2_success}

💡 **TAVSİYELER:**
{generate_recommendations(ws)}
"""
        return analysis
        
    except Exception as e:
        return f"❌ Excel analiz hatası: {e}"

def analyze_color_predictions(worksheet):
    """Renk tahminlerinin başarısını analiz eder"""
    try:
        color_stats = {
            '🔴 MAÇA': {'total': 0, 'correct': 0},
            '🔵 KALP': {'total': 0, 'correct': 0},
            '🟢 KARO': {'total': 0, 'correct': 0},
            '⚫ SİNEK': {'total': 0, 'correct': 0}
        }
        
        for row in range(2, worksheet.max_row + 1):
            color_pred = worksheet.cell(row=row, column=10).value
            result = worksheet.cell(row=row, column=13).value
            winner = worksheet.cell(row=row, column=8).value
            
            if color_pred and result in ['KAZANÇ', 'KAYIP']:
                # Renk tahminini ve sonucu eşleştir
                for color in color_stats.keys():
                    if color in str(color_pred):
                        color_stats[color]['total'] += 1
                        # Basit bir doğruluk kontrolü (gerçek oyun mantığına göre geliştirilebilir)
                        if result == 'KAZANÇ':
                            color_stats[color]['correct'] += 1
                        break
        
        analysis = "🎨 **RENK TAHMİN PERFORMANSI:**\n"
        for color, stats in color_stats.items():
            if stats['total'] > 0:
                success_rate = (stats['correct'] / stats['total']) * 100
                analysis += f"• {color}: %{success_rate:.1f} ({stats['correct']}/{stats['total']})\n"
            else:
                analysis += f"• {color}: Veri yok\n"
                
        return analysis
    except Exception as e:
        return f"❌ Renk analiz hatası: {e}"

def analyze_c2_performance(worksheet):
    """C2 tiplerinin performansını analiz eder"""
    try:
        c2_stats = {}
        
        for row in range(2, worksheet.max_row + 1):
            c2_type = worksheet.cell(row=row, column=9).value
            result = worksheet.cell(row=row, column=13).value
            
            if c2_type and c2_type != 'N/A':
                if c2_type not in c2_stats:
                    c2_stats[c2_type] = {'total': 0, 'wins': 0}
                
                c2_stats[c2_type]['total'] += 1
                if result == 'KAZANÇ':
                    c2_stats[c2_type]['wins'] += 1
        
        analysis = "🎯 **C2 TİP PERFORMANSI:**\n"
        for c2_type, stats in c2_stats.items():
            if stats['total'] > 0:
                win_rate = (stats['wins'] / stats['total']) * 100
                analysis += f"• {c2_type}: %{win_rate:.1f} ({stats['wins']}/{stats['total']})\n"
        
        return analysis if c2_stats else "• C2 verisi bulunamadı\n"
    except Exception as e:
        return f"❌ C2 analiz hatası: {e}"

def generate_recommendations(worksheet):
    """Excel verilerine göre tavsiyeler üretir"""
    try:
        recommendations = []
        
        # Son 20 oyunu analiz et
        recent_games = min(20, worksheet.max_row - 1)
        recent_wins = 0
        recent_losses = 0
        
        for row in range(worksheet.max_row - recent_games + 1, worksheet.max_row + 1):
            result = worksheet.cell(row=row, column=13).value
            if result == 'KAZANÇ':
                recent_wins += 1
            elif result == 'KAYIP':
                recent_losses += 1
        
        recent_win_rate = (recent_wins / recent_games * 100) if recent_games > 0 else 0
        
        # Tavsiyeler
        if recent_win_rate >= 70:
            recommendations.append("✅ Yüksek başarı! Mevcut stratejiye devam edin")
        elif recent_win_rate <= 40:
            recommendations.append("⚠️ Düşük başarı! Strateji değişikliği gerekebilir")
        else:
            recommendations.append("📊 Orta seviye başarı, dikkatli ilerleyin")
            
        # Renk trend analizi
        color_trends = []
        for row in range(max(2, worksheet.max_row - 9), worksheet.max_row + 1):
            color_pred = worksheet.cell(row=row, column=10).value
            if color_pred:
                color_trends.append(color_pred)
        
        if color_trends:
            dominant_color = max(set(color_trends), key=color_trends.count)
            recommendations.append(f"🎯 Son trend: {dominant_color} ağırlıklı")
        
        return "\n".join(recommendations)
        
    except Exception as e:
        return f"❌ Tavsiye oluşturma hatası: {e}"

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

def besli_onay_sistemi(player_cards, banker_cards, game_number):
    onaylar = []
    temel_renk = extract_largest_value_suit(player_cards)
    if temel_renk: 
        onaylar.append(("C2_3", temel_renk))
        print(f"✅ C2_3 onay: {temel_renk}")
    pattern_renk, pattern_sebep = analyze_simple_pattern(player_cards, banker_cards, game_number)
    if pattern_renk and "STANDART" not in pattern_sebep:
        onaylar.append(("PATTERN", pattern_renk))
        print(f"✅ Pattern onay: {pattern_renk} - {pattern_sebep}")
    if color_trend:
        trend_renk = color_trend[-1] if color_trend else None
        if trend_renk: onaylar.append(("TREND", trend_renk))
    if len(color_trend) >= 3:
        son_uc = color_trend[-3:]
        if son_uc.count(temel_renk) >= 2: onaylar.append(("REPEAT", temel_renk))
    renk_oyları = {}
    for yontem, renk in onaylar: renk_oyları[renk] = renk_oyları.get(renk, 0) + 1
    if renk_oyları:
        kazanan_renk = max(renk_oyları, key=renk_oyları.get)
        oy_sayisi = renk_oyları[kazanan_renk]
        güven = oy_sayisi / 5
        print(f"📊 5'li onay: {kazanan_renk} - {oy_sayisi}/5 - %{güven*100:.1f}")
        if oy_sayisi >= 3 and güven >= 0.6: return kazanan_renk, f"✅ 5-Lİ ONAY ({oy_sayisi}/5) - %{güven*100:.1f}"
    return None, "❌ 5'li onay sağlanamadı"

def super_filtre_kontrol(signal_color, reason, game_number):
    if len(color_trend) >= 5:
        if color_trend[-5:].count(signal_color) == 0: return False, "❌ SOĞUK TREND"
    if len(recent_games) >= 3:
        son_kayiplar = sum(1 for oyun in recent_games[-3:] if not oyun.get('kazanç', True))
        if son_kayiplar >= 2: return False, "🎯 ARDIŞIK KAYIPLAR"
    return True, "✅ TÜM FİLTRELER GEÇTİ"

def super_risk_analizi():
    risk_puan, uyarılar = 0, []
    if len(color_trend) >= 5:
        son_5 = color_trend[-5:]
        if len(set(son_5)) == 1: risk_puan, uyarılar = risk_puan + 30, uyarılar + ["🚨 5x AYNI RENK"]
    if risk_puan >= 30: return "🔴 YÜKSEK RİSK", uyarılar
    elif risk_puan >= 20: return "🟡 ORTA RİSK", uyarılar
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

# QUANTUM HİBRİT SİSTEMİ
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

async def quantum_hibrit_sistemi(game_info):
    print("🎯 QUANTUM HİBRİT analiz başlıyor...")
    
    pattern_sonuclari = []
    
    signal_color1, reason1 = analyze_simple_pattern(game_info['player_cards'], 
                                                   game_info['banker_cards'], 
                                                   game_info['game_number'])
    if signal_color1 and "STANDART" not in reason1:
        pattern_sonuclari.append((signal_color1, reason1, "ANA", 1.0))
    
    quantum_renk, quantum_sebep = quantum_pattern_analizi(game_info)
    if quantum_renk:
        pattern_sonuclari.append((quantum_renk, quantum_sebep, "QUANTUM", 0.9))
    
    trend_renk, trend_sebep = quantum_trend_analizi()
    if trend_renk:
        pattern_sonuclari.append((trend_renk, trend_sebep, "TREND", 0.8))
    
    kart_renk, kart_sebep = quantum_kart_analizi(game_info)
    if kart_renk:
        pattern_sonuclari.append((kart_renk, kart_sebep, "KART", 0.7))
    
    if len(pattern_sonuclari) < 2:
        print(f"🚫 Quantum: Yetersiz pattern çeşitliliği ({len(pattern_sonuclari)}/4)")
        return
    
    renk_agirliklari = {}
    
    for renk, sebep, tip, agirlik in pattern_sonuclari:
        pattern_data = pattern_stats.get(sebep, {'total': 0, 'wins': 0})
        if pattern_data['total'] > 0:
            basari_orani = pattern_data['wins'] / pattern_data['total']
            if basari_orani >= 0.8:
                agirlik *= 1.3
            elif basari_orani >= 0.7:
                agirlik *= 1.1
        
        renk_agirliklari[renk] = renk_agirliklari.get(renk, 0) + agirlik
    
    kazanan_renk = max(renk_agirliklari, key=renk_agirliklari.get)
    toplam_agirlik = renk_agirliklari[kazanan_renk]
    
    filtre_sonuclari = []
    
    elite_patternler = ['🏆 DOĞAL KAZANÇ', '🚀 SÜPER HİBRİT', '✅ 5-Lİ ONAY', '🎯 GÜÇLÜ EL']
    pattern_kalite = any(sebep in elite_patternler for _, sebep, _, _ in pattern_sonuclari)
    filtre_sonuclari.append(pattern_kalite)
    
    if len(color_trend) >= 6:
        son_6 = color_trend[-6:]
        trend_destek = son_6.count(kazanan_renk) >= 2
        filtre_sonuclari.append(trend_destek)
    else:
        filtre_sonuclari.append(True)
    
    daily = get_daily_stats()
    performans_uygun = daily['profit'] >= -8
    filtre_sonuclari.append(performans_uygun)
    
    risk_seviye, _ = super_risk_analizi()
    risk_uygun = risk_seviye != "🔴 YÜKSEK RİSK"
    filtre_sonuclari.append(risk_uygun)
    
    pattern_cesitlilik = len(set([sebep for _, sebep, _, _ in pattern_sonuclari])) >= 2
    filtre_sonuclari.append(pattern_cesitlilik)
    
    agirlik_uygun = toplam_agirlik >= 2.5
    filtre_sonuclari.append(agirlik_uygun)
    
    filtre_gecen = sum(filtre_sonuclari)
    
    if filtre_gecen < 5:
        print(f"🚫 Quantum: Yetersiz filtre geçişi ({filtre_gecen}/6)")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    sebep_metin = " + ".join([f"{sebep}" for _, sebep, _, _ in pattern_sonuclari if _ == kazanan_renk])
    
    await send_new_signal(next_game_num, kazanan_renk, 
                         f"⚛️ QUANTUM HİBRİT - {sebep_metin} | Ağırlık:{toplam_agirlik:.1f}", game_info)

# QUANTUM PRO SİSTEMİ
def elite_trend_analizi():
    if len(color_trend) < 12:
        return None, None
    
    son_12 = color_trend[-12:]
    renk_frekans = {renk: son_12.count(renk) for renk in set(son_12)}
    
    for renk, sayi in renk_frekans.items():
        if sayi >= 8:
            return renk, f"👑 ELITE DOMINANCE ({sayi}/12)"
    
    if len(set(son_12[-5:])) == 1:
        return son_12[-1], "🔥 TREND MASTER 5x"
    
    if len(renk_frekans) <= 3:
        dominant_renk = max(renk_frekans, key=renk_frekans.get)
        return dominant_renk, "📈 İSTİKRARLI TREND"
    
    return None, None

def kart_deger_analizi(game_info):
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
    
    if player_toplam in [8, 9] and len(player_kartlar) <= 2:
        return renk, "💎 SAF DOĞAL KAZANÇ"
    
    if player_toplam >= 7 and banker_toplam <= 3:
        return renk, "🎯 YÜKSEK AVANTAJ"
    
    if sum(player_degerler) >= 15 and len(player_kartlar) >= 3:
        return renk, "🃏 GÜÇLÜ 3+KART"
    
    return None, None

def pattern_zincir_analizi():
    if len(performance_stats['signal_history']) < 4:
        return None, None
    
    son_sinyaller = list(performance_stats['signal_history'])[-4:]
    son_patternler = [s.get('pattern_type') for s in son_sinyaller if s.get('pattern_type')]
    
    if len(son_patternler) < 3:
        return None, None
    
    pattern_frekans = {}
    for pattern in son_patternler:
        pattern_frekans[pattern] = pattern_frekans.get(pattern, 0) + 1
    
    for pattern, sayi in pattern_frekans.items():
        if sayi >= 3:
            renk_trendleri = []
            for sinyal in son_sinyaller:
                if sinyal.get('pattern_type') == pattern:
                    for tracker in martingale_trackers.values():
                        if tracker.get('c2_3_description') in pattern:
                            renk_trendleri.append(tracker.get('signal_suit'))
                            break
            
            if renk_trendleri:
                dominant_renk = max(set(renk_trendleri), key=renk_trendleri.count)
                return dominant_renk, f"🔗 ZINCIR {pattern}"
    
    return None, None

def performans_bazli_analiz(game_info):
    daily = get_daily_stats()
    if daily['signals'] == 0:
        return None, None
    
    daily_win_rate = daily['wins'] / daily['signals']
    
    if daily_win_rate >= 0.8 and daily['signals'] >= 3:
        signal_color, reason = analyze_simple_pattern(game_info['player_cards'], 
                                                     game_info['banker_cards'], 
                                                     game_info['game_number'])
        if signal_color and "STANDART" not in reason:
            return signal_color, f"📈 PERFORMANS MOD ({daily_win_rate*100:.0f}%)"
    
    return None, None

async def quantum_pro_sistemi(game_info):
    print("🚀 QUANTUM PRO analiz başlıyor...")
    
    pattern_sonuclari = []
    
    signal_color1, reason1 = analyze_simple_pattern(game_info['player_cards'], 
                                                   game_info['banker_cards'], 
                                                   game_info['game_number'])
    if signal_color1 and "STANDART" not in reason1:
        pattern_sonuclari.append((signal_color1, reason1, "ANA", 1.2))
    
    quantum_renk, quantum_sebep = quantum_pattern_analizi(game_info)
    if quantum_renk:
        pattern_sonuclari.append((quantum_renk, quantum_sebep, "QUANTUM", 1.1))
    
    elite_renk, elite_sebep = elite_trend_analizi()
    if elite_renk:
        pattern_sonuclari.append((elite_renk, elite_sebep, "ELITE_TREND", 1.3))
    
    kart_renk, kart_sebep = kart_deger_analizi(game_info)
    if kart_renk:
        pattern_sonuclari.append((kart_renk, kart_sebep, "KART_DEGER", 1.0))
    
    zincir_renk, zincir_sebep = pattern_zincir_analizi()
    if zincir_renk:
        pattern_sonuclari.append((zincir_renk, zincir_sebep, "ZINCIR", 0.9))
    
    perf_renk, perf_sebep = performans_bazli_analiz(game_info)
    if perf_renk:
        pattern_sonuclari.append((perf_renk, perf_sebep, "PERFORMANS", 1.1))
    
    if len(pattern_sonuclari) < 3:
        print(f"🚫 Quantum PRO: Yetersiz pattern çeşitliliği ({len(pattern_sonuclari)}/6)")
        return
    
    renk_agirliklari = {}
    elite_patternler = ['🏆 DOĞAL KAZANÇ', '🚀 SÜPER HİBRİT', '✅ 5-Lİ ONAY', '🎯 GÜÇLÜ EL']
    
    for renk, sebep, tip, agirlik in pattern_sonuclari:
        pattern_data = pattern_stats.get(sebep, {'total': 0, 'wins': 0})
        if pattern_data['total'] > 0:
            basari_orani = pattern_data['wins'] / pattern_data['total']
            if basari_orani >= 0.85:
                agirlik *= 1.5
            elif basari_orani >= 0.75:
                agirlik *= 1.2
        
        if sebep in elite_patternler:
            agirlik *= 1.3
        
        renk_agirliklari[renk] = renk_agirliklari.get(renk, 0) + agirlik
    
    kazanan_renk = max(renk_agirliklari, key=renk_agirliklari.get)
    toplam_agirlik = renk_agirliklari[kazanan_renk]
    
    filtre_sonuclari = []
    
    elite_pattern_var = any(sebep in elite_patternler for _, sebep, _, _ in pattern_sonuclari)
    filtre_sonuclari.append(elite_pattern_var)
    
    if len(color_trend) >= 8:
        son_8 = color_trend[-8:]
        trend_destek = son_8.count(kazanan_renk) >= 3
        filtre_sonuclari.append(trend_destek)
    else:
        filtre_sonuclari.append(False)
    
    daily = get_daily_stats()
    performans_uygun = daily['profit'] >= -5
    filtre_sonuclari.append(performans_uygun)
    
    risk_seviye, _ = super_risk_analizi()
    risk_uygun = risk_seviye == "🟢 DÜŞÜK RİSK"
    filtre_sonuclari.append(risk_uygun)
    
    pattern_cesitlilik = len(set([sebep for _, sebep, _, _ in pattern_sonuclari])) >= 3
    filtre_sonuclari.append(pattern_cesitlilik)
    
    agirlik_uygun = toplam_agirlik >= 3.5
    filtre_sonuclari.append(agirlik_uygun)
    
    son_5_sinyal = list(performance_stats['signal_history'])[-5:] if performance_stats['signal_history'] else []
    if len(son_5_sinyal) >= 3:
        son_kayiplar = sum(1 for s in son_5_sinyal if s['result'] == 'loss')
        zincir_uygun = son_kayiplar <= 1
        filtre_sonuclari.append(zincir_uygun)
    else:
        filtre_sonuclari.append(True)
    
    current_hour = datetime.now(GMT3).hour
    zaman_uygun = 8 <= current_hour <= 23
    filtre_sonuclari.append(zaman_uygun)
    
    filtre_gecen = sum(filtre_sonuclari)
    
    if filtre_gecen < 7:
        print(f"🚫 Quantum PRO: Yetersiz filtre geçişi ({filtre_gecen}/8)")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    
    elite_sebepler = [sebep for _, sebep, _, _ in pattern_sonuclari if sebep in elite_patternler]
    if elite_sebepler:
        sebep_metin = " + ".join(elite_sebepler[:2])
    else:
        sebep_metin = " + ".join([sebep for _, sebep, _, _ in pattern_sonuclari[:2]])
    
    await send_new_signal(next_game_num, kazanan_renk, 
                         f"🚀 QUANTUM PRO - {sebep_metin} | Ağırlık:{toplam_agirlik:.1f}", game_info)

# MASTER ELITE SİSTEMİ
async def master_elite_sistemi(game_info):
    print("🏆 MASTER ELITE analiz başlıyor...")
    
    ELITE_PATTERNS = ['🏆 DOĞAL KAZANÇ', '🚀 SÜPER HİBRİT']
    
    signal_color, reason = analyze_simple_pattern(game_info['player_cards'], 
                                                 game_info['banker_cards'], 
                                                 game_info['game_number'])
    
    if reason not in ELITE_PATTERNS:
        print(f"🚫 Master Elite: {reason} elite değil")
        return
    
    filtre_gecen = 0
    toplam_filtre = 10
    
    pattern_data = pattern_stats.get(reason, {'total': 0, 'wins': 0})
    if pattern_data['total'] >= 5:
        basari_orani = pattern_data['wins'] / pattern_data['total']
        if basari_orani >= 0.85:
            filtre_gecen += 1
    
    if len(color_trend) >= 10:
        son_10 = color_trend[-10:]
        if son_10.count(signal_color) >= 4:
            filtre_gecen += 1
    
    daily = get_daily_stats()
    if daily['profit'] >= 0:
        filtre_gecen += 1
    
    risk_seviye, _ = super_risk_analizi()
    if risk_seviye == "🟢 DÜŞÜK RİSK":
        filtre_gecen += 1
    
    if performance_stats['current_streak'] >= 0:
        filtre_gecen += 1
    
    current_hour = datetime.now(GMT3).hour
    if 10 <= current_hour <= 22:
        filtre_gecen += 1
    
    son_30_dk = datetime.now(GMT3) - timedelta(minutes=30)
    son_sinyaller = [s for s in performance_stats['signal_history'] 
                    if s['timestamp'] >= son_30_dk]
    if len(son_sinyaller) <= 2:
        filtre_gecen += 1
    
    weekly = get_weekly_stats()
    if weekly['profit'] >= 0:
        filtre_gecen += 1
    
    if pattern_data['total'] <= 20:
        filtre_gecen += 1
    
    if len(color_trend) >= 8:
        son_8 = color_trend[-8:]
        if len(set(son_8)) <= 4:
            filtre_gecen += 1
    
    if filtre_gecen < 8:
        print(f"🚫 Master Elite: Yetersiz filtre ({filtre_gecen}/{toplam_filtre})")
        return
    
    next_game_num = get_next_game_number(game_info['game_number'])
    await send_new_signal(next_game_num, signal_color, 
                         f"🏆 MASTER ELITE - {reason} | {filtre_gecen}/10 Filtre", game_info)

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
        
        # Excel'e kaydet
        if result_type in ['win', 'loss']:
            game_info = {
                'game_number': signal_game_num,
                'player_cards': '',  # Bu bilgiyi saklamamız gerekebilir
                'banker_cards': '',
                'c2_3_type': c2_3_type
            }
            await save_game_result_to_excel(game_info, tracker_info, 
                                          'KAZANÇ' if result_type == 'win' else 'KAYIP')
        
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

async def normal_hibrit_sistemi(game_info):
    trigger_game_num, c2_3_info = game_info['game_number'], {'c2_3_type': game_info.get('c2_3_type'), 'c2_3_description': game_info.get('c2_3_description')}
    print(f"🎯 Normal Hibrit analiz ediyor {c2_3_info['c2_3_description']}...")
    signal_color, reason = analyze_simple_pattern(game_info['player_cards'], game_info['banker_cards'], trigger_game_num)
    if signal_color:
        next_game_num = get_next_game_number(trigger_game_num)
        await send_new_signal(next_game_num, signal_color, reason, c2_3_info)
        print(f"🚀 Normal Hibrit sinyal gönderildi: #{next_game_num} - {reason}")
    else: print(f"🚫 Normal Hibrit: Sinyal yok - {reason}")

async def super_hibrit_sistemi(game_info):
    trigger_game_num, c2_3_info = game_info['game_number'], {'c2_3_type': game_info.get('c2_3_type'), 'c2_3_description': game_info.get('c2_3_description')}
    print(f"🚀 Süper Hibrit analiz ediyor {c2_3_info['c2_3_description']}...")
    signal_color, onay_sebep = besli_onay_sistemi(game_info['player_cards'], game_info['banker_cards'], game_info['game_number'])
    if not signal_color: return print(f"🚫 5'li onay reddedildi: {onay_sebep}")
    filtre_sonuc, filtre_sebep = super_filtre_kontrol(signal_color, onay_sebep, game_info['game_number'])
    if not filtre_sonuc: return print(f"🚫 Süper filtre reddetti: {filtre_sebep}")
    risk_seviye, risk_uyarilar = super_risk_analizi()
    if risk_seviye == "🔴 YÜKSEK RİSK": return print(f"🚫 Yüksek risk: {risk_uyarilar}")
    next_game_num = get_next_game_number(trigger_game_num)
    await send_new_signal(next_game_num, signal_color, f"🚀 SÜPER HİBRİT - {onay_sebep}", c2_3_info)
    print(f"🎯 SÜPER HİBRİT sinyal gönderildi: #{next_game_num}")

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
        
        # Tüm oyunları Excel'e kaydet
        await save_game_result_to_excel(game_info)
        
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
                    
    except Exception as e: print(f"❌ Mesaj işleme hatası: {e}")

# YENİ EXCEL ve C2 ANALİZ KOMUTLARI
@client.on(events.NewMessage(pattern='(?i)/excel'))
async def handle_excel(event):
    if event.sender_id != ADMIN_ID: 
        return await event.reply("❌ Yetkiniz yok!")
    
    try:
        if os.path.exists(EXCEL_FILE):
            await event.reply(f"✅ Excel dosyası mevcut: {EXCEL_FILE}\n📊 Toplam kayıt: {openpyxl.load_workbook(EXCEL_FILE).active.max_row - 1}")
        else:
            await event.reply("❌ Excel dosyası bulunamadı!")
    except Exception as e:
        await event.reply(f"❌ Excel kontrol hatası: {e}")

@client.on(events.NewMessage(pattern='(?i)/excel_analiz'))
async def handle_excel_analiz(event):
    """Excel'deki verileri analiz eder"""
    analysis = analyze_excel_data()
    await event.reply(analysis)

@client.on(events.NewMessage(pattern='(?i)/excel_c2'))
async def handle_excel_c2(event):
    """Excel'den C2 tipi analizi yapar"""
    analysis = analyze_c2_from_excel()
    await event.reply(analysis)

@client.on(events.NewMessage(pattern='(?i)/c2_tavsiye'))
async def handle_c2_tavsiye(event):
    """Excel verilerine göre C2 tavsiyesi verir"""
    recommended_c2, reason = get_c2_recommendation_from_excel()
    
    tavsiye = f"""🎯 **EXCEL C2 TAVSİYESİ** 🎯

📊 **ÖNERİLEN C2 TİPİ:** {recommended_c2}
📈 **Sebep:** {reason}

💡 **DETAYLAR:**
• Bu tavsiye Excel'deki son 30 oyunun analizine dayanır
• En yüksek başarı oranına sahip C2 tipi önerilir
• Gerçek zamanlı verilerle güncellenir

⚡ **Kullanım:** {recommended_c2} tipine odaklanın ve renk tahminlerini buna göre yapın
"""
    await event.reply(tavsiye)

@client.on(events.NewMessage(pattern='(?i)/renk_tahmini'))
async def handle_renk_tahmini(event):
    try:
        if not game_results:
            return await event.reply("📊 Henüz oyun verisi yok!")
        
        # Son oyunu al
        last_game_num = max(game_results.keys())
        last_game = game_results[last_game_num]
        
        # Excel'den C2 tavsiyesi al
        recommended_c2, c2_reason = get_c2_recommendation_from_excel()
        
        # Renk tahminleri yap
        smart_color, smart_reason = predict_color_by_c2_excel(recommended_c2, last_game['player_cards'])
        normal_color, normal_reason = predict_color_game(last_game['player_cards'], last_game['banker_cards'], last_game_num)
        c2_color, c2_reason = predict_color_by_c2_type(recommended_c2, last_game['player_cards'])
        
        tahmin_mesaji = f"""🎨 **RENK TAHMİN ANALİZİ** 🎨

🎯 **Son Oyun:** #{last_game_num}
🃏 **Player:** {last_game['player_cards']}
🏦 **Banker:** {last_game['banker_cards']}

📊 **Excel C2 Analizi:**
• Önerilen Tip: {recommended_c2}
• Sebep: {c2_reason}

🔮 **RENK TAHMİNLERİ:**
• 🤖 Akıllı Tahmin: {smart_color}
• 📊 Sebep: {smart_reason}
• 🎲 Normal Tahmin: {normal_color}
• 📈 C2 Tahmini: {c2_color}

💡 **STRATEJİ:** {smart_color.split()[0]} odaklanın!
"""
        await event.reply(tahmin_mesaji)
        
    except Exception as e:
        await event.reply(f"❌ Renk tahmin hatası: {e}")

@client.on(events.NewMessage(pattern='(?i)/smart_renk'))
async def handle_smart_renk(event):
    """Excel + C2 analizine göre akıllı renk tahmini"""
    try:
        if not game_results:
            return await event.reply("📊 Henüz oyun verisi yok!")
        
        # Excel'den C2 tavsiyesi al
        recommended_c2, c2_reason = get_c2_recommendation_from_excel()
        
        # Son oyunu al
        last_game_num = max(game_results.keys())
        last_game = game_results[last_game_num]
        
        # Akıllı renk tahmini yap
        smart_color, smart_reason = predict_color_by_c2_excel(recommended_c2, last_game['player_cards'])
        
        # Normal tahminler
        normal_color, normal_reason = predict_color_game(last_game['player_cards'], last_game['banker_cards'], last_game_num)
        c2_color, c2_reason = predict_color_by_c2_type(recommended_c2, last_game['player_cards'])
        
        tahmin_mesaji = f"""🎯 **AKILLI RENK TAHMİNİ** 🎯

📊 **Excel C2 Analizi:**
• Önerilen Tip: {recommended_c2}
• Sebep: {c2_reason}

🎨 **TAHMİNLER:**
• 🤖 Akıllı Tahmin: {smart_color}
• 📊 Sebep: {smart_reason}
• 🎲 Normal Tahmin: {normal_color}
• 📈 C2 Tahmini: {c2_color}

💡 **STRATEJİ:**
{generate_smart_strategy(recommended_c2, smart_color)}
"""
        await event.reply(tahmin_mesaji)
        
    except Exception as e:
        await event.reply(f"❌ Akıllı renk tahmin hatası: {e}")

def generate_smart_strategy(c2_type, color_prediction):
    """Akıllı strateji tavsiyesi oluşturur"""
    strategies = {
        '#C2_3': "🎯 KLASİK strateji: Sabit ve güvenilir, yüksek oranlarla oynayın",
        '#C2_2': "🔄 ALTERNATİF strateji: Esnek davranın, orta risk alın", 
        '#C3_2': "⚡ VARYANT strateji: Yüksek risk, dikkatli ilerleyin",
        '#C3_3': "🌟 ÖZEL strateji: Nadir pattern, özel taktik uygulayın"
    }
    
    base_strategy = strategies.get(c2_type, "🎲 Dengeli strateji: Orta riskle ilerleyin")
    
    color_advice = {
        '🔴': "🔴 KIRMIZI agresif: Büyük bahisler deneyebilirsiniz",
        '🔵': "🔵 MAVİ dengeli: Orta bahislerle istikrarlı ilerleyin",
        '🟢': "🟢 YEŞİL riskli: Küçük bahislerle test edin", 
        '⚫': "⚫ SİYAH spekülatif: Çok dikkatli olun"
    }
    
    color_emoji = color_prediction.split()[0] if color_prediction else '🔴'
    color_strategy = color_advice.get(color_emoji, "🎲 Standart strateji uygulayın")
    
    return f"{base_strategy}\n{color_strategy}"

# DİĞER KOMUTLAR (Aynen korundu)
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
💾 **Excel Kayıt:** {openpyxl.load_workbook(EXCEL_FILE).active.max_row - 1 if os.path.exists(EXCEL_FILE) else 0} kayıt

⚡ **Sistem:** Hibrit Pattern + Martingale {MAX_MARTINGALE_STEPS} Seviye
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

@client.on(events.NewMessage(pattern='(?i)/mod_normal'))
async def handle_mod_normal(event):
    global SISTEM_MODU
    SISTEM_MODU = "normal_hibrit"
    await event.reply("✅ NORMAL HİBRİT modu aktif! Daha çok sinyal, normal risk.")

@client.on(events.NewMessage(pattern='(?i)/mod_super'))
async def handle_mod_super(event):
    global SISTEM_MODU
    SISTEM_MODU = "super_hibrit"
    await event.reply("🚀 SÜPER HİBRİT modu aktif! Daha az sinyal, yüksek güvenlik.")

@client.on(events.NewMessage(pattern='(?i)/mod_quantum'))
async def handle_mod_quantum(event):
    global SISTEM_MODU
    SISTEM_MODU = "quantum_hibrit"
    await event.reply("⚛️ QUANTUM HİBRİT modu aktif! 4 analiz + 6 filtre + %85+ başarı hedefi. 3 martingale sabit.")

@client.on(events.NewMessage(pattern='(?i)/mod_quantumpro'))
async def handle_mod_quantumpro(event):
    global SISTEM_MODU
    SISTEM_MODU = "quantum_pro"
    await event.reply("🚀 QUANTUM PRO modu aktif! 6 analiz + 8 filtre + %90+ başarı hedefi. 3 martingale sabit.")

@client.on(events.NewMessage(pattern='(?i)/mod_masterelite'))
async def handle_mod_masterelite(event):
    global SISTEM_MODU
    SISTEM_MODU = "master_elite"
    await event.reply("🏆 MASTER ELITE modu aktif! Sadece elite pattern'ler + 10 filtre + %95+ başarı hedefi. 3 martingale sabit.")

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

🎯 **TEMEL KOMUTLAR:**
• /basla - Botu başlat
• /durum - Sistem durumu
• /istatistik - Detaylı istatistikler
• /performans - Performans raporu
• /rapor - Günlük/haftalık rapor

📊 **ANALİZ KOMUTLARI:**
• /c2analiz - C2-3 tip performansları
• /pattern - Pattern performans tablosu
• /trend - Trend analizi
• /eniyi - En iyi performans
• /enkotu - En kötü performans
• /tavsiye - Trading tavsiyesi

💾 **EXCEL & C2 ANALİZ:**
• /excel - Excel dosyası durumu
• /excel_analiz - Excel veri analizi
• /excel_c2 - Excel C2 tip analizi
• /c2_tavsiye - Excel C2 tavsiyesi
• /renk_tahmini - Renk tahmin analizi
• /smart_renk - Akıllı renk tahmini

🎛️ **SİSTEM MODLARI:**
• /mod_normal - Normal Hibrit Mod
• /mod_super - Süper Hibrit Mod  
• /mod_quantum - Quantum Hibrit Mod
• /mod_quantumpro - Quantum Pro Mod
• /mod_masterelite - Master Elite Mod
• /mod_durum - Aktif modu göster

⚡ **ADMIN KOMUTLARI:**
• /temizle - Trend verilerini temizle
• /acil_durdur - Acil durdurma
• /aktif_et - Sistemi tekrar aktif et

🔧 **Sistem:** Hibrit Pattern + Martingale {MAX_MARTINGALE_STEPS} Seviye
🕒 **Saat Dilimi:** GMT+3 (İstanbul)
💾 **Excel Kayıt:** Tüm veriler otomatik kaydedilir
""".format(MAX_MARTINGALE_STEPS=MAX_MARTINGALE_STEPS)
    await event.reply(yardim_mesaji)

if __name__ == '__main__':
    print("🤖 ROYAL BACCARAT BOT BAŞLIYOR...")
    print(f"🔧 API_ID: {API_ID}")
    print(f"🎯 Kaynak Kanal: {KANAL_KAYNAK_ID}")
    print(f"📤 Hedef Kanal: {KANAL_HEDEF}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"🎛️ Varsayılan Mod: {SISTEM_MODU}")
    print(f"💾 Excel Kayıt Sistemi: AKTİF")
    print(f"📊 C2-3 Analiz Sistemi: AKTİF")
    print(f"📈 Pattern Performans Takibi: AKTİF")
    print(f"🎨 Renk Oyunu Tahmini: AKTİF")
    print(f"🤖 Excel C2 Analizi: AKTİF")
    print(f"⚛️ Quantum Hibrit Sistem: AKTİF")
    print(f"🚀 Quantum PRO Sistem: AKTİF")
    print(f"🏆 Master Elite Sistem: AKTİF")
    print(f"🕒 Saat Dilimi: GMT+3")
    
    # Excel dosyasını başlat
    init_excel_file()
    
    print("⏳ Bağlanıyor...")
    try:
        with client: 
            client.run_until_disconnected()
    except KeyboardInterrupt: 
        print("\n👋 Bot durduruluyor...")
    except Exception as e: 
        print(f"❌ Bot başlangıç hatası: {e}")
