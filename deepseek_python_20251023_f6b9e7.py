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
# Global Değişkenler ve Takip Mekanizmaları - TAMAMEN YENİ STRATEJİ
# ==============================================================================
game_results = {}
martingale_trackers = {}
MAX_MARTINGALE_STEPS = 2  # DAHA DÜŞÜK RİSK - 3 adım (0,1,2)
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

# Kart sembollerinden rengi (suit) ayıran regex
SUIT_REGEX = re.compile(r'([♣♦♥♠])')

# ==============================================================================
# YENİ VE DAHA SIKI PATTERN TANIMLARI
# ==============================================================================

# SADECE EN GÜVENİLİR PATTERNLER
STRONG_PATTERNS = ['#C2_3', '#C3_2', '#C3_3']
# ZAYIF PATTERNLER (ARTIK KULLANILMIYOR)
WEAK_PATTERNS = ['#C2_2', '#X', '#П1', '#П2', '#R', '#T']

# ==============================================================================
# YENİ VE DAHA AKILLI YARDIMCI FONKSİYONLAR
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
    """DAHA GÜVENLİ KART ANALİZİ"""
    cards = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', cards_str)
    if not cards or len(cards) < 2:
        return None

    max_value = -1
    largest_value_suit = None
    
    values = [get_baccarat_value(card[0]) for card in cards]
    
    # AYNI DEĞERLİ KARTLARI TESPİT ET (daha hassas)
    if len(values) == 2 and values[0] == values[1]:
        return None

    for card_char, suit in cards:
        value = get_baccarat_value(card_char)
        if value > max_value:
            max_value = value
            largest_value_suit = suit

    # 0 DEĞERLİ KARTLARI REDDET (A,K,Q,J,2,T)
    if max_value == 0:
        return None
        
    return largest_value_suit

def is_player_drawing(text):
    return '▶️' in text

def calculate_pattern_strength(patterns):
    """DAHA SIKI PATTERN KONTROLÜ"""
    strength = 0
    
    for pattern in patterns:
        if pattern in STRONG_PATTERNS:
            strength += 3
        elif pattern in WEAK_PATTERNS:
            strength += 0  # ZAYIF PATTERNLER ARTIK PUAN ALMIYOR!
    
    return strength

def extract_game_info_from_message(text):
    """DAHA DETAYLI OYUN BİLGİSİ ÇIKARMA"""
    game_info = {
        'game_number': None, 
        'player_cards': '', 
        'banker_cards': '',
        'is_final': False, 
        'is_player_drawing': False, 
        'patterns': [],
        'pattern_strength': 0,
        'hashtags': [],
        'has_strong_pattern': False
    }
    
    game_info['is_player_drawing'] = is_player_drawing(text)

    # Tüm hashtag'leri topla
    all_hashtags = re.findall(r'#[\w\d_]+', text)
    game_info['hashtags'] = all_hashtags
    
    # SADECE GÜÇLÜ PATTERNLERİ TESPİT ET
    detected_patterns = []
    for pattern in STRONG_PATTERNS:
        if pattern in text:
            detected_patterns.append(pattern)
            game_info['has_strong_pattern'] = True
    
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
        
        # DAHA SIKI FINAL KONTROLÜ
        final_indicators = ['✅', '🔰', '#X']
        if any(indicator in text for indicator in final_indicators):
            game_info['is_final'] = True
    
    return game_info

def should_send_signal(game_info):
    """ÇOK DAHA SIKI SİNYAL FİLTRESİ"""
    
    # 1. GÜÇLÜ PATTERN KONTROLÜ - SADECE EN GÜÇLÜ PATTERNLER
    if not game_info['has_strong_pattern']:
        return False, "Güçlü pattern bulunamadı"
    
    # 2. FİNAL KONTROLÜ - KESİNLİKLE FİNAL OLMALI
    if not game_info['is_final']:
        return False, "Final değil"
    
    # 3. KART KONTROLÜ - DAHA SIKI
    signal_suit = extract_largest_value_suit(game_info['player_cards'])
    if signal_suit is None:
        return False, "Uygun kart bulunamadı"
    
    # 4. ARDIŞIK KAYIP KONTROLÜ
    if performance_stats['consecutive_losses'] >= 3:
        return False, f"Ardışık kayıp limiti: {performance_stats['consecutive_losses']}"
    
    return True, signal_suit

async def send_optimized_signal(game_num, signal_suit, game_info):
    """YENİ SİNYAL GÖNDERİM SİSTEMİ"""
    
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
        print(f"🎯 YENİ SİNYAL: {signal_full_text} | Patternler: {game_info['patterns']}")

        martingale_trackers[game_num] = {
            'message_obj': sent_message,
            'step': 0,
            'signal_suit': signal_suit,
            'sent_game_number': game_num,
            'expected_game_number_for_check': game_num,
            'pattern_strength': strength
        }
        is_signal_active = True
        print(f"DEBUG: Yeni sinyal #N{game_num} takibe alındı.")

    except FloodWaitError as e:
        print(f"FloodWait hatası: {e.seconds} saniye bekleniyor.")
        await asyncio.sleep(e.seconds)
        await send_optimized_signal(game_num, signal_suit, game_info)
    except Exception as e:
        print(f"Sinyal gönderme hatası: {e}")

async def check_martingale_trackers():
    """YENİ MARTINGALE TAKİP SİSTEMİ"""
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
            
        print(f"DEBUG: Sinyal #N{signal_game_num} (Adım {current_step}/{MAX_MARTINGALE_STEPS}): {signal_won_this_step}")

        if signal_won_this_step:
            # KAZANDI - Hemen bitir
            performance_stats['wins'] += 1
            performance_stats['consecutive_losses'] = 0  # Kayıp serisini sıfırla
            
            win_text = f"**#N{signal_game_num} - Oyuncu {signal_suit} | ✅ {current_step}️⃣**"
            try:
                await signal_message_obj.edit(win_text)
                print(f"🎯 Sinyal #N{signal_game_num} {current_step}. adımda KAZANDI!")
            except Exception as e:
                print(f"Mesaj düzenleme hatası: {e}")
            
            trackers_to_remove.append(signal_game_num)
            is_signal_active = False

        else:
            # KAYBETTİ
            if current_step < MAX_MARTINGALE_STEPS:
                next_step = current_step + 1
                next_game_num = get_next_game_number(game_to_check)
                
                martingale_trackers[signal_game_num]['step'] = next_step
                martingale_trackers[signal_game_num]['expected_game_number_for_check'] = next_game_num
                
                updated_text = f"**#N{signal_game_num} - Oyuncu {signal_suit} - {MAX_MARTINGALE_STEPS}D | 🔄 {next_step}️⃣**"
                try:
                    await signal_message_obj.edit(updated_text)
                    print(f"🔄 Sinyal #N{signal_game_num} {current_step}. adımda kaybetti. {next_step}. adıma geçiliyor.")
                except Exception as e:
                    print(f"Mesaj güncelleme hatası: {e}")
            else:
                # Maksimum adımda kaybetti
                performance_stats['losses'] += 1
                performance_stats['consecutive_losses'] += 1
                
                # Maksimum ardışık kayıp güncelle
                if performance_stats['consecutive_losses'] > performance_stats['max_consecutive_losses']:
                    performance_stats['max_consecutive_losses'] = performance_stats['consecutive_losses']
                
                loss_text = f"**#N{signal_game_num} - Oyuncu {signal_suit} | ❌**"
                try:
                    await signal_message_obj.edit(loss_text)
                    print(f"💥 Sinyal #N{signal_game_num} {MAX_MARTINGALE_STEPS}. adımda kaybetti. SERİ BİTTİ. Ardışık kayıp: {performance_stats['consecutive_losses']}")
                except Exception as e:
                    print(f"Mesaj düzenleme hatası: {e}")
                
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False

    for game_num_to_remove in trackers_to_remove:
        if game_num_to_remove in martingale_trackers:
            del martingale_trackers[game_num_to_remove]

# ==============================================================================
# YENİ TELEGRAM KOMUTLARI - PERFORMANS ANALİZİ
# ==============================================================================

@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    """Botu başlatan komut"""
    welcome_text = """
🤖 **YENİ BACCARAT BOTU v3.0** 🎰

⚠️ **ÖNEMLİ DEĞİŞİKLİKLER:**
- Sadece en güçlü patternler (#C2_3, #C3_2, #C3_3)
- Daha düşük risk (2 adım Martingale)
- Ardışık kayıp koruması
- Çok daha sıkı filtreler

**📋 Komutlar:**
`/start` - Botu başlat
`/help` - Yardım
`/stats` - İstatistikler
`/status` - Bot durumu
`/patterns` - Patternler
`/active` - Aktif sinyaller
`/analysis` - Detaylı analiz

**🎯 Yeni Strateji:**
- Sadece %100 güvenilir patternler
- Maximum 3 ardışık kayıp koruması
- Daha akıllı kart analizi

Bot otomatik olarak sinyal üretir. İyi şanslar! 🍀
    """
    await event.reply(welcome_text)

@client.on(events.NewMessage(pattern='/analysis'))
async def analysis_command(event):
    """Detaylı performans analizi"""
    total_games = performance_stats['wins'] + performance_stats['losses']
    win_rate = (performance_stats['wins'] / total_games * 100) if total_games > 0 else 0
    
    analysis_text = f"""
📊 **DETAYLI PERFORMANS ANALİZİ**

🎯 **Başarı Metrikleri:**
├─ Toplam Sinyal: `{performance_stats['total_signals']}`
├─ Kazanç: `{performance_stats['wins']}`
├─ Kayıp: `{performance_stats['losses']}`
├─ Kazanç Oranı: `{win_rate:.1f}%`
├─ Ardışık Kayıp: `{performance_stats['consecutive_losses']}`
└─ Maks. Ardışık Kayıp: `{performance_stats['max_consecutive_losses']}`

⚠️ **Risk Durumu:**
{"├─ 🔴 YÜKSEK RİSK - Strateji değişimi gerekli" if performance_stats['consecutive_losses'] >= 3 else "├─ 🟢 DÜŞÜK RİSK - Sistem normal" if win_rate >= 60 else "├- 🟡 ORTA RİSK - İzlemede"}

💡 **Öneriler:**
{"├─ ❌ Sinyal durduruldu (3+ ardışık kayıp)" if performance_stats['consecutive_losses'] >= 3 else "├- ✅ Sistem aktif"}

🔧 **Mevcut Ayarlar:**
├─ Martingale: `{MAX_MARTINGALE_STEPS} adım`
├─ Pattern: `Sadece güçlü patternler`
└─ Son Sinyal: `{performance_stats['last_signal'] or 'Henüz yok'}`
    """
    await event.reply(analysis_text)

@client.on(events.NewMessage(pattern='/help'))
async def help_command(event):
    """Yardım komutu"""
    help_text = """
🆘 **YENİ BACCARAT BOT YARDIMI**

**📖 Komut Listesi:**
`/start` - Botu başlat
`/help` - Yardım mesajı
`/stats` - İstatistikler
`/status` - Bot durumu
`/patterns` - Pattern listesi
`/active` - Aktif sinyaller
`/analysis` - Detaylı performans analizi

**🔧 Yeni Özellikler:**
- Ardışık kayıp koruması
- Sadece güçlü patternler
- Daha akıllı kart analizi
- Otomatik risk yönetimi

**⚠️ Önemli:**
- 3 ardışık kayıpta sinyal durur
- Sadece #C2_3, #C3_2, #C3_3 patternleri
- Daha düşük Martingale (2 adım)

**📞 Destek:**
Sorunlar için geliştirici ile iletişime geçin.
    """
    await event.reply(help_text)

@client.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    """İstatistikleri göster"""
    total_games = performance_stats['wins'] + performance_stats['losses']
    win_rate = (performance_stats['wins'] / total_games * 100) if total_games > 0 else 0
    
    stats_text = f"""
📊 **Bot İstatistikleri v3.0**

🤖 **Performans:**
├─ Toplam Sinyal: `{performance_stats['total_signals']}`
├─ Kazanç: `{performance_stats['wins']}`
├─ Kayıp: `{performance_stats['losses']}`
├─ Kazanç Oranı: `{win_rate:.1f}%`
├─ Ardışık Kayıp: `{performance_stats['consecutive_losses']}`
└─ Aktif Süre: `{performance_stats['active_since']}`

🎯 **Strateji:**
├─ Martingale: `{MAX_MARTINGALE_STEPS} adım`
├─ Pattern: `Sadece güçlü patternler`
└─ Son Sinyal: `{performance_stats['last_signal'] or 'Henüz yok'}`

⚠️ **Durum:**
{"├─ 🔴 SİNYAL DURDURULDU - 3+ ardışık kayıp" if performance_stats['consecutive_losses'] >= 3 else "├- 🟢 SİSTEM AKTİF" if is_signal_active else "├- 🟡 SİNYAL BEKLİYOR"}
    """
    await event.reply(stats_text)

@client.on(events.NewMessage(pattern='/status'))
async def status_command(event):
    """Bot durumunu göster"""
    status_text = f"""
🟢 **YENİ BOT AKTİF v3.0**

📡 **Sistem Durumu:**
├─ Sinyal Durumu: `{'AKTİF 🔄' if is_signal_active else 'PASİF 💤'}`
├─ Aktif Takip: `{len(martingale_trackers)} sinyal`
├─ Ardışık Kayıp: `{performance_stats['consecutive_losses']}`
├─ Çalışma Süresi: `{performance_stats['active_since']}`
└─ Son Sinyal: `{performance_stats['last_signal'] or 'Henüz yok'}`

🎰 **Son İşlemler:**
├─ Toplam Sinyal: `{performance_stats['total_signals']}`
├─ Kazanç/Kayıp: `{performance_stats['wins']}/{performance_stats['losses']}`
└─ Başarı Oranı: `{(performance_stats['wins']/(performance_stats['wins']+performance_stats['losses'])*100) if (performance_stats['wins']+performance_stats['losses']) > 0 else 0:.1f}%`

{"⚠️ **UYARI:** 3 ardışık kayıp limitine ulaşıldı! Sinyal durduruldu." if performance_stats['consecutive_losses'] >= 3 else ""}
    """
    await event.reply(status_text)

@client.on(events.NewMessage(pattern='/patterns'))
async def patterns_command(event):
    """Desteklenen patternleri listele"""
    patterns_text = """
🎯 **YENİ PATTERN SİSTEMİ v3.0**

**🟢 AKTİF PATTERNLER (Sadece Bunlar):**
├─ `#C2_3` 🔴 → En güçlü pattern
├─ `#C3_2` 🟢 → Çok güçlü pattern  
└─ `#C3_3` 🟡 → Güçlü pattern

**🚫 PASİF PATTERNLER (Artık Kullanılmıyor):**
├─ `#C2_2` 🔵 → Çok riskli
├─ `#X`      → Beraberlik
├─ `#П1`     → Oyuncu kazanır
├─ `#П2`     → Banker kazanır
├─ `#R`      → 2'li dağıtım
└─ `#T`      → Toplam

**🎮 Yeni Strateji:**
Sadece yukarıdaki 3 pattern sinyal üretir!
Diğer tüm patternler İPTAL edilmiştir.
    """
    await event.reply(patterns_text)

@client.on(events.NewMessage(pattern='/active'))
async def active_command(event):
    """Aktif sinyal durumunu göster"""
    if performance_stats['consecutive_losses'] >= 3:
        active_text = """
🔴 **SİNYAL SİSTEMİ DURDURULDU**

⚠️ **Neden:**
3 veya daha fazla ardışık kayıp tespit edildi.
Bu, mevcut stratejinin çalışmadığını gösterir.

🔄 **Çözüm:**
1. Patternleri ve stratejiyi gözden geçir
2. `/analysis` komutu ile detaylı analiz yap
3. Gerekirse stratejiyi değiştir

**Sistem güvenliği için otomatik olarak durduruldu.**
        """
    elif is_signal_active and martingale_trackers:
        active_info = []
        for game_num, tracker in martingale_trackers.items():
            active_info.append(f"├─ #N{game_num} - {tracker['signal_suit']} (Adım {tracker['step']})")
        
        active_text = f"""
🔴 **AKTİF SİNYAL VAR**

**📊 Aktif Sinyal Bilgisi:**
{"".join(active_info)}
└─ Toplam: `{len(martingale_trackers)}` aktif sinyal

**📈 Performans:**
├─ Ardışık Kayıp: `{performance_stats['consecutive_losses']}`
├─ Toplam Kazanç: `{performance_stats['wins']}`
└─ Toplam Kayıp: `{performance_stats['losses']}`
        """
    else:
        active_text = """
🟢 **AKTİF SİNYAL YOK**

Bot şu anda sinyal takibi yapmıyor.
Yeni patternler geldiğinde otomatik sinyal üretilecek.

**📊 Sistem Durumu:**
├─ Ardışık Kayıp: `{performance_stats['consecutive_losses']}`
├─ Toplam Sinyal: `{performance_stats['total_signals']}`
└─ Kazanç Oranı: `{(performance_stats['wins']/(performance_stats['wins']+performance_stats['losses'])*100) if (performance_stats['wins']+performance_stats['losses']) > 0 else 0:.1f}%`
        """.format(**performance_stats)
    
    await event.reply(active_text)

# ==============================================================================
# Gelişmiş Telegram Mesaj İşleyicileri
# ==============================================================================

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_source_channel_message(event):
    """YENİ MESAJ İŞLEYİCİ - DAHA GÜVENLİ"""
    
    # Ardışık kayıp kontrolü - 3 kayıptan sonra sinyal durur
    if performance_stats['consecutive_losses'] >= 3:
        print(f"⛔ Sinyal sistemi durduruldu. Ardışık kayıp: {performance_stats['consecutive_losses']}")
        return

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
        # YENİ SIKI SİNYAL TETİKLEYİCİ
        should_send, reason = should_send_signal(game_info)
        
        if should_send:
            trigger_game_num = game_info['game_number']
            signal_suit = reason
            
            next_game_num = get_next_game_number(trigger_game_num)
            await send_optimized_signal(next_game_num, signal_suit, game_info)
        else:
            print(f"DEBUG: Sinyal gönderilmedi. Sebep: {reason} | Patternler: {game_info['patterns']}")

# ==============================================================================
# Botun Başlatılması
# ==============================================================================
if __name__ == '__main__':
    print("🤖 YENİ BACCARAT BOTU v3.0 BAŞLATILIYOR...")
    print("⚠️  ÖNEMLİ DEĞİŞİKLİKLER:")
    print("    - Sadece #C2_3, #C3_2, #C3_3 patternleri")
    print("    - 3 ardışık kayıpta otomatik durdurma")
    print("    - Daha düşük risk (2 adım Martingale)")
    print("    - Çok daha sıkı filtreler")
    print("📞 Telegram komutları aktif:")
    print("   /start, /help, /stats, /status, /patterns, /active, /analysis")
    print("=====================================")
    
    with client:
        client.run_until_disconnected()