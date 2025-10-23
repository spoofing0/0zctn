import re
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
import asyncio
import sys
from datetime import datetime

# ==============================================================================
# Telegram API Bilgileri ve Kanal Ayarları
# ==============================================================================
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'

# --- Kanal Bilgileri ---
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"

client = TelegramClient('rat_bot', API_ID, API_HASH)

# ==============================================================================
# Global Değişkenler ve Takip Mekanizmaları
# ==============================================================================
game_results = {}
martingale_trackers = {}
watched_incomplete = {}
MAX_MARTINGALE_STEPS = 2
MAX_GAME_NUMBER = 1440
is_signal_active = False

# İstatistikler
performance_stats = {
    'total_signals': 0,
    'wins': 0,
    'losses': 0,
    'active_since': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'last_signal': None,
    'consecutive_losses': 0,
    'max_consecutive_losses': 0
}

# Pattern tanımları
STRONG_PATTERNS = ['#C2_3', '#C3_2', '#C3_3']

def is_arrow_on_player_side(text):
    try:
        if '👉' not in text:
            return False, False
            
        parts = re.split(r'[()]', text)
        if len(parts) < 3:
            return False, False
            
        player_section = parts[0] + parts[1]
        banker_section = parts[2]
        
        arrow_player = '👉' in player_section
        arrow_banker = '👉' in banker_section
        
        return arrow_player, arrow_banker
    except Exception as e:
        print(f"Ok tespit hatası: {e}")
        return False, False

def extract_player_suits(text):
    try:
        player_match = re.search(r'\((.*?)\)', text)
        if not player_match:
            return []
        
        player_cards = player_match.group(1)
        suits = re.findall(r'[♣♦♥♠]', player_cards)
        return suits
    except Exception as e:
        print(f"Suit çıkarma hatası: {e}")
        return []

def get_baccarat_value(card_char):
    if card_char == '10': return 10
    if card_char in 'AKQJ2T': return 0
    elif card_char.isdigit(): return int(card_char)
    return -1

def get_next_game_number(current_game_num):
    next_num = current_game_num + 1
    return 1 if next_num > MAX_GAME_NUMBER else next_num

def extract_largest_value_suit(cards_str):
    try:
        cards = re.findall(r'(\d+|[A-Z])([♣♦♥♠])', cards_str)
        if not cards or len(cards) < 2: 
            return None

        max_value = -1
        largest_value_suit = None
        values = [get_baccarat_value(card[0]) for card in cards]
        
        if all(v == 0 for v in values):
            return None

        for card_char, suit in cards:
            value = get_baccarat_value(card_char)
            if value > max_value:
                max_value = value
                largest_value_suit = suit

        return largest_value_suit
    except Exception as e:
        print(f"Kart değeri çıkarma hatası: {e}")
        return None

def extract_game_info_from_message(text):
    game_info = {
        'game_number': None, 'player_cards': '', 'banker_cards': '',
        'is_final': False, 'patterns': [], 'pattern_strength': 0,
        'arrow_on_player': False, 'arrow_on_banker': False,
        'raw_text': text
    }
    
    try:
        # Oyun numarasını çıkar - TÜM FORMATLARI DENE
        game_num_match = re.search(r'#N(\d+)', text)
        if not game_num_match:
            game_num_match = re.search(r'No\s*:\s*(\d+)', text)
        
        if game_num_match:
            game_info['game_number'] = int(game_num_match.group(1))
            print(f"🔢 Oyun numarası bulundu: #{game_info['game_number']}")

        # Pattern tespiti
        detected_patterns = [p for p in STRONG_PATTERNS if p in text]
        game_info['patterns'] = detected_patterns
        game_info['pattern_strength'] = len(detected_patterns) * 3

        # Ok tespiti
        arrow_player, arrow_banker = is_arrow_on_player_side(text)
        game_info['arrow_on_player'] = arrow_player
        game_info['arrow_on_banker'] = arrow_banker

        # Oyun bilgilerini çıkar
        player_match = re.search(r'\((.*?)\)', text)
        if player_match:
            game_info['player_cards'] = player_match.group(1)
            print(f"🎴 Oyuncu kartları: {game_info['player_cards']}")

        banker_match = re.search(r'\((.*?)\)', text[text.find(')')+1:] if ')' in text else text)
        if banker_match:
            game_info['banker_cards'] = banker_match.group(1)
            print(f"🎴 Banker kartları: {game_info['banker_cards']}")

        # Final kontrolü
        if any(indicator in text for indicator in ['✅', '🔰', '#X']) or arrow_banker:
            game_info['is_final'] = True
            print(f"🏁 Final sonucu: {game_info['is_final']}")
        
        return game_info
    except Exception as e:
        print(f"Oyun bilgisi çıkarma hatası: {e}")
        return game_info

async def process_bet(game_num, msg, suits):
    global is_signal_active, performance_stats
    
    if performance_stats['consecutive_losses'] >= 3:
        print(f"❌ Sistem durduruldu - ardışık kayıp: {performance_stats['consecutive_losses']}")
        return
    
    if is_signal_active:
        print("❌ Zaten aktif sinyal var")
        return
    
    game_info = extract_game_info_from_message(msg.text)
    if not game_info['game_number']:
        print("❌ Oyun numarası bulunamadı")
        return
    
    print(f"🔍 Oyun #{game_info['game_number']} analiz ediliyor - Patternler: {game_info['patterns']}")
    
    should_send, reason = should_send_signal(game_info)
    if should_send:
        next_game_num = get_next_game_number(game_num)
        print(f"🎯 Sinyal gönderiliyor: #{next_game_num} - Sebep: {reason}")
        await send_optimized_signal(next_game_num, reason, game_info)
    else:
        print(f"❌ Sinyal gönderilmedi: {reason}")

def should_send_signal(game_info):
    if performance_stats['consecutive_losses'] >= 3:
        return False, "3+ ardışık kayıp - sistem durduruldu"
    if not game_info['patterns']: 
        return False, "Güçlü pattern yok"
    if not game_info['is_final']: 
        return False, "Final değil"
    
    signal_suit = extract_largest_value_suit(game_info['player_cards'])
    return (True, signal_suit) if signal_suit else (False, "Uygun kart yok")

async def send_optimized_signal(game_num, signal_suit, game_info):
    global is_signal_active, performance_stats
    if is_signal_active: 
        return
    
    performance_stats['total_signals'] += 1
    performance_stats['last_signal'] = datetime.now().strftime('%H:%M:%S')
    
    signal_type = "⚡ YÜKSEK GÜVEN" if game_info['pattern_strength'] >= 3 else "🔸 ORTA GÜVEN"
    signal_full_text = f"**#N{game_num} - Oyuncu {signal_suit} - {MAX_MARTINGALE_STEPS}D - {signal_type}**"

    try:
        sent_message = await client.send_message(KANAL_HEDEF, signal_full_text)
        print(f"✅ SİNYAL GÖNDERİLDİ: {signal_full_text}")
        martingale_trackers[game_num] = {
            'message_obj': sent_message, 'step': 0, 'signal_suit': signal_suit,
            'sent_game_number': game_num, 'expected_game_number_for_check': game_num
        }
        is_signal_active = True
    except Exception as e: 
        print(f"❌ Sinyal hatası: {e}")

async def check_martingale_trackers():
    global martingale_trackers, is_signal_active, performance_stats
    trackers_to_remove = []

    for signal_game_num, tracker_info in list(martingale_trackers.items()):
        current_step = tracker_info['step']
        game_to_check = tracker_info['expected_game_number_for_check']
        
        if game_to_check not in game_results: 
            continue
            
        result_info = game_results.get(game_to_check)
        if not result_info['is_final']: 
            continue
        
        player_cards_str = result_info['player_cards']
        signal_won = bool(re.search(re.escape(tracker_info['signal_suit']), player_cards_str))
        
        if signal_won:
            performance_stats['wins'] += 1
            performance_stats['consecutive_losses'] = 0
            win_text = f"**#N{signal_game_num} - {tracker_info['signal_suit']} | ✅ {current_step}️⃣**"
            try: 
                await tracker_info['message_obj'].edit(win_text)
                print(f"✅ KAZANÇ: #{signal_game_num} - Adım {current_step}")
            except Exception as e: 
                print(f"Mesaj düzenleme hatası: {e}")
            trackers_to_remove.append(signal_game_num)
            is_signal_active = False
        else:
            if current_step < MAX_MARTINGALE_STEPS:
                tracker_info['step'] += 1
                tracker_info['expected_game_number_for_check'] = get_next_game_number(game_to_check)
                try: 
                    await tracker_info['message_obj'].edit(f"**#N{signal_game_num} - {tracker_info['signal_suit']} - {MAX_MARTINGALE_STEPS}D | 🔄 {tracker_info['step']}️⃣**")
                    print(f"🔄 MARTINGALE: #{signal_game_num} - Adım {tracker_info['step']}")
                except Exception as e: 
                    print(f"Mesaj düzenleme hatası: {e}")
            else:
                performance_stats['losses'] += 1
                performance_stats['consecutive_losses'] += 1
                if performance_stats['consecutive_losses'] > performance_stats['max_consecutive_losses']:
                    performance_stats['max_consecutive_losses'] = performance_stats['consecutive_losses']
                try: 
                    await tracker_info['message_obj'].edit(f"**#N{signal_game_num} - {tracker_info['signal_suit']} | ❌**")
                    print(f"❌ KAYIP: #{signal_game_num}")
                except Exception as e: 
                    print(f"Mesaj düzenleme hatası: {e}")
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False

    for game_num in trackers_to_remove:
        martingale_trackers.pop(game_num, None)

# ==================== TELEGRAM EVENT HANDLERS ====================

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
async def on_new_message(event):
    msg = event.message
    if not msg.text:
        return

    print(f"📥 YENİ MESAJ: {msg.text[:100]}...")

    try:
        # Oyun numarasını bul - TÜM FORMATLARI DENE
        game_num = 0
        game_num_match = re.search(r'#N(\d+)', msg.text)
        if not game_num_match:
            game_num_match = re.search(r'No\s*:\s*(\d+)', msg.text)
        
        if game_num_match:
            game_num = int(game_num_match.group(1))
            print(f"🔢 Oyun #{game_num} bulundu")
        else:
            print("❌ Oyun numarası bulunamadı")
            return

        # Oyun bilgilerini kaydet
        game_info = extract_game_info_from_message(msg.text)
        if game_info['game_number']:
            game_results[game_info['game_number']] = game_info
            print(f"💾 Oyun #{game_info['game_number']} kaydedildi")

        # Martingale kontrolü
        await check_martingale_trackers()

        # Ardışık kayıp kontrolü
        if performance_stats['consecutive_losses'] >= 3:
            print("🔴 Sistem durduruldu - 3+ ardışık kayıp")
            return

        # Kart kontrolü - parantez içinde kart varsa
        if re.search(r'\(([^)]+)\)', msg.text):
            arrow_player, arrow_banker = is_arrow_on_player_side(msg.text)
            print(f"📍 Ok konumu - Oyuncu: {arrow_player}, Banker: {arrow_banker}")

            # 👉 sağ taraftaysa banker tarafı → işlem yapılabilir
            if arrow_banker:
                suits = extract_player_suits(msg.text)
                if suits:
                    print(f"🎯 Banker tarafında - #{game_num} işleniyor...")
                    await process_bet(game_num, msg, suits)
                else:
                    print(f"❌ Suit bulunamadı - #{game_num}")
            else:
                # 👉 oyuncu tarafında → bekle
                watched_incomplete[msg.id] = (game_num, msg)
                print(f"⏳ Beklemede - #{game_num} oyuncu tarafında")
                
    except Exception as e:
        print(f"❌ Mesaj işleme hatası: {e}")

# ✅ Mesaj düzenlenince banker tarafına geçtiyse işle
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def on_message_edited(event):
    msg = event.message
    if not msg.text:
        return

    print(f"✏️ DÜZENLENEN MESAJ: {msg.text[:100]}...")

    try:
        # Oyun numarasını bul - TÜM FORMATLARI DENE
        game_num = 0
        game_num_match = re.search(r'#N(\d+)', msg.text)
        if not game_num_match:
            game_num_match = re.search(r'No\s*:\s*(\d+)', msg.text)
        
        if game_num_match:
            game_num = int(game_num_match.group(1))
        else:
            print("❌ Düzenlenen mesajda oyun numarası bulunamadı")
            return

        if msg.id in watched_incomplete:
            arrow_player, arrow_banker = is_arrow_on_player_side(msg.text)
            if arrow_banker:
                suits = extract_player_suits(msg.text)
                if suits:
                    await process_bet(game_num, msg, suits)
                    del watched_incomplete[msg.id]
                    print(f"✅ Düzenleme sonucu - #{game_num} banker tarafına geçti")
    except Exception as e:
        print(f"❌ Düzenlenen mesaj işleme hatası: {e}")

# Telegram Komutları
@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    await event.reply("""
🤖 **Baccarat Bot Aktif** 🎰
Komutlar: /start, /help, /stats, /status, /patterns, /active, /analysis
Strateji: 3 adım Martingale + Sadece güçlü patternler
""")

@client.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    total = performance_stats['wins'] + performance_stats['losses']
    win_rate = (performance_stats['wins'] / total * 100) if total > 0 else 0
    await event.reply(f"""
📊 **İstatistikler:**
Sinyal: {performance_stats['total_signals']}
Kazanç: {performance_stats['wins']} | Kayıp: {performance_stats['losses']}
Oran: {win_rate:.1f}%
Ardışık Kayıp: {performance_stats['consecutive_losses']}
""")

@client.on(events.NewMessage(pattern='/analysis'))
async def analysis_command(event):
    status = "🔴 DURDURULDU" if performance_stats['consecutive_losses'] >= 3 else "🟢 AKTİF"
    await event.reply(f"""
📈 **Analiz:**
Durum: {status}
Ardışık Kayıp: {performance_stats['consecutive_losses']}/3
Max Kayıp: {performance_stats['max_consecutive_losses']}
Son Sinyal: {performance_stats['last_signal'] or 'Yok'}
""")

@client.on(events.NewMessage(pattern='/status'))
async def status_command(event):
    await event.reply(f"""
🟢 **Bot Çalışıyor**
Aktif Sinyal: {'✅' if is_signal_active else '❌'}
Takip: {len(martingale_trackers)} sinyal
Ardışık Kayıp: {performance_stats['consecutive_losses']}
""")

@client.on(events.NewMessage(pattern='/patterns'))
async def patterns_command(event):
    await event.reply("""
🎯 **Aktif Patternler:**
#C2_3, #C3_2, #C3_3
""")

@client.on(events.NewMessage(pattern='/active'))
async def active_command(event):
    if performance_stats['consecutive_losses'] >= 3:
        await event.reply("🔴 SİSTEM DURDURULDU - 3+ ardışık kayıp")
    elif is_signal_active:
        active_list = "\n".join([f"#N{num} - {t['signal_suit']} (Adım {t['step']})" for num, t in martingale_trackers.items()])
        await event.reply(f"🔴 AKTİF SİNYAL:\n{active_list}")
    else:
        await event.reply("🟢 Aktif sinyal yok")

if __name__ == '__main__':
    print("🤖 Baccarat Bot Başlatılıyor...")
    print("📡 Kanallar:")
    print(f"   Kaynak: {KANAL_KAYNAK_ID}")
    print(f"   Hedef: {KANAL_HEDEF}")
    print("🎯 Patternler: #C2_3, #C3_2, #C3_3")
    print("⚡ Martingale: 3 adım")
    print("🔍 Oyun numarası formatları: #N, No:")
    
    with client:
        client.run_until_disconnected()
