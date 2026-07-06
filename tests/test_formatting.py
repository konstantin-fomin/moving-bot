from app.database import ActionResult, ChecklistItem
from app.services.formatting import format_action_result, format_items, format_undo_result


def test_format_items_groups_by_category_and_status():
    items = [
        _item(1, "take", "active", "Куртка"),
        _item(2, "buy", "done", "Скотч"),
        _item(3, "important", "active", "Передать показания"),
    ]

    text = format_items(items)

    assert "🛒 Что купить" in text
    assert "✓ #2 Скотч" in text
    assert "🎒 Что взять" in text
    assert "□ #1 Куртка" in text
    assert "⚠️ Важное" in text


def test_format_action_result_mentions_added_and_done_items():
    text = format_action_result(
        ActionResult(
            added=[_item(1, "buy", "active", "Коробки")],
            marked_done=[_item(2, "take", "done", "Куртка")],
        )
    )

    assert "Добавлено:" in text
    assert "• Коробки" in text
    assert "Отмечено выполненным:" in text
    assert "✓ Куртка" in text


def test_format_action_result_mentions_added_link_and_note():
    text = format_action_result(
        ActionResult(
            added=[
                _item(
                    1,
                    "buy",
                    "active",
                    "Пастила конфеты вкусвил для Евы",
                    link="https://example.com/pastila",
                    note="2 упаковки",
                )
            ],
            marked_done=[],
        )
    )

    assert "• Пастила конфеты вкусвил для Евы" in text
    assert "https://example.com/pastila" in text
    assert "(2 упаковки)" in text


def test_format_undo_empty_result():
    assert format_undo_result(None) == "Пока нечего отменять."


def _item(item_id, category, status, name, link=None, note=None):
    return ChecklistItem(
        id=item_id,
        category=category,
        status=status,
        name=name,
        link=link,
        note=note,
        created_at="2026-01-01 00:00:00",
        updated_at="2026-01-01 00:00:00",
    )
