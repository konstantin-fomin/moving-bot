import pytest

from app.database import NewChecklistItem


@pytest.mark.asyncio
async def test_undo_last_add_action_removes_created_items(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    await db.apply_actions(
        owner.id,
        [NewChecklistItem(category="buy", name="Коробки")],
        [],
    )

    undo = await db.undo_last_action(owner.id)

    assert undo is not None
    assert undo.undone is True
    assert await db.list_items() == []


@pytest.mark.asyncio
async def test_undo_last_mark_done_restores_item(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    add_result = await db.apply_actions(
        owner.id,
        [NewChecklistItem(category="take", name="Куртка")],
        [],
    )
    await db.apply_actions(owner.id, [], [add_result.added[0].id])

    undo = await db.undo_last_action(owner.id)
    active = await db.list_items(status="active")

    assert undo is not None
    assert [item.name for item in undo.marked_done] == ["Куртка"]
    assert [item.name for item in active] == ["Куртка"]
