# Разработка

## Локальная среда

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Файл `.env` должен лежать в корне проекта:

```env
BOT_TOKEN=1234567890:telegram-bot-token
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.5-flash
TZ=Etc/UTC
```

Не коммитить `.env`, `venv/`, `data/`, `logs/`, `__pycache__/`, `.pytest_cache/`.

## Запуск

```bash
venv/bin/python bot.py
```

## Docker

```bash
docker compose up -d --build
docker compose logs -f moving-checklist-bot
```

Контейнер использует `.env` через `env_file`, а `data/` и `logs/` монтируются с хоста.

## Проверки

```bash
venv/bin/pytest
find . -path ./venv -prune -o -name '*.py' -print0 | xargs -0 venv/bin/python -m py_compile
docker compose build
```

## Правила изменений

- Все пользовательские тексты держать на русском.
- Вызовы Gemini держать только в `app/services/gemini.py`.
- В тестах не делать реальные запросы к Gemini.
- SQL-логику держать в `app/database/`.
- Повторяемую доменную логику держать в `app/services/`.
- Перед публикацией запускать pytest, py_compile и docker build.
