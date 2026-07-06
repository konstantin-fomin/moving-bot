import pytest

from app.database import NewChecklistItem
from app.services.voice_actions import (
    VoiceCommand,
    apply_voice_commands,
    format_voice_confirmation,
)


def test_format_voice_confirmation_mentions_actions():
    text = format_voice_confirmation(
        [
            VoiceCommand(action="add", category="buy", name="Пастила"),
            VoiceCommand(action="mark_done", item_id=7),
        ],
        [],
    )

    assert "добавить в покупки: Пастила" in text
    assert "отметить выполненным: #7" in text
    assert "Применить это действие?" in text


@pytest.mark.asyncio
async def test_apply_voice_commands_adds_marks_edits_and_deletes(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    result = await db.apply_actions(
        owner.id,
        [
            NewChecklistItem(category="buy", name="Скотч"),
            NewChecklistItem(category="take", name="Старая коробка"),
            NewChecklistItem(category="important", name="Паспорта"),
        ],
        [],
    )

    applied = await apply_voice_commands(
        db,
        owner,
        [
            VoiceCommand(
                action="add",
                category="buy",
                name="Пастила конфеты вкусвил для Евы",
            ),
            VoiceCommand(action="mark_done", item_id=result.added[0].id),
            VoiceCommand(action="delete", item_id=result.added[1].id),
            VoiceCommand(
                action="edit",
                item_id=result.added[2].id,
                new_name="Паспорта и свидетельство",
            ),
        ],
    )

    items = await db.list_items()

    assert [item.name for item in applied.added] == [
        "Пастила конфеты вкусвил для Евы"
    ]
    assert [item.name for item in applied.marked_done] == ["Скотч"]
    assert [item.name for item in applied.deleted] == ["Старая коробка"]
    assert [item.name for item in applied.edited] == ["Паспорта и свидетельство"]
    assert "Старая коробка" not in [item.name for item in items]
