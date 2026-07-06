import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import load_config
from app.database.storage import Database
from app.handlers import setup_routers
from app.logging_config import setup_logging
from app.middlewares import LoggingMiddleware
from app.services.gemini import GeminiChecklistParser


logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config()
    setup_logging()

    database = Database(config.database_path)
    await database.connect()
    await database.init_schema()

    parser = GeminiChecklistParser(
        api_key=config.gemini_api_key,
        model=config.gemini_model,
    )

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher["db"] = database
    dispatcher["parser"] = parser
    dispatcher.message.outer_middleware(LoggingMiddleware())
    dispatcher.callback_query.outer_middleware(LoggingMiddleware())
    setup_routers(dispatcher)

    try:
        logger.info("Запускаю polling moving-checklist-bot")
        await dispatcher.start_polling(bot)
    finally:
        await database.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
