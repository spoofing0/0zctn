import re, json, os, asyncio, sys, pytz
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageNotModifiedError

API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
BOT_TOKEN = ''
KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"
ADMIN_ID = 1136442929
SISTEM_MODU = "normal_hibrit"
GMT3 = pytz.timezone('Europe/Istanbul')
client = TelegramClient('royal_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

game_results, martingale_trackers, color_trend, recent_games = {}, {}, [], []
MAX_MARTINGALE_STEPS, MAX_GAME_NUMBER, is_signal_active, daily_signal_count = 3, 1440, False, 0

def get_suit_display_name(suit_symbol):
    suit_names = {'♠': '♠️ MAÇA', '♥': '❤️ KALP', '♦': '♦️ KARO', '♣': '♣️ SİNEK'}
    return suit_names.get(suit_symbol, f"❓ {suit_symbol}")

C2_3_TYPES = {'#C2_3': {'emoji': '🔴', 'name': 'KLASİK', 'confidence': 0.9}, '#C2_2': {'emoji': '🔵', 'name': 'ALTERNATİF', 'confidence': 0.7}, '#C3_2': {'emoji': '🟢', 'name': 'VARYANT', 'confidence': 0.6}, '#C3_3': {'emoji': '🟡', 'name': 'ÖZEL', 'confidence': 0.7}}

def get_baccarat_value(card_char):
    if card_char == '10': return 10
    if card_char in 'AKQJ2T': return 0
    elif card_char.isdigit(): return int(card_char)
    return -1

def extract_largest_value_suit(cards_str):
    try:
        cards = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', cards_str)
        if not cards: return None
        max_value, largest_value_suit = -1, None
        values = [get_baccarat_value(card[0]) for card in cards]
        if len(values) == 2 and values[0] == values[1]: return None
        for card_char, suit in cards:
            value = get_baccarat_value(card_char)
            if value > max_value: max_value, largest_value_suit = value, suit
        return largest_value_suit if max_value > 0 else None
    except Exception as e:
        print(f"❌ extract_largest_value_suit hatası: {e}")
        return None

def analyze_simple_pattern(player_cards, banker_cards, game_number):
    try:
        signal_color = extract_largest_value_suit(player_cards)
        if not signal_color: return None, "Renk tespit edilemedi"
        color_trend.append(signal_color)
        if len(color_trend) > 10: color_trend.pop(0)
        player_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', player_cards)
        player_values = [get_baccarat_value(card[0]) for card in player_card_data]
        banker_card_data = re.findall(r'(10|[A2-9TJQK])([♣♦♥♠])', banker_cards)
        banker_values = [get_baccarat_value(card[0]) for card in banker_card_data]
        total_cards = len(player_values) + len(banker_values)
        if sum(player_values) >= 8 and len(player_values) >= 3: return signal_color, "🎯 GÜÇLÜ EL"
        elif sum(player_values) in [8, 9]: return signal_color, "🏆 DOĞAL KAZANÇ"
        elif total_cards >= 5: return signal_color, "📊 5+ KART"
        elif len(color_trend) >= 3 and color_trend[-3:] == [signal_color] * 3: return signal_color, "🚨 3x TEKRAR"
        else: return signal_color, "📈 STANDART SİNYAL"
    except Exception as e:
        print(f"❌ Pattern analysis error: {e}")
        return None, f"Hata: {e}"

def besli_onay_sistemi(player_cards, banker_cards, game_number):
    onaylar = []
    temel_renk = extract_largest_value_suit(player_cards)
    if temel_renk: 
        onaylar.append(("C2_3", temel_renk))
        print(f"✅ C2_3 onay: {temel_renk}")
    pattern_renk, pattern_sebep = analyze_simple_pattern(player_cards, banker_cards, game_number)
    if pattern_renk and "STANDART" not in pattern_sebep:
        onaylar.append(("PATTERN", pattern_renk))
        print(f"✅ Pattern onay: {pattern_renk} - {pattern_sebep}")
    if color_trend:
        trend_renk = color_trend[-1] if color_trend else None
        if trend_renk: onaylar.append(("TREND", trend_renk))
    if len(color_trend) >= 3:
        son_uc = color_trend[-3:]
        if son_uc.count(temel_renk) >= 2: onaylar.append(("REPEAT", temel_renk))
    renk_oyları = {}
    for yontem, renk in onaylar: renk_oyları[renk] = renk_oyları.get(renk, 0) + 1
    if renk_oyları:
        kazanan_renk = max(renk_oyları, key=renk_oyları.get)
        oy_sayisi = renk_oyları[kazanan_renk]
        güven = oy_sayisi / 5
        print(f"📊 5'li onay: {kazanan_renk} - {oy_sayisi}/5 - %{güven*100:.1f}")
        if oy_sayisi >= 3 and güven >= 0.6: return kazanan_renk, f"✅ 5-Lİ ONAY ({oy_sayisi}/5) - %{güven*100:.1f}"
    return None, "❌ 5'li onay sağlanamadı"

def super_filtre_kontrol(signal_color, reason, game_number):
    if len(color_trend) >= 5:
        if color_trend[-5:].count(signal_color) == 0: return False, "❌ SOĞUK TREND"
    if len(recent_games) >= 3:
        son_kayiplar = sum(1 for oyun in recent_games[-3:] if not oyun.get('kazanç', True))
        if son_kayiplar >= 2: return False, "🎯 ARDIŞIK KAYIPLAR"
    return True, "✅ TÜM FİLTRELER GEÇTİ"

def super_risk_analizi():
    risk_puan, uyarılar = 0, []
    if len(color_trend) >= 5:
        son_5 = color_trend[-5:]
        if len(set(son_5)) == 1: risk_puan, uyarılar = risk_puan + 30, uyarılar + ["🚨 5x AYNI RENK"]
    if risk_puan >= 30: return "🔴 YÜKSEK RİSK", uyarılar
    elif risk_puan >= 20: return "🟡 ORTA RİSK", uyarılar
    else: return "🟢 DÜŞÜK RİSK", uyarılar

def get_next_game_number(current_game_num):
    next_num = current_game_num + 1
    return 1 if next_num > MAX_GAME_NUMBER else next_num

async def send_new_signal(game_num, signal_suit, reason, c2_3_info=None):
    global is_signal_active, daily_signal_count
    try:
        suit_display = get_suit_display_name(signal_suit)
        if c2_3_info:
            c2_3_type, c2_3_desc = c2_3_info.get('c2_3_type', ''), c2_3_info.get('c2_3_description', '')
            trigger_info = f"{c2_3_desc} {c2_3_type}"
        else: trigger_info = "KLASİK #C2_3"
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        signal_text = f"🎯 **SİNYAL BAŞLADI** 🎯\n#N{game_num} - {suit_display}\n📊 Tetikleyici: {trigger_info}\n🎯 Sebep: {reason}\n⚡ Strateji: Martingale {MAX_MARTINGALE_STEPS} Seviye\n🕒 {gmt3_time} (GMT+3)\n🔴 SONUÇ: BEKLENİYOR..."
        sent_message = await client.send_message(KANAL_HEDEF, signal_text)
        print(f"🚀 Sinyal gönderildi: #N{game_num} - {suit_display} - {trigger_info}")
        daily_signal_count += 1
        martingale_trackers[game_num] = {'message_obj': sent_message, 'step': 0, 'signal_suit': signal_suit, 'sent_game_number': game_num, 'expected_game_number_for_check': game_num, 'start_time': datetime.now(GMT3), 'reason': reason, 'c2_3_type': c2_3_info.get('c2_3_type', '') if c2_3_info else '#C2_3', 'results': []}
        is_signal_active = True
    except Exception as e: print(f"❌ Sinyal gönderme hatası: {e}")

async def update_signal_message(tracker_info, result_type, current_step=None, result_details=None):
    try:
        signal_game_num, signal_suit = tracker_info['sent_game_number'], tracker_info['signal_suit']
        suit_display, message_obj, reason = get_suit_display_name(signal_suit), tracker_info['message_obj'], tracker_info.get('reason', '')
        duration = datetime.now(GMT3) - tracker_info['start_time']
        duration_str = f"{duration.seconds // 60}d {duration.seconds % 60}s"
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        if result_details: tracker_info['results'].append(result_details)
        if result_type == 'win':
            new_text = f"✅ **KAZANÇ** ✅\n#N{signal_game_num} - {suit_display}\n📊 Sebep: {reason}\n🎯 Seviye: {current_step if current_step else 0}. Seviye\n⏱️ Süre: {duration_str}\n🕒 Bitiş: {gmt3_time}\n🏆 **SONUÇ: KAZANDINIZ!**"
        elif result_type == 'loss':
            new_text = f"❌ **KAYIP** ❌\n#N{signal_game_num} - {suit_display}\n📊 Sebep: {reason}\n🎯 Seviye: {current_step if current_step else MAX_MARTINGALE_STEPS}. Seviye\n⏱️ Süre: {duration_str}\n🕒 Bitiş: {gmt3_time}\n💔 **SONUÇ: KAYBETTİNİZ**"
        elif result_type == 'progress':
            step_details = f"{current_step}. seviye → #{tracker_info['expected_game_number_for_check']}"
            results_history = "\n".join([f"• {r}" for r in tracker_info['results']]) if tracker_info['results'] else "• İlk deneme"
            new_text = f"🔄 **MARTINGALE İLERLİYOR** 🔄\n#N{signal_game_num} - {suit_display}\n📊 Sebep: {reason}\n🎯 Adım: {step_details}\n⏱️ Süre: {duration_str}\n🕒 Son Güncelleme: {gmt3_time}\n📈 Geçmiş:\n{results_history}\n🎲 **SONRAKİ: #{tracker_info['expected_game_number_for_check']}**"
        elif result_type == 'step_result':
            new_text = f"📊 **ADIM SONUCU** 📊\n#N{signal_game_num} - {suit_display}\n🎯 Adım: {current_step}. seviye\n📋 Sonuç: {result_details}\n⏱️ Süre: {duration_str}\n🕒 Zaman: {gmt3_time}\n🔄 **DEVAM EDİYOR...**"
        await message_obj.edit(new_text)
        print(f"✏️ Sinyal güncellendi: #{signal_game_num} - {result_type}")
    except MessageNotModifiedError: pass
    except Exception as e: print(f"❌ Mesaj düzenleme hatası: {e}")

async def check_martingale_trackers():
    global martingale_trackers, is_signal_active
    trackers_to_remove = []
    for signal_game_num, tracker_info in list(martingale_trackers.items()):
        current_step, signal_suit, game_to_check = tracker_info['step'], tracker_info['signal_suit'], tracker_info['expected_game_number_for_check']
        if game_to_check not in game_results: continue
        result_info = game_results.get(game_to_check)
        if not result_info['is_final']: continue
        player_cards_str = result_info['player_cards']
        signal_won_this_step = bool(re.search(re.escape(signal_suit), player_cards_str))
        print(f"🔍 Sinyal kontrol: #{signal_game_num} (Seviye {current_step}) → #{game_to_check}")
        if signal_won_this_step:
            result_details = f"#{game_to_check} ✅ Kazanç - {current_step}. seviye"
            await update_signal_message(tracker_info, 'step_result', current_step, result_details)
            await asyncio.sleep(1)
            await update_signal_message(tracker_info, 'win', current_step)
            trackers_to_remove.append(signal_game_num)
            is_signal_active = False
            recent_games.append({'kazanç': True, 'adim': current_step})
            if len(recent_games) > 20: recent_games.pop(0)
            print(f"🎉 Sinyal #{signal_game_num} KAZANDI! Seviye: {current_step}")
        else:
            result_details = f"#{game_to_check} ❌ Kayıp - {current_step}. seviye"
            await update_signal_message(tracker_info, 'step_result', current_step, result_details)
            await asyncio.sleep(1)
            if current_step < MAX_MARTINGALE_STEPS:
                next_step, next_game_num = current_step + 1, get_next_game_number(game_to_check)
                martingale_trackers[signal_game_num]['step'], martingale_trackers[signal_game_num]['expected_game_number_for_check'] = next_step, next_game_num
                await update_signal_message(tracker_info, 'progress', next_step)
                print(f"📈 Sinyal #{signal_game_num} → {next_step}. seviye → #{next_game_num}")
            else:
                await update_signal_message(tracker_info, 'loss', current_step)
                trackers_to_remove.append(signal_game_num)
                is_signal_active = False
                recent_games.append({'kazanç': False, 'adim': current_step})
                if len(recent_games) > 20: recent_games.pop(0)
                print(f"💔 Sinyal #{signal_game_num} KAYBETTİ! Son seviye: {current_step}")
    for game_num_to_remove in trackers_to_remove:
        if game_num_to_remove in martingale_trackers: del martingale_trackers[game_num_to_remove]

def extract_game_info_from_message(text):
    game_info = {'game_number': None, 'player_cards': '', 'banker_cards': '', 'is_final': False, 'is_player_drawing': False, 'is_c2_3': False, 'c2_3_type': None, 'c2_3_description': ''}
    try:
        game_match = re.search(r'#N(\d+)', text)
        if game_match: game_info['game_number'] = int(game_match.group(1))
        player_match = re.search(r'\((.*?)\)', text)
        if player_match: game_info['player_cards'] = player_match.group(1)
        banker_match = re.search(r'\d+\s+\((.*?)\)', text)
        if banker_match: game_info['banker_cards'] = banker_match.group(1)
        for trigger_type, trigger_data in C2_3_TYPES.items():
            if trigger_type in text:
                game_info['is_c2_3'], game_info['c2_3_type'], game_info['c2_3_description'] = True, trigger_type, trigger_data['name']
                break
        if ('✅' in text or '🔰' in text or '#X' in text): game_info['is_final'] = True
    except Exception as e: print(f"❌ Oyun bilgisi çıkarma hatası: {e}")
    return game_info

async def normal_hibrit_sistemi(game_info):
    trigger_game_num, c2_3_info = game_info['game_number'], {'c2_3_type': game_info.get('c2_3_type'), 'c2_3_description': game_info.get('c2_3_description')}
    print(f"🎯 Normal Hibrit analiz ediyor {c2_3_info['c2_3_description']}...")
    signal_color, reason = analyze_simple_pattern(game_info['player_cards'], game_info['banker_cards'], trigger_game_num)
    if signal_color:
        next_game_num = get_next_game_number(trigger_game_num)
        await send_new_signal(next_game_num, signal_color, reason, c2_3_info)
        print(f"🚀 Normal Hibrit sinyal gönderildi: #{next_game_num} - {reason}")
    else: print(f"🚫 Normal Hibrit: Sinyal yok - {reason}")

async def super_hibrit_sistemi(game_info):
    trigger_game_num, c2_3_info = game_info['game_number'], {'c2_3_type': game_info.get('c2_3_type'), 'c2_3_description': game_info.get('c2_3_description')}
    print(f"🚀 Süper Hibrit analiz ediyor {c2_3_info['c2_3_description']}...")
    signal_color, onay_sebep = besli_onay_sistemi(game_info['player_cards'], game_info['banker_cards'], game_info['game_number'])
    if not signal_color: return print(f"🚫 5'li onay reddedildi: {onay_sebep}")
    filtre_sonuc, filtre_sebep = super_filtre_kontrol(signal_color, onay_sebep, game_info['game_number'])
    if not filtre_sonuc: return print(f"🚫 Süper filtre reddetti: {filtre_sebep}")
    risk_seviye, risk_uyarilar = super_risk_analizi()
    if risk_seviye == "🔴 YÜKSEK RİSK": return print(f"🚫 Yüksek risk: {risk_uyarilar}")
    next_game_num = get_next_game_number(trigger_game_num)
    await send_new_signal(next_game_num, signal_color, f"🚀 SÜPER HİBRİT - {onay_sebep}", c2_3_info)
    print(f"🎯 SÜPER HİBRİT sinyal gönderildi: #{next_game_num}")

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
@client.on(events.MessageEdited(chats=KANAL_KAYNAK_ID))
async def handle_source_channel_message(event):
    try:
        message = event.message
        text = message.text or ""
        cleaned_text = re.sub(r'\*\*', '', text).strip()
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        print(f"[{gmt3_time}] 📥 Mesaj: #{len(cleaned_text)} karakter")
        game_info = extract_game_info_from_message(cleaned_text)
        if game_info['game_number'] is None: return
        game_results[game_info['game_number']] = game_info
        await check_martingale_trackers()
        if not is_signal_active:
            if game_info['is_final'] and game_info.get('is_c2_3'):
                trigger_game_num, c2_3_type, c2_3_desc = game_info['game_number'], game_info['c2_3_type'], game_info['c2_3_description']
                print(f"🎯 {c2_3_desc} tespit edildi: #{trigger_game_num} - {c2_3_type}")
                if SISTEM_MODU == "normal_hibrit": await normal_hibrit_sistemi(game_info)
                elif SISTEM_MODU == "super_hibrit": await super_hibrit_sistemi(game_info)
    except Exception as e: print(f"❌ Mesaj işleme hatası: {e}")

@client.on(events.NewMessage(pattern='(?i)/basla'))
async def handle_start(event): await event.reply("🤖 Royal Baccarat Bot Aktif!")

@client.on(events.NewMessage(pattern='(?i)/durum'))
async def handle_durum(event):
    aktif_sinyal = "✅ Evet" if is_signal_active else "❌ Hayır"
    gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
    aktif_takipciler = "\n".join([f"• #{num} (Seviye {info['step']})" for num, info in martingale_trackers.items()])
    if not aktif_takipciler: aktif_takipciler = "• Aktif sinyal yok"
    durum_mesaji = f"🤖 **ROYAL BACCARAT BOT** 🤖\n\n🟢 **Durum:** Çalışıyor\n🎯 **Aktif Sinyal:** {aktif_sinyal}\n📊 **Aktif Takipçiler:**\n{aktif_takipciler}\n📈 **Trend:** {color_trend[-5:] if color_trend else 'Yok'}\n🎛️ **Mod:** {SISTEM_MODU}\n🕒 **Saat:** {gmt3_time} (GMT+3)\n📨 **Günlük Sinyal:** {daily_signal_count} (Sınırsız)\n\n⚡ **Sistem:** Hibrit Pattern + Martingale 3 Seviye"
    await event.reply(durum_mesaji)

@client.on(events.NewMessage(pattern='(?i)/mod_normal'))
async def handle_mod_normal(event):
    global SISTEM_MODU
    SISTEM_MODU = "normal_hibrit"
    await event.reply("✅ NORMAL HİBRİT modu aktif! Daha çok sinyal, normal risk.")

@client.on(events.NewMessage(pattern='(?i)/mod_super'))
async def handle_mod_super(event):
    global SISTEM_MODU
    SISTEM_MODU = "super_hibrit"
    await event.reply("🚀 SÜPER HİBRİT modu aktif! Daha az sinyal, yüksek güvenlik.")

@client.on(events.NewMessage(pattern='(?i)/mod_durum'))
async def handle_mod_status(event): await event.reply(f"🎛️ Aktif Mod: {SISTEM_MODU}")

@client.on(events.NewMessage(pattern='(?i)/temizle'))
async def handle_temizle(event):
    if event.sender_id != ADMIN_ID: return await event.reply("❌ Yetkiniz yok!")
    global color_trend, recent_games, daily_signal_count
    color_trend, recent_games, daily_signal_count = [], [], 0
    await event.reply("✅ Trend verileri temizlendi! Sinyal sayacı sıfırlandı.")

@client.on(events.NewMessage(pattern='(?i)/acil_durdur'))
async def handle_emergency_stop(event):
    global is_signal_active
    if event.sender_id != ADMIN_ID: return await event.reply("❌ Yetkiniz yok!")
    is_signal_active = False
    martingale_trackers.clear()
    await event.reply("🚨 **ACİL DURDURMA** 🚨\n✅ Tüm sinyaller durduruldu\n✅ Takipçiler temizlendi\n✅ Sistem duraklatıldı\nDevam etmek için /aktif_et komutunu kullan")

@client.on(events.NewMessage(pattern='(?i)/aktif_et'))
async def handle_activate(event):
    global is_signal_active
    if event.sender_id != ADMIN_ID: return await event.reply("❌ Yetkiniz yok!")
    is_signal_active = False
    await event.reply(f"✅ **SİSTEM AKTİF** ✅\n🟢 Yeni sinyaller için hazır\n🎛️ Mod: {SISTEM_MODU}\n📊 Bugün: {daily_signal_count} sinyal")

if __name__ == '__main__':
    print("🤖 ROYAL BACCARAT BOT BAŞLIYOR...")
    print(f"🔧 API_ID: {API_ID}")
    print(f"🎯 Kaynak Kanal: {KANAL_KAYNAK_ID}")
    print(f"📤 Hedef Kanal: {KANAL_HEDEF}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"🎛️ Varsayılan Mod: {SISTEM_MODU}")
    print(f"🕒 Saat Dilimi: GMT+3")
    print("⏳ Bağlanıyor...")
    try:
        with client: client.run_until_disconnected()
    except KeyboardInterrupt: print("\n👋 Bot durduruluyor...")
    except Exception as e: print(f"❌ Bot başlangıç hatası: {e}")
