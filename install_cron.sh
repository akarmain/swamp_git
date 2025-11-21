#!/bin/bash
# Установка Swamp Git с использованием cron (альтернатива systemd)

set -e

echo "🌀 Установка Swamp Git (cron версия)..."

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

# Создаем скрипт-обертку для cron
CRON_SCRIPT="$PROJECT_DIR/cron_runner.sh"
cat > "$CRON_SCRIPT" << 'EOF'
#!/bin/bash
# Обертка для запуска из cron

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Загружаем .env
export $(cat .env | grep -v '^#' | xargs)

# Активируем venv и запускаем
source .venv/bin/activate
python source/swamp_git.py gpt-push --count 1 >> "$PROJECT_DIR/logs/swamp_git.log" 2>&1

# Опционально: очистка старых логов (старше 30 дней)
find "$PROJECT_DIR/logs" -name "*.log" -mtime +30 -delete
EOF

chmod +x "$CRON_SCRIPT"

# Создаем директорию для логов
mkdir -p "$PROJECT_DIR/logs"

# Добавляем задачу в crontab
CRON_JOB="20 1 * * * $CRON_SCRIPT"

# Проверяем, не добавлена ли уже задача
if crontab -l 2>/dev/null | grep -F "$CRON_SCRIPT" > /dev/null; then
    echo "⚠️  Задача cron уже существует, пропускаю..."
else
    echo "📅 Добавляю задачу в crontab..."
    # Сохраняем текущий crontab, добавляем новую задачу
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
fi

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📊 Информация:"
echo "   Путь к проекту:     $PROJECT_DIR"
echo "   Скрипт запуска:     $CRON_SCRIPT"
echo "   Логи:               $PROJECT_DIR/logs/swamp_git.log"
echo "   Расписание:         Каждый день в 4:20 МСК (01:20 UTC)"
echo ""
echo "📝 Ваши cron задачи:"
crontab -l | grep -F "$CRON_SCRIPT" || echo "   (не найдено)"
echo ""
echo "📝 Полезные команды:"
echo "   Просмотр crontab:    crontab -l"
echo "   Редактировать cron:  crontab -e"
echo "   Просмотр логов:      tail -f $PROJECT_DIR/logs/swamp_git.log"
echo "   Ручной запуск:       $CRON_SCRIPT"
echo "   Тестовый запуск:     ./test_run.sh"
echo ""
