from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

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
