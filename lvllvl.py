import re
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
import asyncio
import sys
from datetime import datetime
from collections import defaultdict, deque

# ==============================================================================
# Telegram API Bilgileri ve Kanal Ayarları
# ==============================================================================
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"

client = TelegramClient('lvbel_bot', API_ID, API_HASH)

# ==============================================================================
# Global Değişkenler - ÇİFT SİSTEM
# ==============================================================================
game_results = {}
martingale_trackers = {}
MAX_MARTINGALE_STEPS = 6  # 🚀 7 ADIM (0,1,2,3,4,5,6)
MAX_GAME_NUMBER = 1440
is_pattern_signal_active = False  # 🎯 PATTERN SİSTEM İÇİN
is_felaket_signal_active = False  # ⚡ FELAKET SİSTEM İÇİN
MAX_CONSECUTIVE_LOSSES = 5
COOLDOWN_AFTER_LOSS = 5

# ==============================================================================
# ÇAKIŞMA ÖNLEME SİSTEMİ - YENİ
# ==============================================================================
pending_signals = set()  # Bekleyen sinyaller için oyun numaraları
SIGNAL_COOLDOWN = 3  # Aynı oyun numarası için sinyal göndermeden önce beklenecek oyun sayısı

# ==============================================================================
# 7 EL KURALI - FELAKET STRATEJİSİ DEĞİŞKENLERİ (BAĞIMSIZ)
# ==============================================================================
suit_tracker = {
    '♦': {'count': 0, 'last_seen': 0, 'streak': 0},
    '♥': {'count': 0, 'last_seen': 0, 'streak': 0},
    '♠': {'count': 0, 'last_seen': 0, 'streak': 0},
    '♣': {'count': 0, 'last_seen': 0, 'streak': 0}
}
last_processed_game = 0
FELAKET_THRESHOLD = 5  # 🎯 5 EL KURALI
SUPER_FELAKET_THRESHOLD = 7  # 🚨 7 EL SUPER FELAKET
ULTRA_FELAKET_THRESHOLD = 11  # 💥 11 EL ULTRA FELAKET

# ==============================================================================
# PATTERN KONFİGÜRASYONU - AYRI SİSTEM
# ==============================================================================
STRONG_PATTERNS = ['#C3_3', '#C2_3']

PATTERN_STRENGTH = {
    '#C3_3': 10,  # 🏆 EN YÜKSEK GÜVEN
    '#C2_3': 8,   # 🔥 ÇOK GÜÇLÜ
}

MIN_PATTERN_STRENGTH = 8
FINAL_MIN_STRENGTH = 8

STRONG_INDICATORS = ['✅', '🔰', '⭐', '🔥', '⚡', '🎯']

# ==============================================================================
# İSTATİSTİK SİSTEMİ - ÇİFT SİSTEM
# ==============================================================================
performance_stats = {
    'total_signals': 0, 'wins': 0, 'losses': 0,
    'active_since': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'last_signal': None, 'consecutive_losses': 0, 'max_consecutive_losses': 0,
    'games_since_last_loss': 0, 'cooldown_mode': False,
    'max_martingale_steps_reached': 0,
    'step_distribution': {i: 0 for i in range(1, MAX_MARTINGALE_STEPS + 2)},
    'source_channel': KANAL_KAYNAK_ID,
    'session_active': True,
    'felaket_signals': 0,
    'super_felaket_signals': 0,
    'ultra_felaket_signals': 0,
    'pattern_signals': 0,
    'conflict_preventions': 0  # 🎯 YENİ: Çakışma önleme istatistiği
}

early_win_stats = {
    'total_signals': 0, 'early_wins_1_4': 0, 'late_wins_5_7': 0,
    'step_1_wins': 0, 'step_2_wins': 0, 'step_3_wins': 0, 'step_4_wins': 0,
    'pattern_performance': {
        '#C3_3': {'attempts': 0, 'early_wins': 0, 'avg_step': 0},
        '#C2_3': {'attempts': 0, 'early_wins': 0, 'avg_step': 0}
    },
    'felaket_performance': {
        'FELAKET': {'attempts': 0, 'early_wins': 0, 'avg_step': 0},
        'SUPER_FELAKET': {'attempts': 0, 'early_wins': 0, 'avg_step': 0},
        'ULTRA_FELAKET': {'attempts': 0, 'early_wins': 0, 'avg_step': 0}
    },
    'current_streak_early_wins': 0, 'max_streak_early_wins': 0
}

# ==============================================================================
# ÇAKIŞMA ÖNLEME FONKSİYONLARI - YENİ
# ==============================================================================

def is_signal_conflict(game_num):
    """Aynı oyun numarası için çakışma kontrolü"""
    # Aktif martingale trackerlarda bu oyun numarası var mı?
    for tracker_game_num in martingale_trackers.keys():
        if tracker_game_num == game_num:
            return True
    
    # Bekleyen sinyallerde bu oyun numarası var mı?
    if game_num in pending_signals:
        return True
        
    return False

def add_pending_signal(game_num):
    """Bekleyen sinyallere ekle"""
    pending_signals.add(game_num)
    # 3 oyun sonra temizle (cooldown)
    asyncio.create_task(remove_pending_signal_after_delay(game_num))

async def remove_pending_signal_after_delay(game_num):
    """Belirli bir süre sonra bekleyen sinyali temizle"""
    await asyncio.sleep(SIGNAL_COOLDOWN * 60)  # Her oyun ~1 dakika
    if game_num in pending_signals:
        pending_signals.remove(game_num)

def get_available_game_number(base_game_num, system_type):
    """Mevcut olan en yakın oyun numarasını bul"""
    if not is_signal_conflict(base_game_num):
        return base_game_num
    
    # Çakışma varsa, +1, +2, +3 şeklinde deneyerek uygun numara bul
    for offset in range(1, 6):  # Maksimum 5 oyun ileriyi dene
        test_game_num = get_game_number_after_n(base_game_num, offset)
        if not is_signal_conflict(test_game_num):
            performance_stats['conflict_preventions'] += 1
            print(f"🔄 ÇAKIŞMA ÖNLENDİ: #{base_game_num} -> #{test_game_num} ({system_type})")
            return test_game_num
    
    # Uygun numara bulunamazsa None döndür
    return None

# ==============================================================================
# 7 EL KURALI - FELAKET STRATEJİSİ FONKSİYONLARI (BAĞIMSIZ)
# ==============================================================================

def update_felaket_tracker(game_info):
    """7 El Kuralı takip sistemini güncelle - BAĞIMSIZ"""
    global suit_tracker, last_processed_game
    
    if not game_info['game_number'] or game_info['game_number'] <= last_processed_game:
        return
        
    last_processed_game = game_info['game_number']
    current_game = game_info['game_number']
    
    # Tüm suitlerin count'unu artır
    for suit in suit_tracker:
        suit_tracker[suit]['count'] += 1
        suit_tracker[suit]['streak'] += 1
    
    # Oyuncu kartlarındaki suitleri tespit et ve sıfırla
    player_cards = game_info['player_cards']
    if player_cards:
        for suit in suit_tracker:
            if suit in player_cards:
                suit_tracker[suit]['count'] = 0
                suit_tracker[suit]['last_seen'] = current_game
                suit_tracker[suit]['streak'] = 0
    
    # DEBUG: Suit durumlarını yazdır (5+ el çıkmayanları göster)
    print(f"🎯 FELAKET TRACKER - Game #{current_game}:")
    for suit, data in suit_tracker.items():
        if data['count'] >= 5:  # Sadece 5+ el çıkmayanları göster
            print(f"   {suit}: {data['count']} el çıkmadı")

def get_felaket_signals():
    """5+ El Kuralı'na göre sinyal üret - BAĞIMSIZ"""
    felaket_signals = []
    
    for suit, data in suit_tracker.items():
        missing_count = data['count']
        
        if missing_count >= ULTRA_FELAKET_THRESHOLD:
            # 💥 ULTRA FELAKET - 11+ EL ÇIKMADI
            felaket_signals.append({
                'suit': suit,
                'type': 'ULTRA_FELAKET',
                'strength': 15,
                'missing_games': missing_count,
                'reason': f"{suit} {missing_count} EL ÇIKMADI!",
                'system': 'FELAKET'
            })
            
        elif missing_count >= SUPER_FELAKET_THRESHOLD:
            # 🚨 SUPER FELAKET - 7+ EL ÇIKMADI
            felaket_signals.append({
                'suit': suit,
                'type': 'SUPER_FELAKET',
                'strength': 12,
                'missing_games': missing_count,
                'reason': f"{suit} {missing_count} EL ÇIKMADI!",
                'system': 'FELAKET'
            })
            
        elif missing_count >= FELAKET_THRESHOLD:
            # ⚡ FELAKET - 5+ EL ÇIKMADI
            felaket_signals.append({
                'suit': suit,
                'type': 'FELAKET', 
                'strength': 9,
                'missing_games': missing_count,
                'reason': f"{suit} {missing_count} EL ÇIKMADI!",
                'system': 'FELAKET'
            })
    
    return felaket_signals

def should_send_felaket_signal():
    """FELAKET SİSTEMİ - Sadece 5+ El Kuralı'na göre sinyal ver"""
    # 1. GÜVENLİK KONTROLLERİ
    is_safe, reason = check_safety_conditions()
    if not is_safe:
        return False, reason

    # 2. AKTİF SİNYAL KONTROLÜ - SADECE FELAKET SİSTEMİ İÇİN
    if is_felaket_signal_active:
        return False, "Felaket sinyali zaten aktif"

    # 3. FELAKET SİNYALLERİNİ KONTROL ET
    felaket_signals = get_felaket_signals()
    
    if felaket_signals:
        # En güçlü felaket sinyalini seç
        best_felaket = max(felaket_signals, key=lambda x: x['strength'])
        return True, best_felaket
    
    return False, "Felaket kriteri sağlanmadı"

# ==============================================================================
# PATTERN SİSTEMİ FONKSİYONLARI (BAĞIMSIZ)
# ==============================================================================

def should_send_pattern_signal(game_info):
    """PATTERN SİSTEMİ - Sadece pattern'lere göre sinyal ver"""
    # 1. GÜVENLİK KONTROLLERİ
    is_safe, reason = check_safety_conditions()
    if not is_safe:
        return False, reason

    # 2. AKTİF SİNYAL KONTROLÜ - SADECE PATTERN SİSTEMİ İÇİN
    if is_pattern_signal_active:
        return False, "Pattern sinyali zaten aktif"

    # 3. 🎯 PATTERN KONTROLÜ
    if not game_info['patterns'] or game_info['pattern_strength'] < MIN_PATTERN_STRENGTH:
        return False, "Pattern kalitesi yetersiz"

    # 4. 🎯 FİNAL KALİTE KONTROLÜ
    if not game_info['is_final']:
        return False, "Final kalitesi yok"

    # 5. 🎯 KART ANALİZİ
    signal_suit = extract_largest_value_suit(game_info['player_cards'])
    if not signal_suit:
        return False, "Uygun kart yok"

    pattern_signal = {
        'suit': signal_suit,
        'type': 'PATTERN',
        'strength': game_info['pattern_strength'],
        'patterns': game_info['patterns'],
        'reason': "",  # 🎯 DEĞİŞİKLİK: Pattern isimlerini gizle
        'system': 'PATTERN'
    }

    return True, pattern_signal

# ==============================================================================
# ORTAK FONKSİYONLAR
# ==============================================================================

def check_safety_conditions():
    """Tüm güvenlik kontrollerini yap - ORTAK"""
    if not performance_stats['session_active']:
        return False, "Session durduruldu"
    
    if performance_stats['consecutive_losses'] >= MAX_CONSECUTIVE_LOSSES:
        return False, f"Maksimum {MAX_CONSECUTIVE_LOSSES} ardışık kayıp"
    
    if performance_stats['cooldown_mode']:
        if performance_stats['games_since_last_loss'] < COOLDOWN_AFTER_LOSS:
            return False, f"Cooldown: {performance_stats['games_since_last_loss']}/{COOLDOWN_AFTER_LOSS}"
        else:
            performance_stats['cooldown_mode'] = False
            performance_stats['games_since_last_loss'] = 0
    
    return True, "Güvenli"

def update_early_win_stats(signal_type, pattern, win_step):
    """1-4 kazanç istatistiklerini güncelle - ORTAK"""
    if signal_type == 'PATTERN' and pattern in early_win_stats['pattern_performance']:
        stats = early_win_stats['pattern_performance'][pattern]
        stats['attempts'] += 1
        if 1 <= win_step <= 4:
            stats['early_wins'] += 1
            stats['avg_step'] = ((stats['avg_step'] * (stats['attempts'] - 1)) + win_step) / stats['attempts']
    
    elif signal_type == 'FELAKET' and pattern in early_win_stats['felaket_performance']:
        stats = early_win_stats['felaket_performance'][pattern]
        stats['attempts'] += 1
        if 1 <= win_step <= 4:
            stats['early_wins'] += 1
            stats['avg_step'] = ((stats['avg_step'] * (stats['attempts'] - 1)) + win_step) / stats['attempts']
    
    if 1 <= win_step <= 4:
        early_win_stats['early_wins_1_4'] += 1
        early_win_stats['current_streak_early_wins'] += 1
        early_win_stats['max_streak_early_wins'] = max(
            early_win_stats['max_streak_early_wins'],
            early_win_stats['current_streak_early_wins']
        )
        early_win_stats[f'step_{win_step}_wins'] += 1
    else:
        early_win_stats['late_wins_5_7'] += 1
        early_win_stats['current_streak_early_wins'] = 0

def get_baccarat_value(card_char):
    if card_char == '10': return 10
    if card_char in 'AKQJT': return 0
    elif card_char.isdigit(): return int(card_char)
    return -1

def get_next_game_number(current_game_num):
    next_num = current_game_num + 1
    return 1 if next_num > MAX_GAME_NUMBER else next_num

def get_game_number_after_n(current_game_num, n):
    next_num = current_game_num + n
    while next_num > MAX_GAME_NUMBER:
        next_num -= MAX_GAME_NUMBER
    return next_num

def extract_largest_value_suit(cards_str):
    """Kart analizi - ORTAK"""
    cards_str_clean = cards_str.replace(' ', '')
    cards_match = re.search(r'\(([^)]+)\)', cards_str_clean)
    if not cards_match:
        return None
        
    cards_content = cards_match.group(1)
    cards = re.findall(r'([A-Z0-9]+)([♦♥♠♣]️?)', cards_content)
    if not cards:
        return None

    max_value = -1
    largest_value_suit = None
    values = []

    for card_char, suit in cards:
        value = get_baccarat_value(card_char)
        values.append(value)
        if value > max_value:
            max_value = value
            largest_value_suit = suit

    # FİLTRELER
    high_value_cards = [7, 8, 9]
    if max_value in high_value_cards:
        print(f"🎯 DEBUG - YÜKSEK DEĞERLİ KART {max_value}")
    elif max_value <= 3:
        print(f"⚠️ DEBUG - DÜŞÜK DEĞERLİ KART {max_value}")
        return None

    # NATURAL KONTROLÜ
    if len(values) == 3:
        total_value = sum(values) % 10
        if total_value in [8, 9]:
            print(f"🔥 DEBUG - NATURAL {total_value}")

    # FİLTRELEME
    if len(values) == 2 and values[0] == values[1]:
        return None
    if len(values) == 3 and len(set(values)) < 2:
        return None
    if max_value == 0:
        return None

    return largest_value_suit

def extract_game_info_from_message(text):
    game_info = {
        'game_number': None, 'player_cards': '', 'banker_cards': '',
        'is_final': False, 'patterns': [], 'pattern_strength': 0,
        'has_strong_indicator': False, 'raw_message': text,
        'is_tie': False
    }
    
    # PATTERN TESPİTİ
    detected_patterns = [p for p in STRONG_PATTERNS if p in text]
    game_info['patterns'] = detected_patterns
    game_info['pattern_strength'] = sum(PATTERN_STRENGTH.get(p, 0) for p in detected_patterns)
    game_info['has_strong_indicator'] = any(indicator in text for indicator in STRONG_INDICATORS)
    game_info['is_tie'] = '🔰' in text

    # KALİTE KONTROLÜ
    game_info['is_final'] = (
        game_info['pattern_strength'] >= FINAL_MIN_STRENGTH and 
        game_info['has_strong_indicator'] and
        len(game_info['patterns']) >= 1
    )

    # OYUN BİLGİSİ ÇIKARMA
    patterns = [
        r'[⏱⚠️]*\**№?(\d+)\**.*?(\d+\s*\([^)]+\)).*?(\d+\s*\([^)]+\))',
        r'#N?(\d+).*?(\d+\s*\([^)]+\)).*?(\d+\s*\([^)]+\))',
        r'№(\d+).*?(\d+\s*\([^)]+\)).*?(\d+\s*\([^)]+\))',
    ]
    
    game_match = None
    for pattern in patterns:
        game_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if game_match:
            break
    
    if game_match:
        game_info['game_number'] = int(game_match.group(1))
        game_info['player_cards'] = game_match.group(2)
        if len(game_match.groups()) >= 3:
            game_info['banker_cards'] = game_match.group(3)

    return game_info

async def send_signal(game_num, signal_data, current_game_info):
    """Sinyal gönder - DÜZELTİLMİŞ FORMAT"""
    global is_pattern_signal_active, is_felaket_signal_active, performance_stats
    
    # 🎯 ÇAKIŞMA KONTROLÜ - YENİ
    if is_signal_conflict(game_num):
        available_game_num = get_available_game_number(game_num, signal_data.get('system', 'PATTERN'))
        if available_game_num is None:
            print(f"❌ ÇAKIŞMA: #{game_num} için uygun oyun numarası bulunamadı")
            return
        game_num = available_game_num
    
    performance_stats['total_signals'] += 1
    early_win_stats['total_signals'] += 1
    performance_stats['last_signal'] = datetime.now().strftime('%H:%M:%S')
    
    # SİNYAL TİPİNE GÖRE FORMAT - DÜZELTME
    signal_type = signal_data.get('type', 'PATTERN')
    system_type = signal_data.get('system', 'PATTERN')
    
    # 🎯 DÜZELTME: Pattern sinyallerinde sadece güven seviyesi, Felaket'te sebep
    if signal_type == 'ULTRA_FELAKET':
        signal_strength = "🏆 MAXIMUM GÜVEN"
        signal_reason = signal_data['reason']
        performance_stats['ultra_felaket_signals'] += 1
    elif signal_type == 'SUPER_FELAKET':
        signal_strength = "🔥 YÜKSEK GÜVEN" 
        signal_reason = signal_data['reason']
        performance_stats['super_felaket_signals'] += 1
    elif signal_type == 'FELAKET':
        signal_strength = "⚡ ORTA GÜVEN"
        signal_reason = signal_data['reason']
        performance_stats['felaket_signals'] += 1
    else:
        # 🎯 DÜZELTME: Pattern için hiç pattern ismi yazma
        signal_strength = "⚡ YÜKSEK GÜVEN"
        signal_reason = ""  # Pattern için sebep yok
        performance_stats['pattern_signals'] += 1
    
    # 🎯 DÜZELTME: Yeni format - Pattern'de sadece güven seviyesi
    if system_type == 'PATTERN':
        signal_full_text = f"**#N{game_num} - Oyuncu {signal_data['suit']} - {MAX_MARTINGALE_STEPS+1}D - {signal_strength}**"
    else:
        signal_full_text = f"**#N{game_num} - Oyuncu {signal_data['suit']} - {MAX_MARTINGALE_STEPS+1}D - {signal_strength} {signal_reason}**"

    try:
        sent_message = await client.send_message(KANAL_HEDEF, signal_full_text)
        
        # 🎯 DÜZELTME: Pattern sinyali +2, Felaket sinyali +1 ileri atacak
        if system_type == 'PATTERN':
            expected_game_to_check = get_game_number_after_n(current_game_info['game_number'], 2)
        else:  # FELAKET
            expected_game_to_check = get_game_number_after_n(current_game_info['game_number'], 1)
        
        # 🎯 DÜZELTME: Felaket sinyallerinde missing_games bilgisini kaydet
        martingale_data = {
            'message_obj': sent_message, 
            'step': 0, 
            'signal_suit': signal_data['suit'],
            'sent_game_number': game_num, 
            'expected_game_number_for_check': expected_game_to_check,
            'pattern_strength': signal_data.get('strength', 0),
            'patterns': signal_data.get('patterns', []),
            'signal_type': signal_type,
            'system': system_type,
            'source_channel': performance_stats['source_channel']
        }
        
        # Felaket sinyallerinde missing_games bilgisini ekle
        if system_type == 'FELAKET' and 'missing_games' in signal_data:
            martingale_data['missing_games'] = signal_data['missing_games']
            
        martingale_trackers[game_num] = martingale_data
        add_pending_signal(game_num)  # 🎯 YENİ: Bekleyen sinyallere ekle
        
        # SİSTEM TİPİNE GÖRE AKTİVITE FLAG'INI AYARLA
        if system_type == 'PATTERN':
            is_pattern_signal_active = True
        elif system_type == 'FELAKET':
            is_felaket_signal_active = True
            
        print(f"🎯 {system_type} SİNYAL: {signal_full_text}")
        print(f"🔍 İlk kontrol #{expected_game_to_check} oyununda yapılacak")
    except Exception as e: 
        print(f"❌ Sinyal hatası: {e}")

async def check_martingale_trackers():
    """MARTINGALE TAKİP - DÜZELTİLMİŞ KAZANÇ FORMATI"""
    global martingale_trackers, is_pattern_signal_active, is_felaket_signal_active, performance_stats
    trackers_to_remove = []
    
    for signal_game_num, tracker_info in list(martingale_trackers.items()):
        current_step = tracker_info['step']
        game_to_check = tracker_info['expected_game_number_for_check']
        
        if game_to_check not in game_results:
            continue
            
        result_info = game_results.get(game_to_check)
        
        # BERABERE KONTROLÜ
        if result_info.get('is_tie', False):
            next_game_to_check = get_next_game_number(game_to_check)
            tracker_info['expected_game_number_for_check'] = next_game_to_check
            try: 
                await tracker_info['message_obj'].edit(
                    f"**#N{signal_game_num} - {tracker_info['signal_suit']} | 🔄 {current_step + 1}️⃣ (Berabere)**"
                )
                print(f"🔄 BERABERE: #{signal_game_num} -> #{next_game_to_check} kontrol edilecek")
            except Exception: 
                pass
            continue

        if not result_info.get('player_cards'):
            continue

        player_cards_str = result_info['player_cards']
        signal_won = False
        if tracker_info['signal_suit']:
            suit_emoji = tracker_info['signal_suit']
            # 🎯 DÜZELTME: 3 kartı da kontrol et
            signal_won = suit_emoji in player_cards_str
        
        if signal_won:
            # KAZANÇ
            win_step = current_step + 1
            
            # İSTATİSTİK GÜNCELLEME
            system_type = tracker_info.get('system', 'PATTERN')
            signal_type = tracker_info.get('signal_type', 'PATTERN')
            
            if system_type == 'PATTERN' and tracker_info['patterns']:
                main_pattern = tracker_info['patterns'][0]
                update_early_win_stats('PATTERN', main_pattern, win_step)
            elif system_type == 'FELAKET':
                update_early_win_stats('FELAKET', signal_type, win_step)
            
            performance_stats['max_martingale_steps_reached'] = max(
                performance_stats['max_martingale_steps_reached'], win_step
            )
            performance_stats['step_distribution'][win_step] += 1
            
            performance_stats['wins'] += 1
            performance_stats['consecutive_losses'] = 0
            performance_stats['games_since_last_loss'] = 0
            
            # 🎯 DÜZELTME: Yeni kazanç formatı
            system_type = tracker_info.get('system', 'PATTERN')
            
            if system_type == 'PATTERN':
                # Pattern kazancı: Sadece emoji ve adım
                win_text = f"**#N{signal_game_num} - {tracker_info['signal_suit']} | ✅ {win_step}️⃣**"
            else:  # FELAKET
                # Felaket kazancı: Emoji, adım ve kaç el çıkmadığı
                missing_games = tracker_info.get('missing_games', 0)
                win_text = f"**#N{signal_game_num} - {tracker_info['signal_suit']} | ✅ {win_step}️⃣ {missing_games} EL ÇIKMADI**"
                
            try: 
                await tracker_info['message_obj'].edit(win_text)
                print(f"✅ KAZANÇ: #{signal_game_num} - {win_step}. adımda kazanıldı")
                print(f"🔍 Kontrol edilen oyun: #{game_to_check}")
                print(f"🔍 Oyuncu kartları: {player_cards_str}")
            except Exception: 
                pass
            trackers_to_remove.append(signal_game_num)
            
            # SİSTEM TİPİNE GÖRE AKTİVITE FLAG'INI SIFIRLA
            system_type = tracker_info.get('system', 'PATTERN')
            if system_type == 'PATTERN':
                is_pattern_signal_active = False
            elif system_type == 'FELAKET':
                is_felaket_signal_active = False
            
        else:
            # KAYIP
            if current_step < MAX_MARTINGALE_STEPS:
                # MARTINGALE DEVAM
                tracker_info['step'] += 1
                next_game_to_check = get_next_game_number(game_to_check)
                tracker_info['expected_game_number_for_check'] = next_game_to_check
                next_step = tracker_info['step'] + 1
                
                try: 
                    await tracker_info['message_obj'].edit(
                        f"**#N{signal_game_num} - {tracker_info['signal_suit']} | 🔄 {next_step}️⃣**"
                    )
                    print(f"🔄 MARTINGALE: #{signal_game_num} -> #{next_game_to_check} kontrol edilecek (Adım {next_step})")
                except Exception: 
                    pass
                    
            else:
                # MAKSİMUM KAYIP
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
                    print(f"❌ KAYIP: #{signal_game_num} - Tüm martingale adımları denendi")
                    print(f"🔍 Son kontrol edilen oyun: #{game_to_check}")
                    print(f"🔍 Oyuncu kartları: {player_cards_str}")
                except Exception: 
                    pass
                trackers_to_remove.append(signal_game_num)
                
                # SİSTEM TİPİNE GÖRE AKTİVITE FLAG'INI SIFIRLA
                system_type = tracker_info.get('system', 'PATTERN')
                if system_type == 'PATTERN':
                    is_pattern_signal_active = False
                elif system_type == 'FELAKET':
                    is_felaket_signal_active = False

    # TEMİZLİK
    for game_num in trackers_to_remove:
        if game_num in martingale_trackers:
            del martingale_trackers[game_num]

# ==============================================================================
# KOMUTLAR - GÜNCELLENMİŞ
# ==============================================================================

@client.on(events.NewMessage(pattern='/trackers'))
async def trackers_command(event):
    if not martingale_trackers:
        await event.reply("🔍 **Aktif martingale takipçisi yok**")
        return
    
    tracker_list = []
    for game_num, tracker in martingale_trackers.items():
        signal_type = tracker.get('signal_type', 'PATTERN')
        system_type = tracker.get('system', 'PATTERN')
        
        if signal_type == 'ULTRA_FELAKET':
            type_emoji = "💥"
        elif signal_type == 'SUPER_FELAKET':
            type_emoji = "🚨"
        elif signal_type == 'FELAKET':
            type_emoji = "⚡"
        else:
            type_emoji = "🎯"
        
        tracker_list.append(
            f"• {type_emoji} #N{game_num} - {tracker['signal_suit']} "
            f"(Adım {tracker['step'] + 1}/{MAX_MARTINGALE_STEPS + 1}) - {system_type}\n"
            f"  ↳ Sonraki kontrol: #{tracker['expected_game_number_for_check']}"
        )
    
    await event.reply("🔍 **Aktif Martingale Takipçileri:**\n" + "\n".join(tracker_list))

@client.on(events.NewMessage(pattern='/felaket'))
async def felaket_command(event):
    """5+ El Kuralı durumunu göster"""
    status_lines = ["🎯 **5+ EL KURALI - FELAKET STRATEJİSİ**"]
    
    active_felakets = 0
    for suit, data in suit_tracker.items():
        if data['count'] >= ULTRA_FELAKET_THRESHOLD:
            status = f"💥 **ULTRA: {suit} {data['count']} EL ÇIKMADI!**"
            active_felakets += 1
        elif data['count'] >= SUPER_FELAKET_THRESHOLD:
            status = f"🚨 **SUPER: {suit} {data['count']} EL ÇIKMADI!**"
            active_felakets += 1
        elif data['count'] >= FELAKET_THRESHOLD:
            status = f"⚡ **FELAKET: {suit} {data['count']} EL ÇIKMADI!**"
            active_felakets += 1
        elif data['count'] >= 3:
            status = f"🎯 {suit}: {data['count']} el çıkmadı"
        else:
            status = f"✅ {suit}: {data['count']} el çıkmadı"
        
        status_lines.append(status)
    
    status_lines.append(f"\n🔰 **Aktif Felaket Sinyalleri:** {active_felakets}")
    status_lines.append(f"🎯 **Eşikler:** Felaket: {FELAKET_THRESHOLD}+, Super: {SUPER_FELAKET_THRESHOLD}+, Ultra: {ULTRA_FELAKET_THRESHOLD}+")
    
    await event.reply("\n".join(status_lines))

@client.on(events.NewMessage(pattern='/systems'))
async def systems_command(event):
    """Çift sistem durumunu göster"""
    pattern_status = "✅ AKTİF" if is_pattern_signal_active else "❌ PASİF"
    felaket_status = "✅ AKTİF" if is_felaket_signal_active else "❌ PASİF"
    session_status = "✅ AKTİF" if performance_stats['session_active'] else "❌ DURDURULDU"
    
    await event.reply(f"""
🔄 **ÇİFT SİSTEM DURUMU**

🎯 **PATTERN SİSTEMİ:**
• Durum: {pattern_status}
• Sinyaller: {performance_stats['pattern_signals']}
• Aktif Patternler: {', '.join(STRONG_PATTERNS)}

⚡ **FELAKET SİSTEMİ:**
• Durum: {felaket_status}
• Sinyaller: {performance_stats['felaket_signals'] + performance_stats['super_felaket_signals'] + performance_stats['ultra_felaket_signals']}
• Eşik: {FELAKET_THRESHOLD}+ el

🛡️ **ORTAK GÜVENLİK:**
• Session: {session_status}
• Martingale: {MAX_MARTINGALE_STEPS + 1} adım
• Aktif Takipçi: {len(martingale_trackers)}
• Çakışma Önleme: {performance_stats['conflict_preventions']}
""")

@client.on(events.NewMessage(pattern='/daily'))
async def daily_command(event):
    """Günlük durumu göster"""
    session_status = "✅ AKTİF" if performance_stats['session_active'] else "❌ DURDURULDU"
    
    total_signals = performance_stats['total_signals']
    pattern_rate = (performance_stats['pattern_signals']/total_signals*100) if total_signals > 0 else 0
    felaket_rate = ((performance_stats['felaket_signals'] + performance_stats['super_felaket_signals'] + performance_stats['ultra_felaket_signals'])/total_signals*100) if total_signals > 0 else 0
    
    await event.reply(f"""
📅 **ÇİFT SİSTEM - GÜNLÜK DURUM**

⚡ **Performans:**
• Toplam Sinyal: {performance_stats['total_signals']}
• Kazanç: {performance_stats['wins']} | Kayıp: {performance_stats['losses']}
• 1-4 Kazanç: {early_win_stats['early_wins_1_4']}
• Kazanç Oranı: {(early_win_stats['early_wins_1_4']/performance_stats['total_signals']*100) if performance_stats['total_signals'] > 0 else 0:.1f}%

🎯 **Sistem Dağılımı:**
• Pattern: {performance_stats['pattern_signals']} (%{pattern_rate:.1f})
• Felaket: {performance_stats['felaket_signals']} + {performance_stats['super_felaket_signals']} + {performance_stats['ultra_felaket_signals']} (%{felaket_rate:.1f})

🛡️ **Güvenlik:**
• Session: {session_status}
• Martingale: {MAX_MARTINGALE_STEPS + 1} adım
• Max Kayıp: {MAX_CONSECUTIVE_LOSSES}
• Cooldown: {COOLDOWN_AFTER_LOSS} oyun
• Aktif Takipçi: {len(martingale_trackers)}
• Çakışma Önleme: {performance_stats['conflict_preventions']}
""")

@client.on(events.NewMessage(pattern='/reset_daily'))
async def reset_daily_command(event):
    """Günlük istatistikleri sıfırla"""
    global suit_tracker, is_pattern_signal_active, is_felaket_signal_active, pending_signals
    
    performance_stats['wins'] = 0
    performance_stats['losses'] = 0
    performance_stats['consecutive_losses'] = 0
    performance_stats['cooldown_mode'] = False
    performance_stats['games_since_last_loss'] = 0
    performance_stats['session_active'] = True
    performance_stats['felaket_signals'] = 0
    performance_stats['super_felaket_signals'] = 0
    performance_stats['ultra_felaket_signals'] = 0
    performance_stats['pattern_signals'] = 0
    performance_stats['conflict_preventions'] = 0
    
    # Sinyal flag'lerini sıfırla
    is_pattern_signal_active = False
    is_felaket_signal_active = False
    
    # Felaket tracker'ı sıfırla
    for suit in suit_tracker:
        suit_tracker[suit] = {'count': 0, 'last_seen': 0, 'streak': 0}
    
    # Bekleyen sinyalleri temizle
    pending_signals.clear()
    
    await event.reply("🔄 **Tüm istatistikler sıfırlandı! Çift sistem yeniden başlatıldı.**")

@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    await event.reply(f"""
🤖 **BACCARAT BOT - ÇİFT SİSTEM** 🚀

🎯 **SİSTEM 1: PATTERN TABANLI**
• **Patternler:** #C3_3 ve #C2_3
• **Kalite Filtresi:** Güç ≥ 8 + İndikatör
• **Kart Analizi:** Yüksek değerli kartlar
• **Sinyal Zamanı:** +2 el ileri

⚡ **SİSTEM 2: 5+ EL KURALI (FELAKET)**
• **Matematiksel Garanti:** Her suit 7 el içinde çıkar
• **Felaket Sinyali:** 5+ el çıkmayan suit
• **Super Felaket:** 7+ el çıkmayan suit
• **Ultra Felaket:** 11+ el çıkmayan suit
• **Martingale:** {MAX_MARTINGALE_STEPS + 1} adım
• **Sinyal Zamanı:** +1 el ileri

🔄 **BAĞIMSIZ ÇALIŞMA:**
• İki sistem birbirinden bağımsız
• Aynı anda aktif sinyal olabilir
• Ayrı martingale takipleri

🛡️ **ORTAK AYARLAR:**
• Martingale: {MAX_MARTINGALE_STEPS + 1} adım
• Max Kayıp: {MAX_CONSECUTIVE_LOSSES}  
• Cooldown: {COOLDOWN_AFTER_LOSS} oyun
• Çakışma Önleme: Aktif

**Komutlar:**
/daily - Günlük durum
/systems - Sistem durumu
/felaket - 5+ El Kuralı durumu
/reset_daily - İstatistikleri sıfırla
/trackers - Aktif martingaleler
/stats - Detaylı istatistikler
/patterns - Pattern bilgileri
""")

@client.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    total = performance_stats['wins'] + performance_stats['losses']
    win_rate = (performance_stats['wins'] / total * 100) if total > 0 else 0
    
    total_early = early_win_stats['early_wins_1_4'] + early_win_stats['late_wins_5_7']
    early_win_rate = (early_win_stats['early_wins_1_4'] / total_early * 100) if total_early > 0 else 0
    
    session_status = "✅ AKTİF" if performance_stats['session_active'] else "❌ DURDURULDU"
    
    # Pattern başarı oranları
    pattern_stats = []
    for pattern, stats in early_win_stats['pattern_performance'].items():
        if stats['attempts'] > 0:
            success_rate = (stats['early_wins'] / stats['attempts'] * 100)
            pattern_stats.append(f"• {pattern}: %{success_rate:.1f} ({stats['early_wins']}/{stats['attempts']})")
    
    # Felaket başarı oranları
    felaket_stats = []
    for felaket_type, stats in early_win_stats['felaket_performance'].items():
        if stats['attempts'] > 0:
            success_rate = (stats['early_wins'] / stats['attempts'] * 100)
            felaket_stats.append(f"• {felaket_type}: %{success_rate:.1f} ({stats['early_wins']}/{stats['attempts']})")
    
    # Sinyal dağılımı
    total_signals = performance_stats['total_signals']
    pattern_percent = (performance_stats['pattern_signals']/total_signals*100) if total_signals > 0 else 0
    felaket_percent = ((performance_stats['felaket_signals'] + performance_stats['super_felaket_signals'] + performance_stats['ultra_felaket_signals'])/total_signals*100) if total_signals > 0 else 0
    
    await event.reply(f"""
📊 **ÇİFT SİSTEM - DETAYLI İSTATİSTİKLER**

🎯 **Performans:**
• Sinyal: {performance_stats['total_signals']}
• Kazanç: {performance_stats['wins']} | Kayıp: {performance_stats['losses']}
• Oran: {win_rate:.1f}%

🎯 **1-4 Kazanç:**
• Erken Kazanç (1-4): {early_win_stats['early_wins_1_4']}
• Geç Kazanç (5-7): {early_win_stats['late_wins_5_7']}
• Erken Kazanç Oranı: {early_win_rate:.1f}%

📈 **Sistem Dağılımı:**
• Pattern: {performance_stats['pattern_signals']} (%{pattern_percent:.1f})
• Felaket: {performance_stats['felaket_signals']} + {performance_stats['super_felaket_signals']} + {performance_stats['ultra_felaket_signals']} (%{felaket_percent:.1f})

📊 **Pattern Performansları:**
{chr(10).join(pattern_stats) if pattern_stats else '• Henüz veri yok'}

⚡ **Felaket Performansları:**
{chr(10).join(felaket_stats) if felaket_stats else '• Henüz veri yok'}

🛡️ **Güvenlik:**
• Session: {session_status}
• Ardışık Kayıp: {performance_stats['consecutive_losses']}/{MAX_CONSECUTIVE_LOSSES}
• Cooldown: {'✅' if performance_stats['cooldown_mode'] else '❌'}
• Aktif Takipçi: {len(martingale_trackers)}
• Çakışma Önleme: {performance_stats['conflict_preventions']}
""")

@client.on(events.NewMessage(pattern='/patterns'))
async def patterns_command(event):
    patterns_text = "\n".join([f"• {p} - Güç: {PATTERN_STRENGTH[p]}" for p in STRONG_PATTERNS])
    await event.reply(f"""
🎭 **PATTERN SİSTEMİ - AKTİF PATTERNLER:**

{patterns_text}

🎯 **Filtreler:**
• Min Güç: {MIN_PATTERN_STRENGTH}
• Final Kriter: Güç ≥ {FINAL_MIN_STRENGTH} + İndikatör

⚡ **5+ EL KURALI:**
• Felaket: {FELAKET_THRESHOLD}+ el çıkmayan suit
• Super Felaket: {SUPER_FELAKET_THRESHOLD}+ el çıkmayan suit
• Ultra Felaket: {ULTRA_FELAKET_THRESHOLD}+ el çıkmayan suit
• Martingale: {MAX_MARTINGALE_STEPS + 1} adım

🔄 **SİSTEM MANTIĞI:**
• İki sistem BAĞIMSIZ çalışır
• Aynı anda iki sinyal de aktif olabilir
• Her sistem kendi martingale takibini yapar
• Pattern sinyali: +2 el ileri
• Felaket sinyali: +1 el ileri
• Çakışma Önleme: Aktif (aynı oyun numarası için çakışma önlenir)
""")

# ==============================================================================
# ANA MESAJ İŞLEYİCİ - ÇİFT SİSTEM (ÇAKIŞMA ÖNLEMELİ)
# ==============================================================================

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_source_channel_message(event):
    # ÖNCE GÜVENLİK KONTROLÜ
    is_safe, reason = check_safety_conditions()
    if not is_safe:
        return
    
    # COOLDOWN KONTROLÜ
    if performance_stats['cooldown_mode']:
        performance_stats['games_since_last_loss'] += 1
    
    text = re.sub(r'\*\*', '', event.message.text).strip()
    game_info = extract_game_info_from_message(text)
    
    if not game_info['game_number']: 
        return
    
    # OYUN SONUÇLARINI KAYDET
    game_results[game_info['game_number']] = game_info
    
    # 5+ EL KURALI - FELAKET STRATEJİSİ GÜNCELLE (HER ZAMAN)
    update_felaket_tracker(game_info)
    
    # MARTINGALE TAKİP (HER İKİ SİSTEM İÇİN)
    await check_martingale_trackers()
    
    # 🎯 SİSTEM 1: PATTERN SİNYAL KONTROLÜ
    should_send_pattern, pattern_signal_data = should_send_pattern_signal(game_info)
    if should_send_pattern:
        next_game_num = get_game_number_after_n(game_info['game_number'], 2)  # +2 el ileri
        await send_signal(next_game_num, pattern_signal_data, game_info)
    
    # ⚡ SİSTEM 2: FELAKET SİNYAL KONTROLÜ (PATTERN'DEN BAĞIMSIZ)
    should_send_felaket, felaket_signal_data = should_send_felaket_signal()
    if should_send_felaket:
        next_game_num = get_game_number_after_n(game_info['game_number'], 1)  # +1 el ileri
        await send_signal(next_game_num, felaket_signal_data, game_info)

if __name__ == '__main__':
    print("🤖 BACCARAT BOT - ÇİFT SİSTEM BAŞLATILIYOR...")
    print(f"🎯  SİSTEM 1: Pattern Tabanlı (+2 el ileri)")
    print(f"⚡  SİSTEM 2: 5+ El Kuralı (Felaket Stratejisi) (+1 el ileri)")
    print(f"🔄  BAĞIMSIZ: İki sistem ayrı çalışacak")
    print(f"🎯  PATTERNLER: {', '.join(STRONG_PATTERNS)}")
    print(f"⚡  FELAKET: {FELAKET_THRESHOLD}+ el, SUPER: {SUPER_FELAKET_THRESHOLD}+ el, ULTRA: {ULTRA_FELAKET_THRESHOLD}+ el")
    print(f"🎯  MARTINGALE: {MAX_MARTINGALE_STEPS + 1} adım (Her iki sistem için)")
    print(f"🛡️  GÜVENLİK: {MAX_CONSECUTIVE_LOSSES} kayıp, {COOLDOWN_AFTER_LOSS} cooldown")
    print(f"🔄  ÇAKIŞMA ÖNLEME: Aktif (3 oyun cooldown)")
    
    with client:
        client.run_until_disconnected()
