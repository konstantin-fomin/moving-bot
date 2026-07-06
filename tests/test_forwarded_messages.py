from types import SimpleNamespace

import pytest

from app.handlers.checklist import (
    ForwardedItemState,
    finish_forwarded_add,
    start_forwarded_add,
)
from app.texts import ADD_BUY_BUTTON, FORWARDED_CATEGORY_TEXT


@pytest.mark.asyncio
async def test_forwarded_message_adds_item_after_category_selection(db):
    await db.create_owner_if_first(telegram_id=1, name="Анна")
    state = FakeState()
    forwarded_message = FakeMessage(text="Пастила https://example.com/pastila")

    await start_forwarded_add(forwarded_message, db, state)

    assert state.state == ForwardedItemState.waiting_category
    assert state.data == {"forwarded_text": "Пастила https://example.com/pastila"}
    assert forwarded_message.answers[-1].text == FORWARDED_CATEGORY_TEXT

    await finish_forwarded_add(FakeMessage(text=ADD_BUY_BUTTON), db, state)

    items = await db.list_items()
    assert len(items) == 1
    assert items[0].category == "buy"
    assert items[0].name == "Пастила"
    assert items[0].link == "https://example.com/pastila"
    assert state.data == {}


class FakeMessage:
    def __init__(self, text=None, caption=None):
        self.from_user = SimpleNamespace(id=1)
        self.text = text
        self.caption = caption
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
