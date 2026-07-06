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


@pytest.mark.asyncio
async def test_done_items_stay_in_list_after_active_items(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    result = await db.apply_actions(
        owner.id,
        [
            NewChecklistItem(category="buy", name="Коробки"),
            NewChecklistItem(category="buy", name="Скотч"),
        ],
        [],
    )

    await db.apply_actions(owner.id, [], [result.added[0].id])
    items = await db.list_items(category="buy")

    assert [(item.name, item.status) for item in items] == [
        ("Скотч", "active"),
        ("Коробки", "done"),
    ]


@pytest.mark.asyncio
async def test_update_item_changes_text_and_link(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    result = await db.apply_actions(
        owner.id,
        [NewChecklistItem(category="buy", name="Пастила", link=None, note="2 штуки")],
        [],
    )

    updated = await db.update_item(
        result.added[0].id,
        "Пастила конфеты вкусвил для Евы",
        "https://example.com/pastila",
        "2 штуки",
    )

    assert updated is not None
    assert updated.name == "Пастила конфеты вкусвил для Евы"
    assert updated.link == "https://example.com/pastila"
    assert updated.note == "2 штуки"


@pytest.mark.asyncio
async def test_update_item_category_moves_item_between_lists(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    result = await db.apply_actions(
        owner.id,
        [NewChecklistItem(category="buy", name="Пастила")],
        [],
    )

    updated = await db.update_item_category(result.added[0].id, "important")
    buy_items = await db.list_items(category="buy")
    important_items = await db.list_items(category="important")

    assert updated is not None
    assert updated.category == "important"
    assert buy_items == []
    assert [item.name for item in important_items] == ["Пастила"]


@pytest.mark.asyncio
async def test_delete_item_removes_it_from_list(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    result = await db.apply_actions(
        owner.id,
        [NewChecklistItem(category="take", name="Куртка")],
        [],
    )

    deleted = await db.delete_item(result.added[0].id)
    items = await db.list_items()

    assert deleted is not None
    assert deleted.name == "Куртка"
    assert items == []
