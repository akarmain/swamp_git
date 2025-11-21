#!/bin/bash
# Тестовый запуск Swamp Git

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -f .env ]; then
    echo "❌ Файл .env не найден!"
    exit 1
fi

if [ ! -d .venv ]; then
    echo "❌ Виртуальное окружение не найдено! Запустите install.sh"
    exit 1
fi

echo "🧪 Тестовый запуск Swamp Git..."
echo ""

source .venv/bin/activate
python source/swamp_git.py gpt-push --count 1

echo ""
echo "✅ Тестовый запуск завершен!"
