# AGENTS.md

Краткий контекст для будущей работы Codex в этом репозитории.

## Проект

Telegram-бот на Python и aiogram 3.x для организации переезда. Доступ рассчитан на двух пользователей: первый `/start` создаёт владельца, партнёр входит по одноразовому приглашению.

## Важные команды

```bash
venv/bin/python bot.py
docker compose up -d --build
docker compose logs -f moving-checklist-bot
venv/bin/pytest
find . -path ./venv -prune -o -name '*.py' -print0 | xargs -0 venv/bin/python -m py_compile
```

## Важные файлы

- `bot.py` — entrypoint.
- `app/config.py` — `.env`, `BOT_TOKEN`, `GEMINI_API_KEY`, модель Gemini, путь к базе.
- `app/database/storage.py` — SQLite-схема, пользователи, приглашения, чеклист, undo log.
- `app/handlers/start.py` — `/start`, owner/member flow.
- `app/handlers/invitations.py` — `/invite`.
- `app/handlers/checklist.py` — кнопки, свободный текст, откат.
- `app/services/gemini.py` — официальный SDK `google-genai`, системный промпт и JSON parsing.
- `app/services/formatting.py` — форматирование списков и подтверждений.
- `tests/` — тесты базы, приглашений, Gemini parsing, undo и форматирования.
- `Dockerfile`, `docker-compose.yml`, `.dockerignore` — контейнерный запуск.

## Инварианты

- Не перезаписывать и не коммитить `.env`.
- Не коммитить `venv/`, `data/`, `logs/`, кэши Python и pytest.
- Все тексты бота должны быть на русском.
- Первый пользователь становится `owner`.
- Остальные без валидного приглашения получают отказ.
- Приглашения одноразовые.
- Реальные запросы к Gemini в тестах запрещены.

## Стиль изменений

- Сохранять модульную структуру `handlers`, `database`, `keyboards`, `services`.
- Хендлеры держать тонкими: доступ, вызов сервиса/базы, ответ.
- Для новой бизнес-логики добавлять тесты.
- Перед коммитом запускать `venv/bin/pytest`, py_compile и `docker compose build`.
