# ⚡ Быстрый старт Swamp Git

## Выберите ваш способ установки:

---

## 🔧 Вариант 1: Systemd (Linux с systemd)

```bash
# 1. Клонируйте и настройте
git clone git@github.com:akarmain/swamp_git.git
cd swamp_git
cp exemple.env .env
nano .env  # заполните настройки

# 2. Установите
chmod +x install.sh
./install.sh

# 3. Проверьте
systemctl status swamp-git.timer
```

✅ Готово! Автозапуск через systemd timer.

---

## 📅 Вариант 2: Cron (Универсальный Linux/macOS)

```bash
# 1. Клонируйте и настройте
git clone git@github.com:akarmain/swamp_git.git
cd swamp_git
cp exemple.env .env
nano .env  # заполните настройки

# 2. Установите
chmod +x install_cron.sh
./install_cron.sh

# 3. Проверьте
crontab -l | grep swamp
```

✅ Готово! Автозапуск через cron.

---

## 📝 Что нужно заполнить в .env

```env
# ОБЯЗАТЕЛЬНО:
OPENAI_API_KEY=sk-ваш_ключ_здесь
REPO_URL=git@github.com:username/swamp_git.git
GIT_AUTHOR_NAME=Ваше Имя
GIT_AUTHOR_EMAIL=your@email.com

# Опционально (можно оставить как есть):
OPENAI_BASE_URL=https://api.proxyapi.ru/deepseek/
OPENAI_MODEL=deepseek-chat
TIMEZONE=Europe/Amsterdam
```

---

## 🧪 Тестирование

```bash
# Сделать один коммит прямо сейчас
./test_run.sh

# Или вручную:
source .venv/bin/activate
python source/swamp_git.py gpt-push --count 1
```

---

## 📊 Что будет происходить?

Каждый день в **4:20 МСК** автоматически:
1. 🤖 AI сгенерирует сообщение коммита
2. 📝 Создастся файл с активностью за день
3. 💾 Сделается коммит
4. 🚀 Запушится в GitHub

---

## ❓ Помощь

- **Логи systemd**: `sudo journalctl -u swamp-git.service -f`
- **Логи cron**: `tail -f logs/swamp_git.log`
- **Статус timer**: `systemctl status swamp-git.timer`
- **Cron задачи**: `crontab -l`

---

## 📚 Полная документация

- [README.md](README.md) - основная документация
- [INSTALLATION.md](INSTALLATION.md) - детальная установка

---

**Вопросы?** Создайте issue на GitHub! 🐛
