import re
import json
import os
import numpy as np
from datetime import datetime, date, timedelta
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
import asyncio
import sys
from collections import deque

# ==============================================================================
# Telegram API Bilgileri ve Kanal Ayarları
# ==============================================================================
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
BOT_TOKEN = ''  # BURAYA BOT TOKEN'İNİ YAZ

# --- Kanal Bilgileri ---
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"
ADMIN_ID = 1136442929  # BURAYA KENDİ TELEGRAM ID'Nİ YAZ

client = TelegramClient('hibrit_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# ==============================================================================
# Global Değişkenler ve Takip Mekanizmaları
# ==============================================================================
game_results = {}
martingale_trackers = {}
MAX_MARTINGALE_STEPS = 3
MAX_GAME_NUMBER = 1440
is_signal_active = False

# Dosya isimleri
STATS_FILE = 'istatistikler.json'
SETTINGS_FILE = 'ayarlar.json'

# Renk emojileri
SUIT_EMOJIS = {'♠️': '🖤 MAÇA', '♥️': '❤️ KALP', '♦️': '💎 ELMAS', '♣️': '♣️ SİNEK'}

# Durum emojileri
STATUS_EMOJIS = {'win': '✅', 'loss': '❌', 'active': '🎯', 'waiting': '⏳', 'new_signal': '🚀', 'martingale': '📈', 'warning': '⚠️', 'danger': '🔴', 'report': '📊', 'notification': '🔔'}

# ==============================================================================
# HİBRİT SİNYAL SİSTEMİ - AKILLI FİLTRELER
# ==============================================================================

class MarkovPredictor:
    def __init__(self):
        self.transition_matrix = {
            '❤️': {'❤️': 0, '♣️': 0, '♦️': 0, '🖤': 0},
            '♣️': {'❤️': 0, '♣️': 0, '♦️': 0, '🖤': 0},
            '♦️': {'❤️': 0, '♣️': 0, '♦️': 0, '🖤': 0},
            '🖤': {'❤️': 0, '♣️': 0, '♦️': 0, '🖤': 0}
        }
        self.last_color = None
    
    def update_matrix(self, current_color):
        if self.last_color and current_color:
            self.transition_matrix[self.last_color][current_color] += 1
        self.last_color = current_color
    
    def predict_next_color(self):
        if not self.last_color:
            return None, 0
        
        transitions = self.transition_matrix[self.last_color]
        total = sum(transitions.values())
        if total == 0:
            return None, 0
        
        predicted_color = max(transitions.items(), key=lambda x: x[1])[0]
        confidence = transitions[predicted_color] / total
        
        return predicted_color, confidence

class CardCounter:
    def __init__(self):
        self.high_cards = ['10','J','Q','K','A']
        self.low_cards = ['2','3','4','5','6']
        self.neutral_cards = ['7','8','9']
        self.running_count = 0
        self.deck_size = 416
        self.used_cards = 0
    
    def update_count(self, cards_str):
        cards = re.findall(r'(10|[A2-9TJQK])', cards_str)
        for card in cards:
            if card in self.low_cards:
                self.running_count += 1
            elif card in self.high_cards:
                self.running_count -= 1
            self.used_cards += 1
    
    def get_true_count(self):
        remaining_decks = (self.deck_size - self.used_cards) / 52
        if remaining_decks > 0:
            return self.running_count / remaining_decks
        return 0
    
    def get_recommendation(self):
        true_count = self.get_true_count()
        if true_count >= 2:
            return "AGGRESSIVE", true_count
        elif true_count <= -2:
            return "DEFENSIVE", true_count
        else:
            return "NEUTRAL", true_count

def sicarde_analysis(player_cards, banker_cards):
    player_values = [get_baccarat_value(card[0]) for card in re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)]
    banker_values = [get_baccarat_value(card[0]) for card in re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)]
    
    patterns = {
        'strong_hand': sum(player_values) >= 8 and len(player_values) >= 3,
        'weak_hand': sum(player_values) <= 5 and len(player_values) >= 3,
        'balanced': 6 <= sum(player_values) <= 7,
        'banker_advantage': sum(banker_values) > sum(player_values)
    }
    return patterns

# Sistemleri başlat
markov_predictor = MarkovPredictor()
card_counter = CardCounter()

def hybrid_signal_system(game_info):
    """AKILLI HİBRİT SİNYAL SİSTEMİ"""
    
    # 1. Temel C2_3 sinyali
    basic_signal = extract_largest_value_suit(game_info['player_cards'])
    if not basic_signal:
        return None
    
    # 2. Markov tahmini
    markov_prediction, markov_confidence = markov_predictor.predict_next_color()
    
    # 3. Kart sayımı önerisi
    card_advice, true_count = card_counter.get_recommendation()
    
    # 4. Sicarde analizi
    sicarde_patterns = sicarde_analysis(game_info['player_cards'], game_info['banker_cards'])
    
    # Karar mekanizması
    confidence_score = 0
    reasons = []
    
    # Markov onayı (+20 puan)
    if markov_prediction == basic_signal and markov_confidence > 0.6:
        confidence_score += 20
        reasons.append("Markov onayı")
    
    # Kart sayımı onayı (+25 puan)
    if card_advice == "AGGRESSIVE" and true_count >= 1.5:
        confidence_score += 25
        reasons.append("Kart sayımı uygun")
    elif card_advice == "DEFENSIVE":
        confidence_score -= 15
        reasons.append("Kart sayımı riskli")
    
    # Sicarde onayı (+15 puan)
    if sicarde_patterns['strong_hand']:
        confidence_score += 15
        reasons.append("Güçlü el")
    elif sicarde_patterns['weak_hand']:
        confidence_score -= 10
        reasons.append("Zayıf el")
    
    # Toplam güven skoru
    base_confidence = 50  # Temel C2_3 güveni
    total_confidence = base_confidence + confidence_score
    
    return {
        'signal': basic_signal,
        'confidence': total_confidence,
        'reasons': reasons,
        'markov_confidence': markov_confidence,
        'card_count': true_count
    }

def should_send_signal(hybrid_result):
    """Sinyalin gönderilip gönderilmeyeceğine karar ver"""
    if not hybrid_result:
        return False
    
    # Minimum güven eşiği
    if hybrid_result['confidence'] < 65:
        print(f"🚫 Düşük güven skoru: %{hybrid_result['confidence']}")
        return False
    
    # Risk faktörü kontrolü
    if hybrid_result['confidence'] >= 80:
        return True
    elif hybrid_result['confidence'] >= 65 and len(hybrid_result['reasons']) >= 2:
        return True
    
    return False

# ==============================================================================
# Risk Yönetimi Sistemi
# ==============================================================================

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {'daily_loss_limit': 5, 'max_drawdown': 10, 'auto_stop': True, 'notifications': True, 'risk_level': 'medium', 'current_daily_loss': 0, 'last_reset_date': datetime.now().strftime('%Y-%m-%d')}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"❌ Ayarları kaydetme hatası: {e}")

def check_daily_reset(settings):
    today = datetime.now().strftime('%Y-%m-%d')
    if settings['last_reset_date'] != today:
        settings['current_daily_loss'] = 0
        settings['last_reset_date'] = today
        save_settings(settings)
        print("🔄 Günlük kayıp limiti sıfırlandı")

def check_risk_limits():
    settings = load_settings()
    check_daily_reset(settings)
    stats = load_stats()
    total_signals = stats['toplam_sinyal']
    win_rate = (stats['kazanan_sinyal'] / total_signals * 100) if total_signals > 0 else 0
    warnings = []
    if settings['current_daily_loss'] >= settings['daily_loss_limit']:
        warnings.append(f"⚠️ **GÜNLÜK KAYIP LİMİTİ AŞILDI!** ({settings['current_daily_loss']}/{settings['daily_loss_limit']})")
    if total_signals > 20 and win_rate < 50:
        current_drawdown = 100 - win_rate
        if current_drawdown >= settings['max_drawdown']:
            warnings.append(f"🔴 **YÜKSEK ÇEKİLME!** (%{current_drawdown:.1f})")
    if settings['current_daily_loss'] >= 3:
        warnings.append(f"🎯 **ARDIŞIK KAYIP!** ({settings['current_daily_loss']} kayıp)")
    return warnings

async def send_risk_notification(warnings):
    if not warnings: return
    settings = load_settings()
    if not settings['notifications']: return
    warning_message = f"{STATUS_EMOJIS['danger']} **RİSK UYARISI** {STATUS_EMOJIS['danger']}\n\n"
    for warning in warnings: warning_message += f"• {warning}\n"
    warning_message += f"\n📊 Detaylar için: /durum"
    try:
        await client.send_message(ADMIN_ID, warning_message)
        print("🔔 Risk uyarısı gönderildi")
    except Exception as e: print(f"❌ Risk bildirimi gönderme hatası: {e}")

async def send_notification(message, urgent=False):
    settings = load_settings()
    if not settings['notifications']: return
    try:
        emoji = STATUS_EMOJIS['danger'] if urgent else STATUS_EMOJIS['notification']
        formatted_message = f"{emoji} {message}"
        await client.send_message(ADMIN_ID, formatted_message)
        print(f"🔔 Bildirim gönderildi: {message}")
    except Exception as e: print(f"❌ Bildirim gönderme hatası: {e}")

async def send_signal_notification(signal_game_num, signal_suit, result_type, current_step=None):
    suit_display = get_suit_display_name(signal_suit)
    if result_type == 'new': message = f"🚀 **YENİ SİNYAL**\n#N{signal_game_num} - {suit_display}"
    elif result_type == 'win': message = f"✅ **KAZANÇ**\n#N{signal_game_num} - {suit_display} (Adım {current_step})"
    elif result_type == 'loss': message = f"❌ **KAYIP**\n#N{signal_game_num} - {suit_display}"
    elif result_type == 'progress': message = f"📈 **DEVAM**\n#N{signal_game_num} - {suit_display} → {current_step}. Adım"
    await send_notification(message)

# ==============================================================================
# İstatistik Sistemi
# ==============================================================================

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {'baslangic_tarihi': datetime.now().strftime('%Y-%m-%d'), 'toplam_sinyal': 0, 'kazanan_sinyal': 0, 'kaybeden_sinyal': 0, 'bugun_sinyal': 0, 'bugun_kazanan': 0, 'son_guncelleme': datetime.now().strftime('%Y-%m-%d'), 'renk_basarisi': {'❤️': {'toplam': 0, 'kazanan': 0}, '♣️': {'toplam': 0, 'kazanan': 0}, '♦️': {'toplam': 0, 'kazanan': 0}, '🖤': {'toplam': 0, 'kazanan': 0}}}

def save_stats(stats):
    stats['son_guncelleme'] = datetime.now().strftime('%Y-%m-%d')
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"❌ İstatistik kaydetme hatası: {e}")

def gunluk_sifirla_kontrol(stats):
    bugun = datetime.now().strftime('%Y-%m-%d')
    if stats['son_guncelleme'] != bugun:
        stats['bugun_sinyal'] = 0
        stats['bugun_kazanan'] = 0
        stats['son_guncelleme'] = bugun
        save_stats(stats)
        print("🔄 Günlük istatistikler sıfırlandı")

def istatistik_guncelle(sinyal_renk, kazandi):
    stats = load_stats()
    settings = load_settings()
    gunluk_sifirla_kontrol(stats)
    stats['toplam_sinyal'] += 1
    stats['bugun_sinyal'] += 1
    if kazandi:
        stats['kazanan_sinyal'] += 1
        stats['bugun_kazanan'] += 1
    else:
        stats['kaybeden_sinyal'] += 1
        settings['current_daily_loss'] += 1
        save_settings(settings)
    if sinyal_renk in stats['renk_basarisi']:
        stats['renk_basarisi'][sinyal_renk]['toplam'] += 1
        if kazandi: stats['renk_basarisi'][sinyal_renk]['kazanan'] += 1
    save_stats(stats)
    print(f"📊 İstatistik güncellendi: {sinyal_renk} - {'✅' if kazandi else '❌'}")

async def istatistik_goster(event):
    stats = load_stats()
    gunluk_sifirla_kontrol(stats)
    toplam_basari = (stats['kazanan_sinyal'] / stats['toplam_sinyal'] * 100) if stats['toplam_sinyal'] > 0 else 0
    bugun_basari = (stats['bugun_kazanan'] / stats['bugun_sinyal'] * 100) if stats['bugun_sinyal'] > 0 else 0
    renk_basarilari = []
    en_iyi_renk = ''
    en_iyi_oran = 0
    for renk, data in stats['renk_basarisi'].items():
        if data['toplam'] > 0:
            oran = (data['kazanan'] / data['toplam']) * 100
            renk_basarilari.append((renk, oran))
            if oran > en_iyi_oran:
                en_iyi_oran = oran
                en_iyi_renk = renk
    mesaj = f"🏆 **SİNYAL İSTATİSTİKLERİ** 🏆\n\n📅 Bugün: {stats['bugun_sinyal']} Sinyal\n✅ Kazanan: {stats['bugun_kazanan']} (%{bugun_basari:.1f})\n❌ Kaybeden: {stats['bugun_sinyal'] - stats['bugun_kazanan']}\n\n🎯 Toplam: {stats['toplam_sinyal']} Sinyal\n📈 Başarı: %{toplam_basari:.1f}\n\n🎨 Renk Performansı:\n"
    for renk, oran in renk_basarilari:
        renk_adi = SUIT_EMOJIS.get(renk, renk).split()[-1]
        mesaj += f"{renk} {renk_adi}: %{oran:.1f}\n"
    if en_iyi_renk:
        en_iyi_renk_adi = SUIT_EMOJIS.get(en_iyi_renk, en_iyi_renk).split()[-1]
        mesaj += f"\n🔥 En İyi: {en_iyi_renk} {en_iyi_renk_adi} (%{en_iyi_oran:.1f})"
    await event.reply(mesaj)

# ==============================================================================
# Yardımcı Fonksiyonlar
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
    if not cards: return None
    max_value = -1
    largest_value_suit = None
    values = [get_baccarat_value(card[0]) for card in cards]
    if len(values) == 2 and values[0] == values[1]: return None
    for card_char, suit in cards:
        value = get_baccarat_value(card_char)
        if value > max_value:
            max_value = value
            largest_value_suit = suit
    return largest_value_suit if max_value > 0 else None

def is_player_drawing(text): return '▶️' in text

def extract_game_info_from_message(text):
    game_info = {'game_number': None, 'player_cards': '', 'banker_cards': '', 'is_final': False, 'is_player_drawing': False, 'is_c2_3': False}
    game_info['is_player_drawing'] = is_player_drawing(text)
    game_match = re.search(r'#N(\d+)\s+.*?\((.*?)\)\s+.*?(\d+\s+\(.*\))\s+.*?(#C(\d)_(\d))', text.replace('️', ''), re.DOTALL)
    if game_match:
        game_info['game_number'] = int(game_match.group(1))
        game_info['player_cards'] = game_match.group(2)
        game_info['banker_cards'] = game_match.group(3)
        c_tag = game_match.group(4)
        if c_tag == '#C2_3': game_info['is_c2_3'] = True
        if ('✅' in text or '🔰' in text or '#X' in text): game_info['is_final'] = True
    return game_info

def get_suit_display_name(suit_symbol): return SUIT_EMOJIS.get(suit_symbol, f"❓ {suit_symbol}")

async def send_new_signal(game_num, signal_suit, hybrid_data=None):
    global is_signal_active
    
    if is_signal_active:
        print("⚠️ Zaten aktif sinyal var")
        return
    
    settings = load_settings()
    if settings['current_daily_loss'] >= settings['daily_loss_limit'] and settings['auto_stop']:
        await send_notification("❌ **SİNYAL DURDURULDU!** Günlük kayıp limiti aşıldı.", urgent=True)
        return
    
    suit_display = get_suit_display_name(signal_suit)
    
    # Hibrit sistem bilgileri
    if hybrid_data:
        confidence = hybrid_data['confidence']
        reasons = ", ".join(hybrid_data['reasons'])
        signal_text = (
            f"🎯 **AKILLI SİNYAL** 🎯\n"
            f"#N{game_num} - {suit_display}\n"
            f"📊 Güven: %{confidence:.1f}\n"
            f"🎨 Sebep: {reasons}\n"
            f"⚡ Strateji: Martingale {MAX_MARTINGALE_STEPS}D"
        )
    else:
        signal_text = (
            f"{STATUS_EMOJIS['new_signal']} **YENİ SİNYAL** {STATUS_EMOJIS['new_signal']}\n"
            f"🎯 **Oyun:** #N{game_num}\n"
            f"🎨 **Renk:** {suit_display}\n"
            f"📊 **Strateji:** Martingale {MAX_MARTINGALE_STEPS}D\n"
            f"⏰ **Durum:** {STATUS_EMOJIS['active']} Aktif"
        )
    
    try:
        sent_message = await client.send_message(KANAL_HEDEF, signal_text)
        print(f"🚀 Sinyal gönderildi: #N{game_num} - {suit_display}")
        
        martingale_trackers[game_num] = {
            'message_obj': sent_message,
            'step': 0,
            'signal_suit': signal_suit,
            'sent_game_number': game_num,
            'expected_game_number_for_check': game_num,
            'start_time': datetime.now(),
            'hybrid_data': hybrid_data
        }
        is_signal_active = True
        
        await send_signal_notification(game_num, signal_suit, 'new')
        print(f"🔔 Sinyal #N{game_num} takibe alındı")
        
    except FloodWaitError as e:
        print(f"⏳ FloodWait hatası: {e.seconds} saniye bekleniyor...")
        await asyncio.sleep(e.seconds)
        await send_new_signal(game_num, signal_suit, hybrid_data)
    except Exception as e: print(f"❌ Sinyal gönderme hatası: {e}")

async def update_signal_message(tracker_info, result_type, current_step=None):
    signal_game_num = tracker_info['sent_game_number']
    signal_suit = tracker_info['signal_suit']
    suit_display = get_suit_display_name(signal_suit)
    message_obj = tracker_info['message_obj']
    duration = datetime.now() - tracker_info['start_time']
    duration_str = f"{duration.seconds // 60}:{duration.seconds % 60:02d}"
    
    if result_type == 'win':
        new_text = f"{STATUS_EMOJIS['win']} **KAZANAN SİNYAL** {STATUS_EMOJIS['win']}\n🎯 **Oyun:** #N{signal_game_num}\n🎨 **Renk:** {suit_display}\n📊 **Adım:** {current_step if current_step else tracker_info['step']}. Seviye\n⏱️ **Süre:** {duration_str}\n🏆 **Sonuç:** {STATUS_EMOJIS['win']} KAZANÇ"
        istatistik_guncelle(signal_suit, True)
        await send_signal_notification(signal_game_num, signal_suit, 'win', current_step)
    elif result_type == 'loss':
        new_text = f"{STATUS_EMOJIS['loss']} **KAYBEDEN SİNYAL** {STATUS_EMOJIS['loss']}\n🎯 **Oyun:** #N{signal_game_num}\n🎨 **Renk:** {suit_display}\n📊 **Strateji:** Martingale {MAX_MARTINGALE_STEPS}D\n⏱️ **Süre:** {duration_str}\n💔 **Sonuç:** {STATUS_EMOJIS['loss']} KAYIP"
        istatistik_guncelle(signal_suit, False)
        await send_signal_notification(signal_game_num, signal_suit, 'loss')
    elif result_type == 'progress':
        new_text = f"{STATUS_EMOJIS['martingale']} **AKTİF SİNYAL** {STATUS_EMOJIS['martingale']}\n🎯 **Oyun:** #N{signal_game_num}\n🎨 **Renk:** {suit_display}\n📊 **Adım:** {current_step}. Seviye\n⏳ **Sonraki:** #N{tracker_info['expected_game_number_for_check']}\n🎲 **Durum:** {STATUS_EMOJIS['waiting']} Devam Ediyor"
        await send_signal_notification(signal_game_num, signal_suit, 'progress', current_step)
    
    try:
        await message_obj.edit(new_text)
        print(f"✏️ Sinyal #N{signal_game_num} güncellendi: {result_type}")
    except MessageNotModifiedError: pass
    except Exception as e: print(f"❌ Mesaj düzenleme hatası: {e}")

async def check_martingale_trackers():
    global martingale_trackers, i
