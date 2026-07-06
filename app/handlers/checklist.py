from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message

from app.database import Category, Database
from app.handlers.common import require_user
from app.keyboards import main_menu_keyboard
from app.services.checklist import process_user_message
from app.services.formatting import (
    CATEGORY_TITLES,
    format_action_result,
    format_items,
    format_undo_result,
)
from app.services.gemini import ChecklistParser
from app.texts import (
    ALL_ITEMS_BUTTON,
    BUY_BUTTON,
    EMPTY_INPUT_TEXT,
    IMPORTANT_BUTTON,
    PARSER_ERROR_TEXT,
    TAKE_BUTTON,
    UNDO_BUTTON,
)


router = Router(name="checklist")
logger = logging.getLogger(__name__)


@router.message(F.text == BUY_BUTTON)
async def show_buy_items(message: Message, db: Database) -> None:
    await _send_category(message, db, "buy")


@router.message(F.text == TAKE_BUTTON)
async def show_take_items(message: Message, db: Database) -> None:
    await _send_category(message, db, "take")


@router.message(F.text == IMPORTANT_BUTTON)
async def show_important_items(message: Message, db: Database) -> None:
    await _send_category(message, db, "important")


@router.message(F.text == ALL_ITEMS_BUTTON)
async def show_all_items(message: Message, db: Database) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    items = await db.list_items()
    await message.answer(format_items(items), reply_markup=main_menu_keyboard())


@router.message(F.text == UNDO_BUTTON)
async def undo_last_action(message: Message, db: Database) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    result = await db.undo_last_action(user.id)
    await message.answer(format_undo_result(result), reply_markup=main_menu_keyboard())


@router.message(F.text)
async def parse_free_text(
    message: Message,
    db: Database,
    parser: ChecklistParser,
) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer(EMPTY_INPUT_TEXT, reply_markup=main_menu_keyboard())
        return

    try:
        result = await process_user_message(db, user, text, parser)
    except Exception:
        logger.exception("Не удалось разобрать сообщение через Gemini")
        await message.answer(PARSER_ERROR_TEXT, reply_markup=main_menu_keyboard())
        return

    await message.answer(format_action_result(result), reply_markup=main_menu_keyboard())


async def _send_category(message: Message, db: Database, category: Category) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    items = await db.list_items(category=category, status="active")
    await message.answer(
        format_items(items, title=CATEGORY_TITLES[category]),
        reply_markup=main_menu_keyboard(),
    )
