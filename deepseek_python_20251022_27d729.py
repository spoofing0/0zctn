import re
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
import asyncio
import sys
from datetime import datetime

# ==============================================================================
# Telegram API Bilgileri ve Kanal Ayarları
# ==============================================================================
API_ID = 27518940
API_HASH = '30b6658a1870f8462108130783fef14f'

# --- Kanal Bilgileri ---
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@emirbot5"

client = TelegramClient('my_new_baccarat_bot', API_ID, API_HASH)

# ==============================================================================
# Global Değişkenler ve Takip Mekanizmaları
# ==============================================================================
game_results = {}
martingale_trackers = {}
MAX_MARTINGALE_STEPS = 1  # KISA MARTINGALE - sadece 0 ve 1. adımlar
MAX_GAME_NUMBER = 1440
is_signal_active = False

# İstatistikler
performance_stats = {
    'total_signals': 0,
    'wins': 0,
    'losses': 0,
    'active_since': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'last_signal': None
}

# Kart sembollerinden rengi (suit) ayıran regex
SUIT_REGEX = re.compile(r'([♣♦♥♠])')

# ==============================================================================
# Gelişmiş Pattern Tanımları
# ==============================================================================

# Tüm C patternleri
C_PATTERNS = ['#C2_2', '#C2_3', '#C3_2', '#C3_3']

# Güçlü sinyal patternleri
STRONG_PATTERNS = ['#C2_3', '#C3_2', '#C3_3']

# Zayıf patternler (dikkatli kullan)
WEAK_PATTERNS = ['#C2_2']

# Diğer önemli patternler
OTHER_PATTERNS = ['#X', '#П1', '#П2', '#R', '#T']

# ==============================================================================
# Gelişmiş Yardımcı Fonksiyonlar
# ==============================================================================

def get_baccarat_value(card_char):
    if card_char == '10':
        return 10
    if card_char in 'AKQJ2T':
        return 0
    elif card_char.isdigit():
        return int(card_char)
    return -1

def get_next_game_number(current_game_num):
    next_num = current_game_num + 1
    if next_num > MAX_GAME_NUMBER:
        return 1
    return next_num

def extract_largest_value_suit(cards_str):
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

    if max_value == 0:
        return None
        
    return largest_value_suit

def is_player_drawing(text):
    return '▶️' in text

def calculate_pattern_strength(patterns):
    """Patternlere göre sinyal gücünü hesapla"""
    strength = 0
    
    for pattern in patterns:
        if pattern in STRONG_PATTERNS:
            strength += 3
        elif pattern in WEAK_PATTERNS:
            strength += 1
        elif pattern in ['#X', '#П1']:  # Beraberlik veya Oyuncu kazanır
            strength += 2
    
    return strength

def extract_game_info_from_message(text):
    """Gelişmiş pattern tespiti ile oyun bilgilerini çıkar"""
    game_info = {
        'game_number': None, 
        'player_cards': '', 
        'banker_cards': '',
        'is_final': False, 
        'is_player_drawing': False, 
        'patterns': [],
        'pattern_strength': 0,
        'hashtags': []
    }
    
    game_info['is_player_drawing'] = is_player_drawing(text)

    # Tüm hashtag'leri topla
    all_hashtags = re.findall(r'#[\w\d_]+', text)
    game_info['hashtags'] = all_hashtags
    
    # Patternleri tespit et
    detected_patterns = []
    for pattern in C_PATTERNS + OTHER_PATTERNS:
        if pattern in text:
            detected_patterns.append(pattern)
    
    game_info['patterns'] = detected_patterns
    game_info['pattern_strength'] = calculate_pattern_strength(detected_patterns)

    # Oyun bilgilerini çıkar
    game_match = re.search(
        r'#N(\d+)\s+.*?\((.*?)\)\s+.*?(\d+\s+\(.*\))',
        text.replace('️', ''),
        re.DOTALL
    )

    if game_match:
        game_info['game_number'] = int(game_match.group(1))
        game_info['player_cards'] = game_match.group(2)
        game_info['banker_cards'] = game_match.group(3)
        
        # Final kontrolü - daha geniş kriterler
        final_indicators = ['✅', '🔰', '#X', '#П1', '#П2']
        if any(indicator in text for indicator in final_indicators):
            game_info['is_final'] = True
    
    return game_info

def should_send_signal(game_info):
    """Gelişmiş sinyal gönderme kararı"""
    
    # Pattern gücü kontrolü
    if game_info['pattern_strength'] < 2:
        return False, "Pattern gücü yetersiz"
    
    # Final olmayan durumlar için ek kontrol
    if not game_info['is_final']:
        # Sadece çok güçlü patternler için erken sinyal
        if game_info['pattern_strength'] < 3:
            return False, "Final olmayan zayıf pattern"
    
    # Oyuncu kartları kontrolü
    signal_suit = extract_largest_value_suit(game_info['player_cards'])
    if signal_suit is None:
        return False, "Uygun kart bulunamadı"
    
    return True, signal_suit

async def send_optimized_signal(game_num, signal_suit, game_info):
    """Optimize edilmiş sinyal gönderimi"""
    
    global is_signal_active, performance_stats
    
    if is_signal_active:
        print("UYARI: Aktif sinyal var. Yeni sinyal gönderilmiyor.")
        return
    
    # İstatistik güncelle
    performance_stats['total_signals'] += 1
    performance_stats['last_signal'] = datetime.now().strftime('%H:%M:%S')
    
    # Pattern gücüne göre sinyal tipi
    strength = game_info['pattern_strength']
    if strength >= 3:
        signal_type = "⚡ YÜKSEK GÜVEN"
    else:
        signal_type = "🔸 ORTA GÜVEN"
    
    signal_full_text = f"**#N{game_num} - Oyuncu {signal_suit} - {MAX_MARTINGALE_STEPS}D - {signal_type}**"

    try:
        sent_message = await client.send_message(KANAL_HEDEF, signal_full_text)
        print(f"🎯 OPTİMİZE SİNYAL: {signal_full_text} | Patternler: {game_info['patterns']}")

        martingale_trackers[game_num] = {
            'message_obj': sent_message,
            'step': 0,
            'signal_suit': signal_suit,
            'sent_game_number': game_num,
            'expected_game_number_for_check': game_num,
            'pattern_strength': strength
        }
        is_signal_active = True
        print(f"DEBUG: Optimize sinyal #N{game_num} takibe alındı.")

    except FloodWaitError as e:
        print(f"FloodWait hatası: {e.seconds} saniye bekleniyor.")
        await asyncio.sleep(e.seconds)
        await send_optimized_signal(game_num, signal_suit, game_info)
    except Exception as e:
        print(f"Sinyal gönderme hatası: {e}")

async def check_martingale_trackers():
    """Optimize edilmiş Martingale takibi"""
    global martingale_trackers, is_signal_active, performance_stats

    trackers_to_remove = []

    for signal_game_num, tracker_info in list(martingale_trackers.items()):
        current_step = tracker_info['step']
        signal_message_obj = tracker_info['message_obj']
        signal_suit = tracker_info['signal_suit']
        
        game_to_check = tracker_info['expected_game_number_for_check']
        
        if game_to_check not in game_results:
            continue
        
        result_info = game_results.get(game_to_check)

        if not result_info['is_final']:
            continue
        
        player_cards_str = result_info['player_cards']
        signal_won_this_step = bool(re.search(re.escape(signal_suit), player_cards_str))
            
        print(f"DEBUG: Sinyal #N{signal_game_num} (Adım {current_step}/1): {signal_won_this_step}")

        if signal_won_this_step:
            # KAZANDI - Hemen bitir
            performance_stats['wins'] += 1
            win_text = f"**#N{signal_game_num} - Oyuncu {signal_suit} | ✅ {current_step}️⃣**"
            try:
                await signal_message_obj.edit(win_text)
                print(f"🎯 Sinyal #N{signal_game_num} {current_step}. adımda KAZANDI!")
            except Exception as e:
                print(f"Mesaj düzenleme hatası: {e}")
            
            trackers_to_remove.append(signal_game_num)
            is_signal_active = False

        else:
            # KAYBETTİ - Sadece 1 adım hakkı var
            if current_step < MAX_MARTINGALE_STEPS:
                next_step = current_step + 1
                next_game_num = get_next_game_number(game_to_check)
                
                martingale_trackers[signal_game_num]['step'] = next_step
                martingale_trackers[signal_game_num]['expected_game_number_for_check'] = next_game_num
                
                updated_text = f"**#N{signal_game_num} - Oyuncu {signal_suit} - 1D | 🔄 {next_step}️⃣**"
                try:
                    await signal_message_obj.edit(updated_text)
                except Exception as e:
                    print(f"Mesaj güncelleme hatası: {e}")
            else:
                # 1. adımda kaybetti - SERİYİ BİTİR
                performance_stats['losses'] += 1
                loss_text = f"**#N{signal_game_num} - Oyuncu {signal_suit} | ❌**"
                try:
                    await signal_message_obj.edit(loss_text)
                    print(f"💥 Sinyal #N{signal_game_num} 1. adımda kaybetti. SERİ BİTTİ.")
                except Exception as e:
                    print(f"Mesaj düzenleme hatası: {e}")
                
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False

    for game_num_to_remove in trackers_to_remove:
        if game_num_to_remove in martingale_trackers:
            del martingale_trackers[game_num_to_remove]

# ==============================================================================
# Telegram Komutları
# ==============================================================================

@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    """Botu başlatan komut"""
    welcome_text = """
🤖 **Baccarat Sinyal Botu** 🎰

Hoş geldin! Ben Baccarat oyunu için otomatik sinyal üreten bir botum.

**📋 Mevcut Komutlar:**
`/start` - Botu başlat
`/help` - Yardım mesajı
`/stats` - İstatistikleri göster
`/status` - Bot durumu
`/patterns` - Desteklenen patternler
`/active` - Aktif sinyal durumu

**🎯 Strateji:**
- Kısa Martingale (1 adım)
- Pattern bazlı sinyaller
- Yüksek güvenilirlik filtresi

Bot otomatik olarak sinyal üretir. İyi şanslar! 🍀
    """
    await event.reply(welcome_text)

@client.on(events.NewMessage(pattern='/help'))
async def help_command(event):
    """Yardım komutu"""
    help_text = """
🆘 **Baccarat Bot Yardım**

**📖 Komut Listesi:**
`/start` - Botu başlat ve hoş geldin mesajı göster
`/help` - Bu yardım mesajını göster
`/stats` - Bot performans istatistikleri
`/status` - Botun çalışma durumu
`/patterns` - Desteklenen pattern listesi
`/active` - Aktif sinyal olup olmadığını kontrol et

**🔧 Özellikler:**
- Otomatik pattern tanıma
- Akıllı sinyal filtresi
- Kısa Martingale stratejisi
- Gerçek zamanlı takip

**📞 Destek:**
Sorularınız için geliştirici ile iletişime geçin.
    """
    await event.reply(help_text)

@client.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    """İstatistikleri göster"""
    total_games = performance_stats['wins'] + performance_stats['losses']
    win_rate = (performance_stats['wins'] / total_games * 100) if total_games > 0 else 0
    
    stats_text = f"""
📊 **Bot İstatistikleri**

🤖 **Genel Bilgiler:**
├─ Toplam Sinyal: `{performance_stats['total_signals']}`
├─ Kazanç: `{performance_stats['wins']}`
├─ Kayıp: `{performance_stats['losses']}`
├─ Kazanç Oranı: `{win_rate:.1f}%`
└─ Aktif Süre: `{performance_stats['active_since']}`

🎯 **Mevcut Strateji:**
├─ Martingale: `{MAX_MARTINGALE_STEPS} adım`
├─ Pattern Güç: `2+ puan`
└─ Son Sinyal: `{performance_stats['last_signal'] or 'Henüz yok'}`

🔄 **Sistem Durumu:**
├─ Aktif Sinyal: `{'EVET ✅' if is_signal_active else 'HAYIR ❌'}`
├─ Takip Edilen: `{len(martingale_trackers)} sinyal`
└─ Hafıza: `{len(game_results)} oyun`
    """
    await event.reply(stats_text)

@client.on(events.NewMessage(pattern='/status'))
async def status_command(event):
    """Bot durumunu göster"""
    status_text = f"""
🟢 **Bot Aktif**

📡 **Sistem Durumu:**
├─ Sinyal Durumu: `{'AKTİF 🔄' if is_signal_active else 'PASİF 💤'}`
├─ Aktif Takip: `{len(martingale_trackers)} sinyal`
├─ Son Oyun: `{max(game_results.keys()) if game_results else 'Henüz yok'}`
└─ Çalışma Süresi: `{performance_stats['active_since']}`

🎰 **Son İşlemler:**
├─ Toplam Sinyal: `{performance_stats['total_signals']}`
├─ Son Sinyal: `{performance_stats['last_signal'] or 'Henüz yok'}`
└─ Kazanç/Kayıp: `{performance_stats['wins']}/{performance_stats['losses']}`

**ℹ️ Komutlar için `/help` yazın.**
    """
    await event.reply(status_text)

@client.on(events.NewMessage(pattern='/patterns'))
async def patterns_command(event):
    """Desteklenen patternleri listele"""
    patterns_text = """
🎯 **Desteklenen Patternler**

**🟢 GÜÇLÜ PATTERNLER (3 puan):**
├─ `#C2_3` 🔴
├─ `#C3_2` 🟢
└─ `#C3_3` 🟡

**🟡 ORTA PATTERNLER (2 puan):**
├─ `#X` - Beraberlik
└─ `#П1` - Oyuncu kazanır

**🔴 ZAYIF PATTERNLER (1 puan):**
└─ `#C2_2` 🔵

**📊 Diğer İzlenenler:**
├─ `#П2` - Banker kazanır
├─ `#R` - 2'li dağıtım
└─ `#T` - Toplam

**🎮 Strateji:**
Sadece 2+ puan alan patternler sinyal üretir.
    """
    await event.reply(patterns_text)

@client.on(events.NewMessage(pattern='/active'))
async def active_command(event):
    """Aktif sinyal durumunu göster"""
    if is_signal_active and martingale_trackers:
        active_info = []
        for game_num, tracker in martingale_trackers.items():
            active_info.append(
                f"├─ #N{game_num} - {tracker['signal_suit']} (Adım {tracker['step']})"
            )
        
        active_text = f"""
🔴 **AKTİF SİNYAL VAR**

**📊 Aktif Sinyal Bilgisi:**
{"".join(active_info)}
└─ Toplam: `{len(martingale_trackers)}` aktif sinyal

**⏳ Son durum kontrol ediliyor...**
        """
    else:
        active_text = """
🟢 **AKTİF SİNYAL YOK**

Bot şu anda sinyal takibi yapmıyor.
Yeni patternler geldiğinde otomatik sinyal üretilecek.
        """
    
    await event.reply(active_text)

# ==============================================================================
# Gelişmiş Telegram Mesaj İşleyicileri
# ==============================================================================

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_source_channel_message(event):
    message = event.message
    cleaned_text = re.sub(r'\*\*', '', message.text).strip()
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] KAYNAK KANAL Mesaj Alındı. ID: {message.id}", file=sys.stderr)

    game_info = extract_game_info_from_message(cleaned_text)

    if game_info['game_number'] is None:
        return

    game_results[game_info['game_number']] = game_info
    
    await check_martingale_trackers()

    if not is_signal_active:
        # GELİŞMİŞ SİNYAL TETİKLEYİCİ
        should_send, reason = should_send_signal(game_info)
        
        if should_send:
            trigger_game_num = game_info['game_number']
            signal_suit = reason  # reason burada signal_suit dönüyor
            
            next_game_num = get_next_game_number(trigger_game_num)
            await send_optimized_signal(next_game_num, signal_suit, game_info)
        else:
            print(f"DEBUG: Sinyal gönderilmedi. Sebep: {reason} | Patternler: {game_info['patterns']}")

# ==============================================================================
# Botun Başlatılması
# ==============================================================================
if __name__ == '__main__':
    print("🤖 GELİŞMİŞ BACCARAT BOTU BAŞLATILIYOR...")
    print(f"🔍 İzlenen Patternler: {C_PATTERNS}")
    print(f"🎯 Martingale Stratejisi: {MAX_MARTINGALE_STEPS} adım")
    print("📞 Telegram komutları aktif:")
    print("   /start, /help, /stats, /status, /patterns, /active")
    print("=====================================")
    
    with client:
        client.run_until_disconnected()