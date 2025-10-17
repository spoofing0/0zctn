import re
import json
import os
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
import asyncio
import sys

# ==============================================================================
# Telegram API Bilgileri
# ==============================================================================
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
BOT_TOKEN = ''  # BURAYA BOT TOKEN'İNİ YAZ

KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"
ADMIN_ID = 123456789  # BURAYA KENDİ TELEGRAM ID'Nİ YAZ

client = TelegramClient('royal_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# ==============================================================================
# Global Değişkenler
# ==============================================================================
game_results = {}
martingale_trackers = {}
MAX_MARTINGALE_STEPS = 3
MAX_GAME_NUMBER = 1440
is_signal_active = False

# Renk takibi
color_trend = []
MAX_TREND_LENGTH = 10

# Sicarde patternleri
sicarde_patterns = {
    'strong_hand': [],
    'weak_hand': [],
    'color_repeat': []
}

# ==============================================================================
# BASİT SİCARDE ANALİZ SİSTEMİ
# ==============================================================================

def get_baccarat_value(card_char):
    if card_char == '10': return 10
    if card_char in 'AKQJ2T': return 0
    elif card_char.isdigit(): return int(card_char)
    return -1

def analyze_sicarde_pattern(player_cards, banker_cards):
    """
    Basit Sicarde analizi - 5 kartlık pattern tespiti
    """
    # Kartları ayrıştır
    player_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
    banker_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)
    
    if not player_card_data or not banker_card_data:
        return None
    
    # Oyuncu kart değerlerini al
    player_values = [get_baccarat_value(card[0]) for card in player_card_data]
    player_suits = [card[1] for card in player_card_data]
    
    # Banker kart değerlerini al
    banker_values = [get_baccarat_value(card[0]) for card in banker_card_data]
    
    # Toplam kart sayısı
    total_cards = len(player_values) + len(banker_values)
    
    # Pattern tespiti
    patterns = {
        'strong_hand': sum(player_values) >= 8 and len(player_values) >= 3,
        'weak_hand': sum(player_values) <= 5 and len(player_values) >= 3,
        'natural_win': sum(player_values) in [8, 9],
        'banker_advantage': sum(banker_values) > sum(player_values),
        'five_card_winner': total_cards >= 5,
        'player_suit': max(set(player_suits), key=player_suits.count) if player_suits else None
    }
    
    return patterns

def should_send_signal(patterns, game_number):
    """
    Sinyal gönderilip gönderilmeyeceğine karar ver
    """
    if not patterns:
        return False, "Pattern bulunamadı"
    
    # 1. Güçlü el patterni
    if patterns['strong_hand'] and patterns['five_card_winner']:
        return True, "🎯 GÜÇLÜ EL + 5 KART"
    
    # 2. Doğal kazanç patterni
    if patterns['natural_win']:
        return True, "🏆 DOĞAL KAZANÇ"
    
    # 3. Zayıf el sonrası trend değişimi
    if patterns['weak_hand'] and len(sicarde_patterns['weak_hand']) >= 2:
        return True, "📈 ZAYIF EL TREND DEĞİŞİMİ"
    
    return False, "Pattern uygun değil"

def update_trend_analysis(current_color, game_number):
    """
    Renk trend analizini güncelle
    """
    global color_trend
    
    # Trend'i güncelle
    color_trend.append(current_color)
    if len(color_trend) > MAX_TREND_LENGTH:
        color_trend.pop(0)
    
    # Aynı renk tekrar analizi
    if len(color_trend) >= 3:
        last_three = color_trend[-3:]
        if len(set(last_three)) == 1:  # 3 kere üst üste aynı renk
            sicarde_patterns['color_repeat'].append({
                'color': current_color,
                'game_number': game_number
            })
            return f"🚨 3x {current_color} TEKRARI"
    
    return None

# ==============================================================================
# SİNYAL SİSTEMİ
# ==============================================================================

def extract_largest_value_suit(cards_str):
    """Oyuncu kartlarındaki en yüksek değerli kartın sembolünü döndürür."""
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

    return largest_value_suit if max_value > 0 else None

async def send_new_signal(game_num, signal_suit, reason):
    """Yeni sinyal gönder"""
    global is_signal_active
    
    if is_signal_active:
        print("⚠️ Zaten aktif sinyal var")
        return
    
    suit_display = get_suit_display_name(signal_suit)
    
    signal_text = (
        f"🎯 **SİCARDE SİNYAL** 🎯\n"
        f"#N{game_num} - {suit_display}\n"
        f"📊 Sebep: {reason}\n"
        f"⚡ Strateji: Martingale {MAX_MARTINGALE_STEPS}D\n"
        f"🕒 Süre: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    try:
        sent_message = await client.send_message(KANAL_HEDEF, signal_text)
        print(f"🚀 Sinyal gönderildi: #N{game_num} - {reason}")
        
        martingale_trackers[game_num] = {
            'message_obj': sent_message,
            'step': 0,
            'signal_suit': signal_suit,
            'sent_game_number': game_num,
            'expected_game_number_for_check': game_num,
            'start_time': datetime.now(),
            'reason': reason
        }
        is_signal_active = True
        
    except Exception as e:
        print(f"❌ Sinyal gönderme hatası: {e}")

async def update_signal_message(tracker_info, result_type, current_step=None):
    """Sinyal mesajını güncelle"""
    signal_game_num = tracker_info['sent_game_number']
    signal_suit = tracker_info['signal_suit']
    suit_display = get_suit_display_name(signal_suit)
    message_obj = tracker_info['message_obj']
    reason = tracker_info.get('reason', '')
    
    duration = datetime.now() - tracker_info['start_time']
    duration_str = f"{duration.seconds // 60}:{duration.seconds % 60:02d}"
    
    if result_type == 'win':
        new_text = (
            f"✅ **KAZANAN SİNYAL** ✅\n"
            f"#N{signal_game_num} - {suit_display}\n"
            f"📊 Sebep: {reason}\n"
            f"🎯 Adım: {current_step}. Seviye\n"
            f"⏱️ Süre: {duration_str}\n"
            f"🏆 Sonuç: KAZANÇ"
        )
    elif result_type == 'loss':
        new_text = (
            f"❌ **KAYBEDEN SİNYAL** ❌\n"
            f"#N{signal_game_num} - {suit_display}\n"
            f"📊 Sebep: {reason}\n"
            f"⚡ Strateji: Martingale {MAX_MARTINGALE_STEPS}D\n"
            f"⏱️ Süre: {duration_str}\n"
            f"💔 Sonuç: KAYIP"
        )
    elif result_type == 'progress':
        new_text = (
            f"📈 **AKTİF SİNYAL** 📈\n"
            f"#N{signal_game_num} - {suit_display}\n"
            f"📊 Sebep: {reason}\n"
            f"🎯 Adım: {current_step}. Seviye\n"
            f"⏳ Sonraki: #N{tracker_info['expected_game_number_for_check']}\n"
            f"🔄 Durum: Devam Ediyor"
        )
    
    try:
        await message_obj.edit(new_text)
        print(f"✏️ Sinyal güncellendi: #{signal_game_num}")
    except MessageNotModifiedError:
        pass
    except Exception as e:
        print(f"❌ Mesaj düzenleme hatası: {e}")

# ==============================================================================
# MARTINGALE TAKİP SİSTEMİ
# ==============================================================================

def get_next_game_number(current_game_num):
    next_num = current_game_num + 1
    return 1 if next_num > MAX_GAME_NUMBER else next_num

async def check_martingale_trackers():
    global martingale_trackers, is_signal_active
    
    trackers_to_remove = []
    
    for signal_game_num, tracker_info in list(martingale_trackers.items()):
        current_step = tracker_info['step']
        signal_suit = tracker_info['signal_suit']
        game_to_check = tracker_info['expected_game_number_for_check']
        
        if game_to_check not in game_results:
            continue
        
        result_info = game_results.get(game_to_check)
        if not result_info['is_final']:
            continue
        
        player_cards_str = result_info['player_cards']
        signal_won_this_step = bool(re.search(re.escape(signal_suit), player_cards_str))
        
        print(f"🔍 Sinyal kontrolü: #{signal_game_num} (Adım {current_step})")
        
        if signal_won_this_step:
            await update_signal_message(tracker_info, 'win', current_step)
            trackers_to_remove.append(signal_game_num)
            is_signal_active = False
            print(f"🎉 Sinyal #{signal_game_num} kazandı!")
            
            # Kazanç sonrası pattern güncelleme
            sicarde_patterns['strong_hand'].append(signal_game_num)
            
        else:
            if current_step < MAX_MARTINGALE_STEPS:
                next_step = current_step + 1
                next_game_num = get_next_game_number(game_to_check)
                
                martingale_trackers[signal_game_num]['step'] = next_step
                martingale_trackers[signal_game_num]['expected_game_number_for_check'] = next_game_num
                
                await update_signal_message(tracker_info, 'progress', next_step)
                print(f"📈 Sinyal #{signal_game_num} {next_step}. adıma geçiyor")
                
            else:
                await update_signal_message(tracker_info, 'loss')
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False
                print(f"💔 Sinyal #{signal_game_num} kaybetti")
                
                # Kayıp sonrası pattern güncelleme
                sicarde_patterns['weak_hand'].append(signal_game_num)
    
    for game_num_to_remove in trackers_to_remove:
        if game_num_to_remove in martingale_trackers:
            del martingale_trackers[game_num_to_remove]

# ==============================================================================
# ANA MESAJ İŞLEYİCİ - BASİT SİCARDE SİSTEM
# ==============================================================================

def extract_game_info_from_message(text):
    game_info = {
        'game_number': None, 
        'player_cards': '', 
        'banker_cards': '',
        'is_final': False, 
        'is_player_drawing': False, 
        'is_c2_3': False
    }
    
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

def get_suit_display_name(suit_symbol):
    suit_names = {
        '♠': '🖤 MAÇA',
        '♥': '❤️ KALP', 
        '♦': '💎 ELMAS',
        '♣': '♣️ SİNEK'
    }
    return suit_names.get(suit_symbol, f"❓ {suit_symbol}")

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_source_channel_message(event):
    message = event.message
    cleaned_text = re.sub(r'\*\*', '', message.text).strip()
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 Mesaj: '{cleaned_text[:100]}...'")
    
    game_info = extract_game_info_from_message(cleaned_text)
    if game_info['game_number'] is None:
        return

    game_results[game_info['game_number']] = game_info
    
    await check_martingale_trackers()

    if not is_signal_active:
        if game_info['is_final'] and game_info.get('is_c2_3'):
            trigger_game_num = game_info['game_number']
            
            print("🎯 Sicarde Pattern analizi başlatılıyor...")
            
            # Sicarde pattern analizi
            patterns = analyze_sicarde_pattern(game_info['player_cards'], game_info['banker_cards'])
            
            # Renk tespiti
            signal_color = extract_largest_value_suit(game_info['player_cards'])
            
            if signal_color and patterns:
                # Trend analizini güncelle
                trend_alert = update_trend_analysis(signal_color, trigger_game_num)
                
                # Sinyal kararı
                should_send, reason = should_send_signal(patterns, trigger_game_num)
                
                if should_send:
                    next_game_num = get_next_game_number(trigger_game_num)
                    await send_new_signal(next_game_num, signal_color, reason)
                    print(f"🎯 Sicarde sinyal ONAYLANDI: {reason}")
                else:
                    print(f"🚫 Sicarde sinyal REDDEDİLDİ: {reason}")
                    
                    # Trend alert varsa göster
                    if trend_alert:
                        print(f"📈 Trend Uyarısı: {trend_alert}")

# ==============================================================================
# KOMUT SİSTEMİ
# ==============================================================================

@client.on(events.NewMessage(pattern='(?i)/durum'))
async def handle_durum(event):
    aktif_sinyal = "✅ Var" if is_signal_active else "❌ Yok"
    
    durum_mesaji = (
        f"🤖 **SİCARDE BOT DURUMU** 🤖\n\n"
        f"🟢 **Çalışıyor:** Evet\n"
        f"🎯 **Aktif Sinyal:** {aktif_sinyal}\n"
        f"📊 **Takip Edilen:** {len(martingale_trackers)} sinyal\n"
        f"📈 **Pattern Kayıtları:**\n"
        f"• Güçlü El: {len(sicarde_patterns['strong_hand'])}\n"
        f"• Zayıf El: {len(sicarde_patterns['weak_hand'])}\n"
        f"• Renk Tekrar: {len(sicarde_patterns['color_repeat'])}\n"
        f"• Son Trend: {color_trend[-5:] if color_trend else 'Yok'}\n\n"
        f"⚡ **Sistem:** Sicarde Pattern + Trend Takip"
    )
    
    await event.reply(durum_mesaji)

@client.on(events.NewMessage(pattern='(?i)/pattern'))
async def handle_pattern(event):
    pattern_info = (
        f"🎯 **SİCARDE PATTERN SİSTEMİ** 🎯\n\n"
        f"**Aktif Patternler:**\n"
        f"• 🎯 GÜÇLÜ EL + 5 KART\n"
        f"• 🏆 DOĞAL KAZANÇ (8-9)\n"
        f"• 📈 ZAYIF EL TREND DEĞİŞİMİ\n"
        f"• 🚨 3x RENK TEKRARI\n\n"
        f"**Son 5 Pattern:**\n"
    )
    
    # Son patternleri göster
    recent_strong = sicarde_patterns['strong_hand'][-3:] if sicarde_patterns['strong_hand'] else []
    recent_weak = sicarde_patterns['weak_hand'][-3:] if sicarde_patterns['weak_hand'] else []
    
    if recent_strong:
        pattern_info += f"• Güçlü El: {recent_strong}\n"
    if recent_weak:
        pattern_info += f"• Zayıf El: {recent_weak}\n"
    
    if not recent_strong and not recent_weak:
        pattern_info += "• Henüz pattern kaydı yok\n"
    
    pattern_info += f"\n**Son Trend:** {color_trend[-5:] if color_trend else 'Yok'}"
    
    await event.reply(pattern_info)

@client.on(events.NewMessage(pattern='(?i)/temizle'))
async def handle_temizle(event):
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Bu komutu sadece yönetici kullanabilir.")
        return
    
    global sicarde_patterns, color_trend
    sicarde_patterns = {'strong_hand': [], 'weak_hand': [], 'color_repeat': []}
    color_trend = []
    
    await event.reply("✅ Pattern ve trend verileri temizlendi!")

# ==============================================================================
# BOT BAŞLATMA
# ==============================================================================
if __name__ == '__main__':
    print("🤖 SİCARDE PATTERN BOT BAŞLATILIYOR...")
    print("🎯 Sistem: Sicarde Pattern + Trend Takip")
    print("⚡ Özellikler: Güçlü/Zayıf El Tespiti, Renk Trendi")
    print("⏳ Bağlantı kuruluyor...")
    
    try:
        with client:
            client.run_until_disconnected()
    except KeyboardInterrupt:
        print("\n👋 Bot kapatılıyor...")
    except Exception as e:
        print(f"❌ Bot hatası: {e}")
