#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Banker Mirror Bot
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
SOURCE_CHANNEL = -1001626824569          # Kaynak kanal ID veya @username
TARGET_CHANNEL = "@KBBNowGoall"          # Hedef kanal

SESSION_NAME = "banker_mirror_session"
MAX_GAME_NUMBER = 1440
MAX_MARTINGALE_STEPS = 3                # Maksimum martingale adımı (0'dan başlar)
COOLDOWN_GAMES = 1                      # Kazan/kaybet sonrası beklenecek oyun sayısı

# Kart değerleri (As en büyük)
CARD_VALUES = {
    '2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,
    'J':11,'Q':12,'K':13,'A':14
}

# ========================= GLOBAL STATE =========================
pending_signals = {}       # { beklenen_oyun: {msg_id, suit, step, max_steps, expected_game} }
game_results = {}          # { game_number: {player_cards, banker_cards, is_final} }
history = []               # final oyunların listesi (son 200)
is_signal_active = False
cooldown_remaining = 0
bot_paused = False

stats = {"total_signals": 0, "correct": 0, "wrong": 0}
STATS_FILE = "mirror_stats.json"

# ========================= YARDIMCI FONKSİYONLAR =========================
def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)

def now_iso():
    return datetime.now().isoformat()

def get_next_game(n):
    return 1 if n + 1 > MAX_GAME_NUMBER else n + 1

def clean_text(t):
    return re.sub(r'\s+', ' ', t.replace('️','').replace('\u200b','')).strip()

def split_cards(card_str):
    """'10♦️8♦️' -> ['10♦️', '8♦️']"""
    if not card_str:
        return []
    parts = re.split(r'(?=[♣♥♦♠])', card_str)
    cards = []
    for p in parts:
        if p:
            if p[-1] in '♣♥♦♠':
                p += '️'
            cards.append(p)
    return cards

def parse_card(card):
    suit = None
    for s in ['♣️','♥️','♦️','♠️']:
        if s in card:
            suit = s
            val_part = card.replace(s, '')
            break
    if not suit:
        return None, None
    val = CARD_VALUES.get(val_part, None)
    if val is None and val_part.isdigit():
        val = int(val_part)
    return val, suit

def largest_value_suit(cards_str):
    """Kart dizisindeki en yüksek değerli kartın suitini döndürür."""
    cards = split_cards(cards_str)
    best_val = -1
    best_suit = None
    for c in cards:
        v, s = parse_card(c)
        if v is not None and s and v > best_val:
            best_val = v
            best_suit = s
    return best_suit if best_val > 0 else None

def extract_game_info(text):
    """
    Yeni mesaj formatını ayrıştırır.
    Örnek: #N382 ✅8 (6♣️2♦️) - 5 (Q♥️5♦️) #П1 #C2_2
    Döndürür: {game_number, player_cards, banker_cards, is_final}
    """
    text = clean_text(text)
    info = {
        "game_number": None,
        "player_cards": "",
        "banker_cards": "",
        "is_final": False
    }

    # Oyun numarası (#N382 veya №386)
    m = re.search(r'(?:#N|№)\s*(\d+)', text)
    if not m:
        return info
    info["game_number"] = int(m.group(1))

    # İki tarafın kartlarını ve puanlarını ayır
    # Pattern: (kartlar) - (kartlar) veya puan (kartlar) - puan (kartlar)
    # Yaklaşım: İlk parantez içindeki kartları ve ikinci parantez içindeki kartları bul
    parts = re.findall(r'\(([^()]+)\)', text)
    if len(parts) >= 2:
        left_cards = parts[0].strip()
        right_cards = parts[1].strip()
        # Sembolleri düzenle
        left_cards = left_cards.replace('♣','♣️').replace('♦','♦️').replace('♥','♥️').replace('♠','♠️')
        right_cards = right_cards.replace('♣','♣️').replace('♦','♦️').replace('♥','♥️').replace('♠','♠️')
    else:
        return info

    # Hangi tarafın Player / Banker olduğunu #П1 / #П2 belirler
    # Varsayım: #П1 -> Player sol, Banker sağ ; #П2 -> Banker sol, Player sağ
    if '#П1' in text:
        info["player_cards"] = left_cards
        info["banker_cards"] = right_cards
    elif '#П2' in text:
        info["player_cards"] = right_cards
        info["banker_cards"] = left_cards
    else:
        # Etiket yoksa varsayılan: sol Player, sağ Banker
        info["player_cards"] = left_cards
        info["banker_cards"] = right_cards

    # Final kontrolü: içinde ✅ ve (#C2_2 veya #C3_3) olmalı
    if '✅' in text and ( '#C2_2' in text or '#C3_3' in text ):
        info["is_final"] = True

    return info

def load_stats():
    global stats
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats.update(json.load(f))
            log("İstatistikler yüklendi")
        except Exception as e:
            log(f"İstatistik yüklenemedi: {e}")

def save_stats():
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"İstatistik kaydedilemedi: {e}")

# ========================= SİNYAL GÖNDERME VE MARTINGALE =========================
async def send_signal(client, game_num, suit):
    global is_signal_active, stats, cooldown_remaining
    if bot_paused:
        log(f"Bot duraklatıldı, sinyal atlanıyor #{game_num}")
        return False
    if is_signal_active:
        log(f"Aktif sinyal varken yeni sinyal gönderilemez (#{game_num})")
        return False

    # Yeni mesaj formatı (ilk gönderim)
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
            "created_at": now_iso()
        }
        is_signal_active = True
        stats["total_signals"] += 1
        save_stats()
        log(f"🪞 SİNYAL #{game_num} -> {suit}")
        return True
    except FloodWaitError as e:
        log(f"Flood wait {e.seconds}s, bekleniyor...")
        await asyncio.sleep(e.seconds)
        return await send_signal(client, game_num, suit)
    except Exception as e:
        log(f"Sinyal gönderme hatası: {e}")
        return False

async def update_signal_result(client, game_num, won, player_suits):
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
            # Bir sonraki adıma geç
            next_step = step + 1
            next_game = get_next_game(game_num)
            # Sinyali yeni oyuna taşı
            info["step"] = next_step
            info["expected_game"] = next_game
            pending_signals[next_game] = pending_signals.pop(game_num)
            log(f"🔄 #{game_num} step {step} -> {next_step}, yeni kontrol #{next_game}")

            # Mesajı güncelle (beklemede)
            new_text = (
                f"🤖 **Oyun No:** {game_num}\n"
                f"⚡ **Oyuncunun Serisi:** {expected}\n"
                f"🔁 **Kasa Katlama:** {max_steps} Oyun\n"
                f"⏳ **Durum:** {next_step+1}/{max_steps} adım beklendi"
            )
            try:
                await client.edit_message(TARGET_CHANNEL, msg_id, new_text)
            except MessageNotModifiedError:
                pass
            except Exception as e:
                log(f"Mesaj güncelleme hatası: {e}")
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
    # Sonuç mesajını güncelle
    try:
        await client.edit_message(TARGET_CHANNEL, msg_id, new_text)
    except Exception as e:
        log(f"Sonuç mesajı güncellenemedi: {e}")

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
    # Kaydet
    game_results[gnum] = info
    if info["is_final"]:
        history.append(info)
        while len(history) > 200:
            history.pop(0)

    # 1) Bekleyen sinyalleri kontrol et (bu oyunda player kartları varsa)
    if info["player_cards"] and gnum in pending_signals:
        player_suits = re.findall(r'[♣♥♦♠]️?', info["player_cards"])
        expected = pending_signals[gnum]["suit"]
        won = expected in player_suits
        await update_signal_result(client, gnum, won, player_suits)

    # 2) Yeni sinyal üretme (sadece final oyunlarda, cooldown bitmiş ve aktif sinyal yoksa)
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
                log(f"⚠️ #{gnum} Banker kartlarından suit çıkarılamadı: {info['banker_cards']}")
        else:
            log(f"⚠️ #{gnum} Banker kartları yok")

# ========================= KOMUTLAR =========================
async def handle_commands(event):
    cmd = event.raw_text.strip()
    if cmd == "/start":
        await event.reply("🤖 Banker Mirror Bot aktif.\n/help")
    elif cmd == "/help":
        await event.reply(
            "Komutlar:\n"
            "/stats - istatistikler\n"
            "/pause - duraklat\n"
            "/resume - devam et\n"
            "/test - test mesajı gönder"
        )
    elif cmd == "/stats":
        total = stats["total_signals"]
        correct = stats["correct"]
        wrong = stats["wrong"]
        rate = (correct / total * 100) if total else 0
        await event.reply(
            f"📊 **İstatistikler**\n"
            f"Toplam sinyal: {total}\n"
            f"✅ Doğru: {correct}\n"
            f"❌ Yanlış: {wrong}\n"
            f"Başarı oranı: %{rate:.1f}\n"
            f"Bekleyen sinyal: {len(pending_signals)}"
        )
    elif cmd == "/pause":
        global bot_paused
        bot_paused = True
        await event.reply("⏸️ Bot duraklatıldı. `/resume` ile devam edin.")
    elif cmd == "/resume":
        bot_paused = False
        await event.reply("▶️ Bot devam ediyor.")
    elif cmd == "/test":
        try:
            await client.send_message(TARGET_CHANNEL, "🧪 Test mesajı - Banker Mirror Bot aktif")
            await event.reply("✅ Hedef kanala test mesajı gönderildi.")
        except Exception as e:
            await event.reply(f"❌ Hata: {e}")

# ========================= ANA ÇALIŞTIRMA =========================
async def main():
    load_stats()
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    log("✅ Bot giriş yaptı, kanallar dinleniyor...")

    @client.on(events.NewMessage(chats=SOURCE_CHANNEL))
    @client.on(events.MessageEdited(chats=SOURCE_CHANNEL))
    async def source_handler(event):
        await handle_message(client, event)

    @client.on(events.NewMessage(pattern=r'^/(start|help|stats|pause|resume|test)$'))
    async def cmd_handler(event):
        await handle_commands(event)

    # Başlangıç mesajı
    try:
        await client.send_message(TARGET_CHANNEL, "🪞 Banker Mirror Bot aktif. `/help`")
    except Exception as e:
        log(f"Hedef kanala mesaj gönderilemedi: {e}")

    log("🟢 Bot çalışıyor...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("🛑 Bot durduruldu.")
    except Exception as e:
        log(f"❌ Kritik hata: {e}")
    finally:
        save_stats()Cooldown 
