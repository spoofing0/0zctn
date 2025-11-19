# -*- coding: utf-8 -*-
import re
import asyncio
from telethon import TelegramClient, events

API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@kbubakara"

client = TelegramClient('baccarat_fixed_bot', API_ID, API_HASH)

# -------------------------
# Durum depoları / ayarlar
# -------------------------
player_results = {}
banker_results = {}
triggers = {}
martingale_tracker = {}
sent_signals = set()
MAX_GAME_NUMBER = 1440
MAX_MARTINGALE_STEP = 7
step_emojis = {0:"0️⃣",1:"1️⃣",2:"2️⃣",3:"3️⃣",4:"4️⃣",5:"5️⃣",6:"6️⃣",7:"7️⃣"}

# ters çevirme haritası
suit_flip = {"♣️": "♥️", "♥️": "♣️", "♦️": "♠️", "♠️": "♦️",
             "♣":"♥️","♥":"♣️","♦":"♠️","♠":"♦️"}

# -------------------------
# Helper fonksiyonlar
# -------------------------
def clean_text(t):
    return re.sub(r'\s+', ' ', t.replace('️','').replace('\u200b','')).strip()

def get_next_game_number(n, step=1):
    n = int(n) + step
    if n > MAX_GAME_NUMBER:
        n -= MAX_GAME_NUMBER
    return n

def extract_cards(text):
    groups = re.findall(r'\((.*?)\)', text)
    if not groups:
        return None, None
    player_cards = groups[0].replace(' ', '')
    banker_cards = groups[1].replace(' ', '') if len(groups) > 1 else ""
    player_cards = player_cards.replace('♣','♣️').replace('♦','♦️').replace('♥','♥️').replace('♠','♠️')
    banker_cards = banker_cards.replace('♣','♣️').replace('♦','♦️').replace('♥','♥️').replace('♠','♠️')
    return player_cards, banker_cards

def player_has_arrow(text):
    return "👉" in text.split('(')[0]

def suits_from_cards(card_str):
    return re.findall(r'[♣♥♦♠]️?', card_str) if card_str else []

def trigger_suits_from(cards_str):
    """Oyuncunun sadece İLK kartını tetikleyici olarak al"""
    suits = suits_from_cards(cards_str)
    return [suits[0]] if suits else []

def banker_majority_flip(banker_cards_str):
    """Banker'da en çok görülen rengin zıttı"""
    suits = suits_from_cards(banker_cards_str)
    if not suits:
        return None
    
    suit_count = {}
    for suit in suits:
        suit_count[suit] = suit_count.get(suit, 0) + 1
    
    majority_suit = max(suit_count.items(), key=lambda x: x[1])[0]
    return suit_flip.get(majority_suit)

# -------------------------
# Martingale Sistemi - TAMAMEN YENİDEN YAZILDI
# -------------------------
async def update_martingale_for_game(game_number, player_cards_str):
    """Belirli bir oyun için tüm martingale sinyallerini güncelle"""
    signals_to_remove = []
    
    for signal_id, info in list(martingale_tracker.items()):
        if info.get("checked"):
            continue
            
        # Bu sinyalin beklediği oyun numarasını hesapla
        expected_game = info["signal_game"] + info["step"]
        if expected_game > MAX_GAME_NUMBER:
            expected_game -= MAX_GAME_NUMBER
        
        print(f"[MARTINGALE_CHECK] Sinyal #{info['signal_game']} - Adım {info['step']} - Beklenen: #{expected_game}, Mevcut: #{game_number}")
        
        # Eğer bu oyun, sinyalin beklediği oyun ise
        if game_number == expected_game:
            print(f"[MARTINGALE_MATCH] ✅ Eşleşme bulundu: #{game_number}")
            
            # Kazanç kontrolü
            if info["suit"] in player_cards_str:
                # KAZANÇ
                new_text = f"#N{info['signal_game']} - {info['suit']} | ✅ {step_emojis[info['step']]}"
                try:
                    await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                    print(f"[WIN] ✅ #N{info['signal_game']} - {info['suit']} kazandı! Adım: {info['step']}")
                except Exception as e:
                    print(f"[EDIT_ERROR] ❌ Mesaj düzenlenemedi: {e}")
                
                info["checked"] = True
                signals_to_remove.append(signal_id)
                
            else:
                # KAYIP - Bir sonraki adıma geç
                info["step"] += 1
                
                if info["step"] > MAX_MARTINGALE_STEP:
                    # MAKSIMUM KAYIP
                    new_text = f"#N{info['signal_game']} - {info['suit']} | ❌"
                    try:
                        await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                        print(f"[LOSE] ❌ #N{info['signal_game']} - {info['suit']} maksimum kayıp!")
                    except Exception as e:
                        print(f"[EDIT_ERROR] ❌ Mesaj düzenlenemedi: {e}")
                    
                    info["checked"] = True
                    signals_to_remove.append(signal_id)
                    
                else:
                    # DEVAM EDİYOR
                    new_text = f"#N{info['signal_game']} - {info['suit']} | 🔃 {step_emojis[info['step']]}"
                    try:
                        await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                        print(f"[CONTINUE] 🔄 #N{info['signal_game']} - {info['suit']} adım {info['step']}'e geçti")
                    except Exception as e:
                        print(f"[EDIT_ERROR] ❌ Mesaj düzenlenemedi: {e}")
    
    # Tamamlanan sinyalleri temizle
    for signal_id in signals_to_remove:
        if signal_id in martingale_tracker:
            del martingale_tracker[signal_id]
            print(f"[CLEANUP] 🗑️ Sinyal {signal_id} temizlendi")

# -------------------------
# Sinyal Sistemi
# -------------------------
async def send_signal(signal_game, flipped, missing_suit, trigger_start_game):
    if not flipped:
        return
        
    signal_id = f"{signal_game}_{flipped}"
    if signal_id in sent_signals:
        return
        
    # Sinyal mesajı
    text = f"#N{signal_game} - {flipped} | 🔃 {step_emojis[0]}"
    
    try:
        sent = await client.send_message(KANAL_HEDEF, text)
        sent_signals.add(signal_id)
        
        # Martingale takibi için bilgileri kaydet
        martingale_tracker[signal_id] = {
            "msg_id": sent.id, 
            "suit": flipped, 
            "step": 0, 
            "checked": False,
            "signal_game": int(signal_game),  # Sinyalin oyun numarası
            "trigger_game": int(trigger_start_game)  # Tetikleyici oyun
        }
        
        print(f"[SIGNAL] 🎯 Sinyal gönderildi: {text}")
        print(f"[TRACKING] 📍 Sinyal takibe alındı: #{signal_game} - {flipped}")

        # Eğer bu sinyalin oyunu ZATEN oynandıysa, hemen kontrol et
        if int(signal_game) in player_results:
            print(f"[IMMEDIATE_CHECK] 🔍 Sinyal oyunu #{signal_game} zaten oynanmış, hemen kontrol ediliyor...")
            await update_martingale_for_game(int(signal_game), player_results[int(signal_game)])
            
    except Exception as e:
        print(f"[SEND_ERROR] ❌ Sinyal gönderilemedi: {e}")

# -------------------------
# Ana logic - DÜZELTİLDİ
# -------------------------
@client.on(events.NewMessage)
@client.on(events.MessageEdited)
async def handler(event):
    if event.chat_id != KANAL_KAYNAK_ID:
        return
        
    msg = event.message
    if not msg or not msg.text:
        return

    text = clean_text(msg.text)
    m = re.search(r'(?:#N|№)(\d+)', text)
    if not m:
        return
    game_number = int(m.group(1))

    player_cards, banker_cards = extract_cards(text)
    if not player_cards:
        return

    # OK işareti varsa, kartlar tam değilse işleme devam etme
    if player_has_arrow(text):
        print(f"[WAIT] #N{game_number}: oyuncu 3.kart bekleniyor (👉). İşlem yapılmıyor.")
        return

    banker_cards = banker_cards or ""

    # Oyun bilgilerini kaydet (sadece tam kartlar geldiğinde)
    player_results[game_number] = player_cards
    banker_results[game_number] = banker_cards
    
    print(f"[GAME] 🎮 #N{game_number} kaydedildi: oyuncu={player_cards} banker={banker_cards}")

    # 1. ÖNCE martingale güncellemesini yap
    print(f"[MARTINGALE_UPDATE] 🔄 #N{game_number} için martingale kontrolü başlatılıyor...")
    await update_martingale_for_game(game_number, player_cards)

    # 2. Tetikleyici belirle
    trigs = trigger_suits_from(player_cards)
    if trigs:
        triggers[game_number] = trigs
        print(f"[TRIGGER] 🎯 #N{game_number} tetikleyici renk = {trigs}")

    # 3. Tetikleyici kontrolü - 1 EL BEKLEME
    for start_game, trigger_colors in list(triggers.items()):
        next_game = get_next_game_number(start_game, 1)

        for trigger_color in trigger_colors[:]:
            # 1 EL GÖRÜNMEZSE SİNYAL
            if next_game in player_results and trigger_color not in player_results[next_game]:
                banker_mid = banker_majority_flip(banker_results.get(next_game, ""))
                flipped = suit_flip.get(banker_mid)

                if flipped:
                    signal_game = get_next_game_number(next_game, 1)
                    print(f"[SIGNAL_TRIGGER] 🚀 Tetikleyici #{start_game} -> #{signal_game}: {trigger_color} 1 el görülmedi, flip: {flipped}")
                    await send_signal(signal_game, flipped, trigger_color, start_game)

                trigger_colors.remove(trigger_color)
                print(f"[TRIGGER_USED] ✅ Tetikleyici #{start_game} rengi {trigger_color} kullanıldı")

        if not trigger_colors:
            del triggers[start_game]
            print(f"[TRIGGER_CLEAN] 🗑️ Tetikleyici #{start_game} tamamen kullanıldı")

# -------------------------
# Debug komutu - Martingale durumunu göster
# -------------------------
@client.on(events.NewMessage(pattern='/durum'))
async def durum_komutu(event):
    durum_metni = f"""
🎯 SİSTEM DURUMU

📊 Toplam Oyun: {len(player_results)}
🎯 Aktif Sinyal: {len(martingale_tracker)}
🔍 Aktif Tetikleyici: {len(triggers)}

📋 AKTİF SİNYALLER:
"""
    
    for signal_id, info in martingale_tracker.items():
        if not info.get("checked"):
            expected_game = info["signal_game"] + info["step"]
            if expected_game > MAX_GAME_NUMBER:
                expected_game -= MAX_GAME_NUMBER
                
            durum_metni += f"#{info['signal_game']} - {info['suit']} | Adım: {info['step']} → Beklenen: #{expected_game}\n"
    
    await event.reply(durum_metni)

# -------------------------
# Başlat
# -------------------------
async def main():
    print("🎯 BAKARA BOTU - SON SÜRÜM başlatılıyor...")
    print("✅ Strateji: Banker çoğunluk renk flip")
    print("✅ Tetikleyici: Oyuncunun İLK kartı") 
    print("✅ Sinyal Mantığı: Tetikleyici renk 1 EL GÖRÜNMEZSE, banker'ın çoğunluk renginin zıttına bahis")
    print("✅ ANINDA SONUÇ: Kartlar açılır açılmaz sonuç gösterilir")
    print("✅ Martingale: 7 seviye")
    print("✅ DEBUG: /durum komutu ile sistem durumunu kontrol edebilirsiniz")
    
    await client.start()
    me = await client.get_me()
    print(f"✅ Bot aktif: {me.username if me.username else me.first_name}")
    print(f"✅ Hedef kanal: {KANAL_HEDEF}")
    
    # Başlangıç mesajı
    try:
        await client.send_message(KANAL_HEDEF, "🎯 Bakara Botu aktif! /durum komutu ile sistem durumunu kontrol edebilirsiniz.")
    except:
        pass
        
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot manuel durduruldu.")
    except Exception as e:
        print(f"❌ Genel hata: {e}")
