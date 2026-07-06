import pytest

from app.database import NewChecklistItem
from app.services.checklist import process_user_message
from app.services.gemini import MarkDoneAction, ParsedActions, parse_gemini_response


def test_parse_gemini_response_adds_items_and_mark_done():
    parsed = parse_gemini_response(
        """
        [
          {"action":"add","name":"Коробки","category":"buy","link":"https://shop.example/box","note":"20 штук"},
          {"action":"add","name":"Паспорта","category":"important","link":null,"note":null},
          {"action":"mark_done","item_id":7,"name":"Скотч"}
        ]
        """
    )

    assert parsed.new_items == [
        NewChecklistItem(
            category="buy",
            name="Коробки",
            link="https://shop.example/box",
            note="20 штук",
        ),
        NewChecklistItem(category="important", name="Паспорта", link=None, note=None),
    ]
    assert parsed.mark_done == [MarkDoneAction(item_id=7, name="Скотч")]


@pytest.mark.asyncio
async def test_process_user_message_uses_mock_parser(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    parser = FakeParser(
        ParsedActions(
            new_items=[
                NewChecklistItem(category="buy", name="Скотч", link=None, note=None)
            ],
            mark_done=[],
        )
    )

    result = await process_user_message(db, owner, "купить скотч", parser)

    assert parser.seen_text == "купить скотч"
    assert parser.seen_active_items == []
    assert [item.name for item in result.added] == ["Скотч"]


class FakeParser:
    def __init__(self, result):
        self.result = result
        self.seen_text = None
        self.seen_active_items = None

    async def parse_message(self, text, active_items):
        self.seen_text = text
        self.seen_active_items = active_items
        return self.result
