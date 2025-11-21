#!/bin/bash
# Скрипт удаления Swamp Git systemd timer

set -e

SERVICE_NAME="swamp-git"

echo "🗑️  Удаление Swamp Git timer..."

# Останавливаем и отключаем timer
if systemctl is-enabled "${SERVICE_NAME}.timer" &> /dev/null; then
    echo "⏸️  Останавливаю timer..."
    sudo systemctl stop "${SERVICE_NAME}.timer"
    sudo systemctl disable "${SERVICE_NAME}.timer"
fi

# Удаляем файлы systemd
echo "🗑️  Удаляю systemd файлы..."
sudo rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
sudo rm -f "/etc/systemd/system/${SERVICE_NAME}.timer"

# Перезагружаем systemd
sudo systemctl daemon-reload

echo "✅ Swamp Git timer удален!"
echo ""
echo "ℹ️  Проект и виртуальное окружение остались на месте."
echo "   Для полного удаления выполните: rm -rf $(dirname "${BASH_SOURCE[0]}")"
