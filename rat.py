import re
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError
import asyncio
import sys
from datetime import datetime

# ==============================================================================
# Telegram API Bilgileri ve Kanal Ayarları
# ==============================================================================
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'

# --- Kanal Bilgileri ---
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"

client = TelegramClient('rat_bot', API_ID, API_HASH)

# ==============================================================================
# Global Değişkenler ve Takip Mekanizmaları
# ==============================================================================
game_results = {}
martingale_trackers = {}
MAX_MARTINGALE_STEPS = 3  # 🎯 4 ADIM (0,1,2,3)
MAX_GAME_NUMBER = 1440
is_signal_active = False

# İstatistikler
performance_stats = {
    'total_signals': 0,
    'wins': 0,
    'losses': 0,
    'active_since': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'last_signal': None,
    'consecutive_losses': 0,
    'max_consecutive_losses': 0
}

# Pattern tanımları
STRONG_PATTERNS = ['#C2_3', '#C3_2', '#C3_3']

print("🤖 BOT BAŞLATILDI - OK TAKİBİ AKTİF")

# ==============================================================================
# BASİT OK TAKİBİ FONKSİYONLARI
# ==============================================================================

def is_arrow_on_player_side(text):
    """Ok işaretinin hangi tarafta olduğunu tespit eder"""
    try:
        if '▶️' not in text:
            return False, False
        
        arrow_index = text.find('▶️')
        text_before_arrow = text[:arrow_index]
        
        # Sadece oyuncu kartlarının olup olmadığını kontrol et
        player_has_cards = '(' in text_before_arrow and ')' in text_before_arrow
        
        # Oyuncu tarafında ok varsa True döndür
        return player_has_cards, not player_has_cards
    except Exception as e:
        print(f"❌ Ok tespit hatası: {e}")
        return False, False

# ==============================================================================
# TEMEL FONKSİYONLAR
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
    try:
        cards = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', cards_str)
        if not cards or len(cards) < 2: 
            return None

        max_value = -1
        largest_value_suit = None
        values = [get_baccarat_value(card[0]) for card in cards]
        
        if len(values) == 2 and values[0] == values[1]: 
            return None

        for card_char, suit in cards:
            value = get_baccarat_value(card_char)
            if value > max_value:
                max_value = value
                largest_value_suit = suit

        return None if max_value == 0 else largest_value_suit
    except Exception as e:
        print(f"❌ Kart değeri hatası: {e}")
        return None

def extract_game_info_from_message(text):
    """Oyun bilgilerini çıkar"""
    try:
        game_info = {
            'game_number': None, 
            'player_cards': '', 
            'banker_cards': '',
            'is_final': False, 
            'patterns': [], 
            'pattern_strength': 0,
            'arrow_player': False, 
            'arrow_banker': False
        }
        
        # Oyun numarasını bul
        game_match = re.search(r'[#⏱]N?№?\s*(\d+)', text)
        if game_match:
            game_info['game_number'] = int(game_match.group(1))
        
        # Pattern tespiti
        detected_patterns = [p for p in STRONG_PATTERNS if p in text]
        game_info['patterns'] = detected_patterns
        game_info['pattern_strength'] = len(detected_patterns) * 3

        # Ok konumunu tespit et
        game_info['arrow_player'], game_info['arrow_banker'] = is_arrow_on_player_side(text)
        
        # Final kontrolü
        if any(indicator in text for indicator in ['✅', '🔰', '#X']):
            game_info['is_final'] = True

        # Oyuncu ve banker kartlarını çıkar
        card_matches = re.findall(r'\(([^)]+)\)', text)
        if len(card_matches) >= 1:
            game_info['player_cards'] = card_matches[0]
        if len(card_matches) >= 2:
            game_info['banker_cards'] = card_matches[1]
            
        return game_info
    except Exception as e:
        print(f"❌ Oyun bilgisi hatası: {e}")
        return {'game_number': None}

def should_send_signal(game_info):
    """Sinyal gönderilmeli mi?"""
    try:
        if performance_stats['consecutive_losses'] >= 3:
            return False, "3+ ardışık kayıp"
        
        if not game_info['game_number']:
            return False, "Oyun numarası yok"
            
        # Sadece güçlü patternler
        if not game_info['patterns']:
            return False, "Güçlü pattern yok"
        
        # OYUNCU TARAFINDA OK VARSA SİNYAL GÖNDER
        if not game_info['arrow_player']:
            return False, "Oyuncu tarafında ok yok"
        
        # Kart kontrolü
        signal_suit = extract_largest_value_suit(game_info['player_cards'])
        if not signal_suit:
            return False, "Uygun kart yok"
            
        return True, signal_suit
    except Exception as e:
        print(f"❌ Sinyal kontrol hatası: {e}")
        return False, f"Hata: {e}"

# ==============================================================================
# SİNYAL İŞLEMLERİ
# ==============================================================================

async def send_optimized_signal(game_num, signal_suit, game_info):
    global is_signal_active, performance_stats
    
    if is_signal_active: 
        print("⏳ Aktif sinyal var, yeni sinyal gönderilmiyor")
        return
    
    try:
        performance_stats['total_signals'] += 1
        performance_stats['last_signal'] = datetime.now().strftime('%H:%M:%S')
        
        signal_type = "⚡ YÜKSEK GÜVEN" if game_info['pattern_strength'] >= 3 else "🔸 ORTA GÜVEN"
        signal_full_text = f"**#N{game_num} - Oyuncu {signal_suit} - {MAX_MARTINGALE_STEPS}D - {signal_type}**"

        sent_message = await client.send_message(KANAL_HEDEF, signal_full_text)
        print(f"🎯 SİNYAL GÖNDERİLDİ: {signal_full_text}")
        
        martingale_trackers[game_num] = {
            'message_obj': sent_message, 
            'step': 0, 
            'signal_suit': signal_suit,
            'sent_game_number': game_num, 
            'expected_game_number_for_check': game_num
        }
        is_signal_active = True
        
    except Exception as e:
        print(f"❌ Sinyal gönderme hatası: {e}")

async def check_martingale_trackers():
    global martingale_trackers, is_signal_active, performance_stats
    
    trackers_to_remove = []

    for signal_game_num, tracker_info in list(martingale_trackers.items()):
        try:
            current_step = tracker_info['step']
            game_to_check = tracker_info['expected_game_number_for_check']
            
            if game_to_check not in game_results:
                continue
                
            result_info = game_results.get(game_to_check)
            if not result_info:
                continue
            
            # ⚡ BANKERİN BİTMESİNİ BEKLEME! OYUNCU KARTLARI BELLİ OLUR OLMAZ KONTROL ET
            player_cards_str = result_info.get('player_cards', '')
            
            # Oyuncu kartları yoksa veya henüz belli değilse bekle
            if not player_cards_str or len(player_cards_str.strip()) < 2:
                continue
            
            # Oyuncu kartları belli, hemen kontrol et!
            signal_won = bool(re.search(re.escape(tracker_info['signal_suit']), player_cards_str))
            
            if signal_won:
                performance_stats['wins'] += 1
                performance_stats['consecutive_losses'] = 0
                win_text = f"**#N{signal_game_num} - {tracker_info['signal_suit']} | ✅ {current_step}️⃣**"
                try: 
                    await tracker_info['message_obj'].edit(win_text)
                    print(f"🎉 Sinyal #{signal_game_num} KAZANDI! (Adım {current_step}) - OYUNCU KARTLARI: {player_cards_str}")
                except: 
                    pass
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False
            else:
                if current_step < MAX_MARTINGALE_STEPS:
                    tracker_info['step'] += 1
                    tracker_info['expected_game_number_for_check'] = get_next_game_number(game_to_check)
                    try: 
                        await tracker_info['message_obj'].edit(
                            f"**#N{signal_game_num} - {tracker_info['signal_suit']} - {MAX_MARTINGALE_STEPS}D | 🔄 {tracker_info['step']}️⃣**"
                        )
                        print(f"🔄 Sinyal #{signal_game_num} kaybetti, {tracker_info['step']}. adıma geçiyor - OYUNCU KARTLARI: {player_cards_str}")
                    except: 
                        pass
                else:
                    performance_stats['losses'] += 1
                    performance_stats['consecutive_losses'] += 1
                    try: 
                        await tracker_info['message_obj'].edit(
                            f"**#N{signal_game_num} - {tracker_info['signal_suit']} | ❌**"
                        )
                        print(f"💥 Sinyal #{signal_game_num} kaybetti, SERİ BİTTİ - OYUNCU KARTLARI: {player_cards_str}")
                    except: 
                        pass
                    trackers_to_remove.append(signal_game_num)
                    is_signal_active = False
                    
        except Exception as e:
            print(f"❌ Martingale takip hatası #{signal_game_num}: {e}")

    for game_num in trackers_to_remove:
        martingale_trackers.pop(game_num, None)

# ==============================================================================
# EVENT HANDLER'LAR
# ==============================================================================

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
async def handle_new_message(event):
    """YENİ MESAJ İŞLEYİCİ"""
    try:
        msg = event.message
        if not msg.text:
            return

        print(f"📥 YENİ MESAJ: {msg.text[:100]}...")
        
        game_info = extract_game_info_from_message(msg.text)
        if not game_info['game_number']:
            print("⏭️ Oyun numarası bulunamadı, atlanıyor")
            return

        # Oyun bilgisini kaydet
        game_results[game_info['game_number']] = game_info
        
        # DEBUG: Tüm oyun bilgilerini yazdır
        print(f"🔍 Oyun #{game_info['game_number']} - Pattern: {game_info['patterns']} - Ok: P{game_info['arrow_player']}/B{game_info['arrow_banker']} - Final: {game_info['is_final']}")
        print(f"🔍 Oyuncu Kartları: {game_info['player_cards']}")
        
        # Martingale kontrolü (önceki sinyalleri kontrol et)
        await check_martingale_trackers()
        
        # Sinyal gönder
        if not is_signal_active:
            should_send, reason = should_send_signal(game_info)
            if should_send:
                next_game_num = get_next_game_number(game_info['game_number'])
                await send_optimized_signal(next_game_num, reason, game_info)
            else:
                print(f"⏭️ #N{game_info['game_number']} sinyal gönderilmedi: {reason}")
        else:
            print("⏭️ Zaten aktif sinyal var, yeni sinyal gönderilmiyor")
            
    except Exception as e:
        print(f"❌ Mesaj işleme hatası: {e}")

@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_edited_message(event):
    """DÜZENLENEN MESAJ İŞLEYİCİ"""
    try:
        msg = event.message
        if not msg.text:
            return

        print(f"✏️ DÜZENLENEN MESAJ: {msg.text[:100]}...")
        
        game_info = extract_game_info_from_message(msg.text)
        if not game_info['game_number']:
            return

        # Oyun bilgisini güncelle
        game_results[game_info['game_number']] = game_info
        
        # DEBUG: Tüm oyun bilgilerini yazdır
        print(f"🔍 [EDIT] Oyun #{game_info['game_number']} - Pattern: {game_info['patterns']} - Ok: P{game_info['arrow_player']}/B{game_info['arrow_banker']} - Final: {game_info['is_final']}")
        
        # Martingale kontrolü
        await check_martingale_trackers()
        
        # Sinyal gönder
        if not is_signal_active:
            should_send, reason = should_send_signal(game_info)
            if should_send:
                next_game_num = get_next_game_number(game_info['game_number'])
                await send_optimized_signal(next_game_num, reason, game_info)
            else:
                print(f"⏭️ [EDIT] #N{game_info['game_number']} sinyal gönderilmedi: {reason}")
                    
    except Exception as e:
        print(f"❌ Düzenlenen mesaj hatası: {e}")

# ==============================================================================
# TELEGRAM KOMUTLARI
# ==============================================================================

@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    await event.reply("""
🤖 **Baccarat Bot Aktif** 
✅ OK Takibi: ÇALIŞIYOR
🎯 Martingale: 4 ADIM
🔍 Pattern: #C2_3, #C3_2, #C3_3

**Komutlar:**
/start - Bu mesajı göster
/stats - İstatistikler
/status - Bot durumu
/active - Aktif sinyaller
""")

@client.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    total = performance_stats['wins'] + performance_stats['losses']
    win_rate = (performance_stats['wins'] / total * 100) if total > 0 else 0
    await event.reply(f"""
📊 **İstatistikler:**
├─ Sinyal: {performance_stats['total_signals']}
├─ Kazanç: {performance_stats['wins']} 
├─ Kayıp: {performance_stats['losses']}
├─ Oran: {win_rate:.1f}%
├─ Ardışık Kayıp: {performance_stats['consecutive_losses']}
└─ Martingale: {MAX_MARTINGALE_STEPS} adım
""")

@client.on(events.NewMessage(pattern='/status'))
async def status_command(event):
    await event.reply(f"""
🟢 **Bot Durumu:**
├─ Aktif Sinyal: {'✅' if is_signal_active else '❌'}
├─ Takip Edilen: {len(martingale_trackers)} sinyal
├─ Ardışık Kayıp: {performance_stats['consecutive_losses']}
├─ Hafıza: {len(game_results)} oyun
└─ Son Sinyal: {performance_stats['last_signal'] or 'Yok'}
""")

@client.on(events.NewMessage(pattern='/active'))
async def active_command(event):
    if performance_stats['consecutive_losses'] >= 3:
        await event.reply("🔴 SİSTEM DURDURULDU - 3+ ardışık kayıp")
    elif is_signal_active and martingale_trackers:
        active_list = "\n".join([f"├─ #N{num} - {t['signal_suit']} (Adım {t['step']})" for num, t in martingale_trackers.items()])
        await event.reply(f"🔴 **AKTİF SİNYAL:**\n{active_list}\n└─ Toplam: {len(martingale_trackers)} sinyal")
    else:
        await event.reply("🟢 **Aktif sinyal yok**\n└─ Bot sinyal bekliyor...")

# ==============================================================================
# BOT BAŞLATMA
# ==============================================================================

if __name__ == '__main__':
    print("🤖 BACCARAT BOT YENİDEN BAŞLATILDI!")
    print("🎯 Özellikler: OK Takibi + 4 Adım Martingale")
    print("⚡ BANKER BEKLENMEZ - OYUNCU KARTLARI BELLİ OLUR OLMAZ HAREKET EDİLİR")
    print("=====================================")
    
    try:
        with client:
            client.run_until_disconnected()
    except Exception as e:
        print(f"❌ BOT CRASH: {e}")
        sys.exit(1)
