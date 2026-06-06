#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Banker Mirror Bot – Sadeleştirilmiş ve Hatasız Sürüm
- Tüm '️' (U+FE0F) karakterleri temizlenir.
- Suitler tek karakter: ♣ ♦ ♥ ♠
- Kart ayrıştırma basit regex.
"""
import asyncio
import re
import json
import os
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError

# ========================= KULLANICI AYARLARI =========================
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
SOURCE_CHANNEL = -1001626824569
TARGET_CHANNEL = "@KBBNowGoall"

SESSION_NAME = "banker_mirror_session"
MAX_GAME_NUMBER = 1440
MAX_MARTINGALE_STEPS = 3
COOLDOWN_GAMES = 1

CARD_VALUES = {
    '2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,
    'J':11,'Q':12,'K':13,'A':14
}

# ========================= GLOBAL =========================
pending_signals = {}
history = []
is_signal_active = False
cooldown_remaining = 0
bot_paused = False

stats = {"total_signals": 0, "correct": 0, "wrong": 0}
STATS_FILE = "mirror_stats.json"

# ========================= YARDIMCI =========================
def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)

def now_iso():
    return datetime.now().isoformat()

def get_next_game(n):
    return 1 if n + 1 > MAX_GAME_NUMBER else n + 1

def clean_text(t):
    # Önce ** kalıplarını temizle, sonra tüm '️' karakterlerini sil
    t = re.sub(r'\*\*', '', t)
    t = t.replace('️', '')  # U+FE0F tamamen yok
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

def split_cards(card_str):
    """'A♣J♥' -> ['A♣', 'J♥']"""
    if not card_str:
        return []
    # Kartlar: sayı veya JQKA ve ardından suit (♣♦♥♠)
    return re.findall(r'(\d+|J|Q|K|A)([♣♦♥♠])', card_str)

def largest_value_suit(cards_str):
    """En yüksek değerli kartın suitini döndürür."""
    cards = split_cards(cards_str)
    best_val = -1
    best_suit = None
    for val_str, suit in cards:
        val = CARD_VALUES.get(val_str, 0)
        if val > best_val:
            best_val = val
            best_suit = suit
    return best_suit if best_val > 0 else None

def extract_game_info(text):
    text = clean_text(text)
    info = {
        "game_number": None,
        "player_cards": "",
        "banker_cards": "",
        "is_final": False
    }
    m = re.search(r'(?:#N|№)\s*(\d+)', text)
    if not m:
        return info
    info["game_number"] = int(m.group(1))

    # Parantez içindeki kartları bul (ilk iki parantez)
    parts = re.findall(r'\(([^()]+)\)', text)
    if len(parts) < 2:
        return info

    left = parts[0].strip()
    right = parts[1].strip()
    # Zaten '️' temizlendi, sadece suit karakterleri kalır

    if '#П1' in text:
        info["player_cards"] = left
        info["banker_cards"] = right
    elif '#П2' in text:
        info["player_cards"] = right
        info["banker_cards"] = left
    else:
        info["player_cards"] = left
        info["banker_cards"] = right

    # Final: ✅ ve (#C2_2 veya #C3_3)
    if '✅' in text and ('#C2_2' in text or '#C3_3' in text):
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

# ========================= SİNYAL İŞLEMLERİ =========================
async def send_signal(client, game_num, suit):
    global is_signal_active, stats
    if bot_paused or is_signal_active:
        return False

    text = (
        f"🤖 **Oyun No:** {game_num}\n"
        f"⚡ **Oyuncunun Serisi:** {suit}\n"
        f"🔁 **Kasa Katlama:** {MAX_MARTINGALE_STEPS} Oyun"
    )
    try:
        sent = await client.send_message(TARGET_CHANNEL, text)
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
        log(f"🪞 SİNYAL #{game_num} -> {suit}")
        return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        return await send_signal(client, game_num, suit)
    except Exception as e:
        log(f"Sinyal hatası: {e}")
        return False

async def update_signal_result(client, game_num, won, player_cards):
    global is_signal_active, cooldown_remaining
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
        new_text = (
            f"✅ **Sistem Güncellemesi:** Kazandı!\n"
            f"🤖 **Oyun No:** {game_num}\n"
            f"🎉 **Durum:** Seri Tamamlandı {expected}\n"
            f"💰 **Kasa Katlama:** Başarılı ({step_display} adımda)"
        )
        log(f"✅ #{game_num} KAZANÇ! {expected} bulundu")
        del pending_signals[game_num]
        is_signal_active = False
        cooldown_remaining = COOLDOWN_GAMES
    else:
        if step + 1 < max_steps:
            next_step = step + 1
            next_game = get_next_game(game_num)
            info["step"] = next_step
            info["expected_game"] = next_game
            pending_signals[next_game] = pending_signals.pop(game_num)
            log(f"🔄 #{game_num} step {step} -> {next_step}, yeni kontrol #{next_game}")
            new_text = (
                f"🤖 **Oyun No:** {game_num}\n"
                f"⚡ **Oyuncunun Serisi:** {expected}\n"
                f"🔁 **Kasa Katlama:** {max_steps} Oyun\n"
                f"⏳ **Durum:** {next_step+1}/{max_steps} adım beklendi"
            )
            try:
                await client.edit_message(TARGET_CHANNEL, msg_id, new_text)
            except Exception:
                pass
            return
        else:
            stats["wrong"] += 1
            new_text = (
                f"❌ **Sistem Güncellemesi:** Kaybetti\n"
                f"🤖 **Oyun No:** {game_num}\n"
                f"💔 **Durum:** Seri Tamamlanamadı {expected}\n"
                f"💸 **Kasa Katlama:** Başarısız ({max_steps} deneme)"
            )
            log(f"❌ #{game_num} KAYIP! {expected} bulunamadı")
            del pending_signals[game_num]
            is_signal_active = False
            cooldown_remaining = COOLDOWN_GAMES

    save_stats()
    try:
        await client.edit_message(TARGET_CHANNEL, msg_id, new_text)
    except Exception as e:
        log(f"Sonuç mesaj hatası: {e}")

# ========================= ANA HANDLER =========================
async def handle_message(client, event):
    global cooldown_remaining, is_signal_active
    msg = event.message
    if not msg or not msg.text:
        return

    info = extract_game_info(msg.text)
    if info["game_number"] is None:
        return

    gnum = info["game_number"]

    # Bekleyen sinyalleri kontrol et
    if info["player_cards"] and gnum in pending_signals:
        expected_suit = pending_signals[gnum]["suit"]
        won = expected_suit in info["player_cards"]  # direkt karakter karşılaştırması
        await update_signal_result(client, gnum, won, info["player_cards"])

    # Yeni sinyal üret
    if info["is_final"] and not is_signal_active and not bot_paused:
        if cooldown_remaining > 0:
            cooldown_remaining -= 1
            log(f"❄️ Cooldown: {cooldown_remaining} oyun kaldı")
            return

        if info["banker_cards"]:
            suit = largest_value_suit(info["banker_cards"])
            if suit:
                next_game = get_next_game(gnum)
                await send_signal(client, next_game, suit)
            else:
                log(f"⚠️ #{gnum} Banker suit çıkarılamadı: {info['banker_cards']}")

# ========================= KOMUTLAR =========================
async def handle_commands(event):
    cmd = event.raw_text.strip()
    if cmd == "/start":
        await event.reply("🤖 Banker Mirror Bot aktif.\n/help")
    elif cmd == "/help":
        await event.reply("/stats - istatistikler\n/pause - duraklat\n/resume - devam\n/test - test")
    elif cmd == "/stats":
        total = stats["total_signals"]
        correct = stats["correct"]
        wrong = stats["wrong"]
        rate = (correct / total * 100) if total else 0
        await event.reply(
            f"📊 Toplam: {total}\n✅ Doğru: {correct}\n❌ Yanlış: {wrong}\nBaşarı: %{rate:.1f}"
        )
    elif cmd == "/pause":
        global bot_paused
        bot_paused = True
        await event.reply("⏸️ Duraklatıldı.")
    elif cmd == "/resume":
        bot_paused = False
        await event.reply("▶️ Devam ediyor.")
    elif cmd == "/test":
        try:
            await client.send_message(TARGET_CHANNEL, "🧪 Test - Banker Mirror aktif")
            await event.reply("✅ Test mesajı gönderildi.")
        except Exception as e:
            await event.reply(f"❌ Hata: {e}")

# ========================= ANA =========================
async def main():
    load_stats()
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    log("✅ Bot giriş yaptı.")

    @client.on(events.NewMessage(chats=SOURCE_CHANNEL))
    @client.on(events.MessageEdited(chats=SOURCE_CHANNEL))
    async def source_handler(event):
        await handle_message(client, event)

    @client.on(events.NewMessage(pattern=r'^/(start|help|stats|pause|resume|test)$'))
    async def cmd_handler(event):
        await handle_commands(event)

    try:
        await client.send_message(TARGET_CHANNEL, "🪞 Banker Mirror Bot aktif. `/help`")
    except Exception as e:
        log(f"Hedef kanala yazılamadı: {e}")

    log("🟢 Bot çalışıyor...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("🛑 Durduruldu.")
    except Exception as e:
        log(f"❌ Kritik hata: {e}")
    finally:
        save_stats()
