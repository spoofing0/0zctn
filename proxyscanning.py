#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
import argparse
import threading
import time
import json
import csv
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

# ASCII Logosu
print(YEŞİL + r"""
   ___                    ____                    _         
  / _ \_______ __ ____ __/ __/______ ____   ___  (_)__  ___ _
 / ___/ __/ _ \\ \ / // /\ \/ __/ _ `/ _ \/ _ \/ / _ \/ _ `/
/_/  /_/  \___/_\_\\_, /___/\__/\_,_/_//_/_//_/_//_/\_, / 
                  /___/                               /___/  """ + RESET)
print(f"{YEŞİL}root@bossy:~# ProxyScrape v4.1 - Optimized Downloader{RESET}\n")

# ------------------------------------------------------------
# ARGÜMAN TANIMLARI
# ------------------------------------------------------------
parser = argparse.ArgumentParser(description="ProxyScrape v4.1 Advanced CLI Downloader", add_help=False)
parser.add_argument("-h", "--help", action="store_true", help="Yardım mesajını gösterir")
parser.add_argument("--type", required=False, help="Proxy tipi veya tipleri (örn: http veya http,socks4,socks5)")
parser.add_argument("--country", required=False, help="Ülke kodu veya kodları (örn: tr veya tr,us,de,all)")
parser.add_argument("--timeout", required=False, help="Timeout (ms cinsinden, örn: 10000)")
parser.add_argument("--anonymity", required=False, default="elite,anonymous,transparent",
                    help="Anonimlik seviyesi (elite,anonymous,transparent) - Varsayılan: hepsi")
parser.add_argument("--output", required=False, default=None, help="Dosya adı")
parser.add_argument("--format", required=False, default="txt", choices=["txt", "json", "csv"],
                    help="Çıktı formatı (txt, json, csv) - Varsayılan: txt")

def print_colored_help():
    print(f"{MAVİ}KULLANIM KILAVUZU:{RESET}")
    print(f"  python proxyscanning.py --type {SARI}TYPE{RESET} --country {SARI}COUNTRY{RESET} --timeout {SARI}TIMEOUT{RESET} [{BEYAZ}--anonymity ANON{RESET}] [{BEYAZ}--output OUTPUT{RESET}] [{BEYAZ}--format {{txt,json,csv}}{RESET}]\n")
    
    print(f"{MAVİ}SEÇENEKLER (OPTIONS):{RESET}")
    print(f"  {YEŞİL}-h, --help{RESET}             {BEYAZ}Bu renkli yardım mesajını gösterir.{RESET}")
    print(f"  {YEŞİL}--type TYPE{RESET}            {BEYAZ}Proxy tipi veya tipleri (örn: http veya http,socks4,socks5){RESET}")
    print(f"  {YEŞİL}--country COUNTRY{RESET}      {BEYAZ}Ülke kodu veya kodları (örn: tr veya tr,us,de,all){RESET}")
    print(f"  {YEŞİL}--timeout TIMEOUT{RESET}      {BEYAZ}Timeout (ms cinsinden, örn: 10000){RESET}")
    print(f"  {YEŞİL}--anonymity ANON{RESET}       {BEYAZ}Anonimlik seviyesi (elite,anonymous,transparent){RESET}")
    print(f"  {YEŞİL}--output OUTPUT{RESET}        {BEYAZ}Dosya adı (Boş bırakılırsa otomatik isimlendirilir){RESET}")
    print(f"  {YEŞİL}--format FORMAT{RESET}        {BEYAZ}Çıktı formatı (txt, json, csv) - Varsayılan: txt{RESET}\n")
    sys.exit(0)

if "-h" in sys.argv or "--help" in sys.argv:
    print_colored_help()

args = parser.parse_args()

if not all([args.type, args.country, args.timeout]):
    print(f"{KIRMIZI}[-] Eksik parametre girdiniz! Yardım için 'python proxyscanning.py -h' yazın.{RESET}")
    sys.exit(1)

# ------------------------------------------------------------
# PARAMETRE İŞLEME
# ------------------------------------------------------------
proxy_types = [t.strip().lower() for t in args.type.split(",")]
countries_raw = [c.strip().lower() for c in args.country.split(",")]
timeout_val = args.timeout
output_format = args.format.lower()
anonymity_list = [a.strip().lower() for a in args.anonymity.split(",")]

ALL_COUNTRIES = [
    "af","al","dz","ad","ao","ar","am","au","at","az","bd","by","be","bj","bm","bt","bo","bw","bg","bf","bi",
    "kh","cm","ca","td","cl","cn","co","cg","cr","hr","cy","cz","dk","do","ec","eg","sv","gq","ee","sz","et",
    "fj","fi","fr","gm","ge","de","gh","gi","gr","gu","gt","gn","ht","hn","hk","hu","in","id","ir","iq","ie",
    "il","it","jm","jp","jo","kz","ke","kr","kg","lv","lb","ls","lt","mg","mw","my","mv","ml","mt","mu","mx",
    "md","mn","me","ma","mz","mm","na","np","nl","nz","ni","ng","mk","no","pk","ps","pa","py","pe","ph","pl",
    "pt","pr","qa","ro","rw","kn","sa","sn","rs","sc","sl","sg","sk","si","so","za","es","lk","sd","se","ch",
    "sy","tw","tj","tz","th","tl","tg","tn","tr","ug","ua","ae","gb","us","uy","uz","ve","vn","vi","ye","zw"
]

if "all" in countries_raw:
    countries = ALL_COUNTRIES
else:
    countries = [c for c in countries_raw if c in ALL_COUNTRIES]

if not countries:
    print(f"{KIRMIZI}[-] Hata: Geçerli bir ISO ülke kodu girmediniz veya girdiğiniz kod desteklenmiyor.{RESET}")
    sys.exit(1)

# ------------------------------------------------------------
# ANİMASYON THREAD'İ
# ------------------------------------------------------------
done = False

def animate():
    chars = ["|", "/", "-", "\\"]
    idx = 0
    while not done:
        sys.stdout.write(f"\r{SARI}[{chars[idx]}] Proxiler indiriliyor ve işleniyor, lütfen bekleyin...{RESET}")
        sys.stdout.flush()
        idx = (idx + 1) % len(chars)
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * 70 + "\r")
    sys.stdout.flush()

print(f"{BEYAZ}[*] Ayarlar uygulandı, ProxyScrape v4 API'ye istek gönderiliyor...{RESET}")

# ------------------------------------------------------------
# URL OLUŞTURMA
# ------------------------------------------------------------
protocol_str = ",".join(proxy_types)
country_str = ",".join(countries)
anonymity_str = ",".join(anonymity_list)

url = (f"https://api.proxyscrape.com/v4/free-proxy-list/get?"
       f"request=display_proxies&proxy_format=ipport&format=text"
       f"&protocol={protocol_str}&anonymity={anonymity_str}&country={country_str}&timeout={timeout_val}")

# ------------------------------------------------------------
# İSTEK ATMA VE VERİ İŞLEME
# ------------------------------------------------------------
t = threading.Thread(target=animate)
t.start()

unique_proxies = set()
structured_proxies = []
error_occurred = False

try:
    response = requests.get(url, timeout=(int(timeout_val)/1000) + 5)
    
    if response.status_code == 200:
        lines = response.text.strip().splitlines()
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and ":" in line:
                if line not in unique_proxies:
                    unique_proxies.add(line)
                    ip, port = line.split(":", 1)
                    
                    # [DÜZELTME] Eğer birden fazla ülke seçildiyse veri tabanını şişirmemek için 'multiple' yaz,
                    # tek bir ülke seçildiyse o ülkenin kodunu yaz.
                    single_country_display = countries[0] if len(countries) == 1 else "multiple"
                    
                    structured_proxies.append({
                        "ip": ip,
                        "port": port,
                        "type": protocol_str,
                        "country": single_country_display
                    })
    else:
        error_occurred = True
        print(f"\n{KIRMIZI}[-] API'den hata kodu alındı: {response.status_code}{RESET}")

except requests.exceptions.Timeout:
    error_occurred = True
    print(f"\n{KIRMIZI}[-] Bağlantı zaman aşımına uğradı. Lütfen timeout değerini artırın.{RESET}")
except requests.exceptions.ConnectionError:
    error_occurred = True
    print(f"\n{KIRMIZI}[-] API'ye bağlanılamadı. İnternet bağlantınızı kontrol edin.{RESET}")
except Exception as e:
    error_occurred = True
    print(f"\n{KIRMIZI}[-] Beklenmeyen hata: {e}{RESET}")

finally:
    done = True
    t.join()

if error_occurred:
    sys.exit(1)

# ------------------------------------------------------------
# SONUÇLARI KAYDET
# ------------------------------------------------------------
proxy_count = len(unique_proxies)
if proxy_count == 0:
    print(f"{SARI}[!] Seçilen filtrelere uygun hiçbir proxy bulunamadı.{RESET}")
    sys.exit(0)

su_an_ts = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
su_an_human = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

if args.output is None:
    short_types = "_".join(proxy_types)[:20]
    short_countries = "_".join(countries)[:20] if len(countries) < 5 else "multi"
    file_name = f"proxies_{short_types}_{short_countries}_{su_an_ts}.{output_format}"
else:
    file_name = args.output
    if not file_name.endswith(f".{output_format}"):
        file_name = f"{file_name}.{output_format}"

if output_format == "txt":
    with open(file_name, 'w', encoding='utf-8') as fp:
        fp.write(f"# Proxy Listesi Güncelleme Tarihi: {su_an_human}\n")
        fp.write(f"# Toplam Benzersiz Proxy Sayısı: {proxy_count}\n")
        fp.write(f"# Filtreler: Tipler={','.join(proxy_types)} | Ülkeler={country_str}\n")
        fp.write(f"# Anonimlik: {','.join(anonymity_list)}\n")
        fp.write("# --------------------------------------------------\n")
        for p in sorted(list(unique_proxies)):
            fp.write(f"{p}\n")

elif output_format == "json":
    output_data = {
        "metadata": {
            "güncelleme_tarihi": su_an_human,
            "toplam_proxy": proxy_count,
            "filtreler": {
                "tipler": proxy_types,
                "ülkeler": country_str,  # Tüm sorgulanan ülkeler toplu halde metadata içinde güvenle kalıyor
                "anonimlik": anonymity_list
            }
        },
        "proxies": structured_proxies
    }
    with open(file_name, 'w', encoding='utf-8') as fp:
        json.dump(output_data, fp, ensure_ascii=False, indent=4)

elif output_format == "csv":
    with open(file_name, 'w', newline='', encoding='utf-8') as fp:
        writer = csv.writer(fp)
        writer.writerow(["IP", "Port", "Type", "Country"])
        for p in structured_proxies:
            writer.writerow([p["ip"], p["port"], p["type"], p["country"]])

print(f"{YEŞİL}[+] Başarılı! {BEYAZ}[{su_an_human}]{RESET}")
print(f"{YEŞİL}[+] Toplam {BEYAZ}{proxy_count}{RESET}{YEŞİL} adet benzersiz proxy '{file_name}' dosyasına [{output_format.upper()}] formatında kaydedildi.{RESET}")
