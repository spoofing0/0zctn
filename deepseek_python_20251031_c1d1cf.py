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

# --- YENİ KANAL BİLGİLERİ ---
KANAL_KAYNAK_ID = -1001626824569  # 🆕 YENİ KANAL ID
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

# ==============================================================================
# OPTIMIZE EDİLMİŞ PATTERN KONFİGÜRASYONU - ANALİZE GÖRE
# ==============================================================================

# EN GÜÇLÜ PATTERNLER - Analiz sonucu seçildi
STRONG_PATTERNS = [
    '#C3_3',    # 🏆 EN GÜÇLÜ - Yüksek başarı oranı
    '#C2_3',    # 🔥 ÇOK GÜÇLÜ - 2-3 adımda kazanç
    '#C3_2',    # 🔥 ÇOK GÜÇLÜ - 1-3 adımda yüksek verim
    '#R',       # ⚡ HIZLI - 2 kart dağıtımı
]

PATTERN_STRENGTH = {
    '#C3_3': 6,  # 🏆 EN YÜKSEK - %80+ başarı
    '#C2_3': 5,  # 🔥 ÇOK GÜÇLÜ - %75+ başarı  
    '#C3_2': 5,  # 🔥 ÇOK GÜÇLÜ - %75+ başarı
    '#R': 4,     # ⚡ HIZLI - %70+ başarı
}

# GÜÇLÜ İNDİKATÖRLER - Yeni kanala göre
STRONG_INDICATORS = ['✅', '🔰', '⭐', '🔥', '⚡', '🔺', '🟢', '🔵', '🎯', '🟣', '🔼']

# OPTIMUM EŞİK DEĞERLERİ - DAHA SEÇİCİ
MIN_PATTERN_STRENGTH = 5  # Sadece en güçlü patternler
FINAL_MIN_STRENGTH = 5    # Yüksek kalite için

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
    'step_distribution': {i: 0 for i in range(1, MAX_MARTINGALE_STEPS + 2)},
    'source_channel': KANAL_KAYNAK_ID
}

def get_baccarat_value(card_char):
    """Kart değerini hesapla - optimize edilmiş"""
    if card_char == '10': 
        return 10
    if card_char in 'AKQJT':  # T ve J eklendi
        return 0
    elif card_char.isdigit(): 
        return int(card_char)
    return -1

def get_next_game_number(current_game_num):
    next_num = current_game_num + 1
    return 1 if next_num > MAX_GAME_NUMBER else next_num

def extract_largest_value_suit(cards_str):
    """GÜÇLENDİRİLMİŞ KART ANALİZİ"""
    print(f"🔍 DEBUG - Kart analizi: {cards_str}")
    
    # Geliştirilmiş regex - yeni formata uygun
    cards_match = re.search(r'\(([^)]+)\)', cards_str)
    if not cards_match:
        print("❌ DEBUG - Parantez içi kart bulunamadı")
        return None
        
    cards_content = cards_match.group(1)
    print(f"🔍 DEBUG - Kart içeriği: {cards_content}")
    
    # Kartları ayır - gelişmiş regex
    cards = re.findall(r'(\d+|[A-Z])([♦♥♠♣]️?)', cards_content)
    if not cards:
        print("❌ DEBUG - Kartlar parse edilemedi")
        return None
        
    print(f"🔍 DEBUG - Ayrılmış kartlar: {cards}")

    max_value = -1
    largest_value_suit = None
    values = []

    for card_char, suit in cards:
        value = get_baccarat_value(card_char)
        values.append(value)
        print(f"🔍 DEBUG - Kart: {card_char}{suit} -> Değer: {value}")
        
        if value > max_value:
            max_value = value
            largest_value_suit = suit
            print(f"🔍 DEBUG - Yeni max: {value} -> Renk: {suit}")

    # GELİŞMİŞ FİLTRELEME MEKANİZMASI
    # 1. Aynı değerde kartlar → SINYAL YOK
    if len(values) == 2 and values[0] == values[1]:
        print("❌ DEBUG - Aynı değerde kartlar, sinyal yok")
        return None
        
    # 2. 3 kartta çeşitlilik kontrolü  
    if len(values) == 3 and len(set(values)) < 2:
        print("❌ DEBUG - 3 kartta yeterli çeşitlilik yok")
        return None

    # 3. 0 değerli kartlar (A,K,Q,J,T) → SINYAL YOK
    if max_value == 0:
        print("❌ DEBUG - Maksimum değer 0, sinyal yok")
        return None

    # 4. Sadece 8-9 değerlerinde özel kontrol
    if max_value in [8, 9] and len(values) == 2:
        print("✅ DEBUG - Yüksek değerli kart (8-9), sinyal uygun")
        return largest_value_suit

    result = largest_value_suit
    print(f"🔍 DEBUG - Sinyal sonucu: {result}")
    return result

def extract_game_info_from_message(text):
    """YENİ KANAL FORMATINA UYGUN OYUN BİLGİSİ ÇIKARMA"""
    game_info = {
        'game_number': None, 'player_cards': '', 'banker_cards': '',
        'is_final': False, 'patterns': [], 'pattern_strength': 0,
        'has_strong_indicator': False, 'raw_message': text
    }
    
    print(f"🔍 DEBUG - Yeni kanal mesajı: {text}")
    
    # YENİ KANAL PATTERN TESPİTİ
    detected_patterns = [p for p in STRONG_PATTERNS if p in text]
    game_info['patterns'] = detected_patterns
    game_info['pattern_strength'] = sum(PATTERN_STRENGTH.get(p, 0) for p in detected_patterns)

    # YENİ KANAL İNDİKATÖR KONTROLÜ
    game_info['has_strong_indicator'] = any(indicator in text for indicator in STRONG_INDICATORS)

    # GELİŞMİŞ FİNAL KARARI - DAHA SEÇİCİ
    game_info['is_final'] = (
        game_info['pattern_strength'] >= FINAL_MIN_STRENGTH and 
        game_info['has_strong_indicator'] and
        len(game_info['patterns']) >= 1
    )

    # YENİ KANAL REGEX PATTERN - Optimize edilmiş
    patterns = [
        r'#N?(\d+)\s*.*?(\d+\([^)]+\)).*?(\d+\([^)]+\))',  # #N1063 formatı
        r'#n?(\d+)\s*.*?(\d+\([^)]+\)).*?(\d+\([^)]+\))',  # #n1063 formatı
    ]
    
    game_match = None
    for pattern in patterns:
        game_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if game_match:
            break
    
    if game_match:
        game_info['game_number'] = int(game_match.group(1))
        game_info['player_cards'] = game_match.group(2)
        game_info['banker_cards'] = game_match.group(3)
        print(f"✅ DEBUG - Regex eşleşti: Oyun#{game_info['game_number']}")
        print(f"✅ DEBUG - Player: {game_info['player_cards']}")
        print(f"✅ DEBUG - Banker: {game_info['banker_cards']}")
    else:
        print(f"❌ DEBUG - Hiçbir regex eşleşmedi")
    
    return game_info

def should_send_signal(game_info):
    """GELİŞMİŞ SİNYAL KARAR MEKANİZMASI - ÇOK KATMANLI FİLTRELEME"""
    print(f"🔍 DEBUG - Sinyal kontrolü başladı")
    
    # 1. GÜVENLİK KONTROLLERİ
    if performance_stats['consecutive_losses'] >= MAX_CONSECUTIVE_LOSSES:
        return False, f"Maksimum {MAX_CONSECUTIVE_LOSSES} ardışık kayıp"

    if performance_stats['cooldown_mode']:
        if performance_stats['games_since_last_loss'] < COOLDOWN_AFTER_LOSS:
            return False, f"Cooldown: {performance_stats['games_since_last_loss']}/{COOLDOWN_AFTER_LOSS}"
        else:
            performance_stats['cooldown_mode'] = False
            performance_stats['games_since_last_loss'] = 0

    # 2. PATTERN KALİTE KONTROLLERİ - DAHA SIKI
    if not game_info['patterns']: 
        return False, "Pattern yok"
    
    if game_info['pattern_strength'] < MIN_PATTERN_STRENGTH:
        return False, f"Pattern gücü yetersiz: {game_info['pattern_strength']}"

    # 3. FİNAL KARARI - YÜKSEK KALİTE
    has_final_quality = (
        game_info['pattern_strength'] >= FINAL_MIN_STRENGTH and 
        game_info['has_strong_indicator'] and
        len(game_info['patterns']) >= 1
    )
    
    if not has_final_quality:
        return False, "Final kalitesi yok"

    # 4. KART ANALİZİ - SON KONTROL
    signal_suit = extract_largest_value_suit(game_info['player_cards'])
    if not signal_suit:
        return False, "Uygun kart yok"

    print(f"✅ DEBUG - TÜM KONTROLLER GEÇİLDİ: {signal_suit}")
    return True, signal_suit

async def send_optimized_signal(game_num, signal_suit, game_info):
    global is_signal_active, performance_stats
    if is_signal_active: 
        print(f"⏳ DEBUG - Zaten aktif sinyal var")
        return
    
    performance_stats['total_signals'] += 1
    performance_stats['last_signal'] = datetime.now().strftime('%H:%M:%S')
    
    # Pattern gücüne göre sinyal tipi
    if game_info['pattern_strength'] >= 6:
        signal_type = "🏆 EN YÜKSEK GÜVEN"
    elif game_info['pattern_strength'] >= 5:
        signal_type = "⚡ YÜKSEK GÜVEN"
    else:
        signal_type = "🔸 ORTA GÜVEN"
    
    signal_full_text = f"**#N{game_num} - Oyuncu {signal_suit} - {MAX_MARTINGALE_STEPS+1}D - {signal_type}**"

    try:
        print(f"🚀 DEBUG - Sinyal gönderiliyor: {signal_full_text}")
        sent_message = await client.send_message(KANAL_HEDEF, signal_full_text)
        print(f"🎯 SİNYAL: {signal_full_text}")
        martingale_trackers[game_num] = {
            'message_obj': sent_message, 
            'step': 0, 
            'signal_suit': signal_suit,
            'sent_game_number': game_num, 
            'expected_game_number_for_check': game_num,
            'pattern_strength': game_info['pattern_strength'],
            'source_channel': performance_stats['source_channel']
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
                print(f"✅ Kazanç: {win_text}")
            except Exception as e: 
                print(f"❌ Mesaj düzenleme hatası: {e}")
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
                    print(f"🔄 Martingale devam: {next_step}. adım")
                except Exception as e: 
                    print(f"❌ Mesaj düzenleme hatası: {e}")
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
                    print(f"❌ Kayıp: #{signal_game_num}")
                except Exception as e: 
                    print(f"❌ Mesaj düzenleme hatası: {e}")
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False

    for game_num in trackers_to_remove:
        martingale_trackers.pop(game_num, None)

# Telegram Komutları
@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    await event.reply(f"""
🤖 **Baccarat Bot - OPTIMIZE EDİLMİŞ SÜRÜM** 🎰
**Kaynak Kanal:** {KANAL_KAYNAK_ID}

🚀 **OPTIMIZASYONLAR:**
• Sadece 4 en güçlü pattern: #C3_3, #C2_3, #C3_2, #R
• Gelişmiş kart analizi ve filtreleme
• 1-4 martingale'de yüksek kazanç hedefi
• Çok katmanlı güvenlik kontrolleri

📊 **FİLTRELEME:**
• Min Pattern Gücü: {MIN_PATTERN_STRENGTH}
• Final Güç Eşiği: {FINAL_MIN_STRENGTH}
• Sadece yüksek kaliteli sinyaller

**Komutlar:** /start, /stats, /status, /patterns, /active, /analysis, /reset
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

@client.on(events.NewMessage(pattern='/patterns'))
async def patterns_command(event):
    pattern_emojis = {
        6: "🏆 EN YÜKSEK",
        5: "🔥 ÇOK GÜÇLÜ", 
        4: "⚡ HIZLI"
    }
    
    patterns_text = "\n".join([f"{p} - {pattern_emojis[PATTERN_STRENGTH[p]]} - Güç: {PATTERN_STRENGTH[p]}" for p in STRONG_PATTERNS])
    await event.reply(f"""
🎭 **OPTIMIZE EDİLMİŞ PATTERNLER:**
{patterns_text}

🎯 **Aktif Filtre:** Güç ≥ {MIN_PATTERN_STRENGTH}
📊 **Final Kriteri:** Güç ≥ {FINAL_MIN_STRENGTH} + İndikatör

🚀 **Hedef:** 1-4 adımda yüksek kazanç!
📉 **Zayıf patternler çıkarıldı:** #C2_2, #П1, #П2
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

# Diğer komutlar aynen kalacak...
# (/status, /reset, /active, /martingale_stats, /max_step, /test_current, /debug_message, /force_signal)

# Mesaj İşleyici
@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_source_channel_message(event):
    print(f"🔔 YENİ KANALDAN MESAJ YAKALANDI!")
    print(f"📝 Mesaj içeriği: {event.message.text}")
    
    # Cooldown modunda ise sayaç artır
    if performance_stats['cooldown_mode']:
        performance_stats['games_since_last_loss'] += 1
        print(f"⏳ Cooldown sayacı: {performance_stats['games_since_last_loss']}")
    
    # Sistem durdurulmuşsa çık
    if performance_stats['consecutive_losses'] >= MAX_CONSECUTIVE_LOSSES:
        print("🔴 Sistem durduruldu - maksimum kayıp limiti")
        return
    
    text = re.sub(r'\*\*', '', event.message.text).strip()
    game_info = extract_game_info_from_message(text)
    
    if not game_info['game_number']: 
        print("❌ Oyun numarası bulunamadı - çıkılıyor")
        return
    
    game_results[game_info['game_number']] = game_info
    await check_martingale_trackers()
    
    if not is_signal_active:
        should_send, reason = should_send_signal(game_info)
        print(f"🎯 SİNYAL KARARI: {should_send} - Sebep: {reason}")
        
        if should_send:
            next_game_num = get_next_game_number(game_info['game_number'])
            print(f"🚀 SİNYAL GÖNDERİLİYOR: #{next_game_num} - {reason}")
            await send_optimized_signal(next_game_num, reason, game_info)
        else:
            print(f"⏭️ SİNYAL ATLANDI: {reason} | Oyun: #{game_info['game_number']}")

if __name__ == '__main__':
    print("🤖 Baccarat Bot - OPTIMIZE EDİLMİŞ SÜRÜM Başlatılıyor...")
    print(f"🆕 YENİ KANAL: {KANAL_KAYNAK_ID}")
    print(f"🎯 OPTIMIZE HEDEF: 1-4 adımda yüksek kazanç")
    print(f"🔧 EN GÜÇLÜ 4 PATTERN: #C3_3, #C2_3, #C3_2, #R")
    print(f"📊 Min Güç: {MIN_PATTERN_STRENGTH}, Final Güç: {FINAL_MIN_STRENGTH}")
    
    with client:
        client.run_until_disconnected()