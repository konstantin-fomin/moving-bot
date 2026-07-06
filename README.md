# MovingChecklistBot

Telegram-бот для общего чеклиста переезда на владельца и партнёра.

## Возможности

- Первый пользователь, отправивший `/start`, становится владельцем.
- Владелец создаёт одноразовую ссылку для партнёра командой `/invite`.
- Пользователи без валидного приглашения получают вежливый отказ.
- Свободный текст разбирается через Gemini в вещи для покупки, упаковки или важные задачи.
- Сообщения вроде «купила подгузники» отмечают существующую вещь выполненной.
- Кнопка «↩️ Отменить последнее» откатывает последнее действие пользователя.
- База хранится в SQLite: `data/bot.db`.
- Логи пишутся в `logs/bot.log`.

## Структура

```text
.
├── bot.py
├── app/
│   ├── config.py
│   ├── database/
│   ├── handlers/
│   ├── keyboards/
│   ├── middlewares/
│   └── services/
├── tests/
├── docs/
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Настройка

Создайте `.env` в корне проекта:

```env
BOT_TOKEN=1234567890:telegram-bot-token
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.5-flash
TZ=Etc/UTC
```

`.env`, `data/` и `logs/` не коммитятся.

## Установка

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## Запуск

```bash
venv/bin/python bot.py
```

## Docker

```bash
docker compose up -d --build
docker compose logs -f moving-checklist-bot
```

## Проверки

```bash
venv/bin/pytest
find . -path ./venv -prune -o -name '*.py' -print0 | xargs -0 venv/bin/python -m py_compile
docker compose build
```

## Документация

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — устройство проекта.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — разработка и проверки.
- [AGENTS.md](AGENTS.md) — краткий контекст для будущих изменений.
