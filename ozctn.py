# PERFORMANS İZLEME YAPISI - YENİ EKLENECEK
pattern_stats = {
    '🎯 GÜÇLÜ EL': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '🏆 DOĞAL KAZANÇ': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '📊 5+ KART': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '🚨 3x TEKRAR': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '📈 STANDART SİNYAL': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '✅ 5-Lİ ONAY': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '🚀 SÜPER HİBRİT': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0},
    '🎯 KLASİK #C2_3': {'total': 0, 'wins': 0, 'losses': 0, 'profit': 0, 'avg_steps': 0}
}

# PERFORMANS GÜNCELLEME FONKSİYONU - YENİ EKLENECEK
def update_pattern_stats(pattern_type, result_type, steps=0):
    """Pattern istatistiklerini günceller"""
    if pattern_type in pattern_stats:
        stats = pattern_stats[pattern_type]
        stats['total'] += 1
        
        if result_type == 'win':
            stats['wins'] += 1
            stats['profit'] += 1
            # Ortalama adım sayısını güncelle
            if stats['wins'] > 0:
                stats['avg_steps'] = ((stats['avg_steps'] * (stats['wins'] - 1)) + steps) / stats['wins']
        else:
            stats['losses'] += 1
            stats['profit'] -= (2**steps - 1)  # Martingale kaybı

# UPDATE_PERFORMANCE_STATS FONKSİYONUNA EKLEME YAP
def update_performance_stats(result_type, steps=0, c2_3_type=None, pattern_type=None):
    """Performans istatistiklerini günceller"""
    today = datetime.now(GMT3).strftime('%Y-%m-%d')
    week = datetime.now(GMT3).strftime('%Y-%W')
    
    performance_stats['total_signals'] += 1
    performance_stats['signal_history'].append({
        'timestamp': datetime.now(GMT3),
        'result': result_type,
        'steps': steps,
        'c2_3_type': c2_3_type,
        'pattern_type': pattern_type
    })
    
    if result_type == 'win':
        performance_stats['win_signals'] += 1
        performance_stats['current_streak'] += 1
        performance_stats['max_streak'] = max(performance_stats['max_streak'], performance_stats['current_streak'])
        performance_stats['total_profit'] += 1
        performance_stats['daily_stats'][today]['wins'] += 1
        performance_stats['daily_stats'][today]['profit'] += 1
        performance_stats['weekly_stats'][week]['wins'] += 1
        performance_stats['weekly_stats'][week]['profit'] += 1
    else:
        performance_stats['loss_signals'] += 1
        performance_stats['current_streak'] = 0
        performance_stats['total_profit'] -= (2**steps - 1)
        performance_stats['daily_stats'][today]['losses'] += 1
        performance_stats['daily_stats'][today]['profit'] -= (2**steps - 1)
        performance_stats['weekly_stats'][week]['losses'] += 1
        performance_stats['weekly_stats'][week]['profit'] -= (2**steps - 1)
    
    performance_stats['daily_stats'][today]['signals'] += 1
    performance_stats['weekly_stats'][week]['signals'] += 1
    
    # C2-3 istatistiklerini güncelle
    if c2_3_type:
        update_c2_3_stats(c2_3_type, result_type, steps)
    
    # Pattern istatistiklerini güncelle
    if pattern_type:
        update_pattern_stats(pattern_type, result_type, steps)

# PATTERN PERFORMANS RAPORU FONKSİYONU - YENİ EKLENECEK
def get_pattern_performance():
    """Pattern performans analizini döndürür"""
    performance_text = "🎯 **PATTERN PERFORMANS TABLOSU** 🎯\n\n"
    
    # Performansa göre sırala (kazanç oranına göre)
    sorted_patterns = sorted(
        pattern_stats.items(),
        key=lambda x: (x[1]['wins'] / x[1]['total']) if x[1]['total'] > 0 else 0,
        reverse=True
    )
    
    for pattern_type, stats in sorted_patterns:
        if stats['total'] > 0:
            win_rate = (stats['wins'] / stats['total']) * 100
            performance_text += f"{pattern_type}\n"
            performance_text += f"   📊 Toplam: {stats['total']} | ⭕: {stats['wins']} | ❌: {stats['losses']}\n"
            performance_text += f"   🎯 Başarı: %{win_rate:.1f} | 💰 Kâr: {stats['profit']} birim\n"
            performance_text += f"   ⚡ Ort. Adım: {stats['avg_steps']:.1f}\n\n"
        else:
            performance_text += f"{pattern_type}\n"
            performance_text += f"   📊 Henüz veri yok\n\n"
    
    return performance_text

# UPDATE_SIGNAL_MESSAGE FONKSİYONUNU GÜNCELLE
async def update_signal_message(tracker_info, result_type, current_step=None, result_details=None):
    try:
        signal_game_num, signal_suit = tracker_info['sent_game_number'], tracker_info['signal_suit']
        suit_display, message_obj, reason = get_suit_display_name(signal_suit), tracker_info['message_obj'], tracker_info.get('reason', '')
        c2_3_type = tracker_info.get('c2_3_type', '#C2_3')
        
        # Pattern tipini belirle
        pattern_type = None
        for pattern in pattern_stats.keys():
            if pattern in reason:
                pattern_type = pattern
                break
        
        duration = datetime.now(GMT3) - tracker_info['start_time']
        duration_str = f"{duration.seconds // 60}d {duration.seconds % 60}s"
        gmt3_time = datetime.now(GMT3).strftime('%H:%M:%S')
        
        if result_details: 
            tracker_info['results'].append(result_details)
        
        if result_type == 'win':
            new_text = f"✅ **KAZANÇ** ✅\n#N{signal_game_num} - {suit_display}\n📊 Sebep: {reason}\n🎯 Seviye: {current_step if current_step else 0}. Seviye\n⏱️ Süre: {duration_str}\n🕒 Bitiş: {gmt3_time}\n🏆 **SONUÇ: KAZANDINIZ!**"
            # İstatistik güncelleme - pattern_type parametresi eklendi
            update_performance_stats('win', current_step if current_step else 0, c2_3_type, pattern_type)
        elif result_type == 'loss':
            new_text = f"❌ **KAYIP** ❌\n#N{signal_game_num} - {suit_display}\n📊 Sebep: {reason}\n🎯 Seviye: {current_step if current_step else MAX_MARTINGALE_STEPS}. Seviye\n⏱️ Süre: {duration_str}\n🕒 Bitiş: {gmt3_time}\n💔 **SONUÇ: KAYBETTİNİZ**"
            # İstatistik güncelleme - pattern_type parametresi eklendi
            update_performance_stats('loss', current_step if current_step else MAX_MARTINGALE_STEPS, c2_3_type, pattern_type)
        elif result_type == 'progress':
            step_details = f"{current_step}. seviye → #{tracker_info['expected_game_number_for_check']}"
            results_history = "\n".join([f"• {r}" for r in tracker_info['results']]) if tracker_info['results'] else "• İlk deneme"
            new_text = f"🔄 **MARTINGALE İLERLİYOR** 🔄\n#N{signal_game_num} - {suit_display}\n📊 Sebep: {reason}\n🎯 Adım: {step_details}\n⏱️ Süre: {duration_str}\n🕒 Son Güncelleme: {gmt3_time}\n📈 Geçmiş:\n{results_history}\n🎲 **SONRAKİ: #{tracker_info['expected_game_number_for_check']}**"
        elif result_type == 'step_result':
            new_text = f"📊 **ADIM SONUCU** 📊\n#N{signal_game_num} - {suit_display}\n🎯 Adım: {current_step}. seviye\n📋 Sonuç: {result_details}\n⏱️ Süre: {duration_str}\n🕒 Zaman: {gmt3_time}\n🔄 **DEVAM EDİYOR...**"
        
        await message_obj.edit(new_text)
        print(f"✏️ Sinyal güncellendi: #{signal_game_num} - {result_type}")
    except MessageNotModifiedError: 
        pass
    except Exception as e: 
        print(f"❌ Mesaj düzenleme hatası: {e}")

# YENİ KOMUT EKLE - PATTERN PERFORMANS
@client.on(events.NewMessage(pattern='(?i)/pattern'))
async def handle_pattern(event):
    """Pattern performans tablosu"""
    analysis = get_pattern_performance()
    await event.reply(analysis)

# GENERATE_PERFORMANCE_REPORT FONKSİYONUNU GÜNCELLE
def generate_performance_report():
    """Detaylı performans raporu oluşturur"""
    win_rate = calculate_win_rate()
    daily = get_daily_stats()
    weekly = get_weekly_stats()
    
    # En iyi ve en kötü performansları al
    best_type, best_rate = get_best_performing_type()
    worst_type, worst_rate = get_worst_performing_type()
    
    best_type_name = performance_stats['c2_3_performance'][best_type]['name'] if best_type else "Yok"
    worst_type_name = performance_stats['c2_3_performance'][worst_type]['name'] if worst_type else "Yok"
    
    # Pattern performansını al
    pattern_analysis = get_pattern_performance()
    
    report = f"""🎯 **DETAYLI PERFORMANS RAPORU** 🎯

📊 **GENEL İSTATİSTİKLER:**
• Toplam Sinyal: {performance_stats['total_signals']}
• Kazanç: {performance_stats['win_signals']} | Kayıp: {performance_stats['loss_signals']}
• Kazanç Oranı: %{win_rate:.1f}
• Toplam Kâr: {performance_stats['total_profit']} birim
• Mevcut Seri: {performance_stats['current_streak']} kazanç
• En Uzun Seri: {performance_stats['max_streak']} kazanç

🏆 **PERFORMANS ANALİZİ:**
• En İyi Tip: {best_type_name} (%{best_rate:.1f})
• En Kötü Tip: {worst_type_name} (%{worst_rate:.1f})

{pattern_analysis}
"""
    return report
