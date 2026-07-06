from app.database import ChecklistItem
from app.keyboards import (
    item_actions_keyboard,
    items_inline_keyboard,
    voice_confirmation_keyboard,
)


def test_items_inline_keyboard_uses_item_names():
    keyboard = items_inline_keyboard(
        [_item(12, "buy", "active", "Пастила конфеты вкусвил для Евы")],
        "buy",
    )

    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "□ Пастила конфеты вкусвил для Евы"
    assert button.callback_data == "item:menu:12:buy"


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
    assert "item:delete:12:buy" in callback_data
    assert "items:list:buy" in callback_data


def test_voice_confirmation_keyboard_has_confirm_and_cancel():
    keyboard = voice_confirmation_keyboard()
    buttons = keyboard.inline_keyboard[0]

    assert buttons[0].text == "✅"
    assert buttons[0].callback_data == "voice:confirm"
    assert buttons[1].text == "❌"
    assert buttons[1].callback_data == "voice:cancel"


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
