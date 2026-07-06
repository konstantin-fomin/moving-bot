import pytest

from app.database import NewChecklistItem


@pytest.mark.asyncio
async def test_first_user_becomes_owner(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")

    assert owner is not None
    assert owner.telegram_id == 1
    assert owner.role == "owner"
    assert await db.users_count() == 1


@pytest.mark.asyncio
async def test_second_user_without_invite_does_not_become_owner(db):
    await db.create_owner_if_first(telegram_id=1, name="Анна")
    second = await db.create_owner_if_first(telegram_id=2, name="Борис")

    assert second is None
    assert await db.get_user_by_telegram_id(2) is None
    assert await db.users_count() == 1


@pytest.mark.asyncio
async def test_add_and_mark_done_items(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    result = await db.apply_actions(
        owner.id,
        [
            NewChecklistItem(category="buy", name="Коробки", link=None, note="20 штук"),
            NewChecklistItem(category="take", name="Куртки", link=None, note=None),
        ],
        [],
    )

    assert [item.name for item in result.added] == ["Коробки", "Куртки"]

    mark_result = await db.apply_actions(owner.id, [], [result.added[0].id])
    active = await db.list_items(status="active")
    done = await db.list_items(status="done")

    assert [item.name for item in mark_result.marked_done] == ["Коробки"]
    assert [item.name for item in active] == ["Куртки"]
    assert [item.name for item in done] == ["Коробки"]
