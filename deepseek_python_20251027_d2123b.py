#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime

class GercekCornerStatsAnaliz:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
        })
    
    def get_corner_stats_data(self, url):
        """Corner-stats.com'dan gerçek verileri çek"""
        try:
            print("🌐 Corner-stats.com'dan veriler çekiliyor...")
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                return {"error": f"Sayfa yüklenemedi: {response.status_code}"}
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Sayfa başlığını al
            title = soup.find('title')
            page_title = title.text.strip() if title else "Başlık bulunamadı"
            
            # Takım isimlerini çek
            teams = self.extract_teams(soup)
            if not teams:
                return {"error": "Takım isimleri bulunamadı"}
            
            # İstatistikleri çek
            stats = self.extract_statistics(soup)
            
            # Head-to-head verileri
            h2h = self.extract_head_to_head(soup)
            
            # Son maçlar
            recent_matches = self.extract_recent_matches(soup)
            
            return {
                "success": True,
                "page_title": page_title,
                "teams": teams,
                "statistics": stats,
                "head_to_head": h2h,
                "recent_matches": recent_matches,
                "match_date": self.extract_match_date(soup)
            }
            
        except Exception as e:
            return {"error": f"Veri çekme hatası: {str(e)}"}
    
    def extract_teams(self, soup):
        """Takım isimlerini çek"""
        teams = {}
        
        # Farklı selector denemeleri
        selectors = [
            'h1',
            '.match-title',
            '.teams-names',
            '.team-home',
            '.team-away'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text().strip()
                if 'vs' in text or ' - ' in text:
                    # Takım isimlerini ayır
                    if 'vs' in text:
                        parts = text.split('vs')
                    elif ' - ' in text:
                        parts = text.split(' - ')
                    else:
                        continue
                    
                    if len(parts) >= 2:
                        teams['home'] = parts[0].strip()
                        teams['away'] = parts[1].strip()
                        return teams
        
        # Alternatif yöntem: sayfa başlığından çıkar
        title = soup.find('title')
        if title:
            title_text = title.get_text()
            if 'vs' in title_text:
                parts = title_text.split('vs')
                if len(parts) >= 2:
                    teams['home'] = parts[0].strip()
                    teams['away'] = parts[1].split('-')[0].strip()
                    return teams
        
        return teams
    
    def extract_statistics(self, soup):
        """İstatistikleri çek"""
        stats = {}
        
        # İstatistik tablolarını ara
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    stat_name = cells[0].get_text().strip()
                    home_value = cells[1].get_text().strip()
                    away_value = cells[2].get_text().strip()
                    
                    if any(keyword in stat_name.lower() for keyword in ['şut', 'gol', 'korner', 'kart', 'top', 'faul', 'ofsayt']):
                        stats[stat_name] = {
                            'home': home_value,
                            'away': away_value
                        }
        
        # Eğer istatistik bulamazsak, sayfada farklı bölümleri ara
        if not stats:
            stats_elements = soup.find_all(['div', 'span'], class_=re.compile(r'stat|data', re.IGNORECASE))
            for elem in stats_elements:
                text = elem.get_text().strip()
                if any(keyword in text.lower() for keyword in ['şut', 'gol', 'korner']):
                    stats[text] = {"home": "?", "away": "?"}
        
        return stats
    
    def extract_head_to_head(self, soup):
        """Head-to-head verilerini çek"""
        h2h = {}
        
        # H2H bölümünü ara
        h2h_keywords = ['head-to-head', 'h2h', 'karşılaşma', 'son maçlar']
        
        for keyword in h2h_keywords:
            elements = soup.find_all(string=re.compile(keyword, re.IGNORECASE))
            for elem in elements:
                parent = elem.parent
                if parent:
                    # H2H tablosunu veya listesini bulmaya çalış
                    next_elements = parent.find_next_siblings()
                    for next_elem in next_elements[:3]:
                        text = next_elem.get_text().strip()
                        if len(text) > 50:
                            h2h[keyword] = text[:500]
                            break
        
        return h2h
    
    def extract_recent_matches(self, soup):
        """Son maçları çek"""
        recent = {}
        
        # Son maçlar bölümünü ara
        recent_keywords = ['son maçlar', 'recent', 'form', 'performans']
        
        for keyword in recent_keywords:
            elements = soup.find_all(string=re.compile(keyword, re.IGNORECASE))
            for elem in elements:
                parent = elem.parent
                if parent:
                    # Son maçlar listesini bulmaya çalış
                    next_elements = parent.find_next_siblings()
                    for next_elem in next_elements[:3]:
                        text = next_elem.get_text().strip()
                        if len(text) > 50:
                            recent[keyword] = text[:500]
                            break
        
        return recent
    
    def extract_match_date(self, soup):
        """Maç tarihini çek"""
        # Tarih için çeşitli pattern'ler
        date_patterns = [
            r'\d{2}/\d{2}/\d{4}',
            r'\d{2}-\d{2}-\d{4}',
            r'\d{2}\.\d{2}\.\d{4}'
        ]
        
        # Sayfa içinde tarih ara
        text_content = soup.get_text()
        for pattern in date_patterns:
            match = re.search(pattern, text_content)
            if match:
                return match.group()
        
        return "Tarih bulunamadı"
    
    def analyze_data(self, data):
        """Çekilen verileri analiz et"""
        if "error" in data:
            return {"error": data["error"]}
        
        teams = data["teams"]
        stats = data["statistics"]
        
        # Temel analiz
        analysis = {
            "match": f"{teams.get('home', 'Ev Sahibi')} vs {teams.get('away', 'Deplasman')}",
            "date": data.get("match_date", "Bilinmiyor"),
            "analysis": "",
            "prediction": "",
            "goals_prediction": "",
            "key_factors": []
        }
        
        # İstatistik analizi
        if stats:
            home_advantage = 0
            away_advantage = 0
            
            # Şut analizi
            if 'Şut' in stats or 'Şut Sayısı' in stats:
                shot_key = 'Şut Sayısı' if 'Şut Sayısı' in stats else 'Şut'
                try:
                    home_shots = int(stats[shot_key]['home'])
                    away_shots = int(stats[shot_key]['away'])
                    if home_shots > away_shots:
                        home_advantage += 2
                        analysis["key_factors"].append(f"{teams.get('home', 'Ev Sahibi')} şut üstünlüğü ({home_shots}-{away_shots})")
                    else:
                        away_advantage += 2
                        analysis["key_factors"].append(f"{teams.get('away', 'Deplasman')} şut üstünlüğü ({away_shots}-{home_shots})")
                except:
                    pass
            
            # Top hakimiyeti analizi
            if 'Top Hakimiyeti' in stats:
                try:
                    home_possession = int(stats['Top Hakimiyeti']['home'].replace('%', ''))
                    away_possession = int(stats['Top Hakimiyeti']['away'].replace('%', ''))
                    if home_possession > away_possession:
                        home_advantage += 1
                    else:
                        away_advantage += 1
                    analysis["key_factors"].append(f"Top hakimiyeti: {home_possession}%-{away_possession}%")
                except:
                    pass
            
            # Korner analizi
            if 'Korner' in stats:
                try:
                    home_corners = int(stats['Korner']['home'])
                    away_corners = int(stats['Korner']['away'])
                    if home_corners > away_corners:
                        home_advantage += 1
                    else:
                        away_advantage += 1
                    analysis["key_factors"].append(f"Korner: {home_corners}-{away_corners}")
                except:
                    pass
            
            # Tahmin oluştur
            if home_advantage > away_advantage + 2:
                analysis["prediction"] = f"{teams.get('home', 'Ev Sahibi')} kazanır"
                analysis["analysis"] = f"{teams.get('home', 'Ev Sahibi')} istatistiksel üstünlüğe sahip"
            elif away_advantage > home_advantage + 2:
                analysis["prediction"] = f"{teams.get('away', 'Deplasman')} kazanır"
                analysis["analysis"] = f"{teams.get('away', 'Deplasman')} istatistiksel üstünlüğe sahip"
            else:
                analysis["prediction"] = "Beraberlik veya dengeli maç"
                analysis["analysis"] = "İki takım da dengeli görünüyor"
            
            # Gol tahmini
            total_advantage = home_advantage + away_advantage
            if total_advantage >= 6:
                analysis["goals_prediction"] = "2.5 Üst - Yüksek tempolu maç bekleniyor"
            elif total_advantage >= 4:
                analysis["goals_prediction"] = "1.5 Üst - Orta tempolu maç"
            else:
                analysis["goals_prediction"] = "1.5 Alt - Düşük tempolu maç"
        
        else:
            analysis["prediction"] = "Yetersiz veri - İstatistik bulunamadı"
            analysis["analysis"] = "Maç istatistikleri mevcut değil"
            analysis["goals_prediction"] = "Veri yetersiz"
        
        return analysis
    
    def display_analysis(self, data, analysis):
        """Analiz sonuçlarını göster"""
        print(f"\n{'='*80}")
        print("🎯 CORNER-STATS GERÇEK ANALİZ SİSTEMİ")
        print(f"{'='*80}")
        
        if "error" in data:
            print(f"❌ HATA: {data['error']}")
            return
        
        print(f"📊 SAYFA: {data.get('page_title', 'Bilinmiyor')}")
        print(f"🏆 MAÇ: {analysis['match']}")
        print(f"📅 TARİH: {analysis['date']}")
        
        print(f"\n🔍 ANALİZ SONUÇLARI:")
        print(f"   🎯 TAHMİN: {analysis['prediction']}")
        print(f"   📝 AÇIKLAMA: {analysis['analysis']}")
        print(f"   ⚽ GOL TAHMİNİ: {analysis['goals_prediction']}")
        
        if analysis['key_factors']:
            print(f"\n📈 ANAHTAR İSTATİSTİKLER:")
            for factor in analysis['key_factors']:
                print(f"   • {factor}")
        
        # Ham istatistikleri göster
        if data.get('statistics'):
            print(f"\n📊 HAM İSTATİSTİKLER:")
            for stat_name, values in data['statistics'].items():
                print(f"   {stat_name}: {values['home']} - {values['away']}")
        
        # Head-to-head bilgisi
        if data.get('head_to_head'):
            print(f"\n🤝 HEAD-TO-HEAD:")
            for key, value in list(data['head_to_head'].items())[:1]:
                print(f"   {value[:200]}...")
        
        print(f"\n{'='*80}")
        print(f"⏰ Analiz Zamanı: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        print(f"🌐 Veri Kaynağı: corner-stats.com")
        print(f"{'='*80}")

def main():
    analyzer = GercekCornerStatsAnaliz()
    
    print("🏆 CORNER-STATS GERÇEK ANALİZ SİSTEMİ")
    print("🔍 Web'den gerçek verilerle profesyonel futbol analizi\n")
    
    while True:
        try:
            print("\n" + "-"*50)
            url = input("📋 Corner-stats.com maç URL'sini yapıştırın: ").strip()
            
            if not url.startswith('http'):
                print("❌ Geçerli bir URL girin!")
                continue
            
            # Verileri çek
            data = analyzer.get_corner_stats_data(url)
            
            # Analiz yap
            analysis = analyzer.analyze_data(data)
            
            # Sonuçları göster
            analyzer.display_analysis(data, analysis)
            
        except KeyboardInterrupt:
            print("\n\n👋 Program kapatıldı!")
            break
        except Exception as e:
            print(f"❌ Beklenmeyen hata: {e}")
        
        devam = input("\n🔄 Başka maç analizi yapmak istiyor musunuz? (e/h): ").lower()
        if devam != 'e':
            print("👋 Görüşmek üzere!")
            break

if __name__ == "__main__":
    main()