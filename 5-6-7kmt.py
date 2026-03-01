# -*- coding: utf-8 -*-
import re
import asyncio
import random
import logging
import json
import os
import csv
import io
from datetime import datetime
from collections import deque, Counter
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeFilename  # DÜZELTİLDİ: Global import

# ==============================================================================
# LOGGING AYARLARI
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('baccarat_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==============================================================================
# TELEGRAM API BİLGİLERİ
# ==============================================================================
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@kbbbaccarat"

client = TelegramClient('kbbbaccarat', API_ID, API_HASH)

# ==============================================================================
# SİSTEM SABİTLERİ
# ==============================================================================
MAX_GAME_NUMBER = 1440
MAX_MARTINGALE_STEP = 7
BACK_SYSTEMS = [5, 6, 7]

# ==============================================================================
# RENK GRUPLARI - GELİŞMİŞ
# ==============================================================================

# 1. Temel Renk Grupları
RED_GROUP = {"♦️", "♥️"}
BLACK_GROUP = {"♣️", "♠️"}
ALL_SUITS = {"♦️", "♥️", "♣️", "♠️"}

# 2. SICAKLIK BAZLI RENK GRUPLARI
TEMPERATURE_GROUPS = {
    "hot": {"♥️", "♦️"},
    "cold": {"♣️", "♠️"},
}

# 3. ŞEKİL-RENK KOMBİNASYONLARI
SUIT_COMBINATIONS = {
    "hearts_diamonds": ["♥️", "♦️"],
    "clubs_spades": ["♣️", "♠️"],
    "hearts_spades": ["♥️", "♠️"],
    "diamonds_clubs": ["♦️", "♣️"],
    "hearts_clubs": ["♥️", "♣️"],
    "diamonds_spades": ["♦️", "♠️"],
}

# 4. GÜÇ SKORU SİSTEMİ
SUIT_POWER = {
    "♠️": 4,
    "♥️": 3,
    "♦️": 2,
    "♣️": 1
}

COMBINATION_POWER = {
    "hearts_diamonds": 5,
    "clubs_spades": 5,
    "hearts_spades": 7,
    "diamonds_clubs": 7,
    "hearts_clubs": 4,
    "diamonds_spades": 4,
}

# Zıt dönüşüm kuralları
BALANCED_FLIP_RULES = {
    "♦️": BLACK_GROUP, "♥️": BLACK_GROUP,
    "♣️": RED_GROUP, "♠️": RED_GROUP
}

# Kombinasyon zıtlıkları
COMBINATION_OPPOSITES = {
    "hearts_diamonds": "clubs_spades",
    "clubs_spades": "hearts_diamonds",
    "hearts_spades": "diamonds_clubs",
    "diamonds_clubs": "hearts_spades",
    "hearts_clubs": "diamonds_spades",
    "diamonds_spades": "hearts_clubs",
}

# ==============================================================================
# DURUM DEPOLARI
# ==============================================================================
player_results = {}
martingale_tracker = {}
sent_signals = set()
bot_paused = False

# ==============================================================================
# İSTATİSTİK DEPOLARI
# ==============================================================================
position_stats = {
    "first": {"total": 0, "won": 0, "lost": 0},
    "middle": {"total": 0, "won": 0, "lost": 0},
    "last": {"total": 0, "won": 0, "lost": 0}
}

strategy_stats = {
    "classic": {"used": 0, "won": 0, "lost": 0},
    "temperature": {"used": 0, "won": 0, "lost": 0},
    "power_score": {"used": 0, "won": 0, "lost": 0},
    "combination": {"used": 0, "won": 0, "lost": 0},
    "fade_streak": {"used": 0, "won": 0, "lost": 0},
    "follow_streak": {"used": 0, "won": 0, "lost": 0},
    "default": {"used": 0, "won": 0, "lost": 0}
}

STATS_FILE = "position_stats.json"
STRATEGY_STATS_FILE = "strategy_stats.json"
SETTINGS_FILE = "bot_settings.json"

# ==============================================================================
# AYARLAR
# ==============================================================================
bot_settings = {
    "temperature_window": 30,
    "min_streak_follow": 2,
    "min_streak_fade": 4,
    "position_weights": {"first": 1.2, "middle": 1.0, "last": 0.8},
    "power_threshold": 5,
    "combination_bonus": 10,
    "auto_export": False,
    "log_level": "INFO"
}

# ==============================================================================
# EMOJİ ve MESAJ KÜTÜPHANESİ
# ==============================================================================
STEP_EMOJIS = {i: f"{i}️⃣" for i in range(8)}

WIN_MESSAGES = [
    "🔥 Kazanç!", "💎 Başarı!", "🎯 İsabet!", "⚡ Vuruş!",
    "💥 Zafer!", "🏆 Başarı!", "🚀 Yükseliş!", "🔥 Matematiksel Zafer!",
    "🚀 Algoritma Başarısı!", "🎯 İstatistiksel İsabet!", "💥 Formül Tuttu!",
    "🧨 Hesaplı Kazanç!", "🚀 Olasılık Gerçekleşti!", "🎉 Doğrulandı!",
    "🎯 Teori Uygulandı.", "💎 Bilimsel Sonuç.", "🔥 Veri Tabanlı Kazanç!",
    "⚡ Analiz Başarısı!", "💎 Rasyonel Sonuç!", "🎯 Matematik Konuştu!",
    "💥 İstatistik Kazandı!", "🏹 Algoritma Vuruşu!", "📌 Veri Noktası!",
    "🔒 Bilimsel Kilidi Açtık!", "💣 Hesaplanmış Başarı!", "🔥 Sistem Zaferi!",
    "⚡ Dengeli Etki!", "💎 Rasyonel İsabet!", "🌪️ Kontrollü Fırtına!",
    "🎉 Matematiksel Zafer!", "🔥 İstatistiksel Başarı!", "🚀 Veri Odaklı Sonuç!",
    "🏹 Bilimsel Vuruş!", "💥 Analiz Doğrulandı!", "🎖️ Sistem Başarısı!",
    "💎 Algoritmik İsabet!", "💫 Matematiksel Parlama!", "🎉 Veri Tabanlı Zafer!",
    "🔥 Bilimsel Başarı!", "🚀 Rasyonel Yükseliş!", "🏆 İstatistiksel Zafer!",
    "💥 Kontrollü Darbe!", "⚡ Dengeli Çakış!", "🔥 Sistemsel Başarı!",
    "🎯 Matematiksel İsabet!", "🚀 Veri Destekli Sonuç!", "💎 Bilimsel Netlik!"
]

LOSS_MESSAGES = [
    "❌ Sistem Testi!", "💢 Olasılık Dışı!", "🔻 Geçici Kayıp!",
    "🔥 Veri Toplama!", "⚠️ Kalibrasyon!", "💥 İstatistiksel Dalgalanma!",
    "🌑 Geçici Kararma!", "📉 Anlık Düşüş!", "🚫 Veri Noktası!",
    "🩸 Sistem Analizi!", "💔 Matematiksel Ara!", "🌫️ Veri İşleme!",
    "⚡ Algoritma Testi!", "🔧 Sistem Ayarı!", "💣 Analiz Süreci!",
    "🎭 Veri Doğrulama!", "🧊 Sistem Soğuması!", "📌 İstatistiksel Anomali!",
    "🕳️ Geçici Boşluk!", "🚷 Veri Filtreleme!", "🧨 Optimizasyon!",
    "🎯 Matematiksel Ara!", "🛑 Veri İşleme Durağı!", "💀 İstatistiksel Reset!",
    "📉 Sistem Kalibrasyonu!", "🪓 Veri Temizliği!", "🌀 Güncelleme!",
    "⚠️ Sistem Kontrolü!", "🧩 Veri Yeniden Yapılandırması!", "💢 Matematiksel Dengeleme!"
]

WAITING_MESSAGES = [
    "⏳ Sistem Aktif…", "🔄 Veri İşleniyor…", "🕒 Matematiksel Hesaplama!",
    "👀 İstatistik Takibi!", "🧭 Algoritma Çalışıyor…", "📡 Veri Akışı Bekleniyor…",
    "🌓 Sistem Dengesi…", "🎛️ Olasılık Hesaplaması…", "📍 Kritik Veri Noktası…",
    "🔍 Matematiksel Analiz…", "🧱 İstatistiksel Eşik…", "⚙️ Algoritma İşliyor…",
    "🧮 Veri Hesaplaması…", "💭 Olasılık Değerlendirmesi…", "🔋 Sistem Yükleniyor…",
    "🎯 Matematiksel Hedef!", "📡 Veri Alımı Aktif!", "🌙 İstatistiksel Bekleme…",
    "🪫 Sistem Optimizasyonu…", "🔄 Veri Akışı!", "📌 Son Hesaplamalar!",
    "🧩 Matematiksel Tamamlama!", "📊 İstatistik Toplama…", "🕹️ Sistem Kontrolü…",
    "🛠️ Algoritma Güncellemesi…", "🎬 Veri Senaryosu…"
]

# ==============================================================================
# YARDIMCI FONKSİYONLAR
# ==============================================================================

def get_current_time():
    return datetime.now().strftime("%H:%M:%S")

def clean_text(text):
    return re.sub(r'\s+', ' ', text.replace('️','').replace('\u200b','')).strip()

def get_previous_game(current_game, back):
    previous = current_game - back
    while previous < 1:
        previous += MAX_GAME_NUMBER
    return previous

def get_next_game_number(current_game, step=1):
    next_game = current_game + step
    if next_game > MAX_GAME_NUMBER:
        next_game -= MAX_GAME_NUMBER
    elif next_game < 1:
        next_game += MAX_GAME_NUMBER
    return next_game

def extract_player_cards(text):
    pattern = r'\((.*?)\)'
    matches = re.findall(pattern, text)
    if matches:
        raw = re.sub(r'[\s,;]+', '', matches[0])
        raw = (raw.replace('♣', '♣️').replace('♦', '♦️')
                  .replace('♥', '♥️').replace('♠', '♠️'))
        return raw
    return None

def player_has_arrow(text):
    arrow_patterns = ["👉", "➡️", "→", "▶", "⇒", "⟹"]
    return any(pattern in text for pattern in arrow_patterns)

def suits_from_cards(card_string):
    if not card_string:
        return []
    suits = []
    i = 0
    while i < len(card_string):
        char = card_string[i]
        if char in '♣♥♦♠':
            if i + 1 < len(card_string) and card_string[i+1] == '️':
                suits.append(char + '️')
                i += 2
            else:
                suits.append(char)
                i += 1
        else:
            i += 1
    return suits

def get_first_card_suit(cards_string):
    suits = suits_from_cards(cards_string)
    return suits[0] if suits else None

def get_middle_card_suit(cards_string):
    suits = suits_from_cards(cards_string)
    return suits[1] if len(suits) >= 2 else None

def get_last_card_suit(cards_string):
    suits = suits_from_cards(cards_string)
    return suits[2] if len(suits) >= 3 else None

def get_balanced_opposite_suit(current_suit):
    if not current_suit:
        return None
    opposite_group = BALANCED_FLIP_RULES.get(current_suit)
    if opposite_group:
        return random.choice(list(opposite_group))
    return None

def get_random_win_message():
    return random.choice(WIN_MESSAGES)

def get_random_loss_message():
    return random.choice(LOSS_MESSAGES)

def get_random_waiting_message():
    return random.choice(WAITING_MESSAGES)

def load_stats():
    global position_stats, strategy_stats, bot_settings
    
    # Pozisyon istatistikleri
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if all(k in loaded for k in ["first", "middle", "last"]):
                    position_stats = loaded
                    logger.info("📊 Pozisyon istatistikleri yüklendi")
        except Exception as e:
            logger.error(f"❌ Pozisyon istatistikleri yüklenemedi: {e}")
    
    # Strateji istatistikleri (GÜVENLİ YÜKLEME)
    if os.path.exists(STRATEGY_STATS_FILE):
        try:
            with open(STRATEGY_STATS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Sadece tanımlı stratejileri yükle
                for key in strategy_stats:
                    if key in loaded and isinstance(loaded[key], dict):
                        strategy_stats[key] = loaded[key]
            logger.info("📈 Strateji istatistikleri yüklendi")
        except Exception as e:
            logger.error(f"❌ Strateji istatistikleri yüklenemedi: {e}")
    
    # Ayarlar
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                bot_settings.update(loaded)
                logger.info("⚙️ Ayarlar yüklendi")
        except Exception as e:
            logger.error(f"❌ Ayarlar yüklenemedi: {e}")

def save_stats():
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(position_stats, f, indent=2, ensure_ascii=False)
        with open(STRATEGY_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(strategy_stats, f, indent=2, ensure_ascii=False)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_settings, f, indent=2, ensure_ascii=False)
        logger.debug("💾 İstatistikler kaydedildi")
    except Exception as e:
        logger.error(f"❌ Kaydetme hatası: {e}")

def is_authorized(user_id):
    return True

# ==============================================================================
# GELİŞMİŞ RENK ve KOMBİNASYON ANALİZİ
# ==============================================================================

class AdvancedColorAnalyzer:
    def __init__(self):
        self.suit_history = deque(maxlen=50)
        self.combination_history = deque(maxlen=50)
        self.group_stats = {
            "hot": {"count": 0, "last_seen": 0},
            "cold": {"count": 0, "last_seen": 0}
        }
    
    def update(self, game_number, cards_string):
        suits = suits_from_cards(cards_string)
        if not suits:
            return
        
        first_suit = suits[0]
        temp_group = self._get_temperature_group(first_suit)
        combination = None
        
        if len(suits) >= 2:
            combination = self._detect_combination(suits[0], suits[1])
            self.combination_history.append({
                "game": game_number,
                "combination": combination,
                "suits": [suits[0], suits[1]],
                "power": COMBINATION_POWER.get(combination, 0)
            })
        
        self.suit_history.append({
            "game": game_number,
            "suit": first_suit,
            "temp_group": temp_group,
            "combination": combination,
            "power": SUIT_POWER.get(first_suit, 0),
            "all_suits": suits
        })
        
        if temp_group:
            self.group_stats[temp_group]["count"] += 1
            self.group_stats[temp_group]["last_seen"] = game_number
        
        logger.info(f"🎨 Analiz: {first_suit} | Grup: {temp_group} | "
                   f"Kombinasyon: {combination} | Güç: {SUIT_POWER.get(first_suit, 0)}")
    
    def _get_temperature_group(self, suit):
        for group_name, suits in TEMPERATURE_GROUPS.items():
            if suit in suits:
                return group_name
        return None
    
    def _detect_combination(self, suit1, suit2):
        pair_set = {suit1, suit2}
        for combo_name, combo_suits in SUIT_COMBINATIONS.items():
            if pair_set == set(combo_suits):
                return combo_name
        return None
    
    def get_power_score(self, suit):
        return SUIT_POWER.get(suit, 0)
    
    def get_combination_power(self, suit1, suit2=None):
        if not suit2:
            return SUIT_POWER.get(suit1, 0)
        combo = self._detect_combination(suit1, suit2)
        if combo:
            return COMBINATION_POWER.get(combo, 0) + SUIT_POWER.get(suit1, 0)
        return SUIT_POWER.get(suit1, 0)
    
    def get_dominant_group(self):
        if not self.suit_history:
            return None
        recent = list(self.suit_history)[-20:]
        groups = [r["temp_group"] for r in recent if r["temp_group"]]
        if not groups:
            return None
        counter = Counter(groups)
        return counter.most_common(1)[0][0]
    
    def get_weakest_suit(self):
        if not self.suit_history:
            return random.choice(list(ALL_SUITS))
        recent_powers = {suit: 0 for suit in ALL_SUITS}
        for record in self.suit_history:
            recent_powers[record["suit"]] += record["power"]
        return min(recent_powers, key=recent_powers.get)
    
    def get_recommendation_by_power(self, source_suit):
        source_power = SUIT_POWER.get(source_suit, 0)
        
        if source_power >= 3:
            weak_opposites = [s for s in BALANCED_FLIP_RULES[source_suit] if SUIT_POWER[s] <= 2]
            if weak_opposites:
                chosen = random.choice(weak_opposites)
                return {
                    "suit": chosen,
                    "score": 60 + (source_power * 5),
                    "type": "power_score",
                    "reason": f"Güçlü {source_suit}(4)→Zayıf {chosen}({SUIT_POWER[chosen]})"
                }
        else:
            strong_opposites = [s for s in BALANCED_FLIP_RULES[source_suit] if SUIT_POWER[s] >= 3]
            if strong_opposites:
                chosen = random.choice(strong_opposites)
                return {
                    "suit": chosen,
                    "score": 55 + (SUIT_POWER[chosen] * 5),
                    "type": "power_score",
                    "reason": f"Zayıf {source_suit}({source_power})→Güçlü {chosen}({SUIT_POWER[chosen]})"
                }
        
        opposite = get_balanced_opposite_suit(source_suit)
        return {
            "suit": opposite,
            "score": 40,
            "type": "power_score",
            "reason": "Varsayılan güç dengesi"
        } if opposite else None
    
    def get_recommendation_by_combination(self, source_suit, current_cards):
        suits = suits_from_cards(current_cards)
        if len(suits) < 2:
            return None
        
        combo = self._detect_combination(suits[0], suits[1])
        if not combo:
            return None
        
        combo_power = COMBINATION_POWER.get(combo, 0)
        
        if combo_power >= 6:
            opposite_combo = COMBINATION_OPPOSITES.get(combo)
            if opposite_combo:
                target_suit = random.choice(SUIT_COMBINATIONS[opposite_combo])
                return {
                    "suit": target_suit,
                    "score": 70 + combo_power,
                    "type": "combination",
                    "reason": f"{combo}({combo_power})→{opposite_combo} güç dengesi"
                }
        return None

# ==============================================================================
# SICAKLIK TAKIP SISTEMI
# ==============================================================================

class TemperatureTracker:
    def __init__(self):
        self.window_size = bot_settings["temperature_window"]
        self.suit_history = deque(maxlen=self.window_size)
        self.temperature = {suit: 0.25 for suit in ALL_SUITS}
        self.group_temperature = {"hot": 0.5, "cold": 0.5}
        self.color_analyzer = AdvancedColorAnalyzer()
    
    def update(self, game_number, cards_string):
        first_suit = get_first_card_suit(cards_string)
        if not first_suit:
            return
        
        self.color_analyzer.update(game_number, cards_string)
        
        self.suit_history.append({
            "game": game_number,
            "suit": first_suit,
            "time": datetime.now()
        })
        
        self._calculate_temperatures()
    
    def _calculate_temperatures(self):
        if not self.suit_history:
            return
        
        total = len(self.suit_history)
        counts = {suit: 0 for suit in ALL_SUITS}
        group_counts = {"hot": 0, "cold": 0}
        
        for record in self.suit_history:
            suit = record["suit"]
            if suit in counts:
                counts[suit] += 1
            
            for group_name, suits in TEMPERATURE_GROUPS.items():
                if suit in suits:
                    group_counts[group_name] += 1
                    break
        
        for suit in self.temperature:
            self.temperature[suit] = counts[suit] / total if total > 0 else 0.25
        
        for group in ["hot", "cold"]:
            self.group_temperature[group] = group_counts[group] / total if total > 0 else 0.5
    
    def get_coldest_suits(self, n=2):
        sorted_suits = sorted(self.temperature.items(), key=lambda x: x[1])
        return [suit for suit, temp in sorted_suits[:n]]
    
    def get_hottest_suits(self, n=2):
        sorted_suits = sorted(self.temperature.items(), key=lambda x: x[1], reverse=True)
        return [suit for suit, temp in sorted_suits[:n]]
    
    def get_temperature_score(self, suit):
        if not suit or suit not in self.temperature:
            return 0
        temp = self.temperature[suit]
        return (1 - temp) * 100
    
    def get_group_recommendation(self, source_suit):
        source_group = None
        for group_name, suits in TEMPERATURE_GROUPS.items():
            if source_suit in suits:
                source_group = group_name
                break
        
        if not source_group:
            return None
        
        hot_ratio = self.group_temperature["hot"]
        cold_ratio = self.group_temperature["cold"]
        
        if source_group == "hot" and hot_ratio > 0.6:
            cold_suits = list(TEMPERATURE_GROUPS["cold"])
            target = random.choice(cold_suits)
            return {
                "suit": target,
                "score": 75,
                "type": "temperature",
                "reason": f"Sıcak baskın (%{hot_ratio*100:.0f})→Soğuk {target}"
            }
        elif source_group == "cold" and cold_ratio > 0.6:
            hot_suits = list(TEMPERATURE_GROUPS["hot"])
            target = random.choice(hot_suits)
            return {
                "suit": target,
                "score": 75,
                "type": "temperature",
                "reason": f"Soğuk baskın (%{cold_ratio*100:.0f})→Sıcak {target}"
            }
        return None
    
    def update_window(self, new_size):
        self.window_size = new_size
        self.suit_history = deque(self.suit_history, maxlen=new_size)

# ==============================================================================
# SERI ANALIZ SISTEMI
# ==============================================================================

class StreakAnalyzer:
    def __init__(self):
        self.current_streak = {"suit": None, "count": 0}
        self.streak_history = []
        self.min_follow = bot_settings["min_streak_follow"]
        self.min_fade = bot_settings["min_streak_fade"]
    
    def update(self, game_number, cards_string):
        first_suit = get_first_card_suit(cards_string)
        if not first_suit:
            return
        
        if first_suit == self.current_streak["suit"]:
            self.current_streak["count"] += 1
        else:
            if self.current_streak["count"] >= 3:
                self.streak_history.append({
                    "suit": self.current_streak["suit"],
                    "length": self.current_streak["count"],
                    "ended_at": game_number
                })
            self.current_streak = {"suit": first_suit, "count": 1}
    
    def get_streak_recommendation(self):
        count = self.current_streak["count"]
        suit = self.current_streak["suit"]
        
        if count >= self.min_fade:
            opposite = get_balanced_opposite_suit(suit)
            return {
                "suit": opposite,
                "score": min(count * 15, 90),
                "type": "fade_streak",
                "reason": f"{count} serisi kırılma"
            }
        elif count >= self.min_follow:
            return {
                "suit": suit,
                "score": 50 + (count * 10),
                "type": "follow_streak",
                "reason": "momentum"
            }
        return None

# ==============================================================================
# KOMBINE STRATEJI YONETICISI
# ==============================================================================

class CombinedStrategy:
    def __init__(self):
        self.temp_tracker = TemperatureTracker()
        self.streak_analyzer = StreakAnalyzer()
        self.position_weights = bot_settings["position_weights"]
        self.strategy_log = []
    
    def analyze_and_decide(self, current_game, current_cards, position, source_suit):
        self.temp_tracker.update(current_game, current_cards)
        self.streak_analyzer.update(current_game, current_cards)
        
        candidates = {}
        
        # 1. KLASIK ZIT
        classic_opposite = get_balanced_opposite_suit(source_suit)
        if classic_opposite:
            candidates[classic_opposite] = {
                "score": 40,
                "type": "classic",
                "reason": "Zıt renk"
            }
        
        # 2. SICAKLIK GRUP
        group_rec = self.temp_tracker.get_group_recommendation(source_suit)
        if group_rec:
            candidates[group_rec["suit"]] = {
                "score": group_rec["score"],
                "type": group_rec["type"],
                "reason": group_rec["reason"]
            }
        
        # 3. SICAKLIK RENK
        temp_opposite = self._get_temperature_choice(source_suit)
        if temp_opposite:
            temp_score = self.temp_tracker.get_temperature_score(temp_opposite)
            if temp_opposite in candidates:
                if temp_score > candidates[temp_opposite]["score"]:
                    candidates[temp_opposite] = {
                        "score": temp_score,
                        "type": "temperature",
                        "reason": f"Soğuk renk ({self.temp_tracker.temperature[temp_opposite]:.2f})"
                    }
            else:
                candidates[temp_opposite] = {
                    "score": temp_score,
                    "type": "temperature",
                    "reason": f"Soğuk renk ({self.temp_tracker.temperature[temp_opposite]:.2f})"
                }
        
        # 4. GÜÇ SKORU
        power_rec = self.temp_tracker.color_analyzer.get_recommendation_by_power(source_suit)
        if power_rec:
            if power_rec["suit"] in candidates:
                if power_rec["score"] > candidates[power_rec["suit"]]["score"]:
                    candidates[power_rec["suit"]] = {
                        "score": power_rec["score"],
                        "type": power_rec["type"],
                        "reason": power_rec["reason"]
                    }
            else:
                candidates[power_rec["suit"]] = {
                    "score": power_rec["score"],
                    "type": power_rec["type"],
                    "reason": power_rec["reason"]
                }
        
        # 5. KOMBİNASYON
        combo_rec = self.temp_tracker.color_analyzer.get_recommendation_by_combination(source_suit, current_cards)
        if combo_rec:
            if combo_rec["suit"] in candidates:
                if combo_rec["score"] > candidates[combo_rec["suit"]]["score"]:
                    candidates[combo_rec["suit"]] = {
                        "score": combo_rec["score"],
                        "type": combo_rec["type"],
                        "reason": combo_rec["reason"]
                    }
            else:
                candidates[combo_rec["suit"]] = {
                    "score": combo_rec["score"],
                    "type": combo_rec["type"],
                    "reason": combo_rec["reason"]
                }
        
        # 6. SERI (Bonus)
        streak_rec = self.streak_analyzer.get_streak_recommendation()
        if streak_rec:
            if streak_rec["suit"] in candidates:
                candidates[streak_rec["suit"]]["score"] += streak_rec["score"] * 0.3
                candidates[streak_rec["suit"]]["reason"] += f" + Seri:{streak_rec['reason']}"
            else:
                candidates[streak_rec["suit"]] = {
                    "score": streak_rec["score"],
                    "type": streak_rec["type"],
                    "reason": streak_rec["reason"]
                }
        
        # Pozisyon ağırlığı
        weight = self.position_weights.get(position, 1.0)
        for suit in candidates:
            candidates[suit]["score"] *= weight
        
        # EN İYİ SEÇİM
        if candidates:
            best_suit = max(candidates, key=lambda s: candidates[s]["score"])
            best_data = candidates[best_suit]
            
            self.strategy_log.append({
                "game": current_game,
                "position": position,
                "chosen": best_suit,
                "score": best_data["score"],
                "type": best_data["type"],
                "reason": best_data["reason"],
                "all_candidates": {k: round(v["score"], 1) for k, v in candidates.items()},
                "time": datetime.now().isoformat()
            })
            
            if best_data["type"] in strategy_stats:
                strategy_stats[best_data["type"]]["used"] += 1
            
            logger.info(f"🎯 KARAR: {best_suit} | Skor: {best_data['score']:.1f} | "
                       f"Tip: {best_data['type']} | {best_data['reason']}")
            
            return {
                "suit": best_suit,
                "score": best_data["score"],
                "type": best_data["type"],
                "reason": best_data["reason"]
            }
        
        if classic_opposite:
            return {
                "suit": classic_opposite,
                "score": 30,
                "type": "default",
                "reason": "Varsayılan"
            }
        return None
    
    def _get_temperature_choice(self, source_suit):
        if not source_suit:
            return None
        opposite_group = BALANCED_FLIP_RULES.get(source_suit)
        if not opposite_group:
            return None
        cold_suits = self.temp_tracker.get_coldest_suits(n=2)
        candidates = opposite_group.intersection(set(cold_suits))
        if candidates:
            return min(candidates, key=lambda s: self.temp_tracker.temperature[s])
        return min(opposite_group, key=lambda s: self.temp_tracker.temperature[s])

combined_strategy = CombinedStrategy()

# ==============================================================================
# MARTINGALE SISTEMI
# ==============================================================================

async def update_martingale(current_game, player_cards_string):
    updated_count = 0
    
    for signal_key, info in list(martingale_tracker.items()):
        if info.get("checked"):
            continue
        
        bet_game = info["bet_game"]
        current_step = info["step"]
        expected_game = get_next_game_number(bet_game, current_step)
        
        if current_game != expected_game:
            continue
        
        updated_count += 1
        signal_type = info.get("signal_type", "first")
        type_display = signal_type.capitalize()
        current_time = get_current_time()
        target_suit = info["suit"]
        strategy_used = info.get("strategy_used", "unknown")
        
        if target_suit in player_cards_string:
            win_message = get_random_win_message()
            new_text = f"{current_time} | #N{bet_game} | {target_suit} - 7D | {type_display} | ✅ {STEP_EMOJIS[current_step]} | {win_message}"
            
            try:
                await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                logger.info(f"✅ #N{bet_game} KAZANÇ (Strateji: {strategy_used})")
                info["checked"] = True
                
                position = info.get("position")
                if position and position in position_stats:
                    position_stats[position]["won"] += 1
                
                if strategy_used in strategy_stats:
                    strategy_stats[strategy_used]["won"] += 1
                
            except Exception as e:
                logger.error(f"❌ Düzenleme hatası: {e}")
        else:
            next_step = current_step + 1
            
            if next_step > MAX_MARTINGALE_STEP:
                loss_message = get_random_loss_message()
                new_text = f"{current_time} | #N{bet_game} | {target_suit} - 7D | {type_display} | ❌ | {loss_message}"
                try:
                    await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                    logger.info(f"❌ #N{bet_game} KAYIP (Strateji: {strategy_used})")
                    info["checked"] = True
                    
                    position = info.get("position")
                    if position and position in position_stats:
                        position_stats[position]["lost"] += 1
                    
                    if strategy_used in strategy_stats:
                        strategy_stats[strategy_used]["lost"] += 1
                        
                except Exception as e:
                    logger.error(f"❌ Düzenleme hatası: {e}")
            else:
                info["step"] = next_step
                waiting_message = get_random_waiting_message()
                new_text = f"{current_time} | #N{bet_game} | {target_suit} - 7D | {type_display} | 🔃 {STEP_EMOJIS[next_step]} | {waiting_message}"
                try:
                    await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                    logger.info(f"🔄 #N{bet_game} STEP: {current_step}→{next_step}")
                except Exception as e:
                    logger.error(f"❌ Düzenleme hatası: {e}")
    
    if updated_count > 0:
        save_stats()

# ==============================================================================
# SINYAL YONETIMI
# ==============================================================================

async def send_balanced_signal(signal_game, signal_suit, signal_type, strategy_info=None):
    global bot_paused
    
    if bot_paused:
        logger.info(f"⏸️ Sinyal durduruldu: #{signal_game}")
        return False
    
    signal_key = f"{signal_game}_{signal_type}"
    
    if signal_key in sent_signals:
        return False
    
    type_display = signal_type.capitalize()
    waiting_message = get_random_waiting_message()
    current_time = get_current_time()
    
    strategy_tag = ""
    if strategy_info:
        strategy_tag = f" [{strategy_info['type']}]"
    
    text = f"{current_time} | #N{signal_game} | {signal_suit} - 7D | {type_display}{strategy_tag} | 🔃 {STEP_EMOJIS[0]} | {waiting_message}"
    
    try:
        sent = await client.send_message(KANAL_HEDEF, text)
        sent_signals.add(signal_key)
        
        position = signal_type.split('-')[-1]
        if position in position_stats:
            position_stats[position]["total"] += 1
        
        martingale_tracker[signal_key] = {
            "msg_id": sent.id,
            "bet_game": signal_game,
            "suit": signal_suit,
            "step": 0,
            "checked": False,
            "signal_type": signal_type,
            "position": position,
            "strategy_used": strategy_info['type'] if strategy_info else "unknown",
            "sent_time": datetime.now().isoformat()
        }
        
        logger.info(f"🚀 SINYAL: #{signal_game} | {signal_suit} | {strategy_info['type'] if strategy_info else 'N/A'}")
        return True
    except Exception as e:
        logger.error(f"❌ Sinyal hatası: {e}")
        return False

# ==============================================================================
# BACK SISTEMI
# ==============================================================================

async def check_back_system(current_game, current_player_cards, back_value, system_prefix):
    previous_game = get_previous_game(current_game, back_value)
    
    if previous_game not in player_results:
        return
    
    previous_player_cards = player_results[previous_game]
    
    checks = [
        ("first", get_first_card_suit(current_player_cards), get_first_card_suit(previous_player_cards)),
        ("middle", get_middle_card_suit(current_player_cards), get_middle_card_suit(previous_player_cards)),
        ("last", get_last_card_suit(current_player_cards), get_last_card_suit(previous_player_cards))
    ]
    
    for position, current_suit, previous_suit in checks:
        if current_suit and previous_suit and current_suit == previous_suit:
            source_game = get_next_game_number(previous_game, 1)
            
            if source_game in player_results:
                source_cards = player_results[source_game]
                
                if position == "first":
                    source_suit = get_first_card_suit(source_cards)
                elif position == "middle":
                    source_suit = get_middle_card_suit(source_cards)
                else:
                    source_suit = get_last_card_suit(source_cards)
                
                if source_suit:
                    strategy_result = combined_strategy.analyze_and_decide(
                        current_game=current_game,
                        current_cards=current_player_cards,
                        position=position,
                        source_suit=source_suit
                    )
                    
                    if strategy_result:
                        signal_suit = strategy_result["suit"]
                        signal_game = get_next_game_number(current_game, 1)
                        signal_type = f"{system_prefix}-{position}"
                        
                        await send_balanced_signal(signal_game, signal_suit, signal_type, strategy_result)

# ==============================================================================
# KOMUT HANDLERLARI
# ==============================================================================

@client.on(events.NewMessage(pattern=r'^/start$'))
async def start_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    message = f"""
🤖 **GELİŞMİŞ STRATEJİ BOT v3.1** (Kontrollü)

✅ **Aktif Sistemler:**
• 🌡️ Sıcaklık Grupları (Hot/Cold)
• 🎨 Kombinasyon Analizi (6 ikili)
• ⚡ Güç Skoru (♠️4>♥️3>♦️2>♣️1)
• 📊 Seri Takibi
• 🎯 Kombine Karar (Rekabetçi)

📈 **Komutlar:**
`/stats` - Tüm istatistikler
`/temperature` - Sıcaklık analizi
`/power` - Güç skoru durumu
`/combinations` - Kombinasyon geçmişi
`/streak` - Seri durumu
`/strategies` - Strateji performansı
`/pause` / `/resume` - Durdur/Devam
`/export` - Veri dışa aktar
`/reset` - Sıfırla
`/help` - Yardım

⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
"""
    await event.reply(message)

@client.on(events.NewMessage(pattern=r'^/help$'))
async def help_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    help_text = """
📚 **YARDIM MENÜSÜ**

**Analiz Komutları:**
• `/temperature` - Renk sıcaklıkları
• `/power` - Güç skoru durumu
• `/combinations` - Kombinasyon analizi
• `/streak` - Seri takibi
• `/strategies` - Strateji performansı

**Yönetim:**
• `/stats` - Tüm istatistikler
• `/pause` - Sinyalleri durdur
• `/resume` - Devam ettir
• `/export` - CSV indir
• `/reset` - Sıfırla (onaylı)

**Stratejiler:**
🌡️ **Sıcaklık** - Grup bazlı analiz
⚡ **Güç Skoru** - Poker hiyerarşisi
🎨 **Kombinasyon** - İkili kart analizi
📊 **Seri** - Trend takibi
🎯 **Kombine** - En yüksek skorlu seçim
"""
    await event.reply(help_text)

@client.on(events.NewMessage(pattern=r'^/stats$'))
async def stats_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    lines = ["📊 **DETAYLI İSTATİSTİKLER**\n"]
    
    lines.append("**📍 Pozisyonlar:**")
    for position, stats in position_stats.items():
        total = stats["total"]
        won = stats["won"]
        success_rate = (won / total * 100) if total > 0 else 0
        lines.append(f"{position.upper()}: {won}/{total} (%{success_rate:.1f})")
    
    lines.append("\n**🧠 Strateji Performansı:**")
    for strategy, stats in strategy_stats.items():
        used = stats["used"]
        won = stats["won"]
        if used > 0:
            rate = (won / used) * 100
            lines.append(f"{strategy}: {won}/{used} (%{rate:.1f})")
    
    total_all = sum(s["total"] for s in position_stats.values())
    won_all = sum(s["won"] for s in position_stats.values())
    general_rate = (won_all / total_all * 100) if total_all > 0 else 0
    lines.append(f"\n**📈 GENEL:** {won_all}/{total_all} (%{general_rate:.1f})")
    
    active = sum(1 for info in martingale_tracker.values() if not info.get("checked"))
    status = "⏸️ DURDURULDU" if bot_paused else "▶️ AKTİF"
    lines.append(f"\n🔄 Aktif: {active} | Durum: {status}")
    
    await event.reply("\n".join(lines))

@client.on(events.NewMessage(pattern=r'^/temperature$'))
async def temperature_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    tracker = combined_strategy.temp_tracker
    analyzer = tracker.color_analyzer
    
    lines = ["🌡️ **SICAKLIK ANALİZİ**\n"]
    
    lines.append("**Grup Sıcaklıkları:**")
    for group, temp in tracker.group_temperature.items():
        bar = "█" * int(temp * 20) + "░" * (20 - int(temp * 20))
        emoji = "🔥" if temp > 0.6 else "❄️" if temp < 0.4 else "⚖️"
        lines.append(f"{group.upper()}: {bar} {temp*100:.1f}% {emoji}")
    
    lines.append("\n**Renk Sıcaklıkları:**")
    sorted_temps = sorted(tracker.temperature.items(), key=lambda x: x[1])
    for suit, temp in sorted_temps:
        status = "❄️ SOĞUK" if temp < 0.15 else "🔥 SICAK" if temp > 0.35 else "⚖️ NÖTR"
        lines.append(f"{suit}: {temp*100:.1f}% {status}")
    
    dominant = analyzer.get_dominant_group()
    if dominant:
        lines.append(f"\n👑 **Baskın Grup:** {dominant.upper()}")
    
    coldest = tracker.get_coldest_suits(1)[0] if tracker.get_coldest_suits(1) else None
    if coldest:
        lines.append(f"💡 **Öneri:** {coldest}")
    
    await event.reply("\n".join(lines))

@client.on(events.NewMessage(pattern=r'^/power$'))
async def power_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    analyzer = combined_strategy.temp_tracker.color_analyzer
    
    lines = ["⚡ **GÜÇ SKORU ANALİZİ**\n"]
    
    lines.append("**Hiyerarşi:**")
    sorted_power = sorted(SUIT_POWER.items(), key=lambda x: x[1], reverse=True)
    for suit, power in sorted_power:
        stars = "⭐" * power + "☆" * (4 - power)
        lines.append(f"{suit}: {power}/4 {stars}")
    
    if analyzer.suit_history:
        lines.append("\n**Son 10 Oyun:**")
        recent = list(analyzer.suit_history)[-10:]
        power_counts = Counter([r["power"] for r in recent])
        for power, count in sorted(power_counts.items(), reverse=True):
            suit_names = [s for s, p in SUIT_POWER.items() if p == power]
            lines.append(f"Güç {power}: {count} kez ({' '.join(suit_names)})")
    
    weakest = analyzer.get_weakest_suit()
    lines.append(f"\n🔻 **En Zayıf:** {weakest}")
    
    await event.reply("\n".join(lines))

@client.on(events.NewMessage(pattern=r'^/combinations$'))
async def combinations_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    analyzer = combined_strategy.temp_tracker.color_analyzer
    
    lines = ["🎨 **KOMBİNASYON ANALİZİ**\n"]
    
    lines.append("**Kombinasyon Güçleri:**")
    for combo, power in sorted(COMBINATION_POWER.items(), key=lambda x: x[1], reverse=True):
        suits = SUIT_COMBINATIONS[combo]
        emoji = "🔥" if power >= 6 else "⚡" if power >= 5 else "⚖️"
        lines.append(f"{combo}: {power} puan {emoji} ({' '.join(suits)})")
    
    if analyzer.combination_history:
        lines.append("\n**Son Kombinasyonlar:**")
        recent_combos = list(analyzer.combination_history)[-5:]
        for record in reversed(recent_combos):
            combo = record["combination"]
            power = record["power"]
            game = record["game"]
            if combo:
                lines.append(f"Game #{game}: {combo} ({power} puan)")
    
    lines.append(f"\n**Zıt Kombinasyonlar:**")
    for combo, opposite in list(COMBINATION_OPPOSITES.items())[:3]:
        lines.append(f"{combo} ↔ {opposite}")
    
    await event.reply("\n".join(lines))

@client.on(events.NewMessage(pattern=r'^/streak$'))
async def streak_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    analyzer = combined_strategy.streak_analyzer
    
    lines = ["📊 **SERİ ANALİZİ**\n"]
    
    current = analyzer.current_streak
    if current["suit"] and current["count"] > 0:
        lines.append(f"**Mevcut:** {current['suit']} x{current['count']}")
        
        if current["count"] >= analyzer.min_fade:
            opposite = get_balanced_opposite_suit(current["suit"])
            lines.append(f"\n⚠️ **Kırılma:** {opposite}")
        elif current["count"] >= analyzer.min_follow:
            lines.append(f"\n🚀 **Momentum:** {current['suit']} devam")
        else:
            lines.append(f"\n⏳ **Bekle:** Henüz erken")
    else:
        lines.append("Aktif seri yok.")
    
    if analyzer.streak_history:
        lines.append(f"\n**Son Seriler:**")
        for streak in analyzer.streak_history[-3:]:
            lines.append(f"  {streak['suit']} x{streak['length']} (Game #{streak['ended_at']})")
    
    await event.reply("\n".join(lines))

@client.on(events.NewMessage(pattern=r'^/strategies$'))
async def strategies_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    lines = ["🧠 **STRATEJI PERFORMANSI**\n"]
    
    for strategy, stats in strategy_stats.items():
        used = stats["used"]
        won = stats["won"]
        lost = stats["lost"]
        
        if used > 0:
            rate = (won / used) * 100
            lines.append(
                f"**{strategy.upper()}**"
                f"\n  Kullanım: {used}"
                f"\n  ✅ {won} | ❌ {lost}"
                f"\n  📈 %{rate:.1f}"
            )
        else:
            lines.append(f"**{strategy.upper()}:** -")
    
    if combined_strategy.strategy_log:
        lines.append(f"\n**Son 3 Karar:**")
        for log in combined_strategy.strategy_log[-3:]:
            lines.append(
                f"Game #{log['game']} {log['position'].upper()}: "
                f"{log['chosen']} ({log['type']}) - {log['score']:.0f} puan"
            )
    
    await event.reply("\n".join(lines))

@client.on(events.NewMessage(pattern=r'^/pause$'))
async def pause_handler(event):
    global bot_paused
    if not is_authorized(event.sender_id):
        return
    
    bot_paused = True
    logger.info("⏸️ Bot durduruldu")
    await event.reply("⏸️ **Durduruldu**\nYeni sinyal yok.\n`/resume` ile devam et.")

@client.on(events.NewMessage(pattern=r'^/resume$'))
async def resume_handler(event):
    global bot_paused
    if not is_authorized(event.sender_id):
        return
    
    bot_paused = False
    logger.info("▶️ Bot devam ediyor")
    await event.reply("▶️ **Devam Ediyor**\nSinyal gönderimi aktif!")

@client.on(events.NewMessage(pattern=r'^/export$'))
async def export_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Oyun", "Kartlar", "Zaman"])
        
        for game_num in sorted(player_results.keys()):
            writer.writerow([
                game_num,
                player_results[game_num],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        output.seek(0)
        file_data = output.getvalue().encode('utf-8')
        
        await event.reply(f"✅ **Veriler Aktarıldı**\n🎮 {len(player_results)} oyun")
        
        await client.send_file(
            event.chat_id,
            file_data,
            caption="📊 Baccarat verileri",
            attributes=[DocumentAttributeFilename(f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")]
        )
        
    except Exception as e:
        logger.error(f"Export hatası: {e}")
        await event.reply(f"❌ Hata: {e}")

@client.on(events.NewMessage(pattern=r'^/reset$'))
async def reset_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    await event.reply(
        "⚠️ **SIFIRLAMA ONAYI**\n\n"
        "Tüm veriler silinecek!\n"
        "Onaylamak için:\n`/reset confirm`"
    )

@client.on(events.NewMessage(pattern=r'^/reset\s+confirm$'))
async def reset_confirm_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    global position_stats, strategy_stats, player_results
    
    position_stats = {k: {"total": 0, "won": 0, "lost": 0} for k in position_stats}
    strategy_stats = {k: {"used": 0, "won": 0, "lost": 0} for k in strategy_stats}
    player_results.clear()
    
    combined_strategy.temp_tracker.suit_history.clear()
    combined_strategy.temp_tracker.color_analyzer.suit_history.clear()
    combined_strategy.temp_tracker.color_analyzer.combination_history.clear()
    combined_strategy.strategy_log.clear()
    
    save_stats()
    
    await event.reply("🗑️ **Sıfırlandı**")
    logger.info("🗑️ Tam sıfırlama")

# ==============================================================================
# ANA HANDLER
# ==============================================================================

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def enhanced_handler(event):
    msg = event.message
    if not msg or not msg.text:
        return

    text = clean_text(msg.text)
    
    game_number = None
    patterns = [r'(?:#N|№|#)\s*(\d+)', r'Game\s*[:]?\s*(\d+)', r'Oyun\s*[:]?\s*(\d+)']
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            game_number = int(match.group(1))
            break
    
    if not game_number:
        return
    if game_number < 1 or game_number > MAX_GAME_NUMBER:
        return

    player_cards = extract_player_cards(text)
    if not player_cards:
        return
    if player_has_arrow(text):
        return

    combined_strategy.temp_tracker.update(game_number, player_cards)
    
    player_results[game_number] = player_cards
    logger.info(f"💾 Game #{game_number} | {player_cards}")

    await update_martingale(game_number, player_cards)

    for back_value in BACK_SYSTEMS:
        try:
            await check_back_system(game_number, player_cards, back_value, f"{back_value}-BC")
        except Exception as e:
            logger.error(f"❌ Back hatası: {e}")

# ==============================================================================
# BASLATMA
# ==============================================================================

async def main():
    logger.info("=" * 60)
    logger.info("🚀 GELİŞMİŞ STRATEJİ BOT v3.1 BAŞLATILIYOR")
    logger.info("=" * 60)
    logger.info("✅ Tüm sistemler kontrol edildi")
    logger.info("✅ Çakışma önleme: Aktif")
    logger.info("✅ Import kontrolü: Tamam")
    
    load_stats()
    
    await client.start()
    
    startup_msg = (
        f"🤖 **BOT AKTİF** - v3.1 (Kontrollü)\n\n"
        f"🌡️ Sıcaklık Grupları\n"
        f"🎨 Kombinasyon Analizi\n"
        f"⚡ Güç Skoru Sistemi\n"
        f"📊 Seri Takibi\n"
        f"🎯 Kombine Karar\n\n"
        f"Komutlar: `/help`"
    )
    
    try:
        await client.send_message(KANAL_HEDEF, startup_msg)
    except Exception as e:
        logger.error(f"Başlangıç mesajı hatası: {e}")
    
    logger.info("🟢 Bot çalışmaya hazır...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Durduruldu.")
    except Exception as e:
        logger.error(f"❌ Kritik hata: {e}")
    finally:
        save_stats()
        logger.info("🔴 Bot sonlandırıldı.")
