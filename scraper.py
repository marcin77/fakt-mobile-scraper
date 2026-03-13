#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fakt Mobile Code Scraper
Monitoruje forum telepolis.pl i wysyła nowe kody na Telegram.
"""

import requests
import re
import time
import sqlite3
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import sys
import os

try:
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
except ImportError:
    print("❌ Brak pliku config.py")
    print("   Skopiuj: cp config.example.py config.py")
    print("   Uzupełnij dane w config.py")
    sys.exit(1)

# ══════════════════════════════════════════
# KONFIGURACJA
# ══════════════════════════════════════════
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codes.db")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper.log")
CHECK_INTERVAL = 21600 # 6 godzin

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

FALSE_POSITIVES = frozenset({
    'USSD', 'FAKT', 'HTTP', 'HTML', 'PLAY', 'PLUS',
    'CODE', 'PROMO', 'ZERO', 'FREE', 'HOME', 'WORK',
    'CALL', 'TEXT', 'DATA', 'TIME', 'GOLD', 'SPEC',
    'MINI', 'NANO', 'CARD', 'FILE', 'EDIT', 'VIEW',
    'POST', 'USER', 'RANK', 'ABCD', 'EFGH', 'IJKL',
    'MNOP', 'QRST', 'UVWX',
})


class CodeScraper:
    def __init__(self):
        self.init_db()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
            )
        })

    def init_db(self):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sent_codes (
                    code TEXT PRIMARY KEY,
                    date_sent TEXT,
                    post_date TEXT
                )
            ''')

    def is_code_sent(self, code):
        with sqlite3.connect(DB_FILE) as conn:
            return conn.execute(
                "SELECT 1 FROM sent_codes WHERE code=?", (code,)
            ).fetchone() is not None

    def mark_code_sent(self, code, post_date=""):
        with sqlite3.connect(DB_FILE) as conn:
            try:
                conn.execute(
                    "INSERT INTO sent_codes (code, date_sent, post_date) "
                    "VALUES (?, ?, ?)",
                    (code, datetime.now().isoformat(), post_date)
                )
            except sqlite3.IntegrityError:
                pass

    # ──────────────────────────────────────
    # WYKRYWANIE KODÓW
    # ──────────────────────────────────────
    def extract_description(self, context):
        """Wyciąga opis: 10 SMS, 10 minut, 50 MB."""
        patterns = [
            (r'(\d+)\s*(?:MB|mb)', lambda m: f"🌐 {m.group(1)} MB internetu"),
            (r'(\d+)\s*(?:GB|gb)', lambda m: f"🌐 {m.group(1)} GB internetu"),
            (r'(\d+)\s*(?:minut|MIN|min)', lambda m: f"📞 {m.group(1)} minut"),
            (r'(\d+)\s*(?:sms|SMS)', lambda m: f"📱 {m.group(1)} SMS"),
        ]
        for pattern, formatter in patterns:
            m = re.search(pattern, context)
            if m:
                return formatter(m)
        return "🎫 Kod"

    def extract_codes(self, post_element):
        """Wyciąga kody + opis z posta."""
        content = post_element.find('div', class_='content')
        if not content:
            content = post_element

        text = content.get_text()
        codes = []
        seen = set()

        for match in re.finditer(r'\b([A-Z]{4})\b', text):
            code = match.group(1)
            if code in FALSE_POSITIVES or code in seen:
                continue

            start = max(0, match.start() - 120)
            end = min(len(text), match.end() + 60)
            context = text[start:end]
            context_lower = context.lower()

            keywords = [
                'kod', 'sms', 'min', 'mb', 'gb',
                'wyślij', 'wyslij', '4949',
                'internet', 'minut', 'darmow', 'pakiet',
                'to ', '->', '>>'
            ]

            if any(kw in context_lower for kw in keywords):
                seen.add(code)
                codes.append({
                    'code': code,
                    'description': self.extract_description(context),
                })

        return codes

    # ──────────────────────────────────────
    # SCRAPING
    # ──────────────────────────────────────
    def get_last_page_number(self):
        try:
            resp = self.session.get(https://www.telepolis.pl/forum/viewtopic.php?f=76&t=82383&start= + "0", timeout=30)
            soup = BeautifulSoup(resp.text, 'html.parser')
            pagination = soup.find('ul', class_='pagination')
            if not pagination:
                return 86

            max_start = 0
            for link in pagination.find_all('a', href=True):
                m = re.search(r'start=(\d+)', link['href'])
                if m:
                    max_start = max(max_start, int(m.group(1)))
            return max_start // 20 if max_start else 86

        except Exception as e:
            logging.error(f"Błąd paginacji: {e}")
            return 86

    def scrape_latest(self):
        """Scrapuje najnowszą stronę, zwraca nowe kody."""
        page_num = self.get_last_page_number()
        url = f"{https://www.telepolis.pl/forum/viewtopic.php?f=76&t=82383&start=}{page_num * 20}"
        logging.info(f"Scrapuję: {url}")

        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')

            posts = soup.find_all('div', class_='postbody')
            if not posts:
                posts = soup.find_all('div', {'id': re.compile(r'^p\d+')})

            new_codes = []

            for post in reversed(posts):
                text = post.get_text(strip=True)
                if len(text) < 20:
                    continue

                post_date = ""
                date_el = post.find('div', class_='timepost')
                if date_el:
                    dm = re.search(
                        r'(\d{1,2}\s+\w+\s+\d{4})', date_el.get_text()
                    )
                    if dm:
                        post_date = dm.group(1)

                for item in self.extract_codes(post):
                    code = item['code']
                    if not self.is_code_sent(code):
                        item['date'] = post_date
                        new_codes.append(item)
                        self.mark_code_sent(code, post_date)
                        logging.info(f"✅ {code} → {item['description']}")

            return new_codes

        except Exception as e:
            logging.error(f"Błąd: {e}")
            return []

    # ──────────────────────────────────────
    # TELEGRAM
    # ──────────────────────────────────────
    def send_code(self, code_info):
        """Wysyła jeden kod z przyciskiem kopiowania."""
        text = (
            f"{code_info['description']}\n"
            f"{'─' * 22}\n"
            f"Wyślij SMS na 4949 z treścią:\n\n"
            f"<b>{code_info['code']}</b>\n"
        )
        if code_info.get('date'):
            text += f"\n📅 {code_info['date']}"

        keyboard = {
            "inline_keyboard": [[{
                "text": f"📋 Kopiuj {code_info['code']}",
                "copy_text": {"text": code_info['code']}
            }]]
        }

        self._send_telegram(text, keyboard)

    def send_multiple(self, codes):
        """Wysyła wiele kodów z przyciskami."""
        now = datetime.now().strftime("%H:%M")

        text = f"🔔 <b>Nowe kody ({now})</b>\nSMS na <b>4949</b>\n{'─' * 22}\n\n"

        buttons = []
        for c in codes:
            text += f"{c['description']}: <b>{c['code']}</b>\n"
            if c.get('date'):
                text += f"  📅 {c['date']}\n"
            text += "\n"

            buttons.append([{
                "text": f"📋 Kopiuj {c['code']} ({c['description']})",
                "copy_text": {"text": c['code']}
            }])

        keyboard = {"inline_keyboard": buttons}
        self._send_telegram(text, keyboard)

    def _send_telegram(self, text, reply_markup=None):
        if "WPISZ" in TELEGRAM_BOT_TOKEN:
            clean = re.sub(r'<[^>]+>', '', text)
            print(f"\n{clean}")
            return

        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True,
            }
            if reply_markup:
                data['reply_markup'] = reply_markup

            resp = requests.post(url, json=data, timeout=30)
            resp.raise_for_status()
            logging.info("✅ Wysłano")
        except Exception as e:
            logging.error(f"Telegram błąd: {e}")
            if reply_markup:
                data.pop('reply_markup', None)
                try:
                    requests.post(url, json=data, timeout=30)
                except:
                    pass

    # ──────────────────────────────────────
    # PĘTLA
    # ──────────────────────────────────────
    def run_once(self):
        logging.info("Sprawdzam...")
        codes = self.scrape_latest()

        if codes:
            if len(codes) == 1:
                self.send_code(codes[0])
            else:
                self.send_multiple(codes[:5])
            logging.info(f"Wysłano {len(codes)} kodów")
        else:
            logging.info("Brak nowych")

    def run_continuous(self):
        logging.info("Start monitorowania")
        while True:
            try:
                self.run_once()
                time.sleep(CHECK_INTERVAL)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error(f"Błąd: {e}")
                time.sleep(60)


def main():
    scraper = CodeScraper()

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        scraper.run_once()
    else:
        scraper.run_continuous()


if __name__ == "__main__":
    main()
