from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.database import ChecklistItem

from app.texts import (
    ADD_BUTTON,
    ADD_BUY_BUTTON,
    ADD_CANCEL_BUTTON,
    ADD_IMPORTANT_BUTTON,
    ADD_TAKE_BUTTON,
    ALL_ITEMS_BUTTON,
    BUY_BUTTON,
    IMPORTANT_BUTTON,
    TAKE_BUTTON,
    UNDO_BUTTON,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADD_BUTTON)],
            [
                KeyboardButton(text=BUY_BUTTON),
                KeyboardButton(text=TAKE_BUTTON),
            ],
            [
                KeyboardButton(text=IMPORTANT_BUTTON),
                KeyboardButton(text=ALL_ITEMS_BUTTON),
            ],
            [KeyboardButton(text=UNDO_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напишите вещи для переезда",
    )


def add_category_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=ADD_BUY_BUTTON),
                KeyboardButton(text=ADD_IMPORTANT_BUTTON),
            ],
            [KeyboardButton(text=ADD_TAKE_BUTTON)],
            [KeyboardButton(text=ADD_CANCEL_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите категорию",
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=ADD_CANCEL_BUTTON)]],
        resize_keyboard=True,
        input_field_placeholder="Можно отменить действие",
    )


def items_inline_keyboard(
    items: list[ChecklistItem],
    scope: str,
) -> InlineKeyboardMarkup | None:
    if not items:
        return None

    rows = [
        [
            InlineKeyboardButton(
                text=_item_button_text(item),
                callback_data=f"item:menu:{item.id}:{scope}",
            )
        ]
        for item in items
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_actions_keyboard(item: ChecklistItem, scope: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if item.status == "active":
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ Отметить выполненным",
                    callback_data=f"item:done:{item.id}:{scope}",
                )
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="✏️ Редактировать",
                    callback_data=f"item:edit:{item.id}:{scope}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"item:delete:{item.id}:{scope}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ К списку",
                    callback_data=f"items:list:{scope}",
                )
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def voice_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅", callback_data="voice:confirm"),
                InlineKeyboardButton(text="❌", callback_data="voice:cancel"),
            ]
        ]
    )


def _item_button_text(item: ChecklistItem) -> str:
    marker = "✓" if item.status == "done" else "□"
    text = f"{marker} {item.name}"
    if len(text) <= 55:
        return text
    return f"{text[:52]}..."
