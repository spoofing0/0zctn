#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Oyuncu Gecikme Takip Botu (Zırhlı ve Çift İşleme Korumalı Sürüm)
"""
import asyncio
import re
import json
import os
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
MAX_MARTINGALE_STEPS = 3
TRIGGER_DELAY_THRESHOLD = 4

# ========================= GLOBAL VERİLER =========================
pending_signals = {}
is_signal_active = False
bot_paused = False
client = None

# Mükerrer (çift) işlemeyi önlemek için takip değişkenleri
last_processed_game = None
last_processed_cards = ""

suit_delays = {'♣': 0, '♦': 0, '♥': 0, '♠': 0}

stats = {"total_signals": 0, "correct": 0, "wrong": 0}
STATS_FILE = "delay_stats.json"

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

    # Eğer mesajda canlılık emojisi (⏱) varsa veya parantez içi boşsa final DEĞİLDİR.
    # Mesajda net sonuç ibareleri varsa ve kartlar tam açıldıysa final kabul et.
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
    
    # KORUMA: Eğer bu oyun numarası ve bu kartlar daha önce ZATEN işlendiyse hesaplama yapma, pas geç.
    if last_processed_game == game_num and last_processed_cards == player_cards_str:
        return None

    cards = split_cards(player_cards_str)
    current_suits = {suit for _, suit in cards}
    
    # Sayaçları Güncelle
    for suit in suit_delays.keys():
        if suit in current_suits:
            suit_delays[suit] = 0
        else:
            suit_delays[suit] += 1

    # Hafızayı güncelle (Aynı elin tekrar işlenmesini engellemek için)
    last_processed_game = game_num
    last_processed_cards = player_cards_str

    log(f"📊 Oyun #{game_num} Sayaç Durumu -> ♣:{suit_delays['♣']} | ♦:{suit_delays['♦']} | ♥:{suit_delays['♥']} | ♠:{suit_delays['♠']} (Kartlar: {player_cards_str})")

    # En Yüksek Gecikmeleri Sırala
    sorted_delays = sorted(suit_delays.items(), key=lambda x: x[1], reverse=True)
    
    best_suit, best_val = sorted_delays[0]
    second_suit, second_val = sorted_delays[1]

    # Kriter 1: En yüksek gecikme kesinlikle tetiklenme sınırından büyük veya eşit olmalı (≥ 5)
    if best_val < TRIGGER_DELAY_THRESHOLD:
        return None

    # Kriter 2: Yakınlık Koruması (Fark en az 2 olmalı)
    if (best_val - second_val) <= 1:
        log(f"⚠️ Sinyal Pas Geçildi: En yüksek ({best_suit}:{best_val}) ile İkinci ({second_suit}:{second_val}) farkı çok az.")
        return None

    return best_suit

# ========================= SİNYAL İŞLEMLERİ =========================
async def send_signal(bot_client, game_num, suit):
    global is_signal_active, stats
    if bot_paused or is_signal_active:
        return False

    current_delay_value = suit_delays[suit]
    text = (
        f"🤖 **Oyun No:** {game_num}\n"
        f"🎯 **Oyuncu Kaçış Süiti:** {suit}\n"
        f"📊 **Gecikme Derinliği:** {current_delay_value} El\n"
        f"🔁 **Kasa Katlama:** {MAX_MARTINGALE_STEPS} Oyun"
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
        log(f"🚀 SİNYAL TETİKLENDİ #{game_num} -> {suit} ({current_delay_value} eldir gelmiyordu)")
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
        new_text = (
            f"✅ **Sistem Güncellemesi:** Kazandı!\n"
            f"🤖 **Oyun No:** {game_num}\n"
            f"🎉 **Durum:** Süit Oyuncuya Geldi {expected}\n"
            f"💰 **Kasa Katlama:** Başarılı ({step_display} adımda)"
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
            new_text = (
                f"🤖 **Oyun No:** {game_num}\n"
                f"🎯 **Aranan Oyuncu Süiti:** {expected}\n"
                f"🔁 **Kasa Katlama:** {max_steps} Oyun\n"
                f"⏳ **Durum:** {next_step+1}/{max_steps} adım bekleniyor..."
            )
            try:
                await bot_client.edit_message(TARGET_CHANNEL, msg_id, new_text)
            except Exception:
                pass
            return
        else:
            stats["wrong"] += 1
            new_text = (
                f"❌ **Sistem Güncellemesi:** Kaybetti\n"
                f"🤖 **Oyun No:** {game_num}\n"
                f"💔 **Durum:** Süit Gelmedi {expected}\n"
                f"💸 **Kasa Katlama:** Başarısız ({max_steps} deneme)"
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
    # Sadece mesaj kesinlikle FİNAL (Bitti) durumundaysa sayaçları işlet
    if info["player_cards"] and info["is_final"]:
        target_suit_to_signal = update_delays_and_analyze(gnum, info["player_cards"])

    # Aktif sinyal takip ve sonuçlandırma (Burada final şartı aranmaz, anlık kontrol edilir)
    if info["player_cards"] and gnum in pending_signals:
        expected_suit = pending_signals[gnum]["suit"]
        extracted_suits = {s for _, s in split_cards(info["player_cards"])}
        won = expected_suit in extracted_suits
        
        # Eğer kazandıysa veya oyun tamamen bittiyse (is_final) sonucu güncelle
        if won or info["is_final"]:
            await update_signal_result(bot_client, gnum, won, info["player_cards"])

    # Yeni Sinyal Gönderimi (Mesaj kesin bitmiş olmalı ve bekleyen sinyal olmamalı)
    if info["is_final"] and not is_signal_active and not bot_paused:
        if target_suit_to_signal:
            next_game = get_next_game(gnum)
            await send_signal(bot_client, next_game, target_suit_to_signal)

# ========================= KOMUTLAR =========================
async def handle_commands(event):
    cmd = event.raw_text.strip()
    if cmd == "/start":
        await event.reply(f"🤖 Filtreli Gecikme Takip Botu Aktif.\nEşik: ≥ {TRIGGER_DELAY_THRESHOLD}\n/help")
    elif cmd == "/help":
        await event.reply("/stats - istatistikler\n/pause - duraklat\n/resume - devam\n/test - test")
    elif cmd == "/stats":
        total = stats["total_signals"]
        correct = stats["correct"]
        wrong = stats["wrong"]
        rate = (correct / total * 100) if total else 0
        await event.reply(
            f"📊 Toplam: {total}\n✅ Başarılı: {correct}\n❌ Başarısız: {wrong}\n🎯 Oran: %{rate:.1f}"
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
            await client.send_message(TARGET_CHANNEL, "🧪 Test Mesajı")
            await event.reply("✅ Gönderildi.")
        except Exception as e:
            await event.reply(f"❌ Hata: {e}")

# ========================= ANA BAŞLATICI =========================
async def main():
    global client
    load_stats()
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    log("✅ Telegram Client bağlandı.")

    @client.on(events.NewMessage(chats=SOURCE_CHANNEL))
    @client.on(events.MessageEdited(chats=SOURCE_CHANNEL))
    async def source_handler(event):
        await handle_message(client, event)

    @client.on(events.NewMessage(pattern=r'^/(start|help|stats|pause|resume|test)$'))
    async def cmd_handler(event):
        await handle_commands(event)

    log("🟢 Bot çift işlemeye karşı zırhlanmış modda aktif...")
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
