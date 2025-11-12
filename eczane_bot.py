import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from bs4 import BeautifulSoup

# Loglama ayarı
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class EczaneBot:
    def __init__(self):
        # Token direkt entegre
        self.token = "7860718541:AAF1gzM4XY9uE12xBDJqo9HHE7VnEy8pK-U"
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "⚕️ *Eczanem | Nöbetçi Eczane*\n\n"
            "🤖 Nöbetçi eczane sorgulamak için:\n"
            "`/nobetci il ilce` yazın!\n\n"
            "Örnek: `/nobetci Karabuk Merkez`\n"
            "Örnek: `/nobetci Istanbul Kadikoy`",
            parse_mode='Markdown'
        )

    async def nobetci(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args or len(context.args) < 2:
                await update.message.reply_text(
                    "❌ Lütfen il ve ilçe girin!\n"
                    "Örnek: `/nobetci Karabuk Merkez`",
                    parse_mode='Markdown'
                )
                return

            il = context.args[0].title()
            ilce = context.args[1].title()

            eczane_data = await self.scrape_eczane_data(il, ilce)
            if eczane_data:
                await update.message.reply_text(eczane_data, parse_mode='Markdown')
            else:
                await update.message.reply_text(
                    f"❌ {il} {ilce} için nöbetçi eczane bulunamadı.\n"
                    "Lütfen il/ilçe isimlerini kontrol edin.",
                    parse_mode='Markdown'
                )

        except Exception as e:
            logging.error(f"Hata: {e}")
            await update.message.reply_text("❌ Bir hata oluştu, lütfen tekrar deneyin.")

    async def scrape_eczane_data(self, il: str, ilce: str) -> str:
        try:
            # Eczaneler.gen.tr sitesinden veri çek
            il_formatted = self.format_text(il)
            ilce_formatted = self.format_text(ilce)
            
            url = f"https://www.eczaneler.gen.tr/nobetci-{il_formatted}-{ilce_formatted}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'tr-TR,tr;q=0.8,en-US;q=0.5,en;q=0.3',
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Tarih bilgisini al
            tarih_element = soup.find('div', class_='text-center')
            tarih = tarih_element.get_text(strip=True) if tarih_element else "Bugün"
            
            # Eczane listesini al
            eczaneler = []
            eczane_elements = soup.find_all('li', class_='media')
            
            for element in eczane_elements[:6]:
                try:
                    # Eczane adı
                    ad_element = element.find('h5', class_='media-heading')
                    eczane_adi = ad_element.get_text(strip=True) if ad_element else "Bilinmeyen Eczane"
                    
                    # Eczane adresi
                    adres_element = element.find('p', class_='mb-1')
                    eczane_adres = adres_element.get_text(strip=True) if adres_element else "Adres bilgisi yok"
                    
                    # Telefon
                    telefon_element = element.find('span', class_='text-secondary')
                    eczane_telefon = telefon_element.get_text(strip=True) if telefon_element else "Telefon yok"
                    
                    eczaneler.append({
                        'adi': eczane_adi,
                        'adres': eczane_adres,
                        'telefon': eczane_telefon
                    })
                    
                except Exception as e:
                    continue
            
            if not eczaneler:
                return None
                
            # Mesajı formatla
            message = f"🗓 *{tarih}*\n\n"
            message += f"📍 *{il} {ilce}* Nöbetçi Eczaneler\n\n"
            
            for i, eczane in enumerate(eczaneler):
                message += f"⚕ *{eczane['adi']}*\n"
                message += f"📍 {eczane['adres']}\n"
                message += f"☎️ {eczane['telefon']}\n\n"
                
                if i < len(eczaneler) - 1:
                    message += "─" * 30 + "\n\n"
            
            message += "📞 Detaylı bilgi için eczaneleri arayabilirsiniz."
            
            return message
            
        except Exception as e:
            logging.error(f"Scraping hatası: {e}")
            return None

    def format_text(self, text: str) -> str:
        """Metni URL formatına uygun hale getir"""
        replacements = {
            'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
            'Ç': 'c', 'Ğ': 'g', 'İ': 'i', 'Ö': 'o', 'Ş': 's', 'Ü': 'u'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        text = text.replace(' ', '-').lower()
        return text

    def run(self):
        app = Application.builder().token(self.token).build()
        
        # Sadece İngilizce karakterli komutlar
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("nobetci", self.nobetci))
        app.add_handler(CommandHandler("eczane", self.nobetci))
        # "nöbetci" komutunu kaldırdım (Türkçe karakter hatası)
        
        print("🤖 Eczane Botu çalışıyor...")
        app.run_polling()

if __name__ == "__main__":
    bot = EczaneBot()
    bot.run()
