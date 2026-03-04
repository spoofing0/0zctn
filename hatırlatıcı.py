import json
import os
import re
import random
import string
import io
import tempfile
import shutil
import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta, time
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)

# ---------- LOGGING AYARLARI ----------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- KONFIGURASYON ----------
class Config:
    # BOT_TOKEN düzeltildi - os.getenv kullanımı hatalıydı
    BOT_TOKEN = os.getenv("BOT_TOKEN", "8303756408:AAGg6F1fbVO9dxe01F3ZvKiVJhGxD779fSQ")
    DB_PATH = os.getenv("DB_PATH", "hesapla.db")
    BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
    PREMIUM_TRIAL_DAYS = 7
    MAX_FAMILY_MEMBERS = 6
    DEFAULT_CURRENCY = "TRY"
    
    # Ödeme yöntemleri
    PAYMENT_METHODS = ["kart", "nakit", "kredi", "havale", "cek", "mobile"]
    
    # Kategori emojileri
    CATEGORY_EMOJIS = {
        "kira": "🏠", "market": "🛒", "starbucks": "☕", "kahve": "☕",
        "uber": "🚗", "taksi": "🚖", "yemek": "🍽️", "restoran": "🍽️",
        "elektrik": "⚡", "su": "💧", "dogalgaz": "🔥", "internet": "🌐",
        "egitim": "📚", "saglik": "🏥", "giyim": "👕", "eglence": "🎮",
        "spor": "⚽", "seyahat": "✈️", "hediye": "🎁", "fatura": "📄"
    }

# ---------- VERITABANI YONETIMI ----------
class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Veritabani semasini olustur"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Kullanicilar tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    premium_until DATE,
                    family_code TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    language TEXT DEFAULT 'tr',
                    timezone TEXT DEFAULT 'Europe/Istanbul'
                )
            """)
            
            # Aileler tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS families (
                    family_code TEXT PRIMARY KEY,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    name TEXT DEFAULT 'Ailem',
                    FOREIGN KEY (created_by) REFERENCES users(user_id)
                )
            """)
            
            # Harcamalar tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    family_code TEXT,
                    user_id INTEGER,
                    amount REAL,
                    category TEXT,
                    payment_method TEXT,
                    description TEXT,
                    expense_date DATE,
                    currency TEXT DEFAULT 'TRY',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (family_code) REFERENCES families(family_code),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Butce hedefleri tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    family_code TEXT,
                    category TEXT,
                    amount_limit REAL,
                    period_month TEXT,
                    alert_threshold INTEGER DEFAULT 80,
                    FOREIGN KEY (family_code) REFERENCES families(family_code)
                )
            """)
            
            # Indeksler
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_family ON expenses(family_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_user ON expenses(user_id)")
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Baglanti context manager'i"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    # ---------- KULLANICI ISLEMLERI ----------
    def get_user(self, user_id: int) -> Optional[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def create_user(self, user_id: int, username: str, first_name: str) -> Dict:
        """Yeni kullanici olustur ve 7 gunluk premium ver"""
        premium_until = (datetime.now() + timedelta(days=Config.PREMIUM_TRIAL_DAYS)).date()
        family_code = self._generate_family_code()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Kullanici ekle
            cursor.execute("""
                INSERT INTO users (user_id, username, first_name, premium_until, family_code)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, first_name, premium_until, family_code))
            
            # Aile olustur
            cursor.execute("""
                INSERT INTO families (family_code, created_by, name)
                VALUES (?, ?, ?)
            """, (family_code, user_id, f"{first_name}'in Ailesi"))
            
            return {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "premium_until": premium_until,
                "family_code": family_code
            }
    
    def is_premium(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user or not user.get("premium_until"):
            return False
        return datetime.now().date() <= datetime.strptime(user["premium_until"], "%Y-%m-%d").date()
    
    def extend_premium(self, user_id: int, days: int):
        """Premium suresini uzat"""
        current = self.get_user(user_id)
        if current and current.get("premium_until"):
            current_date = datetime.strptime(current["premium_until"], "%Y-%m-%d").date()
            new_date = max(current_date, datetime.now().date()) + timedelta(days=days)
        else:
            new_date = datetime.now().date() + timedelta(days=days)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET premium_until = ? WHERE user_id = ?",
                (new_date, user_id)
            )
    
    # ---------- AILE ISLEMLERI ----------
    def _generate_family_code(self) -> str:
        """Benzersiz 8 karakterlik aile kodu uret"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM families WHERE family_code = ?", (code,))
                if not cursor.fetchone():
                    return code
    
    def get_family(self, family_code: str) -> Optional[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM families WHERE family_code = ?", (family_code,))
            row = cursor.fetchone()
            if not row:
                return None
            
            family = dict(row)
            # Uyeleri al
            cursor.execute(
                "SELECT user_id, first_name FROM users WHERE family_code = ?",
                (family_code,)
            )
            family["members"] = [dict(r) for r in cursor.fetchall()]
            return family
    
    def get_family_members_count(self, family_code: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE family_code = ?",
                (family_code,)
            )
            return cursor.fetchone()[0]
    
    def change_family(self, user_id: int, new_family_code: Optional[str] = None) -> Tuple[bool, str]:
        """Kullanicinin ailesini degistir"""
        user = self.get_user(user_id)
        if not user:
            return False, "Kullanici bulunamadi"
        
        old_family = user.get("family_code")
        
        # Yeni aile kodu verilmediyse yeni aile olustur
        if new_family_code is None:
            new_family_code = self._generate_family_code()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO families (family_code, created_by, name)
                    VALUES (?, ?, ?)
                """, (new_family_code, user_id, "Yeni Aile"))
        else:
            # Mevcut aileye katil
            family = self.get_family(new_family_code)
            if not family:
                return False, "Gecersiz aile kodu"
            
            if len(family["members"]) >= Config.MAX_FAMILY_MEMBERS:
                return False, f"Aile maksimum {Config.MAX_FAMILY_MEMBERS} uye ile sinirlidir"
        
        # Kullaniciyi yeni aileye tasi
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET family_code = ? WHERE user_id = ?",
                (new_family_code, user_id)
            )
            
            # Eski aile bosaldi mi kontrol et
            if old_family:
                count = self.get_family_members_count(old_family)
                if count == 0:
                    cursor.execute("DELETE FROM families WHERE family_code = ?", (old_family,))
        
        return True, new_family_code
    
    # ---------- HARCAMA ISLEMLERI ----------
    def add_expense(self, family_code: str, user_id: int, amount: float, 
                    category: str, payment_method: Optional[str] = None,
                    description: Optional[str] = None, expense_date: Optional[str] = None) -> int:
        """Harcama ekle ve ID dondur"""
        if expense_date is None:
            expense_date = datetime.now().date().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO expenses (family_code, user_id, amount, category, 
                                    payment_method, description, expense_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (family_code, user_id, amount, category.lower(), 
                  payment_method, description, expense_date))
            
            # Butce kontrolu
            self._check_budget_alert(cursor, family_code, category, expense_date[:7])
            
            return cursor.lastrowid
    
    def _check_budget_alert(self, cursor, family_code: str, category: str, month: str):
        """Butce limitini kontrol et ve uyar"""
        cursor.execute("""
            SELECT amount_limit, alert_threshold FROM budgets 
            WHERE family_code = ? AND (category = ? OR category = 'toplam') AND period_month = ?
        """, (family_code, category, month))
        
        budgets = cursor.fetchall()
        if not budgets:
            return
        
        # Kategori toplamini hesapla
        cursor.execute("""
            SELECT SUM(amount) FROM expenses 
            WHERE family_code = ? AND category = ? AND strftime('%Y-%m', expense_date) = ?
        """, (family_code, category, month))
        
        total = cursor.fetchone()[0] or 0
        
        for budget in budgets:
            limit, threshold = budget
            percentage = (total / limit) * 100 if limit > 0 else 0
            
            if percentage >= threshold:
                # Burada bildirim sistemi entegre edilebilir
                logger.info(f"Butce uyarisi: {family_code} - {category} %{percentage:.1f}")
    
    def get_expenses(self, family_code: str, start_date: Optional[str] = None,
                     end_date: Optional[str] = None, category: Optional[str] = None) -> List[Dict]:
        """Harcama sorgula"""
        query = "SELECT * FROM expenses WHERE family_code = ?"
        params = [family_code]
        
        if start_date:
            query += " AND expense_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND expense_date <= ?"
            params.append(end_date)
        if category:
            query += " AND category = ?"
            params.append(category.lower())
        
        query += " ORDER BY expense_date DESC, created_at DESC"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_monthly_summary(self, family_code: str, year_month: str) -> Dict:
        """Aylik ozet rapor"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Toplam harcama
            cursor.execute("""
                SELECT SUM(amount), COUNT(*) FROM expenses 
                WHERE family_code = ? AND strftime('%Y-%m', expense_date) = ?
            """, (family_code, year_month))
            
            total, count = cursor.fetchone()
            total = total or 0
            
            # Kategori dagilimi
            cursor.execute("""
                SELECT category, SUM(amount) as total, COUNT(*) as count
                FROM expenses 
                WHERE family_code = ? AND strftime('%Y-%m', expense_date) = ?
                GROUP BY category
                ORDER BY total DESC
            """, (family_code, year_month))
            
            categories = [dict(row) for row in cursor.fetchall()]
            
            # Gunluk ortalama
            days_in_month = 30  # Basitlestirilmis
            daily_avg = total / days_in_month if days_in_month > 0 else 0
            
            return {
                "total": total,
                "count": count,
                "daily_average": daily_avg,
                "categories": categories,
                "period": year_month
            }
    
    def get_weekly_summary(self, family_code: str, date: Optional[datetime] = None) -> Dict:
        """Haftalik ozet rapor"""
        if date is None:
            date = datetime.now()
        
        # Haftanin baslangici (Pazartesi)
        start = date - timedelta(days=date.weekday())
        end = start + timedelta(days=6)
        
        expenses = self.get_expenses(
            family_code, 
            start_date=start.date().isoformat(),
            end_date=end.date().isoformat()
        )
        
        total = sum(e["amount"] for e in expenses)
        categories = {}
        for e in expenses:
            cat = e["category"]
            categories[cat] = categories.get(cat, 0) + e["amount"]
        
        return {
            "total": total,
            "count": len(expenses),
            "start_date": start.date().isoformat(),
            "end_date": end.date().isoformat(),
            "categories": [{"name": k, "amount": v} for k, v in categories.items()]
        }
    
    # ---------- BUTCE ISLEMLERI ----------
    def set_budget(self, family_code: str, amount: float, 
                   category: Optional[str] = None, month: Optional[str] = None):
        """Butce hedefi belirle"""
        if month is None:
            month = datetime.now().strftime("%Y-%m")
        
        target = category or "toplam"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO budgets (family_code, category, amount_limit, period_month)
                VALUES (?, ?, ?, ?)
            """, (family_code, target, amount, month))
    
    def get_budget_status(self, family_code: str, month: Optional[str] = None) -> List[Dict]:
        """Butce durumunu kontrol et"""
        if month is None:
            month = datetime.now().strftime("%Y-%m")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.*, 
                       COALESCE((SELECT SUM(amount) FROM expenses 
                                WHERE family_code = b.family_code 
                                AND category = b.category 
                                AND strftime('%Y-%m', expense_date) = b.period_month), 0) as spent
                FROM budgets b
                WHERE b.family_code = ? AND b.period_month = ?
            """, (family_code, month))
            
            return [dict(row) for row in cursor.fetchall()]

# ---------- GLOBAL VERITABANI NESNESI ----------
db = Database(Config.DB_PATH)

# ---------- YARDIMCI FONKSIYONLAR ----------
def parse_expense_message(text: str) -> Optional[Tuple[str, float, Optional[str], Optional[str]]]:
    """
    Harcama mesajini ayristir
    Ornekler:
        "market 450" -> ("market", 450.0, None, None)
        "starbucks 85.50 kart" -> ("starbucks", 85.50, "kart", None)
        "kira 15000 nakit mart ayi" -> ("kira", 15000.0, "nakit", "mart ayi")
    """
    text = text.strip().lower()
    
    # Regex: kategori + miktar + opsiyonel odeme/aciklama
    # Miktar: 100, 100.50, 100,50 (Turkce format)
    patterns = [
        r"^(.*?)\s+(\d+(?:[.,]\d{1,2})?)\s*(?:tl|₺|try)?(?:\s+(.*))?$",
        r"^(\d+(?:[.,]\d{1,2})?)\s*(?:tl|₺|try)?\s+(.*?)(?:\s+(.*))?$"  # Ters format: 100 market
    ]
    
    for pattern in patterns:
        match = re.match(pattern, text)
        if match:
            if len(match.groups()) == 3:
                if match.group(1).replace('.', '').replace(',', '').isdigit():
                    # Ters format: miktar once
                    amount_str, category, rest = match.groups()
                else:
                    category, amount_str, rest = match.groups()
            else:
                continue
            
            # Miktar parse et
            try:
                amount = float(amount_str.replace(',', '.'))
            except ValueError:
                continue
            
            if amount <= 0 or amount > 9999999:  # Makul limit
                continue
            
            # Odeme yontemi ve aciklama ayristir
            payment = None
            description = None
            
            if rest:
                rest = rest.strip()
                words = rest.split()
                
                # Ilk kelime odeme yontemi mi?
                if words[0] in Config.PAYMENT_METHODS:
                    payment = words[0]
                    description = ' '.join(words[1:]) if len(words) > 1 else None
                else:
                    description = rest
            
            return category.strip(), amount, payment, description
    
    return None

def format_currency(amount: float, currency: str = "TRY") -> str:
    """Para birimini formatla"""
    if currency == "TRY":
        return f"{amount:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{amount:,.2f} {currency}"

def get_category_emoji(category: str) -> str:
    """Kategori emojisi getir"""
    return Config.CATEGORY_EMOJIS.get(category.lower(), "💰")

# ---------- KOMUT HANDLERLARI ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Baslangic komutu"""
    user = update.effective_user
    existing = db.get_user(user.id)
    
    if existing:
        # Mevcut kullanici
        is_premium = db.is_premium(user.id)
        premium_text = "✅ Aktif" if is_premium else "❌ Pasif"
        
        await update.message.reply_text(
            f"👋 Tekrar hoş geldin, *{user.first_name}*!\n\n"
            f"📅 Premium durumun: {premium_text}\n"
            f"🏠 Aile kodun: `{existing['family_code']}`\n\n"
            f"Harcama girmek için yaz: `kategori miktar`\n"
            f"Yardım için: /yardim",
            parse_mode="Markdown"
        )
        return
    
    # Yeni kullanici
    new_user = db.create_user(user.id, user.username, user.first_name)
    
    welcome_text = (
        f"🎉 *HESAPLA'ya Hoş Geldin, {user.first_name}!*\n\n"
        f"🎁 Sana *{Config.PREMIUM_TRIAL_DAYS} gün ücretsiz* Premium hediye edildi!\n"
        f"📅 Premium süren: `{new_user['premium_until']}`\n\n"
        f"*Temel Komutlar:*\n"
        f"💬 `market 450` - Hızlı harcama girişi\n"
        f"📊 /rapor - Aylık özet\n"
        f"📅 /haftalik - Haftalık rapor\n"
        f"📈 /grafik - Kategori grafiği (Premium)\n"
        f"👨‍👩‍👧 /ailem - Aile yönetimi\n"
        f"🎯 /butce - Bütçe hedefi koy\n\n"
        f"Detaylı bilgi: /yardim"
    )
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yardim komutu"""
    help_text = (
        "📚 *HESAPLA Bot Kullanım Kılavuzu*\n\n"
        "*Harcama Girişi:*\n"
        "• `market 450` - Basit giriş\n"
        "• `starbucks 85.50 kart` - Ödeme yöntemi ile\n"
        "• `kira 15000 nakit mart ayi kira` - Açıklamalı\n\n"
        "*Raporlar:*\n"
        "• /rapor - Bu ayın detaylı özeti\n"
        "• /rapor 2025-01 - Belirli ayın raporu\n"
        "• /haftalik - Bu haftanın özeti\n"
        "• /grafik - Pasta grafiği (Premium)\n\n"
        "*Aile Yönetimi:*\n"
        "• /ailem - Aile bilgilerini gör\n"
        "• /aile_kur - Yeni aile oluştur\n"
        "• /aileye_katil KOD - Aileye katıl\n"
        "• /ayril - Aileden ayrıl\n\n"
        "*Bütçe & Hedefler:*\n"
        "• /butce 10000 - Aylık bütçe belirle\n"
        "• /butce 2000 market - Kategori bütçesi\n"
        "• /durum - Bütçe durumunu kontrol et\n\n"
        "*Diğer:*\n"
        "• /sil ID - Harcama sil (son 5 dk)\n"
        "• /export - Verilerini indir\n"
        "• /premium - Premium bilgisi"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def add_expense_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Harcama ekleme handler'i"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("Önce /start ile kayıt olmalısın.")
        return
    
    text = update.message.text
    parsed = parse_expense_message(text)
    
    if not parsed:
        await update.message.reply_text(
            "❌ Anlaşılamadı. Şu formatları dene:\n"
            "`market 450`\n"
            "`starbucks 85.50 kart`\n"
            "`kira 15000 nakit mart ayi`"
        )
        return
    
    category, amount, payment, description = parsed
    family_code = user_data["family_code"]
    
    try:
        expense_id = db.add_expense(
            family_code=family_code,
            user_id=user.id,
            amount=amount,
            category=category,
            payment_method=payment,
            description=description
        )
        
        # Ay toplamini al
        current_month = datetime.now().strftime("%Y-%m")
        summary = db.get_monthly_summary(family_code, current_month)
        
        emoji = get_category_emoji(category)
        
        response = (
            f"✅ {emoji} *{category.capitalize()}* harcaması kaydedildi!\n"
            f"💵 Tutar: {format_currency(amount)}\n"
        )
        
        if payment:
            response += f"💳 Ödeme: {payment.capitalize()}\n"
        if description:
            response += f"📝 Not: {description}\n"
        
        response += (
            f"\n📊 Bu ay toplam: {format_currency(summary['total'])}\n"
            f"📈 Günlük ortalama: {format_currency(summary['daily_average'])}"
        )
        
        # Butce uyarisi var mi kontrol et (async olarak islenebilir)
        
        await update.message.reply_text(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Harcama eklenirken hata: {e}")
        await update.message.reply_text("❌ Harcama kaydedilirken bir hata oluştu. Lütfen tekrar dene.")

async def monthly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aylik rapor"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("Önce /start ile kayıt ol.")
        return
    
    # Ay parametresi
    target_month = datetime.now().strftime("%Y-%m")
    if context.args:
        # 2025-03 veya 03 formatlarini kabul et
        arg = context.args[0]
        if len(arg) == 7 and arg[4] == '-':
            target_month = arg
        elif len(arg) == 2 and arg.isdigit():
            year = datetime.now().year
            target_month = f"{year}-{arg}"
    
    summary = db.get_monthly_summary(user_data["family_code"], target_month)
    
    if summary["total"] == 0:
        await update.message.reply_text(f"📭 {target_month} ayında harcama bulunmuyor.")
        return
    
    # Kategori listesi
    cat_lines = []
    for cat in summary["categories"]:
        emoji = get_category_emoji(cat["category"])
        percentage = (cat["total"] / summary["total"]) * 100
        cat_lines.append(
            f"{emoji} {cat['category'].capitalize()}: {format_currency(cat['total'])} "
            f"({percentage:.1f}%) - {cat['count']} işlem"
        )
    
    report_text = (
        f"📊 *Aylık Rapor: {target_month}*\n\n"
        f"💰 Toplam Harcama: *{format_currency(summary['total'])}*\n"
        f"📝 İşlem Sayısı: {summary['count']}\n"
        f"📅 Günlük Ortalama: {format_currency(summary['daily_average'])}\n\n"
        f"*Kategori Dağılımı:*\n" + "\n".join(cat_lines)
    )
    
    await update.message.reply_text(report_text, parse_mode="Markdown")

async def weekly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Haftalik rapor"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("Önce /start ile kayıt ol.")
        return
    
    summary = db.get_weekly_summary(user_data["family_code"])
    
    if summary["total"] == 0:
        await update.message.reply_text("📭 Bu hafta harcama bulunmuyor.")
        return
    
    cat_lines = [
        f"{get_category_emoji(c['name'])} {c['name'].capitalize()}: {format_currency(c['amount'])}"
        for c in summary["categories"]
    ]
    
    report_text = (
        f"📅 *Haftalık Rapor*\n"
        f"({summary['start_date']} - {summary['end_date']})\n\n"
        f"💰 Toplam: *{format_currency(summary['total'])}*\n"
        f"📝 İşlem: {summary['count']}\n\n"
        f"*Kategoriler:*\n" + "\n".join(cat_lines)
    )
    
    await update.message.reply_text(report_text, parse_mode="Markdown")

async def grafik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pasta grafiği olustur"""
    user = update.effective_user
    
    # Premium kontrol
    if not db.is_premium(user.id):
        await update.message.reply_text(
            "📊 Grafik özelliği sadece Premium üyeler içindir.\n"
            "🎁 /start ile 7 günlük deneme başlatabilirsiniz."
        )
        return
    
    user_data = db.get_user(user.id)
    if not user_data:
        await update.message.reply_text("Önce /start ile kayıt ol.")
        return
    
    current_month = datetime.now().strftime("%Y-%m")
    summary = db.get_monthly_summary(user_data["family_code"], current_month)
    
    if not summary["categories"]:
        await update.message.reply_text("Bu ay grafik oluşturacak veri yok.")
        return
    
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use('Agg')  # Headless ortam için
        
        # Verileri hazirla
        labels = [c["category"].capitalize() for c in summary["categories"]]
        sizes = [c["total"] for c in summary["categories"]]
        colors = plt.cm.Set3(range(len(labels)))
        
        # Grafik olustur
        fig, ax = plt.subplots(figsize=(10, 8))
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, autopct='%1.1f%%', 
            startangle=90, colors=colors
        )
        
        # Stil ayarlari
        plt.setp(autotexts, size=10, weight="bold")
        plt.setp(texts, size=11)
        ax.set_title(f"Aylık Harcama Dağılımı - {current_month}", 
                    fontsize=14, fontweight='bold', pad=20)
        
        # Legend ekle
        ax.legend(wedges, [f"{l}: {format_currency(s)}" for l, s in zip(labels, sizes)],
                 title="Kategoriler", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
        
        plt.tight_layout()
        
        # Buffer'a kaydet
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        
        await update.message.reply_photo(
            photo=buf, 
            caption=f"📊 {current_month} Aylık Harcama Grafiği\n"
                   f"Toplam: {format_currency(summary['total'])}"
        )
        
    except ImportError:
        await update.message.reply_text("Grafik modülü kurulu değil. Yöneticiye bildirin.")
    except Exception as e:
        logger.error(f"Grafik olusturulurken hata: {e}")
        await update.message.reply_text("Grafik oluşturulurken bir hata oluştu.")

async def family_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aile bilgileri"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("Önce /start ile kayıt ol.")
        return
    
    family = db.get_family(user_data["family_code"])
    if not family:
        await update.message.reply_text("Aile bilgisi bulunamadı.")
        return
    
    # Uye listesi
    member_lines = []
    for member in family["members"]:
        is_creator = "👑" if member["user_id"] == family["created_by"] else "👤"
        member_lines.append(f"{is_creator} {member['first_name']}")
    
    keyboard = [
        [InlineKeyboardButton("➕ Yeni Aile Kur", callback_data="new_family")],
        [InlineKeyboardButton("🚪 Aileden Ayrıl", callback_data="leave_family")]
    ]
    
    text = (
        f"🏠 *Aile Bilgilerin*\n\n"
        f"📝 İsim: {family['name']}\n"
        f"🔑 Kod: `{family['family_code']}`\n"
        f"👥 Üye Sayısı: {len(family['members'])}/{Config.MAX_FAMILY_MEMBERS}\n\n"
        f"*Üyeler:*\n" + "\n".join(member_lines) + "\n\n"
        f"Başka birine katılmak için:\n`/aileye_katil KOD`"
    )
    
    await update.message.reply_text(
        text, 
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def create_family(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yeni aile olustur"""
    user = update.effective_user
    
    if not db.is_premium(user.id):
        await update.message.reply_text(
            "👨‍👩‍👧 Aile oluşturmak Premium özelliktir.\n"
            "🎁 /start ile deneme başlatabilirsiniz."
        )
        return
    
    success, result = db.change_family(user.id, None)
    
    if success:
        await update.message.reply_text(
            f"✅ Yeni ailen oluşturuldu!\n\n"
            f"🏷️ Yeni kodun: `{result}`\n\n"
            f"Bu kodu paylaşarak arkadaşlarını davet edebilirsin.\n"
            f"Not: Eski harcamaların yeni aileye taşınmadı."
        )
    else:
        await update.message.reply_text(f"❌ Hata: {result}")

async def join_family(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aileye katil"""
    user = update.effective_user
    
    if not db.is_premium(user.id):
        await update.message.reply_text(
            "👨‍👩‍👧 Aileye katılmak Premium özelliktir."
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            "Kullanım: `/aileye_katil KOD`\n"
            "Örnek: `/aileye_katil ABC12345`"
        )
        return
    
    family_code = context.args[0].upper().strip()
    current = db.get_user(user.id)
    
    if current and current.get("family_code") == family_code:
        await update.message.reply_text("Zaten bu aileye üyesin.")
        return
    
    success, message = db.change_family(user.id, family_code)
    
    if success:
        await update.message.reply_text(
            f"✅ `{family_code}` ailesine katıldın!\n"
            f"Artık ortak harcamaları görebilirsin."
        )
    else:
        await update.message.reply_text(f"❌ {message}")

async def set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Butce hedefi belirle"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("Önce /start ile kayıt ol.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Kullanım:\n"
            "`/butce 10000` - Aylık toplam bütçe\n"
            "`/butce 2000 market` - Kategori bütçesi"
        )
        return
    
    try:
        amount = float(context.args[0].replace(',', '.'))
        category = context.args[1].lower() if len(context.args) > 1 else None
        
        db.set_budget(user_data["family_code"], amount, category)
        
        target = category.capitalize() if category else "Toplam"
        await update.message.reply_text(
            f"🎯 Bütçe hedefi belirlendi!\n\n"
            f"Kategori: {target}\n"
            f"Limit: {format_currency(amount)}\n"
            f"Ay: {datetime.now().strftime('%Y-%m')}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Geçersiz miktar. Örnek: `/butce 5000`")

async def budget_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Butce durumu"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("Önce /start ile kayıt ol.")
        return
    
    budgets = db.get_budget_status(user_data["family_code"])
    
    if not budgets:
        await update.message.reply_text(
            "🎯 Henüz bütçe hedefi belirlenmemiş.\n"
            "Belirlemek için: /butce"
        )
        return
    
    lines = ["📊 *Bütçe Durumu*\n"]
    for b in budgets:
        spent = b["spent"]
        limit = b["amount_limit"]
        remaining = limit - spent
        percentage = (spent / limit * 100) if limit > 0 else 0
        
        status_emoji = "🟢" if percentage < 80 else "🟡" if percentage < 100 else "🔴"
        category = b["category"].capitalize()
        
        lines.append(
            f"{status_emoji} *{category}*\n"
            f"Hedef: {format_currency(limit)}\n"
            f"Harcanan: {format_currency(spent)} ({percentage:.1f}%)\n"
            f"Kalan: {format_currency(remaining)}\n"
        )
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def premium_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Premium bilgisi"""
    user = update.effective_user
    is_premium = db.is_premium(user.id)
    user_data = db.get_user(user.id)
    
    if is_premium:
        premium_until = user_data.get("premium_until")
        await update.message.reply_text(
            f"⭐ *Premium Üyesin*\n\n"
            f"📅 Bitiş tarihi: `{premium_until}`\n"
            f"✅ Tüm özellikler aktif\n\n"
            f"Premium özellikler:\n"
            f"• Sınırsız grafik raporları\n"
            f"• Aile sistemi (6 kişiye kadar)\n"
            f"• Veri dışa aktarma\n"
            f"• Özel kategoriler\n"
            f"• Gelişmiş analizler"
        )
    else:
        await update.message.reply_text(
            f"⭐ *Premium Bilgisi*\n\n"
            f"Şu an standart kullanıcısın.\n"
            f"Premium ile şunları elde edersin:\n\n"
            f"• Sınırsız grafik raporları\n"
            f"• Aile sistemi (6 kişiye kadar)\n"
            f"• Veri dışa aktarma\n"
            f"• Özel kategoriler\n\n"
            f"🎁 /start ile 7 günlük ücretsiz deneme başlatabilirsin!"
        )

async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verileri disa aktar"""
    user = update.effective_user
    
    if not db.is_premium(user.id):
        await update.message.reply_text("Bu özellik sadece Premium üyeler içindir.")
        return
    
    user_data = db.get_user(user.id)
    expenses = db.get_expenses(user_data["family_code"])
    
    # CSV formatinda olustur
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["Tarih", "Kategori", "Tutar", "Para Birimi", "Ödeme", "Açıklama", "Kullanıcı"])
    
    for exp in expenses:
        writer.writerow([
            exp["expense_date"],
            exp["category"],
            exp["amount"],
            exp["currency"],
            exp["payment_method"] or "",
            exp["description"] or "",
            exp["user_id"]
        ])
    
    # Dosya olarak gonder
    output.seek(0)
    await update.message.reply_document(
        document=output.getvalue().encode('utf-8-sig'),
        filename=f"harcamalar_{datetime.now().strftime('%Y%m%d')}.csv",
        caption="📥 Harcama kayıtların ektedir."
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline buton handler'i"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "new_family":
        await create_family(update, context)
    elif data == "leave_family":
        # Ayrilma onayi
        keyboard = [
            [
                InlineKeyboardButton("✅ Evet, Ayrıl", callback_data="confirm_leave"),
                InlineKeyboardButton("❌ İptal", callback_data="cancel")
            ]
        ]
        await query.edit_message_text(
            "🚪 Aileden ayrılmak istediğine emin misin?\n"
            "Yeni bir aile oluşturman gerekecek.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "confirm_leave":
        success, result = db.change_family(update.effective_user.id, None)
        if success:
            await query.edit_message_text(
                f"✅ Aileden ayrıldın.\n"
                f"Yeni kodun: `{result}`"
            )
    elif data == "cancel":
        await query.edit_message_text("İşlem iptal edildi.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hata yakalama"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Bir hata oluştu. Lütfen daha sonra tekrar dene.\n"
            "Sorun devam ederse yöneticiye bildir."
        )

# ---------- ZAMANLANMIS GOREVLER ----------
async def daily_backup(context: ContextTypes.DEFAULT_TYPE):
    """Gunluk yedekleme"""
    try:
        if not os.path.exists(Config.BACKUP_DIR):
            os.makedirs(Config.BACKUP_DIR)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(Config.BACKUP_DIR, f"backup_{timestamp}.db")
        
        # SQLite backup
        with sqlite3.connect(Config.DB_PATH) as src:
            with sqlite3.connect(backup_path) as dst:
                src.backup(dst)
        
        # Eski yedekleri temizle (son 7 gun)
        cleanup_old_backups()
        
        logger.info(f"Yedekleme tamamlandi: {backup_path}")
        
    except Exception as e:
        logger.error(f"Yedekleme hatasi: {e}")

def cleanup_old_backups():
    """Eski yedekleri temizle"""
    try:
        cutoff = datetime.now() - timedelta(days=7)
        for filename in os.listdir(Config.BACKUP_DIR):
            if filename.startswith("backup_"):
                filepath = os.path.join(Config.BACKUP_DIR, filename)
                file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                if file_time < cutoff:
                    os.remove(filepath)
    except Exception as e:
        logger.error(f"Yedek temizleme hatasi: {e}")

# ---------- MAIN ----------
def main():
    # Klasor yapisi
    os.makedirs(Config.BACKUP_DIR, exist_ok=True)
    
    # Application olustur
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Komut handlerlari
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("yardim", help_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("rapor", monthly_report))
    application.add_handler(CommandHandler("haftalik", weekly_report))
    application.add_handler(CommandHandler("grafik", grafik))
    application.add_handler(CommandHandler("ailem", family_info))
    application.add_handler(CommandHandler("aile_kur", create_family))
    application.add_handler(CommandHandler("aileye_katil", join_family))
    application.add_handler(CommandHandler("butce", set_budget))
    application.add_handler(CommandHandler("durum", budget_status))
    application.add_handler(CommandHandler("premium", premium_info))
    application.add_handler(CommandHandler("export", export_data))
    
    # Callback handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Mesaj handler (harcama girisi)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        add_expense_handler
    ))
    
    # Hata handler
    application.add_error_handler(error_handler)
    
    # Zamanlanmis gorevler
    job_queue = application.job_queue
    if job_queue:
        # Her gun saat 03:00'te yedekle
        job_queue.run_daily(daily_backup, time=time(hour=3, minute=0))
    
    # Baslat
    logger.info("Bot baslatiliyor...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
