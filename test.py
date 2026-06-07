#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Oyuncu Gecikme Takip Botu - Google Colab Kesin Çözüm Sürümü (Connection & Input Onarımı)
"""
import asyncio
import re
import json
import os
import random
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError, SessionPasswordNeededError
import nest_asyncio

# Colab event loop çakışmalarını önleyen yama
nest_asyncio.apply()

# ========================= KULLANICI AYARLARI =========================
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
PHONE_NUMBER = "+905305281971"
SOURCE_CHANNEL = -1001626824569
TARGET_CHANNEL = "@KBBNowGoall"

SESSION_NAME = "colab_player_tracker"
MAX_GAME_NUMBER = 1440
MAX_MARTINGALE_STEPS = 3
TRIGGER_DELAY_THRESHOLD = 4

# ========================= GLOBAL VERİLER =========================
pending_signals = {}
is_signal_active = False
bot_paused = False
client = None

last_processed_game = None
last_processed_cards = ""
suit_delays = {'♣': 0, '♦': 0, '♥': 0, '♠': 0}

stats = {"total_signals": 0, "correct": 0, "wrong": 0}
STATS_FILE = "delay_stats.json"

# ========================= MOTTO VE STRATEJİ HAVUZLARI (EMOJİLİ & ÇOĞALTILMIŞ) =========================
SIGNAL_MOTTOS = [
    "⚠️ Risk yönetimine sadık kalınız. Kasa asla zorlanmamalı.",
    "🎯 Stratejinin matematiğine güvenin, duygulara değil. Yeni sinyal geliyor!",
    "📉 Martingale basamaklarını planladığınız gibi uygulayın. Acele etmeyin.",
    "🧠 Sakin olun. Sistem kâr odaklı çalışır, siz sadece takip edin.",
    "⚖️ Her sinyal bir fırsattır, ama disiplin her şeyden önemlidir.",
    "🛡️ Stop-loss ve hedefinizi belirleyin. Bot sizi yönlendirir.",
    "🚦 Kırmızıyı beklemeden yeşili yakalayın. İşte sinyal!",
    "📊 İstatistikler bizden yana. Sadece plana sadık kalın.",
    "🤝 Sabır en büyük sermayenizdir. Sinyal geldi, sıra sizde.",
    "💎 Her kayıp bir derstir, her kazanç bir teyit. Riski bölün.",
    "🔁 Martingale basamaklarını asla atlamayın. Bot sırasını bekleyin.",
    "🧘 Duygularınızı devre dışı bırakın. Soğukkanlılık kazandırır.",
    "⏳ Zamanlama her şeydir. Bu sinyal tam zamanında!",
    "🎲 Şansa değil, gecikme verilerine güveniyoruz. Sinyal aktif.",
    "💼 Kasa planlamanız hazır mı? Sinyal yolda, hazır olun."
]

WIN_MOTTOS = [
    "🟢 Başarılı! Kasa büyüyor, ancak disiplini elden bırakmayın.",
    "🏆 Harika bir yakalama! Kâr al hedefinize sadık kalın.",
    "✅ Sistem doğrulandı. Plan dahilinde devam edin.",
    "💰 Kâr cebe indi. Günlük hedefinize ulaştıysanız dinlenin.",
    "📈 Kazanç çizginiz yükseliyor. Duygusal hamle yapmayın.",
    "🌟 Mükemmel! Seri devam edebilir, ama risk yönetimi şart.",
    "🎉 Bu zafer sistemin başarısıdır. Sıradaki sinyali bekleyin.",
    "🔒 Kilit pozisyon kapatıldı. Şimdi korumaya geçin.",
    "⚡ Sinyal tuttu! Martingale başarıyla tamamlandı.",
    "🍀 Şans değil, matematik kazandı. Tebrikler!",
    "🏅 Kazandınız! Stop-loss seviyenizi yukarı çekin.",
    "📊 İstatistikler lehinize çalışıyor. Soğukkanlı olun.",
    "🎯 Hedef vuruldu. Sıradaki sinyali izleyin.",
    "💪 Güçlü bir kapanış. Kârınızı garanti altına alın.",
    "✨ Sistem yine tutturdu. Disiplinli kalın."
]

LOSS_MOTTOS = [
    "🔴 Kayıplar oyunun parçasıdır. Stop-loss kurallarına uyun.",
    "⛔ Hırsla devam etmek kasayı eritir. Bugünlük bu kadar.",
    "📉 Bir kayıp uzun vadeli planı bozmamalı. Sakin olun.",
    "💔 Kaybettiniz ama sistem çalışıyor. Sonraki sinyale odaklanın.",
    "⚠️ Stop-loss seviyenize saygı gösterin. Botu bekleyin.",
    "🔄 Martingale tamamlandı, kayıp kabul edildi. Yeni tarama başlıyor.",
    "🧘 Duygularınızı kontrol edin. Kayıp normal bir süreçtir.",
    "📉 Geri çekilme stratejisi devrede. Sabırlı olun.",
    "🎲 Şans bu sefer yaver gitmedi. Veriler yine sizinle.",
    "🛑 Kayıp sinyali. Kasa koruma moduna geçin.",
    "💸 Bu tur kaybedildi, ancak savaş devam ediyor. Planınıza sadık kalın.",
    "📊 Gecikme verileri değişiyor. Yeni sinyali bekleyin.",
    "⚖️ Her kayıp, gelecek kazancın habercisi olabilir. Pes etmeyin.",
    "🎯 Hedef bir sonraki sinyal. Stop-loss çalıştı, sorun yok.",
    "🧠 Unutmayın: Kayıplar disiplini test eder. Kazançlar ise ödüllendirir."
]

CANCEL_MOTTOS = [
    "⏱️ Sinyal süresi doldu. Güvenli liman devreye girdi.",
    "🔄 Zaman aşımı. Yeni tarama başlatıldı, acele etmeyin.",
    "⚪ Pas geçildi. Sabır en büyük sermayedir.",
    "🚦 Süre dolduğu için sinyal iptal edildi. Yeni fırsat kollanıyor.",
    "🛡️ Risk almamak adına bu el pas geçilmiştir.",
    "⏳ Sinyal geçerliliğini yitirdi. Sıradaki tetiklenmeyi bekleyin.",
    "🧘 Aceleye gerek yok. Bot yeniden analiz yapıyor.",
    "🔁 Zaman aşımı nedeniyle iptal. Yeni sinyale kadar bekleyin.",
    "🚫 İptal edildi. Stop-loss ve kâr hedefinizi gözden geçirin.",
    "⌛ Sinyal zamanında yanıtlanmadı. Bir sonrakine odaklanın.",
    "🔄 Sinyal yenilenmedi. Pas geçilmesi en doğru karardır.",
    "⚖️ Süre doldu, kasa korumaya alındı. Yeni sinyal gelecek.",
    "📉 Zaman aşımı kayıptan iyidir. Sabırlı olun.",
    "🎯 Hedef kaçırıldı ama güvenlik ön planda. Bot çalışmaya devam ediyor.",
    "🛌 Yeterli tepki gelmedi, sinyal iptal. Dinlenin ve hazır olun."
]

# ========================= MESAJ ŞABLONLARI SINIFI =========================
class MessageTemplates:
    @staticmethod
    def get_progress_bar(current, max_val):
        filled_length = int(round(10 * current / max_val))
        return '🟢' * filled_length + '⚪' * (10 - filled_length)

    @staticmethod
    def signal_message(game_num, suit, max_steps):
        valid_until = (datetime.now() + timedelta(minutes=5)).strftime("%H:%M:%S")
        motto = random.choice(SIGNAL_MOTTOS)
        return (
            f"⚡ **[ YENİ SİNYAL TETİKLENDİ ]** ⚡\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"🤖 **Hedef Oyun:** #{game_num}\n"
            f"🎯 **Tahmin:** [ {suit} ]\n"
            f"🔁 **Sistem:** {max_steps} Aşama Takip\n"
            f"⏱ **Son Geçerlilik TS:** {valid_until}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"{motto}"
        )

    @staticmethod
    def win_message(game_num, suit, step):
        step_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        step_display = step_emojis[step] if step < len(step_emojis) else f"{step + 1}"
        motto = random.choice(WIN_MOTTOS)
        return (
            f"🎉 ✨ **[ SİSTEM GÜNCELLEMESİ: KAZANÇ ]** ✨ 🎉\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"🤖 **Oyun No:** #{game_num}\n"
            f"💰 **Durum:** Süit Başarıyla Yakalandı! ->  [ {suit} ]\n"
            f"🚀 **Sonuç:** BAŞARILI ({step_display} Adımda)\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"{motto}"
        )

    @staticmethod
    def loss_message(game_num, suit, max_steps):
        motto = random.choice(LOSS_MOTTOS)
        return (
            f"💔 🚨 **[ SİSTEM GÜNCELLEMESİ: KAYIP ]** 🚨 💔\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"🤖 **Oyun No:** #{game_num}\n"
            f"🥀 **Durum:** Süit Seride Gelmedi ->  [ {suit} ]\n"
            f"💸 **Sonuç:** BAŞARISIZ ({max_steps} Deneme)\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"{motto}"
        )

    @staticmethod
    def step_message(game_num, suit, next_step, max_steps):
        return (
            f"🔄 **[ SİNYAL ADIM GÜNCELLEMESİ ]** 🔄\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"🤖 **Aktif Oyun:** #{game_num}\n"
            f"🎯 **Aranan Süit:** [ {suit} ]\n"
            f"⏳ **Durum:** {next_step + 1} / {max_steps} Adım Bekleniyor..."
        )

    @staticmethod
    def cancel_message(game_num):
        motto = random.choice(CANCEL_MOTTOS)
        return (
            f"⏱ **[ SİNYAL GEÇERSİZ / SÜRE DOLDU ]** ⏱\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"🤖 **Oyun No:** #{game_num}\n"
            f"🛡️ **Protokol:** Güvenli Liman Devreye Girdi\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n{motto}"
        )

    @staticmethod
    def get_stats_text(stats_dict):
        total = stats_dict["total_signals"]
        correct = stats_dict["correct"]
        wrong = stats_dict["wrong"]
        rate = (correct / total * 100) if total else 0
        win_bar = MessageTemplates.get_progress_bar(int(rate / 10) if total else 0, 10)
        return (
            f"📊 **[ BOT PERFORMANS İSTATİSTİKLERİ ]** 📊\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"🚀 **Toplam Sinyal:** {total}\n"
            f"✅ **Başarılı (Win):** {correct}\n"
            f"❌ **Başarısız (Loss):** {wrong}\n"
            f"📈 **Başarı Oranı (Win Rate):** %{rate:.1f}\n"
            f"🏆 **Grafik:** {win_bar}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
        )

    @staticmethod
    def control_panel(paused_status):
        status_str = "🟢 AKTİF (Sinyal Arıyor)" if not paused_status else "⏸️ DURAKLATILDI"
        return (
            f"🛠 **[ YAZILIM KONTROL PANELİ ]** 🛠\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📡 **Bot Durumu:** {status_str}\n"
            f"🎯 **Tetik Eşiği:** ≥ {TRIGGER_DELAY_THRESHOLD} El\n"
            f"🔁 **Max Martingale:** {MAX_MARTINGALE_STEPS} Aşama\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
        )

# ========================= YARDIMCI FONKSİYONLAR =========================
def log(msg, level="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}", flush=True)

def get_next_game(n):
    return 1 if n + 1 > MAX_GAME_NUMBER else n + 1

def clean_text(t):
    t = re.sub(r'[\uFE00-\uFE0F]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

def split_cards(card_str):
    if not card_str:
        return []
    return re.findall(r'(\d+|J|Q|K|A)\s*([♣♦♥♠])', card_str)

def extract_game_info(text):
    text = clean_text(text)
    info = {"game_number": None, "player_cards": "", "is_final": False}
    
    m = re.search(r'(?:#N|№)\s*(\d+)', text)
    if not m:
        return info
    info["game_number"] = int(m.group(1))

    parts = re.findall(r'\(([^()]+)\)', text)
    if len(parts) < 2:
        return info

    info["player_cards"] = parts[0].strip()
    if '⏱' not in text and ('WinWin' in text or 'Melbet' in text or '✅' in text or '#X' in text):
        info["is_final"] = True

    return info

def load_stats():
    global stats
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                stats.update(json.load(f))
            log("İstatistikler yüklendi")
        except Exception as e:
            log(f"İstatistik yüklenemedi: {e}")

def save_stats():
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        log(f"İstatistik kaydedilemedi: {e}")

# ========================= SAYAÇ VE STRATEJİ MANTIĞI =========================
def update_delays_and_analyze(game_num, player_cards_str):
    global suit_delays, last_processed_game, last_processed_cards
    
    if last_processed_game == game_num and last_processed_cards == player_cards_str:
        return None

    cards = split_cards(player_cards_str)
    current_suits = {suit for _, suit in cards}
    
    for suit in suit_delays.keys():
        if suit in current_suits:
            suit_delays[suit] = 0
        else:
            suit_delays[suit] += 1

    last_processed_game = game_num
    last_processed_cards = player_cards_str

    log(f"📊 Oyun #{game_num} Sayaç -> ♣:{suit_delays['♣']} | ♦:{suit_delays['♦']} | ♥:{suit_delays['♥']} | ♠:{suit_delays['♠']}")

    sorted_delays = sorted(suit_delays.items(), key=lambda x: x[1], reverse=True)
    best_suit, best_val = sorted_delays[0]
    second_suit, second_val = sorted_delays[1]

    # Sistem alarmı kaldırıldı (eski alert mesajı artık yok)

    if best_val < TRIGGER_DELAY_THRESHOLD:
        return None

    if (best_val - second_val) <= 1:
        return None

    return best_suit

# ========================= SİNYAL İŞLEMLERİ =========================
async def send_signal(bot_client, game_num, suit):
    global is_signal_active, stats
    if bot_paused or is_signal_active:
        return False

    try:
        sent = await bot_client.send_message(TARGET_CHANNEL, MessageTemplates.signal_message(game_num, suit, MAX_MARTINGALE_STEPS))
        pending_signals[game_num] = {
            "msg_id": sent.id, "suit": suit, "step": 0, "max_steps": MAX_MARTINGALE_STEPS, "expected_game": game_num, "timestamp": datetime.now()
        }
        is_signal_active = True
        stats["total_signals"] += 1
        save_stats()
        log(f"🚀 SİNYAL TETİKLENDİ #{game_num} -> {suit}")
        asyncio.create_task(monitor_timeout(bot_client, game_num))
        return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        return await send_signal(bot_client, game_num, suit)
    except Exception as e:
        log(f"Sinyal hatası: {e}")
        return False

async def monitor_timeout(bot_client, game_num):
    await asyncio.sleep(300)
    global is_signal_active
    if game_num in pending_signals:
        info = pending_signals[game_num]
        try:
            await bot_client.edit_message(TARGET_CHANNEL, info["msg_id"], MessageTemplates.cancel_message(game_num))
        except Exception: pass
        del pending_signals[game_num]
        is_signal_active = False

async def update_signal_result(bot_client, game_num, won, player_cards):
    global is_signal_active
    if game_num not in pending_signals:
        return

    info = pending_signals[game_num]
    msg_id = info["msg_id"]
    expected = info["suit"]
    step = info["step"]
    max_steps = info["max_steps"]

    if won:
        stats["correct"] += 1
        new_text = MessageTemplates.win_message(game_num, expected, step)
        del pending_signals[game_num]
        is_signal_active = False
    else:
        if step + 1 < max_steps:
            next_step = step + 1
            next_game = get_next_game(game_num)
            info["step"] = next_step
            info["expected_game"] = next_game
            pending_signals[next_game] = pending_signals.pop(game_num)
            
            new_text = MessageTemplates.step_message(game_num, expected, next_step, max_steps)
            try: await bot_client.edit_message(TARGET_CHANNEL, msg_id, new_text)
            except Exception: pass
            return
        else:
            stats["wrong"] += 1
            new_text = MessageTemplates.loss_message(game_num, expected, max_steps)
            del pending_signals[game_num]
            is_signal_active = False

    save_stats()
    try: await bot_client.edit_message(TARGET_CHANNEL, msg_id, new_text)
    except Exception: pass

# ========================= HANDLERS & PANELS =========================
async def handle_message(bot_client, event):
    global is_signal_active
    msg = event.message
    if not msg or not msg.text: return

    info = extract_game_info(msg.text)
    if info["game_number"] is None: return
    gnum = info["game_number"]
    
    if info["player_cards"] and info["is_final"]:
        target_suit = update_delays_and_analyze(gnum, info["player_cards"])
        if target_suit and not is_signal_active and not bot_paused:
            await send_signal(bot_client, get_next_game(gnum), target_suit)

    if info["player_cards"] and gnum in pending_signals:
        extracted_suits = {s for _, s in split_cards(info["player_cards"])}
        await update_signal_result(bot_client, gnum, pending_signals[gnum]["suit"] in extracted_suits, info["player_cards"])

def get_panel_buttons():
    return [[Button.inline("📊 İstatistik", data="btn_stats"), Button.inline("🧪 Test", data="btn_test")],
            [Button.inline("⏸️ Duraklat" if not bot_paused else "▶️ Başlat", data="btn_pause" if not bot_paused else "btn_resume")]]

async def callback_handler(event):
    global bot_paused
    data = event.data.decode('utf-8')
    if data == "btn_stats":
        await event.respond(MessageTemplates.get_stats_text(stats))
    elif data == "btn_test":
        m = await client.send_message(TARGET_CHANNEL, "🧪 Test Başarılı.")
        await asyncio.sleep(2)
        await client.delete_messages(TARGET_CHANNEL, m.id)
    elif data in ["btn_pause", "btn_resume"]:
        bot_paused = (data == "btn_pause")
        await event.edit(MessageTemplates.control_panel(bot_paused), buttons=get_panel_buttons())

# ========================= ANA BAŞLATICI PROTOKOLÜ =========================
async def main():
    global client
    load_stats()
    
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    log("📡 Telegram sunucularına bağlanılıyor...")
    
    await client.connect()
    
    if not await client.is_user_authorized():
        log(f"🔑 Yetkilendirme gerekiyor. Kod talep ediliyor: {PHONE_NUMBER}")
        sign_code_req = await client.send_code_request(PHONE_NUMBER)
        
        print("\n" + "="*50)
        user_code = input("📥 Lütfen Telegram uygulamanıza gelen 5 haneli kodu girin: ")
        print("="*50 + "\n")
        
        try:
            await client.sign_in(phone=PHONE_NUMBER, code=str(user_code).strip(), phone_code_hash=sign_code_req.phone_code_hash)
        except SessionPasswordNeededError:
            print("\n" + "="*50)
            user_2fa = input("🔐 İki adımlı doğrulama (2FA) şifrenizi girin: ")
            print("="*50 + "\n")
            await client.sign_in(password=str(user_2fa).strip())

    log("✅ Telegram oturumu başarıyla doğrulandı.")
    
    @client.on(events.NewMessage(chats=SOURCE_CHANNEL))
    @client.on(events.MessageEdited(chats=SOURCE_CHANNEL))
    async def msg_handler(event): await handle_message(client, event)

    @client.on(events.NewMessage(pattern=r'^/(start|help)$'))
    async def cmd_handler(event): await event.reply(MessageTemplates.control_panel(bot_paused), buttons=get_panel_buttons())

    @client.on(events.CallbackQuery())
    async def cb_handler(event): await callback_handler(event)

    log("🟢 Bot aktif edildi, dinleme başlıyor...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        log("🛑 Durduruldu.")
    except Exception as e:
        log(f"❌ Kritik Hata: {e}")
