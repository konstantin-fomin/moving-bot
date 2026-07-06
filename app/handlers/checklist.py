from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.database import Category, Database
from app.handlers.common import require_user
from app.keyboards import add_category_keyboard, main_menu_keyboard
from app.services.checklist import build_manual_item, process_user_message
from app.services.formatting import (
    CATEGORY_TITLES,
    format_action_result,
    format_items,
    format_undo_result,
)
from app.services.gemini import ChecklistParser
from app.texts import (
    ADD_BUTTON,
    ADD_BUY_BUTTON,
    ADD_CANCEL_BUTTON,
    ADD_CATEGORY_TEXT,
    ADD_EMPTY_TEXT,
    ADD_IMPORTANT_BUTTON,
    ADD_ITEM_TEXT,
    ADD_TAKE_BUTTON,
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


class AddItemState(StatesGroup):
    waiting_category = State()
    waiting_text = State()


ADD_CATEGORY_BY_BUTTON: dict[str, Category] = {
    ADD_BUY_BUTTON: "buy",
    ADD_TAKE_BUTTON: "take",
    ADD_IMPORTANT_BUTTON: "important",
}


@router.message(F.text == ADD_BUTTON)
async def start_manual_add(
    message: Message,
    db: Database,
    state: FSMContext,
) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    await state.set_state(AddItemState.waiting_category)
    await message.answer(ADD_CATEGORY_TEXT, reply_markup=add_category_keyboard())


@router.message(AddItemState.waiting_category, F.text == ADD_CANCEL_BUTTON)
@router.message(AddItemState.waiting_text, F.text == ADD_CANCEL_BUTTON)
async def cancel_manual_add(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Добавление отменено.", reply_markup=main_menu_keyboard())


@router.message(AddItemState.waiting_category, F.text.in_(ADD_CATEGORY_BY_BUTTON))
async def select_manual_add_category(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return

    await state.update_data(category=ADD_CATEGORY_BY_BUTTON[message.text])
    await state.set_state(AddItemState.waiting_text)
    await message.answer(ADD_ITEM_TEXT)


@router.message(AddItemState.waiting_category)
async def reject_unknown_manual_add_category(message: Message) -> None:
    await message.answer(ADD_CATEGORY_TEXT, reply_markup=add_category_keyboard())


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


@router.message(AddItemState.waiting_text)
async def finish_manual_add(
    message: Message,
    db: Database,
    state: FSMContext,
) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    data = await state.get_data()
    category = data.get("category")
    if category not in ("buy", "take", "important"):
        await state.clear()
        await message.answer(
            "Категория потерялась. Нажмите «➕ Добавить» ещё раз.",
            reply_markup=main_menu_keyboard(),
        )
        return

    item = build_manual_item(category, message.text or "")
    if item is None:
        await message.answer(ADD_EMPTY_TEXT)
        return

    result = await db.apply_actions(user.id, [item], [])
    await state.clear()
    await message.answer(format_action_result(result), reply_markup=main_menu_keyboard())


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
