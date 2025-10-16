from telethon import TelegramClient, events
import re
import asyncio
from datetime import datetime, timedelta

# API BİLGİLERİ
API_ID = 29581698
API_HASH = '0caabd4263f1d4e5f753659a787c2e7d'
BOT_TOKEN = 'bot_token_buraya'  # BURAYA BOT TOKEN'İNİ YAZ

KANAL_KAYNAK_ID = -1001626824569
KANAL_HEDEF = "@royalbaccfree"

client = TelegramClient('onceden_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

class OncedenStrateji:
    def __init__(self):
        self.son_tahmin = None
        self.bekleyen_oyunlar = {}
        
    def sonraki_oyun_tahmini(self, mevcut_oyun_no):
        """Bir sonraki oyun için tahmin yap"""
        sonraki_oyun_no = mevcut_oyun_no + 1
        son_rakam = sonraki_oyun_no % 10
        
        # Basit ve etkili tahmin stratejisi
        tahminler = {
            0: {'sinyal': '♣️', 'hedef': 2},
            1: {'sinyal': '♥️', 'hedef': 3},
            2: {'sinyal': '♦️', 'hedef': 4},
            3: {'sinyal': '♣️', 'hedef': 5},
            4: {'sinyal': '♠️', 'hedef': 6},
            5: {'sinyal': '♦️', 'hedef': 7},
            6: {'sinyal': '♥️', 'hedef': 8},
            7: {'sinyal': '♠️', 'hedef': 9},
            8: {'sinyal': '♦️', 'hedef': 0},
            9: {'sinyal': '♦️', 'hedef': 1}
        }
        
        return tahminler.get(son_rakam, {'sinyal': '♥️', 'hedef': 3})

# Global değişkenler
strateji = OncedenStrateji()
son_islenen_oyun = None

async def hizli_mesaj_gonder(chat, text):
    """Hızlı mesaj gönderme"""
    try:
        return await client.send_message(chat, text)
    except:
        return None

async def hizli_mesaj_duzenle(chat, message_id, text):
    """Hızlı mesaj düzenleme"""
    try:
        await client.edit_message(chat, message_id, text)
        return True
    except:
        return False

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
async def onceden_sinyal(event):
    global son_islenen_oyun
    
    try:
        msg = event.message
        if not msg.text:
            return

        print(f"📥 Gelen mesaj: {msg.text[:100]}...")

        # Oyun sonuç mesajını ara
        if '❌' not in msg.text and '✅' not in msg.text:
            return

        # Oyun kodu ara
        match = re.search(r'#N(\d+)', msg.text)
        if not match:
            return

        oyun_kodu = match.group()
        oyun_numarasi = int(match.group(1))
        
        # Aynı oyunu tekrar işleme
        if oyun_kodu == son_islenen_oyun:
            return
            
        son_islenen_oyun = oyun_kodu
        print(f"🎯 Oyun sonuç bulundu: {oyun_kodu}")

        # BİR SONRAKİ OYUN İÇİN TAHMİN YAP
        sonraki_tahmin = strateji.sonraki_oyun_tahmini(oyun_numarasi)
        sonraki_oyun_no = oyun_numarasi + 1
        
        # Sonuç durumunu kontrol et
        if '✅' in msg.text:
            # Kazanç durumu - emoji ve adımı al
            kazanc_emoji = "✅"
            adim_match = re.search(r'(\d+)️⃣', msg.text)
            adim = adim_match.group(1) if adim_match else "0"
            durum = f"{kazanc_emoji} {adim}️⃣"
        else:
            # Kayıp durumu
            durum = "❌"

        # ÖNCEKİ OYUN SONUCU + SONRAKİ OYUN TAHMİNİ
        mesaj = (
            f"{oyun_kodu} - Oyuncu (kart) | {durum}\n"
            f"#N{sonraki_oyun_no} - {sonraki_tahmin['sinyal']} | {sonraki_tahmin['hedef']}D"
        )

        # MESAJI GÖNDER
        gonderilen = await hizli_mesaj_gonder(KANAL_HEDEF, mesaj)
        
        if gonderilen:
            strateji.son_tahmin = {
                'oyun_no': sonraki_oyun_no,
                'sinyal': sonraki_tahmin['sinyal'],
                'hedef': sonraki_tahmin['hedef'],
                'mesaj_id': gonderilen.id,
                'timestamp': datetime.now()
            }
            print(f"✅ Önceden sinyal gönderildi: #N{sonraki_oyun_no} - {sonraki_tahmin['sinyal']}")

    except Exception as e:
        print(f"❌ Hata: {e}")

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
async def gercek_sonuc_kontrol(event):
    """Gerçek oyun sonucu geldiğinde tahmini güncelle"""
    try:
        msg = event.message
        if not msg.text:
            return

        # Oyun başlangıç mesajını ara (banker kartları)
        if '▶️' not in msg.text:
            return

        match = re.search(r'#N(\d+)', msg.text)
        if not match:
            return

        oyun_kodu = match.group()
        oyun_numarasi = int(match.group(1))

        # Eğer bu oyun için önceden tahmin yapıldıysa
        if (strateji.son_tahmin and 
            strateji.son_tahmin['oyun_no'] == oyun_numarasi):
            
            tahmin = strateji.son_tahmin
            print(f"🔍 Tahmin kontrolü: #{oyun_numarasi} - Tahmin: {tahmin['sinyal']}")

    except Exception as e:
        print(f"❌ Sonuç kontrol hatası: {e}")

@client.on(events.NewMessage(chats=KANAL_KAYNAK_ID))
async def sonuc_dogrulama(event):
    """Oyuncu kartları geldiğinde tahmini doğrula"""
    try:
        msg = event.message
        if not msg.text:
            return

        # Oyuncu kartlarını içeren mesaj
        oyuncu_kartlar = re.findall(r'[AKQJ10-9][♠️♥️♦️♣️]', msg.text)
        if not oyuncu_kartlar:
            return

        match = re.search(r'#N(\d+)', msg.text)
        if not match:
            return

        oyun_numarasi = int(match.group(1))

        # Eğer bu oyun için tahmin varsa
        if (strateji.son_tahmin and 
            strateji.son_tahmin['oyun_no'] == oyun_numarasi):
            
            tahmin = strateji.son_tahmin
            sinyal = tahmin['sinyal']
            
            # Tahmin doğru mu?
            if any(sinyal in kart for kart in oyuncu_kartlar):
                durum = "✅ 0️⃣"  # İlk adımda kazanç
            else:
                durum = "❌"
            
            # Mesajı güncelle
            guncel_mesaj = (
                f"#N{oyun_numarasi} - Oyuncu (kart) | {durum}\n"
                f"#N{oyun_numarasi + 1} - {strateji.sonraki_oyun_tahmini(oyun_numarasi)['sinyal']} | {strateji.sonraki_oyun_tahmini(oyun_numarasi)['hedef']}D"
            )
            
            await hizli_mesaj_duzenle(KANAL_HEDEF, tahmin['mesaj_id'], guncel_mesaj)
            print(f"📊 Sonuç doğrulandı: #{oyun_numarasi} - {durum}")

    except Exception as e:
        print(f"❌ Doğrulama hatası: {e}")

async def temizlik():
    """Eski tahminleri temizle"""
    while True:
        try:
            simdi = datetime.now()
            if (strateji.son_tahmin and 
                simdi - strateji.son_tahmin['timestamp'] > timedelta(minutes=10)):
                strateji.son_tahmin = None
                print("🧹 Eski tahmin temizlendi")
                
        except Exception as e:
            print(f"❌ Temizlik hatası: {e}")
        
        await asyncio.sleep(300)

@client.on(events.NewMessage(chats=KANAL_HEDEF))
async def komutlar(event):
    msg = event.message.message.lower().strip()

    if msg == '/baslat':
        await event.respond(
            "🤖 **ÖNCEDEN TAHMİN BOTU**\n\n"
            "🎯 **Sistem:** Aktif\n"
            "📊 **Mod:** Sonraki Oyun Tahmini\n"
            "⏱️ **Son Tahmin:** " + 
            (f"#N{strateji.son_tahmin['oyun_no']}" if strateji.son_tahmin else "Yok")
        )

    elif msg == '/durum':
        aktif = "Var" if strateji.son_tahmin else "Yok"
        await event.respond(
            f"📊 **SİSTEM DURUMU**\n\n"
            f"🟢 **Aktif Tahmin:** {aktif}\n"
            f"⏱️ **Saat:** {datetime.now().strftime('%H:%M:%S')}"
        )

    elif msg == '/sonraki':
        if strateji.son_tahmin:
            tahmin = strateji.son_tahmin
            await event.respond(
                f"🎯 **SONRAKİ OYUN TAHMİNİ**\n\n"
                f"#N{tahmin['oyun_no']} - {tahmin['sinyal']} | {tahmin['hedef']}D\n"
                f"⏰ {tahmin['timestamp'].strftime('%H:%M:%S')}"
            )
        else:
            await event.respond("❌ Henüz tahmin yapılmadı.")

    elif msg == '/yardim':
        yardim = (
            "🤖 **ÖNCEDEN TAHMİN BOTU**\n\n"
            "⚡ **/baslat** - Bot durumu\n"
            "📊 **/durum** - Sistem durumu\n"
            "🎯 **/sonraki** - Son tahmini göster\n"
            "📚 **/yardim** - Bu menü\n\n"
            "🎯 **ÇALIŞMA MANTIĞI:**\n"
            "• Önceki oyun sonucunu alır\n"
            "• Sonraki oyun için tahmin yapar\n"
            "• Tahmini 2 dakika önceden verir\n"
            "• Format: #NXXX - Sinyal | XD"
        )
        await event.respond(yardim)

async def main():
    # Temizlik görevini başlat
    asyncio.create_task(temizlik())
    
    print("🎯 ÖNCEDEN TAHMİN BOTU BAŞLATILDI!")
    print(f"📡 Kaynak: {KANAL_KAYNAK_ID}")
    print(f"🎯 Hedef: {KANAL_HEDEF}")
    print("⚡ Mod: Sonraki Oyun Tahmini")
    print("⏱️ " + datetime.now().strftime('%H:%M:%S'))
    print("🤖 Bot önceki oyun sonuçlarını bekliyor...")

if __name__ == '__main__':
    try:
        client.loop.run_until_complete(main())
        client.run_until_disconnected()
    except Exception as e:
        print(f"🔥 BAŞLATMA HATASI: {e}")
