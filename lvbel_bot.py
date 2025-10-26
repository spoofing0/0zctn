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
KANAL_KAYNAK_ID = -1001610392716  # 🆕 YENİ KANAL ID
KANAL_HEDEF = "@royalbaccfree"

client = TelegramClient('lvbel_bot', API_ID, API_HASH)

# ==============================================================================
# Global Değişkenler ve Takip Mekanizmaları
# ==============================================================================
game_results = {}
martingale_trackers = {}
MAX_MARTINGALE_STEPS = 6  # 7 adım (0,1,2,3,4,5,6)
MAX_GAME_NUMBER = 1440
is_signal_active = False
MAX_CONSECUTIVE_LOSSES = 5  # Maksimum ardışık kayıp limiti
COOLDOWN_AFTER_LOSS = 3     # Kayıptan sonra kaç oyun bekleyecek

# İstatistikler - SIFIRDAN BAŞLIYOR
performance_stats = {
    'total_signals': 0,
    'wins': 0,
    'losses': 0,
    'active_since': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'last_signal': None,
    'consecutive_losses': 0,
    'max_consecutive_losses': 0,
    'games_since_last_loss': 0,
    'cooldown_mode': False,
    'max_martingale_steps_reached': 0,
    'step_distribution': {i: 0 for i in range(1, MAX_MARTINGALE_STEPS + 2)}
}

# Pattern tanımları - GENİŞLETİLMİŞ 🆕
STRONG_PATTERNS = [
    '#C2_2', '#C2_3', '#C3_2', '#C3_3',  # Mevcut güçlü patternler
    '#R',    # Раздача - 2 kart dağıtımı (Oyuncu ve Banker 2'şer kart) 🆕
    '#X',    # Ничья - Beraberlik patterni 🆕
    '#П1',   # Победа Игрока - Oyuncu galibiyeti 🆕
]

PATTERN_STRENGTH = {
    '#C2_2': 3,
    '#C2_3': 4,
    '#C3_2': 4,
    '#C3_3': 5,
    '#R': 4,     # 2 kart dağıtımı - yüksek güvenilirlik 🆕
    '#X': 3,     # Beraberlik - orta güvenilirlik 🆕
    '#П1': 3,    # Oyuncu galibiyeti - orta güvenilirlik 🆕
}

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
    
    # Aynı değerde kartlar varsa sinyal verme
    if len(values) == 2 and values[0] == values[1]: return None
    # 3 kart durumunda en az 2 farklı değer olmalı
    if len(values) == 3 and len(set(values)) < 2: return None

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
        'has_strong_indicator': False
    }
    
    # Pattern tespiti - GENİŞLETİLMİŞ 🆕
    detected_patterns = [p for p in STRONG_PATTERNS if p in text]
    game_info['patterns'] = detected_patterns
    game_info['pattern_strength'] = sum(PATTERN_STRENGTH.get(p, 0) for p in detected_patterns)

    # Güçlü indikatör kontrolü - GENİŞLETİLMİŞ 🆕
    strong_indicators = ['✅', '🔰', '#X', '⭐', '🔥', '#R', '#П1']
    game_info['has_strong_indicator'] = any(indicator in text for indicator in strong_indicators)

    # Oyun bilgilerini çıkar
    game_match = re.search(r'#N(\d+)\s+.*?\((.*?)\)\s+.*?(\d+\s+\(.*\))', text.replace('️', ''), re.DOTALL)
    if game_match:
        game_info['game_number'] = int(game_match.group(1))
        game_info['player_cards'] = game_match.group(2)
        game_info['banker_cards'] = game_match.group(3)
        if game_info['has_strong_indicator']:
            game_info['is_final'] = True
    
    return game_info

def should_send_signal(game_info):
    # Cooldown modu kontrolü
    if performance_stats['cooldown_mode']:
        if performance_stats['games_since_last_loss'] >= COOLDOWN_AFTER_LOSS:
            performance_stats['cooldown_mode'] = False
            performance_stats['games_since_last_loss'] = 0
        else:
            return False, "Cooldown modu aktif"
    
    # Güvenlik kontrolleri
    if performance_stats['consecutive_losses'] >= MAX_CONSECUTIVE_LOSSES:
        return False, f"Maksimum {MAX_CONSECUTIVE_LOSSES} ardışık kayıp - sistem durduruldu"
    
    if not game_info['patterns']: 
        return False, "Güçlü pattern yok"
    
    if not game_info['is_final']: 
        return False, "Final değil"
    
    if game_info['pattern_strength'] < 4:  # Minimum pattern gücü
        return False, "Pattern gücü yetersiz"
    
    # Kart analizi
    signal_suit = extract_largest_value_suit(game_info['player_cards'])
    return (True, signal_suit) if signal_suit else (False, "Uygun kart yok")

async def send_optimized_signal(game_num, signal_suit, game_info):
    global is_signal_active, performance_stats
    if is_signal_active: 
        return
    
    performance_stats['total_signals'] += 1
    performance_stats['last_signal'] = datetime.now().strftime('%H:%M:%S')
    
    # Pattern gücüne göre sinyal tipi
    if game_info['pattern_strength'] >= 5:
        signal_type = "⚡ YÜKSEK GÜVEN"
    elif game_info['pattern_strength'] >= 4:
        signal_type = "🔸 ORTA GÜVEN"
    else:
        signal_type = "⚠️ DÜŞÜK GÜVEN"
    
    signal_full_text = f"**#N{game_num} - Oyuncu {signal_suit} - {MAX_MARTINGALE_STEPS+1}D - {signal_type}**"

    try:
        sent_message = await client.send_message(KANAL_HEDEF, signal_full_text)
        print(f"🎯 SİNYAL: {signal_full_text}")
        martingale_trackers[game_num] = {
            'message_obj': sent_message, 
            'step': 0, 
            'signal_suit': signal_suit,
            'sent_game_number': game_num, 
            'expected_game_number_for_check': game_num,
            'pattern_strength': game_info['pattern_strength']
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
        
        if game_to_check not in game_results: 
            continue
            
        result_info = game_results.get(game_to_check)
        if not result_info['is_final']: 
            continue
        
        player_cards_str = result_info['player_cards']
        signal_won = bool(re.search(re.escape(tracker_info['signal_suit']), player_cards_str))
        
        if signal_won:
            # Martingale adım istatistiklerini güncelle
            win_step = current_step + 1
            performance_stats['max_martingale_steps_reached'] = max(
                performance_stats['max_martingale_steps_reached'], 
                win_step
            )
            performance_stats['step_distribution'][win_step] += 1
            
            performance_stats['wins'] += 1
            performance_stats['consecutive_losses'] = 0
            win_text = f"**#N{signal_game_num} - {tracker_info['signal_suit']} | ✅ {win_step}️⃣**"
            try: 
                await tracker_info['message_obj'].edit(win_text)
            except Exception as e: 
                print(f"Mesaj düzenleme hatası: {e}")
            trackers_to_remove.append(signal_game_num)
            is_signal_active = False
        else:
            if current_step < MAX_MARTINGALE_STEPS:
                tracker_info['step'] += 1
                tracker_info['expected_game_number_for_check'] = get_next_game_number(game_to_check)
                next_step = tracker_info['step'] + 1
                try: 
                    await tracker_info['message_obj'].edit(
                        f"**#N{signal_game_num} - {tracker_info['signal_suit']} - {MAX_MARTINGALE_STEPS+1}D | 🔄 {next_step}️⃣**"
                    )
                except Exception as e: 
                    print(f"Mesaj düzenleme hatası: {e}")
            else:
                # Kayıp durumunda maksimum adımı güncelle
                performance_stats['max_martingale_steps_reached'] = max(
                    performance_stats['max_martingale_steps_reached'], 
                    MAX_MARTINGALE_STEPS + 1
                )
                
                performance_stats['losses'] += 1
                performance_stats['consecutive_losses'] += 1
                performance_stats['max_consecutive_losses'] = max(
                    performance_stats['max_consecutive_losses'], 
                    performance_stats['consecutive_losses']
                )
                performance_stats['cooldown_mode'] = True
                performance_stats['games_since_last_loss'] = 0
                
                try: 
                    await tracker_info['message_obj'].edit(f"**#N{signal_game_num} - {tracker_info['signal_suit']} | ❌**")
                except Exception as e: 
                    print(f"Mesaj düzenleme hatası: {e}")
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False

    for game_num in trackers_to_remove:
        martingale_trackers.pop(game_num, None)

# Telegram Komutları
@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    await event.reply("""
🤖 **Baccarat Bot Geliştirilmiş Sürüm** 🎰
**Komutlar:** /start, /help, /stats, /status, /patterns, /active, /analysis, /reset, /martingale_stats, /max_step
**Strateji:** 7 adım Martingale + Strict pattern filtreleme
**Güvenlik:** 5 ardışık kayıp limiti + Cooldown sistemi
**Kanal:** 🆕 Yeni Kaynak Kanalı Aktif!
**Pattern:** 🆕 Genişletilmiş Pattern Listesi!
**İstatistik:** SIFIRDAN BAŞLIYOR! 🔄
""")

@client.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    total = performance_stats['wins'] + performance_stats['losses']
    win_rate = (performance_stats['wins'] / total * 100) if total > 0 else 0
    await event.reply(f"""
📊 **Detaylı İstatistikler:**
🎯 Sinyal: {performance_stats['total_signals']}
✅ Kazanç: {performance_stats['wins']} | ❌ Kayıp: {performance_stats['losses']}
📈 Oran: {win_rate:.1f}%
⚡ Ardışık Kayıp: {performance_stats['consecutive_losses']}/{MAX_CONSECUTIVE_LOSSES}
🛡️ Max Kayıp: {performance_stats['max_consecutive_losses']}
🔁 Cooldown: {'✅' if performance_stats['cooldown_mode'] else '❌'}
""")

@client.on(events.NewMessage(pattern='/analysis'))
async def analysis_command(event):
    status = "🔴 DURDURULDU" if performance_stats['consecutive_losses'] >= MAX_CONSECUTIVE_LOSSES else "🟢 AKTİF"
    cooldown_status = "✅ AKTİF" if performance_stats['cooldown_mode'] else "❌ PASİF"
    
    await event.reply(f"""
🔍 **Detaylı Analiz:**

💚 **Sistem Durumu:**
🟢 Durum: {status}
🔁 Cooldown: {cooldown_status}

🛡️ **Risk Yönetimi:**
⚡ Ardışık Kayıp: {performance_stats['consecutive_losses']}/{MAX_CONSECUTIVE_LOSSES}
🛡️ Max Kayıp: {performance_stats['max_consecutive_losses']}
⏳ Cooldown Sayacı: {performance_stats['games_since_last_loss']}/{COOLDOWN_AFTER_LOSS}

🎯 **Martingale Performansı:**
🔥 En Yüksek Adım: {performance_stats['max_martingale_steps_reached']}/{MAX_MARTINGALE_STEPS+1}
✅ Toplam Kazanç: {performance_stats['wins']} sinyal

📅 **Son Aktivite:**
🕒 Son Sinyal: {performance_stats['last_signal'] or 'Yok'}
""")

@client.on(events.NewMessage(pattern='/status'))
async def status_command(event):
    cooldown_info = ""
    if performance_stats['cooldown_mode']:
        cooldown_info = f"\n⏳ Cooldown: {performance_stats['games_since_last_loss']}/{COOLDOWN_AFTER_LOSS}"
    
    await event.reply(f"""
💚 **Bot Durumu:**
🎯 Aktif Sinyal: {'✅' if is_signal_active else '❌'}
📊 Takip: {len(martingale_trackers)} sinyal
⚡ Ardışık Kayıp: {performance_stats['consecutive_losses']}/{MAX_CONSECUTIVE_LOSSES}
{cooldown_info}
""")

@client.on(events.NewMessage(pattern='/patterns'))
async def patterns_command(event):
    patterns_text = "\n".join([f"{p} - {['💪','🔥','⚡','🎯'][PATTERN_STRENGTH[p]-2 if PATTERN_STRENGTH[p]<=5 else 3]} Güç: {PATTERN_STRENGTH[p]}" for p in STRONG_PATTERNS])
    await event.reply(f"""
🎭 **Aktif Patternler (Güç Değerleri):**
{patterns_text}

🎯 **Aktif Filtre:** Güç ≥ 4
📊 **Aktif Pattern:** {len([p for p in STRONG_PATTERNS if PATTERN_STRENGTH[p] >= 4])}
""")

@client.on(events.NewMessage(pattern='/reset'))
async def reset_command(event):
    global performance_stats, martingale_trackers, is_signal_active
    performance_stats['consecutive_losses'] = 0
    performance_stats['cooldown_mode'] = False
    performance_stats['games_since_last_loss'] = 0
    performance_stats['max_martingale_steps_reached'] = 0
    performance_stats['step_distribution'] = {i: 0 for i in range(1, MAX_MARTINGALE_STEPS + 2)}
    martingale_trackers = {}
    is_signal_active = False
    await event.reply("🔄 **Sistem sıfırlandı!** Tüm istatistikler ve takipler temizlendi.")

@client.on(events.NewMessage(pattern='/active'))
async def active_command(event):
    if performance_stats['consecutive_losses'] >= MAX_CONSECUTIVE_LOSSES:
        await event.reply(f"🔴 **SİSTEM DURDURULDU** - {MAX_CONSECUTIVE_LOSSES}+ ardışık kayıp")
    elif performance_stats['cooldown_mode']:
        await event.reply(f"⏳ **COOLDOWN MODU** - {performance_stats['games_since_last_loss']}/{COOLDOWN_AFTER_LOSS} oyun bekleniyor")
    elif is_signal_active:
        active_list = "\n".join([f"#N{num} - {t['signal_suit']} (Adım {t['step']+1}/{MAX_MARTINGALE_STEPS+1})" for num, t in martingale_trackers.items()])
        await event.reply(f"🔴 **AKTİF SİNYALLER:**\n{active_list}")
    else:
        await event.reply("🟢 **Aktif sinyal yok** - Sistem bekliyor")

@client.on(events.NewMessage(pattern='/martingale_stats'))
async def martingale_stats_command(event):
    total_wins = performance_stats['wins']
    step_distribution = performance_stats['step_distribution']
    
    distribution_text = ""
    for step in range(1, MAX_MARTINGALE_STEPS + 2):
        count = step_distribution.get(step, 0)
        if count > 0:
            percentage = (count / total_wins * 100) if total_wins > 0 else 0
            distribution_text += f"{step}️⃣. adım: {count} kez ({percentage:.1f}%)\n"
    
    if not distribution_text:
        distribution_text = "Henüz veri yok"
    
    total_games = total_wins + performance_stats['losses']
    win_rate = (total_wins / total_games * 100) if total_games > 0 else 0
    
    # Ortalama adım hesaplamasını ayrı yap
    total_steps = sum(step * count for step, count in step_distribution.items())
    average_step = total_steps / total_wins if total_wins > 0 else 0
    
    martingale_structure = MAX_MARTINGALE_STEPS + 1
    
    message_text = f"""
📊 **Martingale İstatistikleri:**

🎯 **En Yüksek Adım:** {performance_stats['max_martingale_steps_reached']}. adım

📈 **Kazanç Dağılımı:**
{distribution_text}

📊 **Genel İstatistikler:**
🎯 Toplam Sinyal: {total_games}
✅ Kazanç: {total_wins} | ❌ Kayıp: {performance_stats['losses']}
📈 Kazanç Oranı: {win_rate:.1f}%

💡 **Ortalama Kazanç Adımı:** {average_step:.1f}. adım

🔢 **Martingale Yapısı:** {martingale_structure} adım (1️⃣-{martingale_structure}️⃣)
"""
    
    await event.reply(message_text)

@client.on(events.NewMessage(pattern='/max_step'))
async def max_step_command(event):
    max_step = performance_stats['max_martingale_steps_reached']
    total_wins = performance_stats['wins']
    
    if max_step == 0:
        await event.reply("📊 **Henüz yeterli veri yok**")
        return
        
    reaction = ""
    if max_step <= 3:
        reaction = "🎉 MÜKEMMEL! Çoğu 3.adımdan önce kazanılmış"
    elif max_step <= 5:
        reaction = "✅ İYİ! Makul seviyede"
    else:
        reaction = "⚠️ DİKKAT! Yüksek adımlara çıkılmış"
    
    martingale_structure = MAX_MARTINGALE_STEPS + 1
    
    message_text = f"""
🔥 **En Yüksek Martingale Adımı:**

🎯 **Rekor:** {max_step}. adım
📊 **Toplam Kazanç:** {total_wins} sinyal
💬 **Durum:** {reaction}

ℹ️ _Sistem {martingale_structure} adım martingale kullanıyor_
"""
    
    await event.reply(message_text)

# Mesaj İşleyici
@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_source_channel_message(event):
    # Cooldown modunda ise sayaç artır
    if performance_stats['cooldown_mode']:
        performance_stats['games_since_last_loss'] += 1
    
    # Sistem durdurulmuşsa çık
    if performance_stats['consecutive_losses'] >= MAX_CONSECUTIVE_LOSSES:
        return
    
    text = re.sub(r'\*\*', '', event.message.text).strip()
    game_info = extract_game_info_from_message(text)
    if not game_info['game_number']: 
        return
    
    game_results[game_info['game_number']] = game_info
    await check_martingale_trackers()
    
    if not is_signal_active:
        should_send, reason = should_send_signal(game_info)
        if should_send:
            next_game_num = get_next_game_number(game_info['game_number'])
            await send_optimized_signal(next_game_num, reason, game_info)
        else:
            # Debug için neden sinyal gönderilmediğini yazdır
            print(f"⏭️ Sinyal atlandı: {reason} | Oyun: #{game_info['game_number']}")

if __name__ == '__main__':
    print("🤖 Baccarat Bot Geliştirilmiş Sürüm Başlatılıyor...")
    print(f"📊 İstatistikler SIFIRDAN başlıyor!")
    print(f"🎯 Martingale: {MAX_MARTINGALE_STEPS+1} adım")
    print(f"🛡️  Güvenlik: {MAX_CONSECUTIVE_LOSSES} max kayıp, {COOLDOWN_AFTER_LOSS} cooldown")
    print(f"📡 Kaynak Kanal: {KANAL_KAYNAK_ID}")
    print(f"🎭 Aktif Pattern: {len(STRONG_PATTERNS)} pattern")
    
    with client:
        client.run_until_disconnected()
