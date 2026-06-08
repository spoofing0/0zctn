#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import re
import json
import os
import random
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError

# ========================= KULLANICI AYARLARI =========================
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
SOURCE_CHANNEL = -1001626824569
TARGET_CHANNEL = "@KBBNowGoall"

SESSION_NAME = "player_delay_tracker"
MAX_GAME_NUMBER = 1440

# Varsayılan değerler (config'ten yüklenir)
TRIGGER_DELAY_THRESHOLD = 5
MAX_MARTINGALE_STEPS = 3

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
CONFIG_FILE = "bot_config.json"

# ========================= MOTİVASYON MESAJLARI (GÜNCEL, 45 ADET) =========================
motivation_messages = [
    "🥳 Disiplin kazanmanın anahtarıdır!",
    "⭐ Şans, hazırlıkla fırsatın buluşmasıdır!",
    "🎈 Her kayıp, daha güçlü bir sinyalin habercisidir!",
    "💎 Soğukkanlı kal, stratejine sadık kal!",
    "🎯 Odaklan, doğru anı bekle!",
    "🎊 Sabırlı ol, sonuç gelecek!",
    "🔥 Devam et, başarı seninle!",
    "🏆 Büyük kazançlar sabır ister!",
    "🪅 Şansın bol olsun!",
    "💪 Tutarlılık kazandırır!",
    "🍾 Bugün kazanma günün!",
    "💡 Her sinyal yeni bir fırsattır!",
    "🎲 Stratejine güven, kazanacaksın!",
    "🎉 Pes etme, kazanmaya yakınsın!",
    "⚡ Disiplin + Sabır = Başarı!",
    "🥂 Büyük resme bak, küçük dalgalanmalar önemli değil!",
    "📊 Veri yalan söylemez, stratejine güven!",
    "⏳ Sabır en büyük silahındır!",
    "🧠 Duygularını kontrol et, stratejini uygula!",
    "💎 Her kayıp aslında bir derstir!",
    "🎯 Hedefine odaklan, gerisi teferruat!",
    "🔄 Her döngüde daha da güçleneceksin!",
    "✨ Başarı, sıradan şeyleri sıradan insanlardan daha uzun süre yapmaktır!",
    "🚀 Büyük kazançlar için küçük adımlarla yürü!",
    "🎁 Şans, hazır olanı sever!",
    "💪 Kaybetmek asla pes etmek değildir!",
    "🎈 Sakin ol, doğru anı bekle!",
    "🔥 Bu seride patlama yapma zamanı!",
    "⚡ Disiplinli ol, kazançlar gelecek!",
    "🎊 Her şey gönlünce olsun, rahat ol!",
    "💖 Kazanmaya odaklan, gerisi teferruat!",
    "😍 Bu sinyal tam sana göre, hadi!",
    "👏 Harika bir fırsat, kaçırma!",
    "🎉 Kutlama zamanı yakın, inan!",
    "🕺 Dans et, çünkü kazanacaksın!",
    "🌟 Yıldızlar seninle, korkma!",
    "💥 Patlama yapma vakti geldi!",
    "🤩 Gözlerini yumma, büyük anı gör!",
    "🎯 Hedef 12'den vur, emin ol!",
    "🚀 Roket gibi fırla, durma!",
    "💎 Elmas gibi değerli bu sinyal, değerlendir!",
    "🍾 Şampanyayı patlatmaya hazır mısın?",
    "💃 Sevinçle zıpla, kazanç kapıda!",
    "⭐ Sakin ol, ama kazanacağını bil!",
    "🏆 Bu sinyal senin için, al ve koş!"
]

# ========================= YARDIMCI FONKSİYONLAR =========================
def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)

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
    info = {
        "game_number": None,
        "player_cards": "",
        "is_final": False
    }
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

def load_config():
    global TRIGGER_DELAY_THRESHOLD, MAX_MARTINGALE_STEPS
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                cfg = json.load(f)
                TRIGGER_DELAY_THRESHOLD = cfg.get("trigger_delay_threshold", 5)
                MAX_MARTINGALE_STEPS = cfg.get("max_martingale_steps", 3)
            log("Konfigürasyon yüklendi")
        except Exception as e:
            log(f"Config yüklenemedi: {e}")
    else:
        save_config()

def save_config():
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({
                "trigger_delay_threshold": TRIGGER_DELAY_THRESHOLD,
                "max_martingale_steps": MAX_MARTINGALE_STEPS
            }, f, indent=2)
    except Exception as e:
        log(f"Config kaydedilemedi: {e}")

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

    log(f"📊 Oyun #{game_num} Sayaç Durumu -> ♣:{suit_delays['♣']} | ♦:{suit_delays['♦']} | ♥:{suit_delays['♥']} | ♠:{suit_delays['♠']} (Kartlar: {player_cards_str})")

    sorted_delays = sorted(suit_delays.items(), key=lambda x: x[1], reverse=True)
    best_suit, best_val = sorted_delays[0]
    second_suit, second_val = sorted_delays[1]

    if best_val < TRIGGER_DELAY_THRESHOLD:
        return None
    if (best_val - second_val) <= 1:
        log(f"⚠️ Sinyal Pas Geçildi: En yüksek ({best_suit}:{best_val}) ile İkinci ({second_suit}:{second_val}) farkı çok az.")
        return None
    return best_suit

# ========================= SİNYAL İŞLEMLERİ =========================
async def send_signal(bot_client, game_num, suit):
    global is_signal_active, stats
    if bot_paused or is_signal_active:
        return False

    mot_msg = random.choice(motivation_messages)
    log(f"🎲 Sinyale eşlik eden motivasyon: {mot_msg}")  # Hangi mesajın seçildiğini gösterir
    text = (
        f"🤖 Oyun No: {game_num}\n"
        f"⚡ Oyuncunun Serisi: {suit}\n"
        f"🔁 Kasa Katlama: {MAX_MARTINGALE_STEPS} Oyun\n\n"
        f"{mot_msg}"
    )
    try:
        sent = await bot_client.send_message(TARGET_CHANNEL, text)
        pending_signals[game_num] = {
            "msg_id": sent.id,
            "suit": suit,
            "step": 0,
            "max_steps": MAX_MARTINGALE_STEPS,
            "expected_game": game_num,
        }
        is_signal_active = True
        stats["total_signals"] += 1
        save_stats()
        log(f"🚀 SİNYAL TETİKLENDİ #{game_num} -> {suit}")
        return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        return await send_signal(bot_client, game_num, suit)
    except Exception as e:
        log(f"Sinyal hatası: {e}")
        return False

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
        step_display = f"{step+1}️⃣" if step+1 <= 5 else f"{step+1}"
        mot_msg = random.choice(motivation_messages)
        log(f"🎉 Kazanç motivasyonu: {mot_msg}")
        new_text = (
            f"✅ Sistem Güncellemesi: Kazandı!\n"
            f"🤖 Oyun No: {game_num}\n"
            f"🎉 Durum: Seri Tamamlandı {expected}\n"
            f"💰 Kasa Katlama: Başarılı ({step_display} adımda)\n\n"
            f"{mot_msg}"
        )
        log(f"✅ #{game_num} KAZANÇ! {expected} yakalandi.")
        del pending_signals[game_num]
        is_signal_active = False
    else:
        if step + 1 < max_steps:
            next_step = step + 1
            next_game = get_next_game(game_num)
            info["step"] = next_step
            info["expected_game"] = next_game
            pending_signals[next_game] = pending_signals.pop(game_num)
            log(f"🔄 #{game_num} Katlama {step} -> {next_step}, Yeni Hedef #{next_game}")
            return
        else:
            stats["wrong"] += 1
            mot_msg = random.choice(motivation_messages)
            log(f"💔 Kayıp motivasyonu: {mot_msg}")
            new_text = (
                f"❌ Sistem Güncellemesi: Kaybetti\n"
                f"🤖 Oyun No: {game_num}\n"
                f"💔 Durum: Seri Tamamlanamadı {expected}\n"
                f"💸 Kasa Katlama: Başarısız ({max_steps} deneme)\n\n"
                f"{mot_msg}"
            )
            log(f"❌ #{game_num} KAYIP! Seri başarısız.")
            del pending_signals[game_num]
            is_signal_active = False

    save_stats()
    try:
        await bot_client.edit_message(TARGET_CHANNEL, msg_id, new_text)
    except Exception as e:
        log(f"Mesaj düzenleme hatası: {e}")

# ========================= ANA HANDLER =========================
async def handle_message(bot_client, event):
    global is_signal_active
    msg = event.message
    if not msg or not msg.text:
        return

    info = extract_game_info(msg.text)
    if info["game_number"] is None:
        return

    gnum = info["game_number"]

    target_suit_to_signal = None
    if info["player_cards"] and info["is_final"]:
        target_suit_to_signal = update_delays_and_analyze(gnum, info["player_cards"])

    if info["player_cards"] and gnum in pending_signals:
        expected_suit = pending_signals[gnum]["suit"]
        extracted_suits = {s for _, s in split_cards(info["player_cards"])}
        won = expected_suit in extracted_suits
        if won or info["is_final"]:
            await update_signal_result(bot_client, gnum, won, info["player_cards"])

    if info["is_final"] and not is_signal_active and not bot_paused:
        if target_suit_to_signal:
            next_game = get_next_game(gnum)
            await send_signal(bot_client, next_game, target_suit_to_signal)

# ========================= RESET ONAY MEKANİZMASI =========================
reset_confirm = {}

async def clear_reset_confirm(user_id):
    await asyncio.sleep(30)
    reset_confirm.pop(user_id, None)

# ========================= ANA BAŞLATICI =========================
async def main():
    global client
    load_stats()
    load_config()
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    log("✅ Telegram Client bağlandı.")

    # ---------- Tüm handler'lar burada tanımlanmalı ----------
    @client.on(events.NewMessage(chats=SOURCE_CHANNEL))
    @client.on(events.MessageEdited(chats=SOURCE_CHANNEL))
    async def source_handler(event):
        await handle_message(client, event)

    @client.on(events.NewMessage(pattern=r'^/start$'))
    async def start_cmd(event):
        await event.reply(
            f"🤖 Gecikme Takip Botu Aktif.\n"
            f"⚙️ Eşik: ≥ {TRIGGER_DELAY_THRESHOLD}\n"
            f"🔁 Katlama: {MAX_MARTINGALE_STEPS}\n"
            f"📌 /help - Tüm komutlar"
        )

    @client.on(events.NewMessage(pattern=r'^/help$'))
    async def help_cmd(event):
        await event.reply(
            "/stats - İstatistikler\n"
            "/status - Detaylı durum\n"
            "/pause - Duraklat\n"
            "/resume - Devam\n"
            "/reset_stats - İstatistik sıfırla\n"
            "/set threshold <1-10> - Eşik değiştir\n"
            "/set martingale <1-5> - Katlama adımı değiştir\n"
            "/test - Test mesajı"
        )

    @client.on(events.NewMessage(pattern=r'^/stats$'))
    async def stats_cmd(event):
        total = stats["total_signals"]
        correct = stats["correct"]
        wrong = stats["wrong"]
        rate = (correct / total * 100) if total else 0
        await event.reply(
            f"📊 Toplam: {total}\n"
            f"✅ Kazanç: {correct}\n"
            f"❌ Kayıp: {wrong}\n"
            f"🎯 Oran: %{rate:.1f}"
        )

    @client.on(events.NewMessage(pattern=r'^/status$'))
    async def status_cmd(event):
        pending = "Evet" if pending_signals else "Hayır"
        total = stats["total_signals"]
        correct = stats["correct"]
        wrong = stats["wrong"]
        rate = (correct / total * 100) if total else 0
        await event.reply(
            f"🤖 Bot Durumu: {'Duraklatılmış' if bot_paused else 'Aktif'}\n"
            f"📡 Sinyal aktif: {'Evet' if is_signal_active else 'Hayır'}\n"
            f"🕒 Bekleyen sinyal: {pending}\n"
            f"📈 Toplam sinyal: {total}\n"
            f"✅ Kazanç: {correct}\n"
            f"❌ Kayıp: {wrong}\n"
            f"🎯 Başarı: %{rate:.1f}"
        )

    @client.on(events.NewMessage(pattern=r'^/pause$'))
    async def pause_cmd(event):
        global bot_paused
        bot_paused = True
        await event.reply("⏸️ Duraklatıldı. Sinyal gönderilmeyecek.")

    @client.on(events.NewMessage(pattern=r'^/resume$'))
    async def resume_cmd(event):
        global bot_paused
        bot_paused = False
        await event.reply("▶️ Devam ediyor. Sinyal takibi aktif.")

    @client.on(events.NewMessage(pattern=r'^/reset_stats(\s+confirm)?$'))
    async def reset_stats_cmd(event):
        user_id = event.sender_id
        if event.pattern_match.group(1) == " confirm":
            if reset_confirm.get(user_id):
                global stats
                stats = {"total_signals": 0, "correct": 0, "wrong": 0}
                save_stats()
                await event.reply("📊 İstatistikler sıfırlandı.")
                reset_confirm.pop(user_id, None)
            else:
                await event.reply("❌ Önce /reset_stats yazarak onay isteyin.")
        else:
            reset_confirm[user_id] = True
            await event.reply("⚠️ Tüm istatistikler sıfırlanacak!\n30 saniye içinde /reset_stats confirm yazın.")
            asyncio.create_task(clear_reset_confirm(user_id))

    @client.on(events.NewMessage(pattern=r'^/set threshold (\d+)$'))
    async def set_threshold_cmd(event):
        global TRIGGER_DELAY_THRESHOLD
        new_val = int(event.pattern_match.group(1))
        if 1 <= new_val <= 10:
            TRIGGER_DELAY_THRESHOLD = new_val
            save_config()
            await event.reply(f"✅ Gecikme eşiği {new_val} olarak ayarlandı.")
        else:
            await event.reply("❌ 1-10 arasında bir sayı girin.")

    @client.on(events.NewMessage(pattern=r'^/set martingale (\d+)$'))
    async def set_martingale_cmd(event):
        global MAX_MARTINGALE_STEPS
        new_val = int(event.pattern_match.group(1))
        if 1 <= new_val <= 5:
            MAX_MARTINGALE_STEPS = new_val
            save_config()
            await event.reply(f"✅ Maksimum katlama adımı {new_val} olarak ayarlandı.")
        else:
            await event.reply("❌ 1-5 arasında bir sayı girin.")

    @client.on(events.NewMessage(pattern=r'^/test$'))
    async def test_cmd(event):
        try:
            await client.send_message(TARGET_CHANNEL, "🧪 Test mesajı – bot çalışıyor.")
            await event.reply("✅ Test mesajı gönderildi.")
        except Exception as e:
            await event.reply(f"❌ Hata: {e}")

    # Bot başlangıç mesajı (hedef kanala)
    try:
        await client.send_message(
            TARGET_CHANNEL,
            "🤖 **Bot yeniden başlatıldı!**\n🔥 Sinyal takibi aktif, bol kazançlar!"
        )
    except Exception as e:
        log(f"Başlangıç mesajı gönderilemedi: {e}")

    log("🟢 Bot tamamen hazır – strateji gizli, motive edici mesajlar aktif.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("🛑 Durduruldu.")
    except Exception as e:
        log(f"❌ Kritik Hata: {e}")
    finally:
        save_stats()
        save_config()
