#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time

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
            
            # Tüm sayfa metnini al
            all_text = soup.get_text()
            
            # Takım isimlerini çek
            teams = self.extract_teams_from_text(all_text)
            
            # Oranları çek
            odds = self.extract_odds_from_text(all_text)
            
            # Head-to-head verilerini çek
            h2h_data = self.extract_h2h_from_text(all_text)
            
            # Maç tarihini çek
            match_date = self.extract_match_date(all_text)
            
            # İstatistikleri çek (eğer maç oynandıysa)
            stats = self.extract_statistics_from_text(all_text)
            
            return {
                "success": True,
                "page_title": page_title,
                "teams": teams,
                "odds": odds,
                "head_to_head": h2h_data,
                "match_date": match_date,
                "statistics": stats,
                "raw_text": all_text[:5000]  # Debug için
            }
            
        except Exception as e:
            return {"error": f"Veri çekme hatası: {str(e)}"}

    def extract_teams_from_text(self, text):
        """Metinden takım isimlerini çek"""
        teams = {}
        
        # Pattern'ler: "Takım1 vs Takım2" veya "Takım1 - Takım2"
        patterns = [
            r'(\w+(?:\s+\w+)*)\s+vs\s+(\w+(?:\s+\w+)*)',
            r'(\w+(?:\s+\w+)*)\s+-\s+(\w+(?:\s+\w+)*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                teams['home'] = match.group(1).strip()
                teams['away'] = match.group(2).strip()
                break
        
        return teams

    def extract_odds_from_text(self, text):
        """Metinden bahis oranlarını çek"""
        odds = {}
        
        # 1xBet oranlarını ara
        pinnacle_match = re.search(r'Pinnacle.*?(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)', text, re.DOTALL)
        if pinnacle_match:
            odds['pinnacle'] = {
                '1': float(pinnacle_match.group(1)),
                'X': float(pinnacle_match.group(2)),
                '2': float(pinnacle_match.group(3))
            }
        
        # 1xBet oranlarını ara
        xbet_match = re.search(r'1xbet.*?(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)', text, re.DOTALL)
        if xbet_match:
            odds['1xbet'] = {
                '1': float(xbet_match.group(1)),
                'X': float(xbet_match.group(2)),
                '2': float(xbet_match.group(3))
            }
        
        return odds

    def extract_h2h_from_text(self, text):
        """Metinden head-to-head verilerini çek"""
        h2h_matches = []
        
        # H2H maçlarını ara
        h2h_section = re.search(r'H2H matches(.*?)(?=Current coach|$)', text, re.DOTALL)
        if h2h_section:
            h2h_text = h2h_section.group(1)
            
            # Maçları bul
            matches = re.findall(r'(\d{2}/\d{2}/\d{2,4}).*?(\w+(?:\s+\w+)*)\s+(\d+)\s+(\d+)\s+(\w+(?:\s+\w+)*)', h2h_text)
            
            for match in matches[:10]:  # Son 10 maç
                tarih, ev_takim, ev_gol, dep_gol, dep_takim = match
                h2h_matches.append({
                    'date': tarih,
                    'home_team': ev_takim,
                    'home_score': int(ev_gol),
                    'away_team': dep_takim,
                    'away_score': int(dep_gol)
                })
        
        return h2h_matches

    def extract_match_date(self, text):
        """Maç tarihini çek"""
        date_patterns = [
            r'\d{2}/\d{2}/\d{4}',
            r'\d{2}-\d{2}-\d{4}',
            r'\d{2}\.\d{2}\.\d{4}'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        
        return "Tarih bulunamadı"

    def extract_statistics_from_text(self, text):
        """İstatistikleri çek (eğer maç oynandıysa)"""
        stats = {}
        
        # Şut istatistikleri
        shots_match = re.search(r'Shots on target.*?(\d+)\s*-\s*(\d+)', text)
        if shots_match:
            stats['shots_on_target'] = {
                'home': int(shots_match.group(1)),
                'away': int(shots_match.group(2))
            }
        
        # Korner istatistikleri
        corners_match = re.search(r'Corners.*?(\d+)\s*-\s*(\d+)', text)
        if corners_match:
            stats['corners'] = {
                'home': int(corners_match.group(1)),
                'away': int(corners_match.group(2))
            }
        
        return stats

    def analyze_data(self, data):
        """Çekilen verileri detaylı analiz et"""
        if "error" in data:
            return {"error": data["error"]}
        
        teams = data["teams"]
        odds = data["odds"]
        h2h_matches = data["head_to_head"]
        
        analysis = {
            "match_info": {
                "teams": teams,
                "date": data.get("match_date", "Bilinmiyor"),
                "page_title": data.get("page_title", "")
            },
            "odds_analysis": self.analyze_odds(odds),
            "h2h_analysis": self.analyze_h2h(h2h_matches, teams),
            "prediction": "",
            "confidence": 0,
            "key_factors": [],
            "betting_recommendations": []
        }
        
        # Tahmin oluştur
        final_prediction = self.generate_prediction(analysis)
        analysis.update(final_prediction)
        
        return analysis

    def analyze_odds(self, odds):
        """Oranları analiz et"""
        analysis = {}
        
        if '1xbet' in odds:
            xbet = odds['1xbet']
            analysis['1xbet'] = {
                'home_win': xbet['1'],
                'draw': xbet['X'],
                'away_win': xbet['2'],
                'favorite': 'Ev Sahibi' if xbet['1'] < xbet['2'] else 'Deplasman'
            }
        
        if 'pinnacle' in odds:
            pinnacle = odds['pinnacle']
            analysis['pinnacle'] = {
                'home_win': pinnacle['1'],
                'draw': pinnacle['X'],
                'away_win': pinnacle['2'],
                'favorite': 'Ev Sahibi' if pinnacle['1'] < pinnacle['2'] else 'Deplasman'
            }
        
        return analysis

    def analyze_h2h(self, h2h_matches, current_teams):
        """Head-to-head verilerini analiz et"""
        if not h2h_matches:
            return {"error": "H2H verisi bulunamadı"}
        
        analysis = {
            "total_matches": len(h2h_matches),
            "home_wins": 0,
            "away_wins": 0,
            "draws": 0,
            "total_home_goals": 0,
            "total_away_goals": 0,
            "recent_trend": "",
            "dominant_team": ""
        }
        
        for match in h2h_matches:
            if match['home_score'] > match['away_score']:
                analysis["home_wins"] += 1
            elif match['home_score'] < match['away_score']:
                analysis["away_wins"] += 1
            else:
                analysis["draws"] += 1
            
            analysis["total_home_goals"] += match['home_score']
            analysis["total_away_goals"] += match['away_score']
        
        # Trend analizi
        if analysis["away_wins"] > analysis["home_wins"]:
            analysis["dominant_team"] = current_teams.get('away', 'Deplasman')
            analysis["recent_trend"] = f"{analysis['dominant_team']} son {analysis['total_matches']} maçta dominant"
        elif analysis["home_wins"] > analysis["away_wins"]:
            analysis["dominant_team"] = current_teams.get('home', 'Ev Sahibi')
            analysis["recent_trend"] = f"{analysis['dominant_team']} son {analysis['total_matches']} maçta dominant"
        else:
            analysis["recent_trend"] = "Maçlar dengeli geçmiş"
        
        return analysis

    def generate_prediction(self, analysis):
        """Analizlere dayalı tahmin oluştur"""
        h2h = analysis["h2h_analysis"]
        odds = analysis["odds_analysis"]
        
        prediction = {
            "prediction": "",
            "confidence": 0,
            "score_prediction": "",
            "key_factors": [],
            "betting_recommendations": []
        }
        
        # H2H ve oranlara göre tahmin
        if "error" not in h2h and odds:
            # Favori takımı belirle
            if '1xbet' in odds:
                favorite = odds['1xbet']['favorite']
                away_odds = odds['1xbet']['away_win']
                
                # Güven skoru hesapla
                confidence = self.calculate_confidence(h2h, away_odds)
                
                if favorite == 'Deplasman' and confidence > 60:
                    prediction["prediction"] = f"{analysis['match_info']['teams'].get('away')} kazanır"
                    prediction["confidence"] = confidence
                    prediction["score_prediction"] = self.predict_score(h2h)
                    prediction["key_factors"].append("Deplasman takımı net favori")
                    prediction["key_factors"].append(f"Son {h2h['total_matches']} maçta {h2h['away_wins']} galibiyet")
                    
                    # Bahis önerileri
                    prediction["betting_recommendations"].append("✅ Deplasman takımı kazanır (Ana bahis)")
                    prediction["betting_recommendations"].append("⚽ Maçta 2.5 Üst gol bekleniyor")
                    prediction["betting_recommendations"].append("🎯 Deplasman takım gol - EVET")
        
        return prediction

    def calculate_confidence(self, h2h, away_odds):
        """Güven skoru hesapla"""
        confidence = 0
        
        # H2H galibiyet yüzdesi
        if h2h['total_matches'] > 0:
            win_percentage = (h2h['away_wins'] / h2h['total_matches']) * 100
            confidence += win_percentage * 0.6
        
        # Oranlara göre güven
        if away_odds < 1.8:
            confidence += 30
        elif away_odds < 2.2:
            confidence += 20
        else:
            confidence += 10
        
        return min(95, int(confidence))

    def predict_score(self, h2h):
        """Skor tahmini yap"""
        if h2h['total_matches'] == 0:
            return "1-2 veya 0-2"
        
        avg_home_goals = h2h['total_home_goals'] / h2h['total_matches']
        avg_away_goals = h2h['total_away_goals'] / h2h['total_matches']
        
        home_pred = max(0, int(avg_home_goals))
        away_pred = max(1, int(avg_away_goals) + 1)  # Favori takıma +1 gol
        
        return f"{home_pred}-{away_pred}"

    def display_analysis(self, data, analysis):
        """Analiz sonuçlarını göster"""
        print(f"\n{'='*80}")
        print("🎯 CORNER-STATS GERÇEK ANALİZ SİSTEMİ")
        print(f"{'='*80}")
        
        if "error" in data:
            print(f"❌ HATA: {data['error']}")
            return
        
        match_info = analysis["match_info"]
        print(f"🏆 MAÇ: {match_info['teams'].get('home', 'Ev Sahibi')} vs {match_info['teams'].get('away', 'Deplasman')}")
        print(f"📅 TARİH: {match_info['date']}")
        
        # Oran analizi
        if analysis["odds_analysis"]:
            print(f"\n💰 ORAN ANALİZİ:")
            for bookmaker, odds in analysis["odds_analysis"].items():
                print(f"   📊 {bookmaker.upper()}:")
                print(f"      🏠 Ev: {odds['home_win']} | 🤝 Beraberlik: {odds['draw']} | 🚍 Deplasman: {odds['away_win']}")
                print(f"      ⭐ Favori: {odds['favorite']}")
        
        # H2H analizi
        h2h = analysis["h2h_analysis"]
        if "error" not in h2h:
            print(f"\n📊 HEAD-TO-HEAD ANALİZİ (Son {h2h['total_matches']} maç):")
            print(f"   🏆 Galibiyetler: {match_info['teams'].get('home', 'Ev')} {h2h['home_wins']} - {h2h['draws']} - {h2h['away_wins']} {match_info['teams'].get('away', 'Dep')}")
            print(f"   ⚽ Goller: {h2h['total_home_goals']} - {h2h['total_away_goals']}")
            print(f"   📈 Trend: {h2h['recent_trend']}")
        
        # Tahminler
        print(f"\n🎯 TAHMİNLER:")
        print(f"   🔮 SONUÇ: {analysis['prediction']}")
        print(f"   💪 GÜVEN: %{analysis['confidence']}")
        print(f"   📝 SKOR: {analysis['score_prediction']}")
        
        # Anahtar Faktörler
        if analysis['key_factors']:
            print(f"\n🔑 ANAHTAR FAKTÖRLER:")
            for factor in analysis['key_factors']:
                print(f"   ✅ {factor}")
        
        # Bahis Önerileri
        if analysis['betting_recommendations']:
            print(f"\n💎 BAHİS ÖNERİLERİ:")
            for recommendation in analysis['betting_recommendations']:
                print(f"   {recommendation}")
        
        # Detaylı H2H
        if "error" not in h2h and h2h['total_matches'] > 0:
            print(f"\n📋 DETAYLI H2H MAÇLARI (Son 5):")
            data_to_show = min(5, len(data["head_to_head"]))
            for i in range(data_to_show):
                match = data["head_to_head"][i]
                print(f"   📅 {match['date']}: {match['home_team']} {match['home_score']}-{match['away_score']} {match['away_team']}")
        
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
            print("⏳ Veriler çekiliyor ve analiz ediliyor...")
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