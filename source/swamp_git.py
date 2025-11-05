#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
swamp_git.py — единый скрипт для авто-ведения репозитория активности
с AI-коммитами и пушем на GitHub/доп. удалённый. Упор на:
- корректного автора (Actor из .env / локального конфига),
- надёжный пуш (SSH, upstream при первом пуше),
- запись файлов за нужную дату (включая бэктейт).

Зависимости:
  python3 -m venv .venv
  source .venv/bin/activate
  pip install gitpython loguru python-dateutil pytz openai python-dotenv

Примеры:
  # Разовая запись активности + коммит/пуш
  python source/swamp_git.py push "Собрал прототип генератора QR"

  # Сгенерировать N AI-коммитов с паузой и бэктейтом по дням
  python source/swamp_git.py gpt-push --count 5 --delay-sec 20 --backdate daily

  # Заполнить конкретные даты
  python source/swamp_git.py fill-missing 2025-10-01,2025-10-02,2025-10-04
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

from dotenv import load_dotenv
from dateutil.relativedelta import relativedelta
from loguru import logger
from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Actor

# --- AI (OpenAI-совместимый клиент) ---
try:
    from openai import OpenAI  # openai>=1.0
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

# === Загрузка .env (из каталога скрипта) ===
_SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(_SCRIPT_DIR / ".env")
load_dotenv()  # на всякий случай (если запускают из другого места)

# --- Конфигурация ---
DEFAULTS = {
    "REPO_PATH": str((_SCRIPT_DIR / "../cache/swamp_git").resolve()),
    "BRANCH": "main",
    "SECONDARY_REMOTE_NAME": "gitlab",
    "FORCE_PUSH_SECONDARY": "1",
    "TIMEZONE": "Europe/Amsterdam",
    "OPENAI_BASE_URL": "https://api.proxyapi.ru/deepseek/",
    "OPENAI_MODEL": "deepseek-chat",
}

AI_PROMPT = (
    "Ты — генератор коротких git-commit messages для проекта QR-IN "
    "(сервис генерации динамических QR + аналитика).\n\n"
    "Правила:\n"
    "- русский язык (если не указано другое)\n"
    "- длина ≤200 символов\n"
    "- 1 сообщение, без скобок, без объяснений задачи\n"
    "- стиль: лёгкий, оптимистичный, ироничный ИЛИ полностью серьёзный\n"
    "- обязательно 1–2 уместных эмодзи в конце\n"
    "- тематика — работа разработчика в QR-IN: frontend/backend/devops/архитектура/инфраструктура/ML/боты/UTM/аналитика\n"
    "- коммит выглядит как личная маленькая заметка дня разработчика\n"
    "- желательно использовать названия технологий, тесты, API, базы, QR форматы\n"
    "- каждый коммит связан с QR-IN (фича/фикс/инфра/тест/идея)\n\n"
    "Режим: выдай 1 короткий commit message (только текст)."
)

# --- Настройки ---

@dataclass
class Settings:
    repo_url: str
    repo_path: str = DEFAULTS["REPO_PATH"]
    branch: str = DEFAULTS["BRANCH"]
    secondary_remote_name: str = DEFAULTS["SECONDARY_REMOTE_NAME"]
    secondary_remote_url: Optional[str] = None
    force_push_secondary: bool = DEFAULTS["FORCE_PUSH_SECONDARY"] == "1"
    timezone: str = DEFAULTS["TIMEZONE"]

    # Автор коммитов
    author_name: str = os.getenv("GIT_AUTHOR_NAME", "")
    author_email: str = os.getenv("GIT_AUTHOR_EMAIL", "")

    # AI
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", DEFAULTS["OPENAI_BASE_URL"])
    openai_model: str = os.getenv("OPENAI_MODEL", DEFAULTS["OPENAI_MODEL"])


def load_settings(repo_url_arg: Optional[str]) -> Settings:
    repo_url = repo_url_arg or os.getenv("REPO_URL")
    if not repo_url:
        raise SystemExit("Не задан REPO_URL и не передан --repo-url (используй SSH: git@github.com:USER/REPO.git)")

    return Settings(
        repo_url=repo_url,
        repo_path=os.getenv("REPO_PATH", DEFAULTS["REPO_PATH"]),
        branch=os.getenv("BRANCH", DEFAULTS["BRANCH"]),
        secondary_remote_name=os.getenv("SECONDARY_REMOTE_NAME", DEFAULTS["SECONDARY_REMOTE_NAME"]),
        secondary_remote_url=os.getenv("SECONDARY_REMOTE_URL") or None,
        force_push_secondary=os.getenv("FORCE_PUSH_SECONDARY", DEFAULTS["FORCE_PUSH_SECONDARY"]) == "1",
        timezone=os.getenv("TIMEZONE", DEFAULTS["TIMEZONE"]),
        author_name=os.getenv("GIT_AUTHOR_NAME", ""),
        author_email=os.getenv("GIT_AUTHOR_EMAIL", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", DEFAULTS["OPENAI_BASE_URL"]),
        openai_model=os.getenv("OPENAI_MODEL", DEFAULTS["OPENAI_MODEL"]),
    )

# --- Git helpers ---

def ensure_repo(repo_path: str, git_url: str) -> Repo:
    try:
        if not os.path.exists(repo_path):
            logger.info("Клонирую репозиторий...")
            return Repo.clone_from(git_url, repo_path)
        return Repo(repo_path)
    except (InvalidGitRepositoryError, NoSuchPathError):
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        logger.info("Пере-клонирую репозиторий...")
        return Repo.clone_from(git_url, repo_path)


def ensure_remote_url(repo: Repo, expected_url: str, name: str = "origin") -> None:
    """Гарантируем корректный URL удалённого (по умолчанию origin)."""
    remotes = {r.name: r for r in repo.remotes}
    if name not in remotes:
        repo.create_remote(name, expected_url)
        logger.info(f"Добавлен remote '{name}' → {expected_url}")
        return
    current = list(remotes[name].urls)[0]
    if current != expected_url:
        logger.info(f"Обновляю remote '{name}' URL:\n  {current}\n→ {expected_url}")
        repo.git.remote("set-url", name, expected_url)


def sync_with_origin(repo: Repo, branch: str) -> None:
    """Надёжная синхронизация локальной ветки с origin/<branch>.
    Обрабатывает случаи: нет удалённой ветки; нет локальной ветки; detached HEAD.
    """
    logger.info(f"Синхронизация с origin/{branch}...")
    repo.git.fetch("--all", "--prune")

    def remote_branch_exists() -> bool:
        try:
            out = repo.git.ls_remote("--heads", "origin", branch)
            return bool(out.strip())
        except GitCommandError:
            return False

    if remote_branch_exists():
        repo.git.checkout("-B", branch, f"origin/{branch}")
        repo.git.reset("--hard", f"origin/{branch}")
        return

    # Удалённой ветки нет: создаём/переключаем локальную
    local_branches = [h.name for h in repo.heads]
    if branch in local_branches:
        repo.git.checkout(branch)
    else:
        repo.git.checkout("-B", branch)


def _ensure_repo_identity(repo: Repo, settings: Settings) -> Actor:
    """
    Возвращает Actor для автора/коммитера и параллельно
    записывает user.name/user.email в локальный config репозитория.
    Источники: .env (GIT_AUTHOR_NAME/EMAIL) → локальный конфиг → ошибка.
    """
    name = settings.author_name
    email = settings.author_email

    if not name or not email:
        try:
            cr = repo.config_reader()
            name = name or cr.get_value("user", "name")
            email = email or cr.get_value("user", "email")
        except Exception:
            pass

    if not name or not email:
        raise SystemExit(
            "Не задан автор коммитов. Укажи GIT_AUTHOR_NAME и GIT_AUTHOR_EMAIL в .env "
            "или пропиши user.name/user.email в репозитории."
        )

    try:
        with repo.config_writer() as cw:
            cw.set_value("user", "name", name)
            cw.set_value("user", "email", email)
    except Exception:
        pass

    return Actor(name, email)


def update_activity_file(repo_path: str, timezone: str, activity: str, when: Optional[dt.datetime] = None) -> str:
    """Создаёт/дополняет файл за дату `when` (локальная TZ). Если when=None — берём текущее время."""
    import pytz
    tz = pytz.timezone(timezone)
    now = when.astimezone(tz) if when else dt.datetime.now(tz)

    dir_path = Path(repo_path) / now.strftime("%Y") / now.strftime("%m")
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{now.strftime('%d')}.md"

    if not file_path.exists() or file_path.stat().st_size == 0:
        header = f"# {now.strftime('%d.%m.%y')}\n\n{activity}\n"
        file_path.write_text(header, encoding="utf-8")
    else:
        upd = f"\n<hr>\n\n_UPD ({now.strftime('%H:%M')}):_\n\n{activity}\n"
        with file_path.open("a", encoding="utf-8") as f:
            f.write(upd)

    return str(file_path)


def commit_and_push(
    repo: Repo,
    settings: Settings,
    branch: str,
    message: str,
    secondary_remote_name: Optional[str],
    force_push_secondary: bool,
    author_date: Optional[str] = None,
    committer_date: Optional[str] = None,
) -> None:
    """
    Коммит ЗА УКАЗАННОГО АВТОРА (Actor) и пуш. При первом пуше — set-upstream.
    """
    ensure_remote_url(repo, settings.repo_url, "origin")
    if settings.secondary_remote_url:
        ensure_remote_url(repo, settings.secondary_remote_url, settings.secondary_remote_name)
    repo.git.checkout("-B", branch)

    author_actor = _ensure_repo_identity(repo, settings)

    repo.git.add(A=True)

    if repo.is_dirty(index=True, working_tree=True, untracked_files=True):
        kwargs = {}
        if author_date:
            kwargs["author_date"] = author_date
        if committer_date:
            kwargs["commit_date"] = committer_date

        repo.index.commit(
            message,
            author=author_actor,
            committer=author_actor,
            **kwargs,
        )
    else:
        logger.info("Нечего коммитить — рабочее дерево чистое")

    # Пуш (с созданием апстрима при необходимости)
    try:
        tracking = None
        try:
            tracking = repo.active_branch.tracking_branch()
        except Exception:
            tracking = None

        if tracking is None:
            logger.info("Ветка без апстрима — делаю set-upstream → origin")
            repo.git.push("--set-upstream", "origin", branch)
        else:
            repo.git.push("origin", branch)
    except GitCommandError as e:
        logger.error(f"Пуш в origin провалился: {e}")
        raise

    if secondary_remote_name and secondary_remote_name in [r.name for r in repo.remotes]:
        try:
            if force_push_secondary:
                repo.git.push(secondary_remote_name, branch, "--force")
            else:
                repo.git.push(secondary_remote_name, branch)
        except GitCommandError as e:
            logger.error(f"Пуш в '{secondary_remote_name}' провалился: {e}")

# --- AI ---

def build_ai_client(settings: Settings):
    if OpenAI is None:
        raise RuntimeError("Модуль 'openai' недоступен. Установите: pip install openai")
    if not settings.openai_api_key:
        raise RuntimeError("Не задан OPENAI_API_KEY")

    default_headers = None
    if "openrouter.ai" in (settings.openai_base_url or ""):
        default_headers = {
            "HTTP-Referer": "https://github.com/akarmain/swamp_git",
            "X-Title": "swamp_git automation",
        }

    return OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        default_headers=default_headers,
    )


def generate_ai_commit_text(settings: Settings, context: Optional[str] = None) -> str:
    client = build_ai_client(settings)
    sys = "Ты — лаконичный генератор commit messages."
    user = AI_PROMPT
    if context:
        user += f"\nКонтекст: {context}\n"

    chat = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
        temperature=0.9,
    )
    text = chat.choices[0].message.content.strip()
    return text[:220].rstrip()

# --- Даты для бэктейта ---

def compute_backdated_when(timezone: str, scheme: Optional[str], index: int) -> dt.datetime:
    import pytz
    tz = pytz.timezone(timezone)
    base = dt.datetime.now(tz)

    delta = relativedelta()
    if scheme == "hourly":
        delta = relativedelta(hours=index)
    elif scheme == "daily":
        delta = relativedelta(days=index)
    elif scheme == "weekly":
        delta = relativedelta(weeks=index)

    when = base - delta
    return when.replace(hour=12, minute=0, second=0, microsecond=0)

# --- Операции ---

def op_push(settings: Settings, text: str) -> None:
    repo = ensure_repo(settings.repo_path, settings.repo_url)
    sync_with_origin(repo, settings.branch)

    file_path = update_activity_file(settings.repo_path, settings.timezone, text)
    logger.info(f"Обновлён файл активности: {file_path}")

    msg = f"Update activities for {dt.date.today().isoformat()} — {uuid.uuid4().hex[:6]}"
    commit_and_push(
        repo,
        settings,
        settings.branch,
        msg,
        settings.secondary_remote_name if settings.secondary_remote_url else None,
        settings.force_push_secondary,
    )


def op_gpt_push(
    settings: Settings,
    count: int = 1,
    delay_sec: int = 0,
    context: Optional[str] = None,
    backdate: Optional[str] = None,
) -> None:
    repo = ensure_repo(settings.repo_path, settings.repo_url)
    sync_with_origin(repo, settings.branch)

    import pytz
    tz = pytz.timezone(settings.timezone)
    base = dt.datetime.now(tz).replace(hour=12, minute=0, second=0, microsecond=0)

    for i in range(count):
        when = base if not backdate else compute_backdated_when(settings.timezone, backdate, i)

        text_commit = generate_ai_commit_text(settings, context=context)
        file_path = update_activity_file(settings.repo_path, settings.timezone, text_commit, when=when)
        logger.info(f"[{i+1}/{count}] Обновлён файл: {file_path}")

        iso = when.strftime("%Y-%m-%d %H:%M:%S %z")
        msg = f"Update activities for {when.date().isoformat()}"

        commit_and_push(
            repo,
            settings,
            settings.branch,
            msg,
            settings.secondary_remote_name if settings.secondary_remote_url else None,
            settings.force_push_secondary,
            author_date=iso,
            committer_date=iso,
        )

        if i < count - 1 and delay_sec > 0:
            time.sleep(delay_sec)


def fill_missing_days(settings: Settings, missing_dates: List[str]) -> None:
    """Для каждой даты генерируем текст, пишем файл за эту дату и делаем backdated commit."""
    import pytz
    tz = pytz.timezone(settings.timezone)

    repo = ensure_repo(settings.repo_path, settings.repo_url)
    sync_with_origin(repo, settings.branch)

    for d in missing_dates:
        when = tz.localize(dt.datetime.strptime(d, "%Y-%m-%d").replace(hour=12, minute=0, second=0, microsecond=0))
        text_commit = generate_ai_commit_text(settings, context=f"день {d} для QR-IN")
        file_path = update_activity_file(settings.repo_path, settings.timezone, text_commit, when=when)
        logger.info(f"Дата {d} → файл обновлён: {file_path}")

        iso = when.strftime("%Y-%m-%d %H:%M:%S %z")
        msg = f"Update activities for {when.date().isoformat()}"

        commit_and_push(
            repo,
            settings,
            settings.branch,
            msg,
            settings.secondary_remote_name if settings.secondary_remote_url else None,
            settings.force_push_secondary,
            author_date=iso,
            committer_date=iso,
        )

# --- CLI ---

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Swamp Git — авто-коммиты с AI и пуш в Git.")
    p.add_argument("--repo-url", help="git URL репозитория (если не задан REPO_URL)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp1 = sub.add_parser("push", help="Записать текст и сделать обычный коммит/пуш")
    sp1.add_argument("text", help="Текст активности/коммита")

    sp2 = sub.add_parser("gpt-push", help="Сгенерировать AI-коммит(ы) и запушить")
    sp2.add_argument("--count", type=int, default=1, help="Сколько коммитов сделать (по умолчанию 1)")
    sp2.add_argument("--delay-sec", type=int, default=0, help="Пауза между коммитами, сек")
    sp2.add_argument("--context", type=str, default=None, help="Краткий контекст для AI")
    sp2.add_argument(
        "--backdate",
        choices=["hourly", "daily", "weekly"],
        help="Бэктейтинг дат коммитов: на час/день/неделю назад для каждого следующего",
    )

    sp3 = sub.add_parser("fill-missing", help="Сделать коммиты за конкретные прошлые даты (через запятую)")
    sp3.add_argument("dates", help="Напр.: 2025-10-01,2025-10-02,2025-10-04")

    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    settings = load_settings(args.repo_url)
    try:
        _ = Repo.init(settings.repo_path).config_reader().get_value("user", "name")  # type: ignore
    except Exception:
        os.system('git config --global user.name  "swamp_git"')
        os.system('git config --global user.email "swamp_git@example.local"')

    if args.cmd == "push":
        op_push(settings, args.text)
    elif args.cmd == "gpt-push":
        op_gpt_push(
            settings,
            count=args.count,
            delay_sec=args.delay_sec,
            context=args.context,
            backdate=args.backdate,
        )
    elif args.cmd == "fill-missing":
        dates = [d.strip() for d in args.dates.split(",") if d.strip()]
        fill_missing_days(settings, dates)
    else:
        raise SystemExit("Неизвестная команда")


if __name__ == "__main__":
    main()
