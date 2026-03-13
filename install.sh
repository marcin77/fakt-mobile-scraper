#!/bin/bash
set -e

echo "📦 Instalacja Fakt Mobile Scraper"
echo "══════════════════════════════════"

# Zależności
pip3 install -r requirements.txt

# Config
if [ ! -f config.py ]; then
    cp config.example.py config.py
    echo ""
    echo "✏️  Uzupełnij dane w config.py:"
    echo "   nano config.py"
    echo ""
fi

# Test
echo "🧪 Test:"
python3 scraper.py --once

# Cron
echo ""
read -p "Dodać crona (6:00, 12:00, 18:00)? [y/N] " answer
if [ "$answer" = "y" ]; then
    SCRIPT_DIR=$(pwd)
    PYTHON_PATH=$(which python3)
    CRON_LINE="0 6,12,18 * * * cd $SCRIPT_DIR && $PYTHON_PATH scraper.py --once >> $SCRIPT_DIR/cron.log 2>&1"

    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo "✅ Cron dodany:"
    echo "   $CRON_LINE"
fi

echo ""
echo "✅ Gotowe!"
