from __future__ import annotations

import logging
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.database import Category, Database
from app.handlers.common import require_user
from app.keyboards import add_category_keyboard, cancel_keyboard, main_menu_keyboard
from app.services.checklist import build_manual_item, process_user_message
from app.services.formatting import (
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
    DELETE_BUTTON,
    EDIT_BUTTON,
    EDIT_ITEM_TEXT,
    EMPTY_INPUT_TEXT,
    INVALID_ITEM_ID_TEXT,
    IMPORTANT_BUTTON,
    ITEM_ID_TEXT,
    ITEM_NOT_FOUND_TEXT,
    MARK_DONE_BUTTON,
    PARSER_ERROR_TEXT,
    TAKE_BUTTON,
    UNDO_BUTTON,
)


router = Router(name="checklist")
logger = logging.getLogger(__name__)


class AddItemState(StatesGroup):
    waiting_category = State()
    waiting_text = State()


class ManageItemState(StatesGroup):
    waiting_mark_done_id = State()
    waiting_delete_id = State()
    waiting_edit_id = State()
    waiting_edit_text = State()


ADD_CATEGORY_BY_BUTTON: dict[str, Category] = {
    ADD_BUY_BUTTON: "buy",
    ADD_TAKE_BUTTON: "take",
    ADD_IMPORTANT_BUTTON: "important",
}
ITEM_ID_RE = re.compile(r"#?\s*(\d+)")


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
@router.message(ManageItemState.waiting_mark_done_id, F.text == ADD_CANCEL_BUTTON)
@router.message(ManageItemState.waiting_delete_id, F.text == ADD_CANCEL_BUTTON)
@router.message(ManageItemState.waiting_edit_id, F.text == ADD_CANCEL_BUTTON)
@router.message(ManageItemState.waiting_edit_text, F.text == ADD_CANCEL_BUTTON)
async def cancel_state_action(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu_keyboard())


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


@router.message(F.text == MARK_DONE_BUTTON)
async def start_mark_done(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    await state.set_state(ManageItemState.waiting_mark_done_id)
    await message.answer(ITEM_ID_TEXT, reply_markup=cancel_keyboard())


@router.message(ManageItemState.waiting_mark_done_id)
async def finish_mark_done(
    message: Message,
    db: Database,
    state: FSMContext,
) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    item_id = _parse_item_id(message.text or "")
    if item_id is None:
        await message.answer(INVALID_ITEM_ID_TEXT, reply_markup=cancel_keyboard())
        return

    item = await db.get_item(item_id)
    if item is None:
        await message.answer(ITEM_NOT_FOUND_TEXT, reply_markup=cancel_keyboard())
        return
    if item.status == "done":
        await state.clear()
        await message.answer(
            f"Уже отмечено выполненным:\n✓ {item.name}",
            reply_markup=main_menu_keyboard(),
        )
        return

    result = await db.apply_actions(user.id, [], [item_id])
    await state.clear()
    await message.answer(format_action_result(result), reply_markup=main_menu_keyboard())


@router.message(F.text == DELETE_BUTTON)
async def start_delete_item(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    await state.set_state(ManageItemState.waiting_delete_id)
    await message.answer(ITEM_ID_TEXT, reply_markup=cancel_keyboard())


@router.message(ManageItemState.waiting_delete_id)
async def finish_delete_item(
    message: Message,
    db: Database,
    state: FSMContext,
) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    item_id = _parse_item_id(message.text or "")
    if item_id is None:
        await message.answer(INVALID_ITEM_ID_TEXT, reply_markup=cancel_keyboard())
        return

    deleted = await db.delete_item(item_id)
    if deleted is None:
        await message.answer(ITEM_NOT_FOUND_TEXT, reply_markup=cancel_keyboard())
        return

    await state.clear()
    await message.answer(
        f"Удалено:\n• {deleted.name}",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == EDIT_BUTTON)
async def start_edit_item(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    await state.set_state(ManageItemState.waiting_edit_id)
    await message.answer(ITEM_ID_TEXT, reply_markup=cancel_keyboard())


@router.message(ManageItemState.waiting_edit_id)
async def select_edit_item(
    message: Message,
    db: Database,
    state: FSMContext,
) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    item_id = _parse_item_id(message.text or "")
    if item_id is None:
        await message.answer(INVALID_ITEM_ID_TEXT, reply_markup=cancel_keyboard())
        return

    item = await db.get_item(item_id)
    if item is None:
        await message.answer(ITEM_NOT_FOUND_TEXT, reply_markup=cancel_keyboard())
        return

    await state.update_data(item_id=item.id)
    await state.set_state(ManageItemState.waiting_edit_text)
    await message.answer(
        f"Сейчас:\n• {item.name}\n\n{EDIT_ITEM_TEXT}",
        reply_markup=cancel_keyboard(),
    )


@router.message(ManageItemState.waiting_edit_text)
async def finish_edit_item(
    message: Message,
    db: Database,
    state: FSMContext,
) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    data = await state.get_data()
    item_id = data.get("item_id")
    if not isinstance(item_id, int):
        await state.clear()
        await message.answer(
            "Номер пункта потерялся. Нажмите «✏️ Редактировать» ещё раз.",
            reply_markup=main_menu_keyboard(),
        )
        return

    existing = await db.get_item(item_id)
    if existing is None:
        await state.clear()
        await message.answer(ITEM_NOT_FOUND_TEXT, reply_markup=main_menu_keyboard())
        return

    edited = build_manual_item(existing.category, message.text or "")
    if edited is None:
        await message.answer(ADD_EMPTY_TEXT, reply_markup=cancel_keyboard())
        return

    updated = await db.update_item(
        existing.id,
        edited.name,
        edited.link or existing.link,
        existing.note,
    )
    await state.clear()
    if updated is None:
        await message.answer(ITEM_NOT_FOUND_TEXT, reply_markup=main_menu_keyboard())
        return

    await message.answer(
        "Обновлено:\n"
        f"{format_items([updated])}",
        reply_markup=main_menu_keyboard(),
    )


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

    items = await db.list_items(category=category)
    await message.answer(format_items(items), reply_markup=main_menu_keyboard())


def _parse_item_id(text: str) -> int | None:
    match = ITEM_ID_RE.search(text)
    if match is None:
        return None
    return int(match.group(1))
