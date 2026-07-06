from types import SimpleNamespace

import pytest

from app.database import NewChecklistItem
from app.handlers.checklist import (
    DuplicateAddState,
    _apply_actions_or_ask_duplicate,
    confirm_duplicate_add,
)
from app.texts import DUPLICATE_ADD_BUTTON, DUPLICATE_CONFIRM_TEXT


@pytest.mark.asyncio
async def test_duplicate_add_waits_for_confirmation(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    await db.apply_actions(
        owner.id,
        [NewChecklistItem(category="buy", name="Пастила")],
        [],
    )
    message = FakeMessage()
    state = FakeState()

    await _apply_actions_or_ask_duplicate(
        message,
        db,
        owner.id,
        state,
        [NewChecklistItem(category="take", name="Пастила")],
        [],
    )

    assert state.state == DuplicateAddState.waiting_confirmation
    assert DUPLICATE_CONFIRM_TEXT.split("{items}")[0] in message.answers[-1].text
    assert len(await db.list_items()) == 1

    await confirm_duplicate_add(FakeMessage(text=DUPLICATE_ADD_BUTTON), db, state)

    items = await db.list_items()
    assert [item.name for item in items] == ["Пастила", "Пастила"]
    assert {item.category for item in items} == {"buy", "take"}
    assert state.data == {}


class FakeMessage:
    def __init__(self, text=None):
        self.from_user = SimpleNamespace(id=1)
        self.text = text
        self.answers = []

    async def answer(self, text, reply_markup=None):
        self.answers.append(SimpleNamespace(text=text, reply_markup=reply_markup))


class FakeState:
    def __init__(self):
        self.data = {}
        self.state = None

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, state):
        self.state = state

    async def get_data(self):
        return self.data

    async def clear(self):
        self.data.clear()
        self.state = None
