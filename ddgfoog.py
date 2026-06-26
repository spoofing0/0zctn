#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
import argparse
import threading
import time
import json
import csv
import urllib.parse
import re
from datetime import datetime

# ANSI Renk Kodları
YEŞİL = "\033[92m"
KIRMIZI = "\033[91m"
SARI = "\033[93m"
MAVİ = "\033[94m"
BEYAZ = "\033[97m"
RESET = "\033[0m"

try:
    import requests
except ImportError:
    print(f"{SARI}[*] 'requests' modülü bulunamadı. Otomatik kuruluyor...{RESET}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests
        print(f"{YEŞİL}[+] Kurulum başarıyla tamamlandı!\n{RESET}")
    except Exception as e:
        print(f"{KIRMIZI}[-] Otomatik kurulum başarısız oldu: {e}{RESET}")
        sys.exit(1)

# ASCII Logosu (DuckDuckGo temalı)
print(YEŞİL + r"""
    ____  ____   ______   ______                  
   / __ \/ __ \ / ____/  / ____/____  ____  ____ _
  / / / / / / // / __   / /_   / __ \/ __ \/ __ `/
 / /_/ / /_/ // /_/ /  / __/  / /_/ / /_/ / /_/ / 
/_____/_____/ \____/  /_/     \____/\____/\__, /  
                                         /____/   """ + RESET)
print(f"{YEŞİL}root@bossy:~# DuckDuckGo Smart Answer CLI v2.0 (Enhanced){RESET}\n")

# ------------------------------------------------------------
# ARGÜMAN TANIMLARI
# ------------------------------------------------------------
parser = argparse.ArgumentParser(description="DuckDuckGo Smart Answer CLI", add_help=False)
parser.add_argument("-h", "--help", action="store_true", help="Yardım mesajını gösterir")
parser.add_argument("-q", "--query", required=False, help="Aranacak kelime veya kavram (örnek: 'python nedir')")
parser.add_argument("--output", required=False, default=None, help="Sonuçların kaydedileceği dosya adı")
parser.add_argument("--format", required=False, default="txt", choices=["txt", "json", "csv"],
                    help="Çıktı formatı (txt, json, csv) - Varsayılan: txt")

def print_colored_help():
    print(f"{MAVİ}KULLANIM KILAVUZU:{RESET}")
    print(f"  python duckduckgo.py -q {SARI}\"ARANACAK_KELİME\"{RESET}\n")
    sys.exit(0)

if "-h" in sys.argv or "--help" in sys.argv:
    print_colored_help()

args = parser.parse_args()

if not args.query:
    print(f"{KIRMIZI}[-] Eksik parametre! Arama yapmak için -q seçeneğini kullanın.{RESET}")
    sys.exit(1)

# ------------------------------------------------------------
# YARDIMCI FONKSİYONLAR
# ------------------------------------------------------------
def clean_query(query):
    """Sorgudan 'nedir', 'kimdir' gibi ek kelimeleri temizler."""
    # Türkçe soru kelimelerini ve gereksiz ekleri kaldır
    stop_words = ["nedir", "kimdir", "ne", "kim", "hangisi", "nasıl", "nerede", "ne zaman"]
    words = query.lower().split()
    cleaned = [w for w in words if w not in stop_words]
    return " ".join(cleaned) if cleaned else query

def get_wikipedia_summary(title):
    """Wikipedia'dan özet çeker, başarısız olursa None döner."""
    try:
        safe_title = urllib.parse.quote(title)
        url = f"https://tr.wikipedia.org/api/rest_v1/page/summary/{safe_title}"
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "title": data.get("title", title),
                "abstract": data.get("extract", ""),
                "source_url": data.get("content_urls", {}).get("desktop", {}).get("page", "")
            }
    except:
        pass
    return None

# ------------------------------------------------------------
# ANA ARAMA FONKSİYONU
# ------------------------------------------------------------
def search(query):
    """Önce DDG, sonra Wikipedia, en son RelatedTopics dener."""
    result = {
        "query": query,
        "title": "",
        "abstract": "",
        "source_url": "",
        "related_topics": []
    }
    api_used = "DuckDuckGo API"
    
    # 1. DuckDuckGo Abstract
    try:
        url_ddg = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        resp = requests.get(url_ddg, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("AbstractText"):
                result["title"] = data.get("Heading", query)
                result["abstract"] = data.get("AbstractText", "")
                result["source_url"] = data.get("AbstractURL", "")
                return result, api_used
            # Related Topics varsa onları sakla
            if data.get("RelatedTopics"):
                for item in data["RelatedTopics"][:5]:
                    if "Text" in item:
                        result["related_topics"].append(item["Text"])
    except:
        pass
    
    # 2. Fallback: Wikipedia (önce temizlenmiş sorguyla dene)
    cleaned = clean_query(query)
    for try_query in [cleaned, query]:  # önce temizlenmiş, olmazsa orijinal
        if try_query != query:
            # DDG'de zaten query ile denendi, tekrar etme
            pass
        # Wikipedia opensearch
        try:
            url_search = f"https://tr.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(try_query)}&limit=1&namespace=0&format=json"
            resp = requests.get(url_search, headers=headers, timeout=5)
            if resp.status_code == 200:
                search_data = resp.json()
                if search_data[1]:  # başlık var
                    title = search_data[1][0]
                    summary = get_wikipedia_summary(title)
                    if summary and summary["abstract"]:
                        result["title"] = summary["title"]
                        result["abstract"] = summary["abstract"]
                        result["source_url"] = summary["source_url"]
                        api_used = "Wikipedia API (Fallback)"
                        return result, api_used
        except:
            pass
    
    # 3. Hiçbir şey bulunamadıysa, eğer related_topics varsa onları göster
    if result["related_topics"]:
        api_used = "DuckDuckGo Related Topics"
        return result, api_used
    
    # 4. Tamamen boş
    return None, None

# ------------------------------------------------------------
# ANA PROGRAM
# ------------------------------------------------------------
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Animasyon
done = False
def animate():
    chars = ["|", "/", "-", "\\"]
    idx = 0
    while not done:
        sys.stdout.write(f"\r{SARI}[{chars[idx]}] Veri tabanlarında aranıyor, lütfen bekleyin...{RESET}")
        sys.stdout.flush()
        idx = (idx + 1) % len(chars)
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * 70 + "\r")
    sys.stdout.flush()

t = threading.Thread(target=animate)
t.start()

result, api_used = search(args.query)

done = True
t.join()

if result is None:
    print(f"\n{KIRMIZI}[-] Üzgünüm, aradığınız kavram hiçbir veri tabanında bulunamadı.{RESET}")
    print(f"{SARI}[!] İpucu: Daha basit bir sorgu deneyin (örnek: 'python' veya 'istanbul').{RESET}")
    sys.exit(1)

# ------------------------------------------------------------
# SONUÇLARI EKRANA YAZ
# ------------------------------------------------------------
print(f"\n{MAVİ}=== ARAMA SONUCU ({api_used}): {BEYAZ}{result['title']}{MAVİ} ==={RESET}\n")

if result["abstract"]:
    print(f"{YEŞİL}[Özet Bilgi]:{RESET}")
    print(f"{BEYAZ}{result['abstract']}{RESET}\n")
    if result["source_url"]:
        print(f"{SARI}[Kaynak Bağlantısı]:{RESET} {MAVİ}{result['source_url']}{RESET}\n")
else:
    if result["related_topics"]:
        print(f"{SARI}[!] Doğrudan net bir tanım bulunamadı ancak ilgili konular listelendi.{RESET}")
        print(f"\n{YEŞİL}[İlgili Olabilecek Konular / Alt Başlıklar]:{RESET}")
        for topic in result["related_topics"]:
            print(f" {BEYAZ}- {topic}{RESET}")
        print()

# ------------------------------------------------------------
# DOSYAYA KAYDET
# ------------------------------------------------------------
if args.output:
    out_fmt = args.format.lower()
    file_name = args.output
    if not file_name.endswith(f".{out_fmt}"):
        file_name = f"{file_name}.{out_fmt}"
    
    su_an_human = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    
    try:
        if out_fmt == "txt":
            with open(file_name, 'w', encoding='utf-8') as fp:
                fp.write(f"Sorgu Tarihi: {su_an_human}\nAranan: {result['query']}\nBaşlık: {result['title']}\n")
                fp.write(f"--------------------------------------------------\nÖzet:\n{result['abstract']}\n\nKaynak: {result['source_url']}\n")
        elif out_fmt == "json":
            with open(file_name, 'w', encoding='utf-8') as fp:
                json.dump({
                    "metadata": {"tarih": su_an_human, "api": api_used},
                    "result": result
                }, fp, ensure_ascii=False, indent=4)
        elif out_fmt == "csv":
            with open(file_name, 'w', newline='', encoding='utf-8') as fp:
                writer = csv.writer(fp)
                writer.writerow(["Sorgu", "Başlık", "Özet", "Kaynak"])
                writer.writerow([result["query"], result["title"], result["abstract"], result["source_url"]])
        print(f"{YEŞİL}[+] Sonuçlar başarıyla '{file_name}' dosyasına kaydedildi!{RESET}")
    except Exception as e:
        print(f"{KIRMIZI}[-] Dosya yazma hatası: {e}{RESET}")
