#!/bin/bash
# Скрипт установки Swamp Git для автоматических коммитов в 4:20 МСК

set -e

echo "🌀 Установка Swamp Git..."

# Определяем директорию проекта
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Проверяем наличие .env
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден!"
    echo "📝 Скопируйте exemple.env в .env и заполните настройки:"
    echo "   cp exemple.env .env"
    echo "   nano .env"
    exit 1
fi

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не установлен!"
    exit 1
fi

echo "✅ Python найден: $(python3 --version)"

# Создаем виртуальное окружение
if [ ! -d .venv ]; then
    echo "📦 Создаю виртуальное окружение..."
    python3 -m venv .venv
fi

# Активируем и устанавливаем зависимости
echo "📦 Устанавливаю зависимости..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Создаем systemd service
SERVICE_NAME="swamp-git"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
TIMER_FILE="/etc/systemd/system/${SERVICE_NAME}.timer"

echo "🔧 Создаю systemd service и timer..."

# Создаем service файл
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Swamp Git Daily Commit
After=network.target

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python $PROJECT_DIR/source/swamp_git.py gpt-push --count 1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Создаем timer файл (4:20 по МСК = 01:20 UTC)
sudo tee "$TIMER_FILE" > /dev/null << EOF
[Unit]
Description=Swamp Git Daily Timer (4:20 MSK)
Requires=${SERVICE_NAME}.service

[Timer]
# Запуск каждый день в 01:20 UTC (4:20 МСК)
OnCalendar=*-*-* 01:20:00
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
EOF

# Перезагружаем systemd и включаем timer
echo "🔄 Перезагружаю systemd daemon..."
sudo systemctl daemon-reload

echo "▶️  Включаю и запускаю timer..."
sudo systemctl enable "${SERVICE_NAME}.timer"
sudo systemctl start "${SERVICE_NAME}.timer"

# Показываем статус
echo ""
echo "✅ Установка завершена!"
echo ""
echo "📊 Статус timer:"
sudo systemctl status "${SERVICE_NAME}.timer" --no-pager
echo ""
echo "⏰ Следующий запуск:"
systemctl list-timers --no-pager | grep swamp-git
echo ""
echo "📝 Полезные команды:"
echo "   Просмотр логов:      sudo journalctl -u ${SERVICE_NAME}.service -f"
echo "   Статус timer:        sudo systemctl status ${SERVICE_NAME}.timer"
echo "   Остановить timer:    sudo systemctl stop ${SERVICE_NAME}.timer"
echo "   Отключить timer:     sudo systemctl disable ${SERVICE_NAME}.timer"
echo "   Ручной запуск:       sudo systemctl start ${SERVICE_NAME}.service"
echo "   Тестовый запуск:     $PROJECT_DIR/.venv/bin/python $PROJECT_DIR/source/swamp_git.py gpt-push --count 1"
echo ""
