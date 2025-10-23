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
KANAL_HEDEF = \"@royalbaccfree\"

client = TelegramClient('pislik_bot', API_ID, API_HASH)

# ==============================================================================
# Global Değişkenler ve Takip Mekanizmaları
# ==============================================================================
game_results = {}
martingale_trackers = {}
MAX_MARTINGALE_STEPS = 3  # 3 adım (0,1,2)
MAX_GAME_NUMBER = 1440
is_signal_active = False

# ✅ YENİ: Tamamlanmamış oyunları takip için
watched_incomplete = {}
trend_history = []

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
game_number_pattern = r'#N(\d+)|Game (\d+)'

# ==============================================================================
# Helper Functions
# ==============================================================================

def get_baccarat_value(card_char):
    \"\"\"Kart değerini hesapla\"\"\"
    if card_char == '10': 
        return 10
    if card_char in 'AKQJ2T': 
        return 0
    elif card_char.isdigit(): 
        return int(card_char)
    return -1

def get_next_game_number(current_game_num):
    \"\"\"Sonraki oyun numarasını al\"\"\"
    next_num = current_game_num + 1
    return 1 if next_num > MAX_GAME_NUMBER else next_num

def is_arrow_on_player_side(text):
    \"\"\"Ok işaretinin hangi tarafta olduğunu kontrol et\"\"\"
    # Oyuncu ve banker taraflarını bul
    player_match = re.search(r'Player.*?(\d+)\s+\((.*?)\)', text, re.DOTALL)
    banker_match = re.search(r'Banker.*?(\d+)\s+\((.*?)\)', text, re.DOTALL)
    
    if not player_match or not banker_match:
        return False, False
    
    player_section = player_match.group(2)
    banker_section = banker_match.group(2)
    
    # 👉 işaretini kontrol et
    arrow_on_player = '👉' in player_section
    arrow_on_banker = '👉' in banker_section
    
    return arrow_on_player, arrow_on_banker

def extract_player_suits(text):
    \"\"\"Oyuncu kartlarından suit'leri çıkar\"\"\"
    player_match = re.search(r'Player.*?\d+\s+\((.*?)\)', text, re.DOTALL)
    if not player_match:
        return None
    
    player_cards = player_match.group(1)
    # Kartları çıkar (10, A-K, suit sembolleri)
    cards = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
    return [suit for _, suit in cards] if cards else None

def extract_largest_value_suit(cards_str):
    \"\"\"En büyük değerli kartın suit'ini bul\"\"\"
    cards = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', cards_str)
    if not cards or len(cards) < 2: 
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

    return None if max_value == 0 else largest_value_suit

def extract_game_info_from_message(text):
    \"\"\"Mesajdan oyun bilgilerini çıkar\"\"\"
    game_info = {
        'game_number': None, 
        'player_cards': '', 
        'banker_cards': '',
        'is_final': False, 
        'patterns': [], 
        'pattern_strength': 0
    }
    
    # Pattern tespiti
    detected_patterns = [p for p in STRONG_PATTERNS if p in text]
    game_info['patterns'] = detected_patterns
    game_info['pattern_strength'] = len(detected_patterns) * 3

    # Oyun bilgilerini çıkar
    game_match = re.search(r'#N(\d+)\s+.*?\((.*?)\)\s+.*?(\d+\s+\(.*\))', text.replace('️', ''), re.DOTALL)
    if game_match:
        game_info['game_number'] = int(game_match.group(1))
        game_info['player_cards'] = game_match.group(2)
        game_info['banker_cards'] = game_match.group(3)
        if any(indicator in text for indicator in ['✅', '🔰', '#X']):
            game_info['is_final'] = True
    
    return game_info

def should_send_signal(game_info):
    \"\"\"Sinyal gönderilmeli mi kontrol et\"\"\"
    if performance_stats['consecutive_losses'] >= 3:
        return False, \"3+ ardışık kayıp - sistem durduruldu\"
    if not game_info['patterns']: 
        return False, \"Güçlü pattern yok\"
    if not game_info['is_final']: 
        return False, \"Final değil\"
    
    signal_suit = extract_largest_value_suit(game_info['player_cards'])
    return (True, signal_suit) if signal_suit else (False, \"Uygun kart yok\")

async def process_bet(game_num, msg, suits):
    \"\"\"Bahis işlemini yap\"\"\"
    card_count = len(suits)
    print(f\"[PROCESS] 🎯 #N{game_num} - {card_count} kart işlendi\")
    
    # Game results'a ekle
    game_info = extract_game_info_from_message(msg.text)
    if game_info['game_number']:
        game_results[game_info['game_number']] = game_info
    
    await check_martingale_trackers()
    
    if not is_signal_active:
        should_send, reason = should_send_signal(game_info)
        if should_send:
            next_game_num = get_next_game_number(game_info['game_number'])
            await send_optimized_signal(next_game_num, reason, game_info)

# ==============================================================================
# Signal Management
# ==============================================================================

async def send_optimized_signal(game_num, signal_suit, game_info):
    \"\"\"Optimize edilmiş sinyal gönder\"\"\"
    global is_signal_active, performance_stats
    if is_signal_active: 
        return
    
    performance_stats['total_signals'] += 1
    performance_stats['last_signal'] = datetime.now().strftime('%H:%M:%S')
    
    signal_type = \"⚡ YÜKSEK GÜVEN\" if game_info['pattern_strength'] >= 3 else \"🔸 ORTA GÜVEN\"
    signal_full_text = f\"**#N{game_num} - Oyuncu {signal_suit} - {MAX_MARTINGALE_STEPS}D - {signal_type}**\"

    try:
        sent_message = await client.send_message(KANAL_HEDEF, signal_full_text)
        print(f\"🎯 SİNYAL: {signal_full_text}\")
        martingale_trackers[game_num] = {
            'message_obj': sent_message, 
            'step': 0, 
            'signal_suit': signal_suit,
            'sent_game_number': game_num, 
            'expected_game_number_for_check': game_num
        }
        is_signal_active = True
    except Exception as e: 
        print(f\"❌ Sinyal hatası: {e}\")

async def check_martingale_trackers():
    \"\"\"Martingale takipçilerini kontrol et\"\"\"
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
            win_text = f\"**#N{signal_game_num} - {tracker_info['signal_suit']} | ✅ {current_step}️⃣**\"
            try: 
                await tracker_info['message_obj'].edit(win_text)
            except: 
                pass
            trackers_to_remove.append(signal_game_num)
            is_signal_active = False
            print(f\"✅ KAZANÇ: #N{signal_game_num}\")
        else:
            if current_step < MAX_MARTINGALE_STEPS:
                tracker_info['step'] += 1
                tracker_info['expected_game_number_for_check'] = get_next_game_number(game_to_check)
                try: 
                    await tracker_info['message_obj'].edit(
                        f\"**#N{signal_game_num} - {tracker_info['signal_suit']} - {MAX_MARTINGALE_STEPS}D | 🔄 {tracker_info['step']}️⃣**\"
                    )
                except: 
                    pass
                print(f\"🔄 Martingale Adım {tracker_info['step']}: #N{signal_game_num}\")
            else:
                performance_stats['losses'] += 1
                performance_stats['consecutive_losses'] += 1
                if performance_stats['consecutive_losses'] > performance_stats['max_consecutive_losses']:
                    performance_stats['max_consecutive_losses'] = performance_stats['consecutive_losses']
                try: 
                    await tracker_info['message_obj'].edit(
                        f\"**#N{signal_game_num} - {tracker_info['signal_suit']} | ❌**\"
                    )
                except: 
                    pass
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False
                print(f\"❌ KAYIP: #N{signal_game_num}\")

    for game_num in trackers_to_remove:
        martingale_trackers.pop(game_num, None)

# ==============================================================================
# ✅ TELEGRAM EVENT HANDLERS - YENİ ENTEGRASYON
# ==============================================================================

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
async def on_new_message(event):
    \"\"\"Yeni mesaj geldiğinde tetiklenir\"\"\"
    msg = event.message
    if not msg.text:
        return

    # Oyun numarasını çıkar
    games = [int(m1 or m2) for m1, m2 in re.findall(game_number_pattern, msg.text)]
    game_num = games[0] if games else 0

    if not game_num:
        return

    # Parantez içi içerik var mı kontrol et
    if re.search(r'\(([^)]+)\)', msg.text):
        arrow_player, arrow_banker = is_arrow_on_player_side(msg.text)

        # 👉 sağ taraftaysa banker tarafı → işlem yapılabilir
        if arrow_banker:
            suits = extract_player_suits(msg.text)
            if suits:
                card_count = len(suits)
                trend_history.append(card_count)
                print(f\"[PROCESS] 🎯 #N{game_num} tamamlandı (👉 banker tarafında)\")
                await process_bet(game_num, msg, suits)
        else:
            # 👉 oyuncu tarafında → bekle
            watched_incomplete[msg.id] = (game_num, msg)
            print(f\"[WAIT] ⏳ #N{game_num} 👉 oyuncu kart açıyor, bekleniyor...\")

# ✅ YENİ ENTEGRASYON: Mesaj düzenlenince banker tarafına geçtiyse işle
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def on_message_edited(event):
    \"\"\"Mesaj düzenlendiğinde tetiklenir\"\"\"
    msg = event.message
    if not msg.text:
        return

    games = [int(m1 or m2) for m1, m2 in re.findall(game_number_pattern, msg.text)]
    game_num = games[0] if games else 0

    if msg.id in watched_incomplete:
        arrow_player, arrow_banker = is_arrow_on_player_side(msg.text)
        if arrow_banker:
            suits = extract_player_suits(msg.text)
            if suits:
                card_count = len(suits)
                trend_history.append(card_count)
                await process_bet(game_num, msg, suits)
                del watched_incomplete[msg.id]
                print(f\"[EDIT] ✅ #N{game_num} banker tarafına geçti → sonuç işlendi.\")

# ==============================================================================
# TELEGRAM KOMUTLARI
# ==============================================================================

@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    \"\"\"Bot başlatma komutu\"\"\"
    await event.reply(\"\"\"
🤖 **Baccarat Bot Aktif** 🎰

📋 **Komutlar:**
• /start - Botu başlat
• /help - Yardım menüsü
• /stats - İstatistikler
• /status - Bot durumu
• /patterns - Aktif patternler
• /active - Aktif sinyaller
• /analysis - Detaylı analiz

🎯 **Strateji:** 
3 adım Martingale + Sadece güçlü patternler
\"\"\")

@client.on(events.NewMessage(pattern='/help'))
async def help_command(event):
    \"\"\"Yardım komutu\"\"\"
    await event.reply(\"\"\"
ℹ️ **Yardım Menüsü**

Bot, güçlü pattern'leri tespit eder ve Martingale stratejisiyle sinyal gönderir.

**Nasıl çalışır?**
1. Kaynak kanaldan mesajları takip eder
2. #C2_3, #C3_2, #C3_3 patternlerini arar
3. Uygun durumlarda sinyal gönderir
4. 3 adımlı Martingale ile takip eder

**Güvenlik:**
• 3 ardışık kayıptan sonra durdurulur
• Sadece güçlü patternlerde sinyal verir
\"\"\")

@client.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    \"\"\"İstatistik komutu\"\"\"
    total = performance_stats['wins'] + performance_stats['losses']
    win_rate = (performance_stats['wins'] / total * 100) if total > 0 else 0
    await event.reply(f\"\"\"
📊 **İstatistikler:**

📈 Toplam Sinyal: {performance_stats['total_signals']}
✅ Kazanç: {performance_stats['wins']}
❌ Kayıp: {performance_stats['losses']}
📊 Başarı Oranı: {win_rate:.1f}%
🔄 Ardışık Kayıp: {performance_stats['consecutive_losses']}
📉 Max Ardışık Kayıp: {performance_stats['max_consecutive_losses']}
🕐 Aktif Since: {performance_stats['active_since']}
⏱️ Son Sinyal: {performance_stats['last_signal'] or 'Yok'}
\"\"\")

@client.on(events.NewMessage(pattern='/analysis'))
async def analysis_command(event):
    \"\"\"Analiz komutu\"\"\"
    status = \"🔴 DURDURULDU\" if performance_stats['consecutive_losses'] >= 3 else \"🟢 AKTİF\"
    await event.reply(f\"\"\"
📈 **Detaylı Analiz:**

🚦 Durum: {status}
🔄 Ardışık Kayıp: {performance_stats['consecutive_losses']}/3
📉 Max Ardışık Kayıp: {performance_stats['max_consecutive_losses']}
⏱️ Son Sinyal: {performance_stats['last_signal'] or 'Yok'}
📊 Aktif Takip: {len(martingale_trackers)} sinyal
⏳ Bekleyen: {len(watched_incomplete)} oyun

**Trend Geçmişi:**
Son 10 kart sayısı: {trend_history[-10:] if trend_history else 'Yok'}
\"\"\")

@client.on(events.NewMessage(pattern='/status'))
async def status_command(event):
    \"\"\"Durum komutu\"\"\"
    await event.reply(f\"\"\"
🟢 **Bot Çalışıyor**

🎯 Aktif Sinyal: {'✅ Evet' if is_signal_active else '❌ Hayır'}
📊 Takip Edilen: {len(martingale_trackers)} sinyal
⏳ Bekleyen Oyun: {len(watched_incomplete)} oyun
🔄 Ardışık Kayıp: {performance_stats['consecutive_losses']}/3
\"\"\")

@client.on(events.NewMessage(pattern='/patterns'))
async def patterns_command(event):
    \"\"\"Pattern komutu\"\"\"
    await event.reply(\"\"\"
🎯 **Aktif Patternler:**

✅ #C2_3
✅ #C3_2  
✅ #C3_3

Bu patternler tespit edildiğinde sinyal gönderilir.
\"\"\")

@client.on(events.NewMessage(pattern='/active'))
async def active_command(event):
    \"\"\"Aktif sinyal komutu\"\"\"
    if performance_stats['consecutive_losses'] >= 3:
        await event.reply(\"🔴 **SİSTEM DURDURULDU**\n\n3+ ardışık kayıp nedeniyle sistem güvenlik modunda.\")
    elif is_signal_active and martingale_trackers:
        active_list = \"\n\".join([
            f\"#N{num} - {t['signal_suit']} (Adım {t['step']})\" 
            for num, t in martingale_trackers.items()
        ])
        await event.reply(f\"🔴 **AKTİF SİNYALLER:**\n\n{active_list}\")
    else:
        await event.reply(\"🟢 **Aktif sinyal yok**\n\nYeni fırsatlar bekleniyor...\")

# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == '__main__':
    print(\"=\" * 60)
    print(\"🤖 Baccarat Bot Başlatılıyor...\")
    print(\"=\" * 60)
    print(f\"📡 Kaynak Kanal ID: {KANAL_KAYNAK_ID}\")
    print(f\"📤 Hedef Kanal: {KANAL_HEDEF}\")
    print(f\"🎯 Max Martingale Adımı: {MAX_MARTINGALE_STEPS + 1}\")
    print(f\"🔍 Takip Edilen Patternler: {', '.join(STRONG_PATTERNS)}\")
    print(\"=\" * 60)
    print(\"✅ Bot aktif! Mesajlar bekleniyor...\")
    print(\"=\" * 60)
    
    with client:
        client.run_until_disconnected()
"
Observation: Create successful: /app/backend/telegram_bot.py
