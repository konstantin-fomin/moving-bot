from __future__ import annotations

from io import BytesIO
import logging
import re

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.database import Category, Database
from app.handlers.common import require_user
from app.keyboards import (
    add_category_keyboard,
    cancel_keyboard,
    item_actions_keyboard,
    items_inline_keyboard,
    main_menu_keyboard,
    voice_confirmation_keyboard,
)
from app.services.checklist import build_manual_item, process_user_message
from app.services.formatting import (
    CATEGORY_TITLES,
    format_action_result,
    format_items,
    format_undo_result,
)
from app.services.gemini import ChecklistParser
from app.services.voice_actions import (
    apply_voice_commands,
    format_voice_apply_result,
    format_voice_confirmation,
    voice_commands_from_dicts,
    voice_commands_to_dicts,
)
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
    VOICE_EMPTY_TEXT,
    VOICE_ERROR_TEXT,
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


class VoiceActionState(StatesGroup):
    waiting_confirmation = State()


ADD_CATEGORY_BY_BUTTON: dict[str, Category] = {
    ADD_BUY_BUTTON: "buy",
    ADD_TAKE_BUTTON: "take",
    ADD_IMPORTANT_BUTTON: "important",
}
ITEM_ID_RE = re.compile(r"#?\s*(\d+)")
SCOPE_CATEGORIES: dict[str, Category | None] = {
    "all": None,
    "buy": "buy",
    "take": "take",
    "important": "important",
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
@router.message(ManageItemState.waiting_mark_done_id, F.text == ADD_CANCEL_BUTTON)
@router.message(ManageItemState.waiting_delete_id, F.text == ADD_CANCEL_BUTTON)
@router.message(ManageItemState.waiting_edit_id, F.text == ADD_CANCEL_BUTTON)
@router.message(ManageItemState.waiting_edit_text, F.text == ADD_CANCEL_BUTTON)
@router.message(VoiceActionState.waiting_confirmation, F.text == ADD_CANCEL_BUTTON)
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

    await _send_items_list(message, db, "all")


@router.message(F.text == UNDO_BUTTON)
async def undo_last_action(message: Message, db: Database) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    result = await db.undo_last_action(user.id)
    await message.answer(format_undo_result(result), reply_markup=main_menu_keyboard())


@router.message(F.voice)
async def parse_voice(
    message: Message,
    bot: Bot,
    db: Database,
    parser: ChecklistParser,
    state: FSMContext,
) -> None:
    user = await require_user(message, db)
    if user is None or message.voice is None:
        return

    items = await db.list_items()
    buffer = BytesIO()
    await bot.download(message.voice, destination=buffer)
    audio = buffer.getvalue()
    mime_type = message.voice.mime_type or "audio/ogg"

    try:
        commands = await parser.parse_voice_message(audio, mime_type, items)
    except Exception:
        logger.exception("Не удалось разобрать голосовое сообщение через Gemini")
        await message.answer(VOICE_ERROR_TEXT, reply_markup=main_menu_keyboard())
        return

    if not commands:
        await message.answer(VOICE_EMPTY_TEXT, reply_markup=main_menu_keyboard())
        return

    await state.update_data(voice_commands=voice_commands_to_dicts(commands))
    await state.set_state(VoiceActionState.waiting_confirmation)
    await message.answer(
        format_voice_confirmation(commands, items),
        reply_markup=voice_confirmation_keyboard(),
    )


@router.callback_query(VoiceActionState.waiting_confirmation, F.data == "voice:cancel")
async def cancel_voice_action(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.edit_text("Голосовое действие отменено.")
    await callback.answer()


@router.callback_query(VoiceActionState.waiting_confirmation, F.data == "voice:confirm")
async def confirm_voice_action(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    data = await state.get_data()
    raw_commands = data.get("voice_commands")
    commands = (
        voice_commands_from_dicts(raw_commands)
        if isinstance(raw_commands, list)
        else []
    )
    await state.clear()

    if not commands:
        if callback.message is not None:
            await callback.message.edit_text("Голосовое действие уже не найдено.")
        await callback.answer()
        return

    result = await apply_voice_commands(db, user, commands)
    if callback.message is not None:
        await callback.message.edit_text(format_voice_apply_result(result))
    await callback.answer("Готово.")


@router.message(F.text == MARK_DONE_BUTTON)
async def start_mark_done(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    await state.set_state(ManageItemState.waiting_mark_done_id)
    await message.answer(ITEM_ID_TEXT, reply_markup=cancel_keyboard())


@router.callback_query(F.data.startswith("items:list:"))
async def callback_show_items_list(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    scope = _parse_list_callback(callback.data or "")
    if scope is None:
        await callback.answer("Не поняла список.", show_alert=True)
        return

    await _edit_items_list(callback, db, scope)
    await callback.answer()


@router.callback_query(F.data.startswith("item:menu:"))
async def callback_open_item_menu(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    item_id, scope = _parse_item_callback(callback.data or "", "menu")
    if item_id is None or scope is None:
        await callback.answer("Не поняла пункт.", show_alert=True)
        return

    item = await db.get_item(item_id)
    if item is None:
        await callback.answer(ITEM_NOT_FOUND_TEXT, show_alert=True)
        return

    if callback.message is not None:
        await callback.message.edit_text(
            format_items([item]),
            reply_markup=item_actions_keyboard(item, scope),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("item:done:"))
async def callback_mark_done(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    item_id, scope = _parse_item_callback(callback.data or "", "done")
    if item_id is None or scope is None:
        await callback.answer("Не поняла пункт.", show_alert=True)
        return

    item = await db.get_item(item_id)
    if item is None:
        await callback.answer(ITEM_NOT_FOUND_TEXT, show_alert=True)
        return
    if item.status == "done":
        await callback.answer("Уже отмечено.", show_alert=True)
        return

    await db.apply_actions(user.id, [], [item_id])
    await _edit_items_list(callback, db, scope)
    await callback.answer("Отмечено.")


@router.callback_query(F.data.startswith("item:delete:"))
async def callback_delete_item(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    item_id, scope = _parse_item_callback(callback.data or "", "delete")
    if item_id is None or scope is None:
        await callback.answer("Не поняла пункт.", show_alert=True)
        return

    deleted = await db.delete_item(item_id)
    if deleted is None:
        await callback.answer(ITEM_NOT_FOUND_TEXT, show_alert=True)
        return

    await _edit_items_list(callback, db, scope)
    await callback.answer("Удалено.")


@router.callback_query(F.data.startswith("item:edit:"))
async def callback_start_edit_item(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    item_id, scope = _parse_item_callback(callback.data or "", "edit")
    if item_id is None or scope is None:
        await callback.answer("Не поняла пункт.", show_alert=True)
        return

    item = await db.get_item(item_id)
    if item is None:
        await callback.answer(ITEM_NOT_FOUND_TEXT, show_alert=True)
        return

    await state.update_data(item_id=item.id, return_scope=scope)
    await state.set_state(ManageItemState.waiting_edit_text)
    if callback.message is not None:
        await callback.message.answer(
            f"Сейчас:\n• {item.name}\n\n{EDIT_ITEM_TEXT}",
            reply_markup=cancel_keyboard(),
        )
    await callback.answer()


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
        edited.link,
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

    await _send_items_list(message, db, category)


def _parse_item_id(text: str) -> int | None:
    match = ITEM_ID_RE.search(text)
    if match is None:
        return None
    return int(match.group(1))


async def _send_items_list(message: Message, db: Database, scope: str) -> None:
    items = await _items_for_scope(db, scope)
    if not items:
        await message.answer(format_items(items), reply_markup=main_menu_keyboard())
        return

    await message.answer(
        _items_picker_text(scope),
        reply_markup=items_inline_keyboard(items, scope),
    )


async def _edit_items_list(callback: CallbackQuery, db: Database, scope: str) -> None:
    items = await _items_for_scope(db, scope)
    if callback.message is None:
        return
    if not items:
        await callback.message.edit_text("Список пока пуст.")
        return
    await callback.message.edit_text(
        _items_picker_text(scope),
        reply_markup=items_inline_keyboard(items, scope),
    )


async def _items_for_scope(db: Database, scope: str) -> list:
    category = SCOPE_CATEGORIES.get(scope)
    if scope != "all" and category is None:
        return []
    return await db.list_items(category=category)


async def _require_callback_user(callback: CallbackQuery, db: Database):
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(
            "Это личный бот для переезда. Попросите владельца прислать приглашение.",
            show_alert=True,
        )
    return user


def _parse_list_callback(data: str) -> str | None:
    parts = data.split(":")
    if len(parts) != 3 or parts[:2] != ["items", "list"]:
        return None
    scope = parts[2]
    return scope if scope in SCOPE_CATEGORIES else None


def _parse_item_callback(data: str, action: str) -> tuple[int | None, str | None]:
    parts = data.split(":")
    if len(parts) != 4 or parts[:2] != ["item", action]:
        return None, None
    scope = parts[3]
    if scope not in SCOPE_CATEGORIES:
        return None, None
    try:
        return int(parts[2]), scope
    except ValueError:
        return None, None


def _items_picker_text(scope: str) -> str:
    category = SCOPE_CATEGORIES.get(scope)
    if category is None:
        return "Выберите пункт:"
    return f"{CATEGORY_TITLES[category]}\nВыберите пункт:"
