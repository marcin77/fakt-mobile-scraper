# 📱 Fakt Mobile Code Scraper

Monitoruje forum [telepolis.pl](https://www.telepolis.pl/forum/viewtopic.php?f=76&t=82383)
i wysyła nowe kody Fakt Mobile na Telegram.

Kody dotyczą darmowych pakietów:
- 📱 SMS
- 📞 Minuty
- 🌐 Internet (MB/GB)

## Szybki start

```bash
git clone https://github.com/USER/fakt-mobile-scraper.git
cd fakt-mobile-scraper
chmod +x install.sh
./install.sh
```
## Ręczna instalacja

```
pip3 install -r requirements.txt
cp config.example.py config.py
nano config.py  # uzupełnij token i chat_id
```

## Konfiguracja Telegram

1. Napisz do @BotFather → /newbot
2. Skopiuj token do config.py
3. Napisz do @userinfobot → skopiuj chat ID
4. Napisz cokolwiek do swojego bota (żeby aktywować czat)

## Użycie

```
# Jednorazowe sprawdzenie
python3 scraper.py --once

# Ciągłe monitorowanie (co 5 min)
python3 scraper.py
```

## Cron (zalecane)

```
crontab -e
```

```cron
0 6,12,18 * * * cd /root/fakt && /usr/bin/python3 scraper.py --once >> /root/fakt/cron.log 2>&1
```

## Jak działa

1. Pobiera najnowszą stronę wątku na forum
2. Szuka kodów (4 wielkie litery) w kontekście słów kluczowych
3. Nowe kody wysyła na Telegram z przyciskiem kopiowania
4. Zapisuje wysłane kody w SQLite żeby nie powtarzać


## Przykład wiadomości

```text

📞 10 minut
──────────────────────
Wyślij SMS na 4949 z treścią:

XKMP

📅 15 stycznia 2025

┌──────────────────────┐
│  📋 Kopiuj XKMP      │
└──────────────────────┘
```