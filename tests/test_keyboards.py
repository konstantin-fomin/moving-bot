from app.database import ChecklistItem
from app.keyboards import (
    duplicate_confirmation_keyboard,
    item_actions_keyboard,
    item_move_category_keyboard,
    items_inline_keyboard,
    voice_confirmation_keyboard,
)
from app.texts import DUPLICATE_ADD_BUTTON, DUPLICATE_CANCEL_BUTTON


def test_items_inline_keyboard_uses_item_names():
    keyboard = items_inline_keyboard(
        [_item(12, "buy", "active", "Пастила конфеты вкусвил для Евы")],
        "buy",
    )

    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "□ Пастила конфеты вкусвил для Евы"
    assert button.callback_data == "item:menu:12:buy"


def test_all_items_inline_keyboard_adds_category_headers():
    keyboard = items_inline_keyboard(
        [
            _item(12, "buy", "active", "Пастила"),
            _item(13, "take", "active", "Куртка"),
        ],
        "all",
    )

    assert keyboard is not None
    rows = keyboard.inline_keyboard
    assert rows[0][0].text == "🛒 Что купить"
    assert rows[0][0].callback_data == "items:list:buy"
    assert rows[1][0].callback_data == "item:menu:12:all"
    assert rows[2][0].text == "🎒 Что взять"
    assert rows[2][0].callback_data == "items:list:take"
    assert rows[3][0].callback_data == "item:menu:13:all"


def test_item_actions_keyboard_has_context_actions():
    keyboard = item_actions_keyboard(
        _item(12, "buy", "active", "Пастила"),
        "buy",
    )
    callback_data = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]

    assert "item:done:12:buy" in callback_data
    assert "item:edit:12:buy" in callback_data
    assert "item:move:12:buy" in callback_data
    assert "item:delete:12:buy" in callback_data
    assert "items:list:buy" in callback_data


def test_item_move_category_keyboard_uses_other_categories():
    keyboard = item_move_category_keyboard(
        _item(12, "buy", "active", "Пастила"),
        "buy",
    )
    callback_data = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]

    assert "item:move_to:12:take:buy" in callback_data
    assert "item:move_to:12:important:buy" in callback_data
    assert "item:move_to:12:buy:buy" not in callback_data
    assert "item:menu:12:buy" in callback_data


def test_voice_confirmation_keyboard_has_confirm_and_cancel():
    keyboard = voice_confirmation_keyboard()
    buttons = keyboard.inline_keyboard[0]

    assert buttons[0].text == "✅"
    assert buttons[0].callback_data == "voice:confirm"
    assert buttons[1].text == "❌"
    assert buttons[1].callback_data == "voice:cancel"


def test_duplicate_confirmation_keyboard_has_add_and_cancel():
    keyboard = duplicate_confirmation_keyboard()
    buttons = keyboard.keyboard[0]

    assert buttons[0].text == DUPLICATE_ADD_BUTTON
    assert buttons[1].text == DUPLICATE_CANCEL_BUTTON


def _item(item_id, category, status, name):
    return ChecklistItem(
        id=item_id,
        category=category,
        status=status,
        name=name,
        link=None,
        note=None,
        created_at="2026-01-01 00:00:00",
        updated_at="2026-01-01 00:00:00",
    )
