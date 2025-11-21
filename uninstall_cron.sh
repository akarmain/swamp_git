#!/bin/bash
# Удаление cron задачи Swamp Git

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_SCRIPT="$PROJECT_DIR/cron_runner.sh"

echo "🗑️  Удаление Swamp Git из cron..."

# Удаляем задачу из crontab
if crontab -l 2>/dev/null | grep -F "$CRON_SCRIPT" > /dev/null; then
    echo "📅 Удаляю задачу из crontab..."
    crontab -l | grep -v -F "$CRON_SCRIPT" | crontab -
    echo "✅ Задача удалена из crontab"
else
    echo "⚠️  Задача не найдена в crontab"
fi

# Удаляем скрипт-обертку
if [ -f "$CRON_SCRIPT" ]; then
    rm "$CRON_SCRIPT"
    echo "✅ Скрипт cron_runner.sh удален"
fi

echo ""
echo "✅ Swamp Git удален из cron!"
echo ""
echo "ℹ️  Проект и логи остались на месте."
echo "   Для полного удаления: rm -rf $PROJECT_DIR"
