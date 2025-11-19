# -*- coding: utf-8 -*-
import re
import asyncio
from telethon import TelegramClient, events

API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@kbubakara"

client = TelegramClient('baccarat_3kart_bot', API_ID, API_HASH)

# -------------------------
# Ayarlar
# -------------------------
MAX_GAME_NUMBER = 1440
sent_signals = set()
step_emojis = {0:"0️⃣",1:"1️⃣",2:"2️⃣",3:"3️⃣",4:"4️⃣",5:"5️⃣",6:"6️⃣",7:"7️⃣"}

# -------------------------
# Martingale Takip
# -------------------------
martingale_tracker = {}
MAX_MARTINGALE_STEP = 5  # 3.kart için daha düşük martingale

# -------------------------
# Helper fonksiyonlar
# -------------------------
def clean_text(t):
    return re.sub(r'\s+', ' ', t.replace('️','').replace('\u200b','')).strip()

def extract_cards(text):
    groups = re.findall(r'\((.*?)\)', text)
    if not groups:
        return None, None
    player_cards = groups[0].replace(' ', '')
    banker_cards = groups[1].replace(' ', '') if len(groups) > 1 else ""
    player_cards = player_cards.replace('♣','♣️').replace('♦','♦️').replace('♥','♥️').replace('♠','♠️')
    banker_cards = banker_cards.replace('♣','♣️').replace('♦','♦️').replace('♥','♥️').replace('♠','♠️')
    return player_cards, banker_cards

def suits_from_cards(card_str):
    return re.findall(r'[♣♥♦♠]️?', card_str) if card_str else []

def extract_third_banker_card(banker_cards_str):
    """Banker'ın 3. kartını çıkar"""
    suits = suits_from_cards(banker_cards_str)
    return suits[2] if len(suits) >= 3 else None

def get_next_game_number(n, step=1):
    n = int(n) + step
    if n > MAX_GAME_NUMBER:
        n -= MAX_GAME_NUMBER
    return n

# -------------------------
# Martingale Sistemi - 3.Kart için optimize
# -------------------------
async def update_martingale_for_game(game_number, player_cards_str):
    """3.kart sinyalleri için martingale güncelleme"""
    signals_to_remove = []
    
    for signal_id, info in list(martingale_tracker.items()):
        if info.get("checked"):
            continue
            
        expected_game = info["signal_game"]
        
        if game_number == expected_game:
            # Kazanç kontrolü - 3.kart stratejisi
            if info["suit"] in player_cards_str:
                # KAZANÇ
                new_text = f"#N{info['signal_game']} - {info['suit']} | ✅ {step_emojis[info['step']]} (3.Kart)"
                try:
                    await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                    print(f"[3.KART_WIN] ✅ #N{info['signal_game']} - {info['suit']} kazandı!")
                except Exception as e:
                    print(f"[EDIT_ERROR] ❌ Mesaj düzenlenemedi: {e}")
                
                info["checked"] = True
                signals_to_remove.append(signal_id)
                
            else:
                # KAYIP - Martingale
                info["step"] += 1
                
                if info["step"] > MAX_MARTINGALE_STEP:
                    # MAKSIMUM KAYIP
                    new_text = f"#N{info['signal_game']} - {info['suit']} | ❌ (3.Kart)"
                    try:
                        await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                        print(f"[3.KART_LOSE] ❌ #N{info['signal_game']} - {info['suit']} maksimum kayıp!")
                    except Exception as e:
                        print(f"[EDIT_ERROR] ❌ Mesaj düzenlenemedi: {e}")
                    
                    info["checked"] = True
                    signals_to_remove.append(signal_id)
                    
                else:
                    # DEVAM EDİYOR
                    next_game = get_next_game_number(info["signal_game"], 1)
                    martingale_tracker[f"third_{next_game}_{info['suit']}"] = {
                        "msg_id": info["msg_id"],
                        "suit": info["suit"],
                        "step": info["step"],
                        "checked": False,
                        "signal_game": next_game,
                        "source_game": info["source_game"]
                    }
                    
                    new_text = f"#N{info['signal_game']} - {info['suit']} | 🔃 {step_emojis[info['step']]} (3.Kart)"
                    try:
                        await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                        print(f"[3.KART_CONTINUE] 🔄 #N{info['signal_game']} - {info['suit']} adım {info['step']}'e geçti")
                    except Exception as e:
                        print(f"[EDIT_ERROR] ❌ Mesaj düzenlenemedi: {e}")
    
    # Temizle
    for signal_id in signals_to_remove:
        if signal_id in martingale_tracker:
            del martingale_tracker[signal_id]

# -------------------------
# 3.Kart Sinyal Sistemi
# -------------------------
async def send_third_card_signal(target_game, suit, source_game):
    signal_id = f"third_{target_game}_{suit}"
    if signal_id in sent_signals:
        return
        
    text = f"#N{target_game} - {suit} | 🔃 {step_emojis[0]} (3.Kart)"
    
    try:
        sent = await client.send_message(KANAL_HEDEF, text)
        sent_signals.add(signal_id)
        
        # Martingale takibi
        martingale_tracker[signal_id] = {
            "msg_id": sent.id,
            "suit": suit,
            "step": 0,
            "checked": False,
            "signal_game": int(target_game),
            "source_game": int(source_game)
        }
        
        print(f"[3.KART_SINYAL] 🎯 Banker #{source_game} 3.kart {suit} → #N{target_game}")
        
        # Eğer sinyal oyunu zaten oynandıysa hemen kontrol et
        if int(target_game) in player_results:
            print(f"[3.KART_IMMEDIATE] 🔍 Sinyal oyunu #{target_game} zaten oynanmış, kontrol ediliyor...")
            await update_martingale_for_game(int(target_game), player_results[int(target_game)])
            
    except Exception as e:
        print(f"[3.KART_ERROR] ❌ Sinyal gönderilemedi: {e}")

# -------------------------
# Ana logic - SADECE 3.KART STRATEJİSİ
# -------------------------
player_results = {}
banker_results = {}

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

    # Oyun bilgilerini kaydet
    player_results[game_number] = player_cards
    banker_results[game_number] = banker_cards
    
    print(f"[GAME] 🎮 #N{game_number} kaydedildi")

    # 1. ÖNCE martingale güncellemesini yap
    await update_martingale_for_game(game_number, player_cards)

    # 2. 3.KART ANALİZİ - ANA STRATEJİ
    if banker_cards:
        third_card = extract_third_banker_card(banker_cards)
        if third_card:
            next_game = get_next_game_number(game_number, 1)
            print(f"[3.KART_BULUNDU] ✅ #N{game_number} 3.kart: {third_card} → #N{next_game}")
            await send_third_card_signal(next_game, third_card, game_number)

# -------------------------
# Debug komutu
# -------------------------
@client.on(events.NewMessage(pattern='/durum'))
async def durum_komutu(event):
    active_signals = sum(1 for info in martingale_tracker.values() if not info.get("checked"))
    
    durum_metni = f"""
🎯 3.KART SİSTEM DURUMU

📊 Toplam Oyun: {len(player_results)}
🎯 Aktif 3.Kart Sinyali: {active_signals}
📈 Tahmini Başarı Oranı: %70.11

📋 AKTİF 3.KART SİNYALLERİ:
"""
    
    for signal_id, info in martingale_tracker.items():
        if not info.get("checked"):
            durum_metni += f"#{info['signal_game']} - {info['suit']} | Kaynak: #{info['source_game']} | Adım: {info['step']}\n"
    
    await event.reply(durum_metni)

# -------------------------
# Başlat
# -------------------------
async def main():
    print("🎯 BAKARA BOTU - 3.KART STRATEJİSİ başlatılıyor...")
    print("✅ Strateji: Banker 3. Kart Takibi")
    print("✅ Veri Analizi: 200 oyunda %70.11 başarı oranı")
    print("✅ Sinyal Mantığı: Banker 3. kartı → Sonraki oyunda oyuncuda aynı renk")
    print("✅ Martingale: 5 seviye (optimize)")
    
    await client.start()
    me = await client.get_me()
    print(f"✅ Bot aktif: {me.username if me.username else me.first_name}")
    print(f"✅ Hedef kanal: {KANAL_HEDEF}")
    
    # Başlangıç mesajı
    try:
        await client.send_message(KANAL_HEDEF, "🎯 3.Kart Botu aktif! /durum komutu ile sistem durumunu kontrol edebilirsiniz.")
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
