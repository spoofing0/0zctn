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
MAX_MARTINGALE_STEPS = 3  # 🎯 4 ADIM (0,1,2,3) - SENİN İSTEDİĞİN GİBİ!
MAX_GAME_NUMBER = 1440
is_signal_active = False

# Yeni: Tamamlanmamış oyunları takip
watched_incomplete = {}

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

# ==============================================================================
# YENİ EKLENEN FONKSİYONLAR - OK TAKİBİ
# ==============================================================================

def is_arrow_on_player_side(text):
    """Ok işaretinin hangi tarafta olduğunu tespit eder"""
    if '▶️' not in text:
        return False, False
    
    # Metni parçalara ayır ve ok işaretinin konumunu bul
    parts = text.split('▶️')
    if len(parts) < 2:
        return False, False
    
    # Ok işaretinden önceki kısımda oyuncu kartları var mı?
    before_arrow = parts[0]
    player_arrow = '(' in before_arrow and ')' in before_arrow
    
    # Ok işaretinden sonraki kısımda banker kartları var mı?
    after_arrow = parts[1]
    banker_arrow = '(' in after_arrow and ')' in after_arrow
    
    return player_arrow, banker_arrow

def extract_player_suits(text):
    """Oyuncu kartlarındaki suit'leri çıkarır"""
    # Oyuncu kartlarını bul (ilk parantez içi)
    player_match = re.search(r'\((.*?)\)', text)
    if player_match:
        player_cards = player_match.group(1)
        # Tüm suit'leri bul
        suits = re.findall(r'[♣♦♥♠]', player_cards)
        return suits
    return []

# ==============================================================================
# MEVCUT FONKSİYONLAR (GÜNCELLENDİ)
# ==============================================================================

def get_baccarat_value(card_char):
    if card_char == '10': return 10
    if card_char in 'AKQJ2T': return 0
    elif card_char.isdigit(): return int(card_char)
    return -1

def get_next_game_number(current_game_num):
    next_num = current_game_num + 1
    return 1 if next_num > MAX_GAME_NUMBER else next_num

def extract_largest_value_suit(cards_str):
    cards = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', cards_str)
    if not cards or len(cards) < 2: return None

    max_value = -1
    largest_value_suit = None
    values = [get_baccarat_value(card[0]) for card in cards]
    
    if len(values) == 2 and values[0] == values[1]: return None

    for card_char, suit in cards:
        value = get_baccarat_value(card_char)
        if value > max_value:
            max_value = value
            largest_value_suit = suit

    return None if max_value == 0 else largest_value_suit

def extract_game_info_from_message(text):
    game_info = {
        'game_number': None, 'player_cards': '', 'banker_cards': '',
        'is_final': False, 'patterns': [], 'pattern_strength': 0,
        'arrow_player': False, 'arrow_banker': False
    }
    
    # Ok konumunu tespit et
    game_info['arrow_player'], game_info['arrow_banker'] = is_arrow_on_player_side(text)
    
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
    if performance_stats['consecutive_losses'] >= 3:
        return False, "3+ ardışık kayıp - sistem durduruldu"
    
    # YENİ: Sadece banker tarafında ok varsa veya finalse işlem yap
    if not game_info['arrow_banker'] and not game_info['is_final']:
        return False, "Banker tarafında ok yok ve final değil"
    
    if not game_info['patterns']: 
        return False, "Güçlü pattern yok"
    
    signal_suit = extract_largest_value_suit(game_info['player_cards'])
    return (True, signal_suit) if signal_suit else (False, "Uygun kart yok")

async def process_bet(game_num, msg, suits):
    """Yeni: Banker tarafında ok varsa işlem yap"""
    if performance_stats['consecutive_losses'] >= 3:
        return
    
    game_info = extract_game_info_from_message(msg.text)
    if not game_info['patterns']:
        return
    
    should_send, reason = should_send_signal(game_info)
    if should_send:
        next_game_num = get_next_game_number(game_num)
        await send_optimized_signal(next_game_num, reason, game_info)

async def send_optimized_signal(game_num, signal_suit, game_info):
    global is_signal_active, performance_stats
    if is_signal_active: return
    
    performance_stats['total_signals'] += 1
    performance_stats['last_signal'] = datetime.now().strftime('%H:%M:%S')
    
    signal_type = "⚡ YÜKSEK GÜVEN" if game_info['pattern_strength'] >= 3 else "🔸 ORTA GÜVEN"
    signal_full_text = f"**#N{game_num} - Oyuncu {signal_suit} - {MAX_MARTINGALE_STEPS}D - {signal_type}**"

    try:
        sent_message = await client.send_message(KANAL_HEDEF, signal_full_text)
        print(f"🎯 SİNYAL: {signal_full_text} | Ok: Banker | Martingale: {MAX_MARTINGALE_STEPS} adım")
        martingale_trackers[game_num] = {
            'message_obj': sent_message, 'step': 0, 'signal_suit': signal_suit,
            'sent_game_number': game_num, 'expected_game_number_for_check': game_num
        }
        is_signal_active = True
    except Exception as e: 
        print(f"Sinyal hatası: {e}")

async def check_martingale_trackers():
    global martingale_trackers, is_signal_active, performance_stats
    trackers_to_remove = []

    for signal_game_num, tracker_info in list(martingale_trackers.items()):
        current_step = tracker_info['step']
        game_to_check = tracker_info['expected_game_number_for_check']
        
        if game_to_check not in game_results: continue
        result_info = game_results.get(game_to_check)
        if not result_info['is_final']: continue
        
        player_cards_str = result_info['player_cards']
        signal_won = bool(re.search(re.escape(tracker_info['signal_suit']), player_cards_str))
        
        if signal_won:
            performance_stats['wins'] += 1
            performance_stats['consecutive_losses'] = 0
            win_text = f"**#N{signal_game_num} - {tracker_info['signal_suit']} | ✅ {current_step}️⃣**"
            try: await tracker_info['message_obj'].edit(win_text)
            except: pass
            trackers_to_remove.append(signal_game_num)
            is_signal_active = False
            print(f"🎯 Sinyal #{signal_game_num} {current_step}. adımda KAZANDI!")
        else:
            if current_step < MAX_MARTINGALE_STEPS:
                tracker_info['step'] += 1
                tracker_info['expected_game_number_for_check'] = get_next_game_number(game_to_check)
                try: 
                    await tracker_info['message_obj'].edit(f"**#N{signal_game_num} - {tracker_info['signal_suit']} - {MAX_MARTINGALE_STEPS}D | 🔄 {tracker_info['step']}️⃣**")
                    print(f"🔄 Sinyal #{signal_game_num} {current_step}. adımda kaybetti. {tracker_info['step']}. adıma geçiliyor.")
                except: pass
            else:
                performance_stats['losses'] += 1
                performance_stats['consecutive_losses'] += 1
                try: 
                    await tracker_info['message_obj'].edit(f"**#N{signal_game_num} - {tracker_info['signal_suit']} | ❌**")
                    print(f"💥 Sinyal #{signal_game_num} {MAX_MARTINGALE_STEPS}. adımda kaybetti. SERİ BİTTİ.")
                except: pass
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False

    for game_num in trackers_to_remove:
        martingale_trackers.pop(game_num, None)

# ==============================================================================
# YENİ TELEGRAM EVENT'LERİ - OK TAKİBİ
# ==============================================================================

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
async def on_new_message(event):
    """Yeni mesajlarda ok konumunu takip et"""
    msg = event.message
    if not msg.text:
        return

    # Oyun numarasını bul
    game_match = re.search(r'#N(\d+)', msg.text)
    game_num = int(game_match.group(1)) if game_match else 0

    # Oyuncu kartları var mı?
    if re.search(r'\(([^)]+)\)', msg.text):
        arrow_player, arrow_banker = is_arrow_on_player_side(msg.text)

        # 👉 Banker tarafındaysa işlem yap
        if arrow_banker:
            suits = extract_player_suits(msg.text)
            if suits:
                print(f"[PROCESS] 🎯 #N{game_num} tamamlandı (👉 banker tarafında)")
                await process_bet(game_num, msg, suits)
        else:
            # 👉 Oyuncu tarafında → bekle
            watched_incomplete[msg.id] = (game_num, msg)
            print(f"[WAIT] ⏳ #N{game_num} 👉 oyuncu kart açıyor, bekleniyor...")

@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def on_message_edited(event):
    """Düzenlenen mesajlarda ok konum değişikliğini takip et"""
    msg = event.message
    if not msg.text:
        return

    # Eğer bu mesaj beklenen listesindeyse kontrol et
    if msg.id in watched_incomplete:
        arrow_player, arrow_banker = is_arrow_on_player_side(msg.text)
        if arrow_banker:
            suits = extract_player_suits(msg.text)
            if suits:
                game_num, original_msg = watched_incomplete[msg.id]
                await process_bet(game_num, msg, suits)
                del watched_incomplete[msg.id]
                print(f"[EDIT] ✅ #N{game_num} banker tarafına geçti → sonuç işlendi.")

# ==============================================================================
# MEVCUT TELEGRAM KOMUTLARI
# ==============================================================================

@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    await event.reply("""
🤖 **Baccarat Bot Aktif** 🎰
🎯 **Martingale: 4 ADIM** (0,1,2,3)
🔍 **Yeni: Ok takibi aktif**

**Komutlar:**
/start, /stats, /status, /patterns, /active, /analysis
""")

@client.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    total = performance_stats['wins'] + performance_stats['losses']
    win_rate = (performance_stats['wins'] / total * 100) if total > 0 else 0
    await event.reply(f"""
📊 **İstatistikler:**
├─ Sinyal: {performance_stats['total_signals']}
├─ Kazanç: {performance_stats['wins']} 
├─ Kayıp: {performance_stats['losses']}
├─ Oran: {win_rate:.1f}%
├─ Ardışık Kayıp: {performance_stats['consecutive_losses']}
├─ Martingale: {MAX_MARTINGALE_STEPS} adım
└─ Bekleyen: {len(watched_incomplete)} oyun
""")

@client.on(events.NewMessage(pattern='/analysis'))
async def analysis_command(event):
    status = "🔴 DURDURULDU" if performance_stats['consecutive_losses'] >= 50 else "🟢 AKTİF"
    await event.reply(f"""
📈 **Detaylı Analiz:**
├─ Durum: {status}
├─ Ardışık Kayıp: {performance_stats['consecutive_losses']}/50
├─ Maks Kayıp: {performance_stats['max_consecutive_losses']}
├─ Son Sinyal: {performance_stats['last_signal'] or 'Yok'}
├─ Martingale: {MAX_MARTINGALE_STEPS} adım
└─ Bekleyen: {len(watched_incomplete)} oyun
""")

@client.on(events.NewMessage(pattern='/status'))
async def status_command(event):
    await event.reply(f"""
🟢 **Bot Çalışıyor**
├─ Aktif Sinyal: {'✅' if is_signal_active else '❌'}
├─ Takip: {len(martingale_trackers)} sinyal
├─ Ardışık Kayıp: {performance_stats['consecutive_losses']}
├─ Martingale: {MAX_MARTINGALE_STEPS} adım
└─ Bekleyen: {len(watched_incomplete)} oyun
""")

@client.on(events.NewMessage(pattern='/patterns'))
async def patterns_command(event):
    await event.reply("""
🎯 **Aktif Patternler:**
#C2_3, #C3_2, #C3_3

🔍 **Özellikler:**
├─ Martingale: 4 adım (0,1,2,3)
├─ Ok takibi: Aktif
├─ Otomatik koruma: 3 kayıpta durur
└─ Pattern: Sadece güçlü 3 pattern
""")

@client.on(events.NewMessage(pattern='/active'))
async def active_command(event):
    if performance_stats['consecutive_losses'] >= 50:
        await event.reply("🔴 SİSTEM DURDURULDU - 3+ ardışık kayıp")
    elif is_signal_active:
        active_list = "\n".join([f"├─ #N{num} - {t['signal_suit']} (Adım {t['step']})" for num, t in martingale_trackers.items()])
        await event.reply(f"🔴 **AKTİF SİNYAL:**\n{active_list}\n└─ Toplam: {len(martingale_trackers)} sinyal")
    else:
        await event.reply(f"🟢 **Aktif sinyal yok**\n└─ Bekleyen: {len(watched_incomplete)} oyun")

if __name__ == '__main__':
    print("🤖 BACCARAT BOT BAŞLATILIYOR...")
    print(f"🎯 Martingale: {MAX_MARTINGALE_STEPS} adım (0,1,2,3)")
    print("🔍 Ok takibi: AKTİF")
    print("🛡️  Otomatik koruma: AKTİF")
    print("📊 Komutlar: /start, /stats, /status, /patterns, /active, /analysis")
    print("=====================================")
    
    with client:
        client.run_until_disconnected()
