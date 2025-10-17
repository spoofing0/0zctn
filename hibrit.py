import re
import json
import os
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
import asyncio
import sys

# ==============================================================================
# Telegram API Bilgileri ve Kanal Ayarları
# ==============================================================================
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
BOT_TOKEN = ''  # BURAYA BOT TOKEN'İNİ YAZ

# --- Kanal Bilgileri ---
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"
ADMIN_ID = 1136442929

client = TelegramClient('royal_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# ==============================================================================
# Global Değişkenler ve Takip Mekanizmaları
# ==============================================================================
game_results = {}
martingale_trackers = {}
MAX_MARTINGALE_STEPS = 3
MAX_GAME_NUMBER = 1440
is_signal_active = False

# Basit trend takibi
color_trend = []
recent_games = []

# ==============================================================================
# BASİT SİNYAL SİSTEMİ (Hibrit Yerine)
# ==============================================================================

def get_baccarat_value(card_char):
    """Kart değerini hesapla"""
    if card_char == '10': return 10
    if card_char in 'AKQJ2T': return 0
    elif card_char.isdigit(): return int(card_char)
    return -1

def extract_largest_value_suit(cards_str):
    """Oyuncu kartlarındaki en yüksek değerli kartın sembolünü döndürür."""
    try:
        cards = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', cards_str)
        if not cards:
            return None

        max_value = -1
        largest_value_suit = None
        
        # Eğer iki kart aynı değerdeyse None döndür
        values = [get_baccarat_value(card[0]) for card in cards]
        if len(values) == 2 and values[0] == values[1]:
            return None

        for card_char, suit in cards:
            value = get_baccarat_value(card_char)
            if value > max_value:
                max_value = value
                largest_value_suit = suit

        return largest_value_suit if max_value > 0 else None
    except Exception as e:
        print(f"❌ extract_largest_value_suit hatası: {e}")
        return None

def analyze_simple_pattern(player_cards, banker_cards, game_number):
    """Basit pattern analizi"""
    try:
        # Renk tespiti
        signal_color = extract_largest_value_suit(player_cards)
        if not signal_color:
            return None, "Renk tespit edilemedi"
        
        # Trend analizi
        color_trend.append(signal_color)
        if len(color_trend) > 10:
            color_trend.pop(0)
        
        # Basit patternler
        player_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
        player_values = [get_baccarat_value(card[0]) for card in player_card_data]
        
        banker_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)
        banker_values = [get_baccarat_value(card[0]) for card in banker_card_data]
        
        total_cards = len(player_values) + len(banker_values)
        
        # Pattern tespiti
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
        print(f"❌ Pattern analiz hatası: {e}")
        return None, f"Hata: {e}"

def should_send_signal(signal_color, reason, game_number):
    """Sinyal gönderim kontrolü"""
    if not signal_color:
        return False, "Renk yok"
    
    # Aktif sinyal kontrolü
    global is_signal_active
    if is_signal_active:
        return False, "Aktif sinyal var"
    
    # Basit filtreler
    if "Hata:" in reason:
        return False, reason
    
    return True, reason

# ==============================================================================
# SİNYAL YÖNETİMİ
# ==============================================================================

def get_suit_display_name(suit_symbol):
    """Renk görüntüleme adı"""
    suit_names = {
        '♠': '🖤 MAÇA',
        '♥': '❤️ KALP', 
        '♦': '💎 ELMAS',
        '♣': '♣️ SİNEK'
    }
    return suit_names.get(suit_symbol, f"❓ {suit_symbol}")

async def send_new_signal(game_num, signal_suit, reason):
    """Yeni sinyal gönder"""
    global is_signal_active
    
    try:
        suit_display = get_suit_display_name(signal_suit)
        
        signal_text = (
            f"🎯 **SİNYAL** 🎯\n"
            f"#N{game_num} - {suit_display}\n"
            f"📊 Sebep: {reason}\n"
            f"⚡ Strateji: Martingale {MAX_MARTINGALE_STEPS}D\n"
            f"🕒 {datetime.now().strftime('%H:%M:%S')}"
        )
        
        sent_message = await client.send_message(KANAL_HEDEF, signal_text)
        print(f"🚀 Sinyal gönderildi: #N{game_num} - {suit_display} - {reason}")
        
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
        
        # Admin bildirimi
        try:
            await client.send_message(
                ADMIN_ID, 
                f"🔔 Yeni sinyal: #N{game_num} - {suit_display}\nSebep: {reason}"
            )
        except:
            pass
            
    except Exception as e:
        print(f"❌ Sinyal gönderme hatası: {e}")

async def update_signal_message(tracker_info, result_type, current_step=None):
    """Sinyal mesajını güncelle"""
    try:
        signal_game_num = tracker_info['sent_game_number']
        signal_suit = tracker_info['signal_suit']
        suit_display = get_suit_display_name(signal_suit)
        message_obj = tracker_info['message_obj']
        reason = tracker_info.get('reason', '')
        
        duration = datetime.now() - tracker_info['start_time']
        duration_str = f"{duration.seconds // 60}:{duration.seconds % 60:02d}"
        
        if result_type == 'win':
            new_text = (
                f"✅ **KAZANÇ** ✅\n"
                f"#N{signal_game_num} - {suit_display}\n"
                f"📊 Sebep: {reason}\n"
                f"🎯 Adım: {current_step if current_step else 0}. Seviye\n"
                f"⏱️ {duration_str}\n"
                f"🏆 KAZANÇ"
            )
        elif result_type == 'loss':
            new_text = (
                f"❌ **KAYIP** ❌\n"
                f"#N{signal_game_num} - {suit_display}\n"
                f"📊 Sebep: {reason}\n"
                f"⚡ Martingale {MAX_MARTINGALE_STEPS}D\n"
                f"⏱️ {duration_str}\n"
                f"💔 KAYIP"
            )
        elif result_type == 'progress':
            new_text = (
                f"📈 **DEVAM** 📈\n"
                f"#N{signal_game_num} - {suit_display}\n"
                f"📊 Sebep: {reason}\n"
                f"🎯 Adım: {current_step}. Seviye\n"
                f"⏳ Sonraki: #N{tracker_info['expected_game_number_for_check']}\n"
                f"🔄 Devam Ediyor"
            )
        
        await message_obj.edit(new_text)
        print(f"✏️ Sinyal güncellendi: #{signal_game_num} - {result_type}")
        
    except MessageNotModifiedError:
        pass
    except Exception as e:
        print(f"❌ Mesaj düzenleme hatası: {e}")

# ==============================================================================
# MARTINGALE SİSTEMİ
# ==============================================================================

def get_next_game_number(current_game_num):
    """Sonraki oyun numarası"""
    next_num = current_game_num + 1
    return 1 if next_num > MAX_GAME_NUMBER else next_num

async def check_martingale_trackers():
    """Martingale takibi"""
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
        
        print(f"🔍 Sinyal kontrol: #{signal_game_num} (Adım {current_step})")
        
        if signal_won_this_step:
            await update_signal_message(tracker_info, 'win', current_step)
            trackers_to_remove.append(signal_game_num)
            is_signal_active = False
            print(f"🎉 Sinyal #{signal_game_num} kazandı!")
            
        else:
            if current_step < MAX_MARTINGALE_STEPS:
                next_step = current_step + 1
                next_game_num = get_next_game_number(game_to_check)
                
                martingale_trackers[signal_game_num]['step'] = next_step
                martingale_trackers[signal_game_num]['expected_game_number_for_check'] = next_game_num
                
                await update_signal_message(tracker_info, 'progress', next_step)
                print(f"📈 Sinyal #{signal_game_num} → {next_step}. adım")
                
            else:
                await update_signal_message(tracker_info, 'loss')
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False
                print(f"💔 Sinyal #{signal_game_num} kaybetti")
    
    for game_num_to_remove in trackers_to_remove:
        if game_num_to_remove in martingale_trackers:
            del martingale_trackers[game_num_to_remove]

# ==============================================================================
# ANA MESAJ İŞLEYİCİ
# ==============================================================================

def extract_game_info_from_message(text):
    """Oyun bilgilerini çıkar"""
    game_info = {
        'game_number': None, 
        'player_cards': '', 
        'banker_cards': '',
        'is_final': False, 
        'is_player_drawing': False, 
        'is_c2_3': False
    }
    
    try:
        # Basit regex pattern
        game_match = re.search(r'#N(\d+)', text)
        if game_match:
            game_info['game_number'] = int(game_match.group(1))
        
        # Oyuncu kartları
        player_match = re.search(r'\((.*?)\)', text)
        if player_match:
            game_info['player_cards'] = player_match.group(1)
        
        # Banker kartları - basit yaklaşım
        banker_match = re.search(r'\d+\s+\((.*?)\)', text)
        if banker_match:
            game_info['banker_cards'] = banker_match.group(1)
        
        # C2_3 kontrolü
        if '#C2_3' in text:
            game_info['is_c2_3'] = True
        
        # Final kontrolü
        if ('✅' in text or '🔰' in text or '#X' in text):
            game_info['is_final'] = True
            
    except Exception as e:
        print(f"❌ Oyun bilgisi çıkarma hatası: {e}")
    
    return game_info

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_source_channel_message(event):
    """Kaynak kanal mesajlarını işle"""
    try:
        message = event.message
        text = message.text or ""
        cleaned_text = re.sub(r'\*\*', '', text).strip()
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 Mesaj: #{len(cleaned_text)} karakter")
        
        game_info = extract_game_info_from_message(cleaned_text)
        
        if game_info['game_number'] is None:
            print("❌ Oyun numarası bulunamadı")
            return

        # Oyun bilgisini kaydet
        game_results[game_info['game_number']] = game_info
        
        # Martingale kontrolü
        await check_martingale_trackers()

        # Yeni sinyal kontrolü
        if not is_signal_active:
            if game_info['is_final'] and game_info.get('is_c2_3'):
                trigger_game_num = game_info['game_number']
                print(f"🎯 C2_3 tespit edildi: #{trigger_game_num}")
                
                # Basit pattern analizi
                signal_color, reason = analyze_simple_pattern(
                    game_info['player_cards'], 
                    game_info['banker_cards'],
                    trigger_game_num
                )
                
                # Sinyal gönderim kontrolü
                should_send, send_reason = should_send_signal(signal_color, reason, trigger_game_num)
                
                if should_send:
                    next_game_num = get_next_game_number(trigger_game_num)
                    await send_new_signal(next_game_num, signal_color, reason)
                    print(f"🚀 Sinyal onaylandı: #{next_game_num} - {reason}")
                else:
                    print(f"🚫 Sinyal reddedildi: {send_reason}")
                    
    except Exception as e:
        print(f"❌ Mesaj işleme hatası: {e}")

# ==============================================================================
# KOMUT SİSTEMİ
# ==============================================================================

@client.on(events.NewMessage(pattern='(?i)/start'))
async def handle_start(event):
    await event.reply("🤖 Royal Baccarat Bot Aktif!")

@client.on(events.NewMessage(pattern='(?i)/durum'))
async def handle_durum(event):
    aktif_sinyal = "✅ Var" if is_signal_active else "❌ Yok"
    
    durum_mesaji = (
        f"🤖 **ROYAL BACCARAT BOT** 🤖\n\n"
        f"🟢 **Durum:** Çalışıyor\n"
        f"🎯 **Aktif Sinyal:** {aktif_sinyal}\n"
        f"📊 **Takip:** {len(martingale_trackers)} sinyal\n"
        f"📈 **Trend:** {color_trend[-5:] if color_trend else 'Yok'}\n"
        f"🕒 **Saat:** {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"⚡ **Sistem:** Basit Pattern + Martingale"
    )
    
    await event.reply(durum_mesaji)

@client.on(events.NewMessage(pattern='(?i)/temizle'))
async def handle_temizle(event):
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Yetkiniz yok!")
        return
        
    global color_trend, recent_games, is_signal_active
    color_trend = []
    recent_games = []
    
    await event.reply("✅ Trend verileri temizlendi!")

# ==============================================================================
# BOT BAŞLATMA
# ==============================================================================
if __name__ == '__main__':
    print("🤖 ROYAL BACCARAT BOT BAŞLATILIYOR...")
    print(f"🔧 API_ID: {API_ID}")
    print(f"🎯 Kaynak Kanal: {KANAL_KAYNAK_ID}")
    print(f"📤 Hedef Kanal: {KANAL_HEDEF}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("⏳ Bağlantı kuruluyor...")
    
    try:
        with client:
            client.run_until_disconnected()
    except KeyboardInterrupt:
        print("\n👋 Bot kapatılıyor...")
    except Exception as e:
        print(f"❌ Bot başlatma hatası: {e}")
