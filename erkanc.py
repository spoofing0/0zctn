# -*- coding: utf-8 -*-
import re
import asyncio
from telethon import TelegramClient, events

API_ID = 22739329
API_HASH = '06359bb9ddf6646c225b3cf112c5fba7'
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@erkans10"

client = TelegramClient('baccarat_final_bot_v28', API_ID, API_HASH)

# -------------------------
# Durum depoları / ayarlar
# -------------------------
player_results = {}        # {game_num: "cards string"}
banker_results = {}        # {game_num: "cards string"}
martingale_tracker = {}    # {signal_game: {msg_id, suit, step, checked, signal_type}}
sent_signals = set()
MAX_GAME_NUMBER = 1440
MAX_MARTINGALE_STEP = 7
step_emojis = {0:"0️⃣",1:"1️⃣",2:"2️⃣",3:"3️⃣",4:"4️⃣",5:"5️⃣",6:"6️⃣",7:"7️⃣"}

# Renk çevirme kuralları
suit_flip = {"♣️": "♦️", "♦️": "♣️", "♥️": "♠️", "♠️": "♥️",
             "♣":"♦️","♦":"♣️","♥":"♠️","♠":"♥️"}

# -------------------------
# Helper fonksiyonlar
# -------------------------
def clean_text(t):
    return re.sub(r'\s+', ' ', t.replace('️','').replace('\u200b','')).strip()

def get_previous_game(n, back=10):
    """n oyunundan back kadar geriye git (döngüsel)"""
    r = n - back
    while r < 1:
        r += MAX_GAME_NUMBER
    return r

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
    # normalize variants to emoji form
    player_cards = player_cards.replace('♣','♣️').replace('♦','♦️').replace('♥','♥️').replace('♠','♠️')
    banker_cards = banker_cards.replace('♣','♣️').replace('♦','♦️').replace('♥','♥️').replace('♠','♠️')
    return player_cards, banker_cards

def player_has_arrow(text):
    # Daha esnek ok kontrolü
    return "👉" in text or "➡️" in text or "→" in text

def suits_from_cards(card_str):
    return re.findall(r'[♣♥♦♠]️?', card_str) if card_str else []

def get_first_card_suit(cards_str):
    """Oyuncunun ilk kartının rengini döndürür"""
    suits = suits_from_cards(cards_str)
    return suits[0] if suits else None

def get_middle_card_suit(cards_str):
    """Oyuncunun orta kartının rengini döndürür (en az 2 kart varsa)"""
    suits = suits_from_cards(cards_str)
    return suits[1] if len(suits) >= 2 else None

# -------------------------
# Martingale (TAMAMEN YENİ MANTIK - STEP SAYISI DÜZELTİLMİŞ)
# -------------------------
async def update_martingale(current_game, player_cards_str):
    for bet_game, info in list(martingale_tracker.items()):
        if info.get("checked"):
            continue
        
        # DÜZELTME: Beklenen oyun = sinyal oyunu + step
        expected_game = get_next_game_number(bet_game, info["step"])
        
        print(f"[DEBUG] 🎯 Martingale kontrol: Oyun #{current_game}, Sinyal #{bet_game}, Step {info['step']}, Beklenen: #{expected_game}, Renk: {info['suit']}")
        
        if current_game != expected_game:
            continue
            
        type_tag = " O" if info.get("signal_type") == "middle" else ""
        
        if info["suit"] in player_cards_str:
            # KAZANILDI - ✅ işareti ve kazanılan step (STEP + 1 olarak göster)
            kazanim_step = info["step"]  # Bu step'te kazanıldı
            new_text = f"#N{bet_game} - {info['suit']}✅{type_tag} {step_emojis[kazanim_step]}"
            try:
                await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                print(f"[RESULT] ✅ #N{bet_game}: {new_text} (Step {kazanim_step}'de kazanıldı)")
            except Exception as e:
                print(f"[EDIT ERROR] ❌ #N{bet_game} düzenlenirken hata: {e}")
            info["checked"] = True
            
        else:
            info["step"] += 1
            
            if info["step"] > MAX_MARTINGALE_STEP:
                # TAM KAYIP - ❌ işareti
                new_text = f"#N{bet_game} - {info['suit']}❌{type_tag}"
                try:
                    await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                    print(f"[RESULT] ❌ #N{bet_game}: Maksimum step kayıp - {new_text}")
                except Exception as e:
                    print(f"[EDIT ERROR] ❌ #N{bet_game} düzenlenirken hata: {e}")
                info["checked"] = True
                
            else:
                # BİR SONRAKİ ADIM - step emojisi gösterilecek
                new_text = f"#N{bet_game} - {info['suit']}{step_emojis[info['step']]}{type_tag}"
                try:
                    await client.edit_message(KANAL_HEDEF, info["msg_id"], new_text)
                    print(f"[STEP] 🔄 Martingale Adım {info['step']}: {new_text}")
                except Exception as e:
                    print(f"[EDIT ERROR] ❌ #N{bet_game} düzenlenirken hata: {e}")

# -------------------------
# Sinyal gönderme (DÜZELTİLMİŞ - İLK STEP 1 OLARAK BAŞLAT)
# -------------------------
async def send_signal(signal_game, signal_suit, signal_type):
    """signal_type: 'first' veya 'middle'"""
    # Aynı oyun için farklı türde sinyal gönderilmesine izin ver
    signal_key = f"{signal_game}_{signal_type}"
    
    if signal_key in sent_signals:
        return
    
    type_tag = " O" if signal_type == "middle" else ""
    # DÜZELTME: İlk sinyalde step 1 olarak başlat
    text = f"#N{signal_game} - {signal_suit}{step_emojis[1]}{type_tag}"
    
    try:
        sent = await client.send_message(KANAL_HEDEF, text)
        sent_signals.add(signal_key)
        martingale_tracker[signal_game] = {
            "msg_id": sent.id, 
            "suit": signal_suit, 
            "step": 1,  # DÜZELTME: Step 1'den başlat
            "checked": False,
            "signal_type": signal_type
        }
        print(f"[SIGNAL] 🎯 Gönderildi: {text}")
    except Exception as e:
        print(f"[SEND ERROR] ❌ Sinyal gönderilemedi: {e}")

# -------------------------
# 10-oyun geri sistemi
# -------------------------
async def check_10_game_back_system(current_game, current_player_cards):
    """10 oyun geri sistemi ile sinyal kontrolü - KAYNAK OYUN RENGİNİN TERSİ"""
    
    # 10 oyun gerideki oyunu bul
    previous_game_10 = get_previous_game(current_game, 10)
    
    # Eğer 10 oyun gerideki oyun veritabanında yoksa çık
    if previous_game_10 not in player_results:
        return
    
    previous_player_cards = player_results[previous_game_10]
    
    # 1. İlk Kart Eşleşmesi Kontrolü
    current_first_suit = get_first_card_suit(current_player_cards)
    previous_first_suit = get_first_card_suit(previous_player_cards)
    
    if current_first_suit and previous_first_suit and current_first_suit == previous_first_suit:
        # Kaynak oyun: previous_game_10 + 1
        signal_source_game = get_next_game_number(previous_game_10, 1)
        if signal_source_game in player_results:
            signal_source_first_suit = get_first_card_suit(player_results[signal_source_game])
            if signal_source_first_suit:
                # KAYNAK OYUNUN RENGİNİN TERSİ
                signal_suit = suit_flip.get(signal_source_first_suit)
                # Sinyal oyunu: previous_game_10 + 11 (current_game + 1)
                signal_game = get_next_game_number(previous_game_10, 11)
                await send_signal(signal_game, signal_suit, "first")
                print(f"[10-BACK] 🔄 İlk kart eşleşmesi: #{previous_game_10}-#{current_game} → #{signal_game} - {signal_suit} (Kaynak #{signal_source_game}: {signal_source_first_suit} tersi)")
    
    # 2. Orta Kart Eşleşmesi Kontrolü
    current_middle_suit = get_middle_card_suit(current_player_cards)
    previous_middle_suit = get_middle_card_suit(previous_player_cards)
    
    if (current_middle_suit and previous_middle_suit and 
        current_middle_suit == previous_middle_suit):
        # Kaynak oyun: previous_game_10 + 1
        signal_source_game = get_next_game_number(previous_game_10, 1)
        if signal_source_game in player_results:
            signal_source_middle_suit = get_middle_card_suit(player_results[signal_source_game])
            if signal_source_middle_suit:
                # KAYNAK OYUNUN RENGİNİN TERSİ
                signal_suit = suit_flip.get(signal_source_middle_suit)
                # Sinyal oyunu: previous_game_10 + 11 (current_game + 1)
                signal_game = get_next_game_number(previous_game_10, 11)
                await send_signal(signal_game, signal_suit, "middle")
                print(f"[10-BACK] 🔄 Orta kart eşleşmesi: #{previous_game_10}-#{current_game} → #{signal_game} - {signal_suit} (Kaynak #{signal_source_game}: {signal_source_middle_suit} tersi)")

# -------------------------
# Ana handler
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
    
    # Birden fazla oyun formatını destekle
    m = re.search(r'(?:#N|№|#)(\d+)', text)
    if not m:
        return
    
    game_number = int(m.group(1))
    
    # Geçersiz oyun numarası kontrolü
    if game_number < 1 or game_number > MAX_GAME_NUMBER:
        print(f"[WARNING] ⚠️ Geçersiz oyun numarası: #{game_number}")
        return

    # Kartları çıkar
    player_cards, banker_cards = extract_cards(text)
    if not player_cards:
        return

    # Eğer oyuncuda 3.kart bekleniyorsa işlem yapma
    if player_has_arrow(text):
        print(f"[WAIT] #N{game_number}: oyuncu 3.kart bekleniyor (👉). Kartlar: {player_cards}")
        return

    banker_cards = banker_cards or ""

    # Veritabanına kaydet
    player_results[game_number] = player_cards
    banker_results[game_number] = banker_cards
    print(f"[STORE] #N{game_number} kaydedildi: oyuncu={player_cards} banker={banker_cards}")

    # 1) Martingale güncelle
    await update_martingale(game_number, player_cards)

    # 2) Yeni 10-oyun geri sistemi ile sinyal kontrolü
    await check_10_game_back_system(game_number, player_cards)

# -------------------------
# Başlat
# -------------------------
async def main():
    print("🎯 Bakara Botu (v28) başlatılıyor... (DÜZELTİLMİŞ MARTINGALE - STEP 1'DEN BAŞLAR)")
    await client.start()
    me = await client.get_me()
    print(f"✅ Bot aktif: {me.username if me.username else me.first_name}")
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot manuel durduruldu.")
    except Exception as e:
        print("❌ Genel hata:", e)