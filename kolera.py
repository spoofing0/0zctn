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
        
        # Renk tahminleri yap
        color_prediction, color_reason = predict_color_game(player_cards, banker_cards, game_info['game_number'])
        c2_color_prediction, c2_color_reason = predict_color_by_c2_type(game_info.get('c2_3_type', '#C2_3'), player_cards)
        
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
            'color_prediction': f"{color_prediction} | {c2_color_prediction}",
            'pattern_type': signal_info.get('reason', 'N/A') if signal_info else 'N/A',
            'signal_level': signal_info.get('step', 0) if signal_info else 0,
            'result': result_type if result_type else 'BEKLİYOR',
            'profit_loss': 1 if result_type == 'KAZANÇ' else -1 if result_type == 'KAYIP' else 0,
            'total_profit': performance_stats['total_profit']
        }
        
        # Excel'e kaydet
        save_to_excel(excel_data)
        
        # Renk tahminlerini konsola yazdır
        print(f"🎨 Renk Tahmini: {color_prediction} - {color_reason}")
        print(f"🎯 C2 Renk Tahmini: {c2_color_prediction} - {c2_color_reason}")
        
    except Exception as e:
        print(f"❌ Excel kayıt hatası: {e}")

# [ÖNCEKİ TÜM FONKSİYONLAR AYNI ŞEKİLDE KALACAK...]
# analyze_simple_pattern, besli_onay_sistemi, super_filtre_kontrol, vs. tüm fonksiyonlar burada olacak

# Sinyal güncelleme fonksiyonuna Excel kaydı ekle
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

# Mesaj işleme fonksiyonuna Excel kaydı ekle
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

# Yeni komut: Excel raporu
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

# Yeni komut: Renk analizi
@client.on(events.NewMessage(pattern='(?i)/renk_tahmini'))
async def handle_renk_tahmini(event):
    try:
        if not game_results:
            return await event.reply("📊 Henüz oyun verisi yok!")
        
        # Son oyunu al
        last_game_num = max(game_results.keys())
        last_game = game_results[last_game_num]
        
        # Renk tahminleri yap
        color_pred, color_reason = predict_color_game(last_game['player_cards'], last_game['banker_cards'], last_game_num)
        c2_color_pred, c2_color_reason = predict_color_by_c2_type(last_game.get('c2_3_type', '#C2_3'), last_game['player_cards'])
        
        tahmin_mesaji = f"""🎨 **RENK TAHMİN ANALİZİ** 🎨

🎯 **Son Oyun:** #{last_game_num}
🃏 **Player:** {last_game['player_cards']}
🏦 **Banker:** {last_game['banker_cards']}

🔮 **RENK TAHMİNLERİ:**
• 🎲 Oyun Analizi: {color_pred}
• 📊 Sebep: {color_reason}
• 🎯 C2 Tip Tahmini: {c2_color_pred}  
• 📈 Strateji: {c2_color_reason}

💡 **ÖNERİ:** Renk oyunu için {color_pred.split()[0]} odaklanın!
"""
        await event.reply(tahmin_mesaji)
        
    except Exception as e:
        await event.reply(f"❌ Renk tahmin hatası: {e}")

# Bot başlangıcında Excel dosyasını başlat
if __name__ == '__main__':
    print("🤖 ROYAL BACCARAT BOT BAŞLIYOR...")
    print(f"🔧 API_ID: {API_ID}")
    print(f"🎯 Kaynak Kanal: {KANAL_KAYNAK_ID}")
    print(f"📤 Hedef Kanal: {KANAL_HEDEF}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"🎛️ Varsayılan Mod: {SISTEM_MODU}")
    print(f"📊 Excel Kayıt Sistemi: AKTİF")
    print(f"🎨 Renk Oyunu Tahmini: AKTİF")
    print(f"📈 C2 Tip Analizi: AKTİF")
    
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
