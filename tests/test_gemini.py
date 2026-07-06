import pytest

from app.database import NewChecklistItem
from app.services.checklist import build_manual_item, process_user_message
from app.services.gemini import (
    MarkDoneAction,
    ParsedActions,
    parse_gemini_response,
    parse_voice_gemini_response,
)
from app.services.voice_actions import VoiceCommand


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


def test_parse_voice_gemini_response_adds_and_manages_items():
    parsed = parse_voice_gemini_response(
        """
        [
          {"action":"add","name":"Пастила конфеты вкусвил для Евы","category":"buy","link":null,"note":null},
          {"action":"mark_done","item_id":7,"name":"Скотч"},
          {"action":"delete","item_id":8,"name":"Старые коробки"},
          {"action":"edit","item_id":9,"name":"Паспорта","new_name":"Паспорта и свидетельство","new_link":null,"new_note":null}
        ]
        """
    )

    assert parsed == [
        VoiceCommand(
            action="add",
            category="buy",
            name="Пастила конфеты вкусвил для Евы",
        ),
        VoiceCommand(action="mark_done", item_id=7),
        VoiceCommand(action="delete", item_id=8),
        VoiceCommand(
            action="edit",
            item_id=9,
            new_name="Паспорта и свидетельство",
        ),
    ]


def test_build_manual_item_preserves_full_text():
    item = build_manual_item("buy", "Пастила конфеты вкусвил для Евы")

    assert item == NewChecklistItem(
        category="buy",
        name="Пастила конфеты вкусвил для Евы",
        link=None,
        note=None,
    )


def test_build_manual_item_extracts_link_from_text():
    item = build_manual_item(
        "buy",
        "Пастила конфеты вкусвил для Евы https://example.com/pastila",
    )

    assert item == NewChecklistItem(
        category="buy",
        name="Пастила конфеты вкусвил для Евы",
        link="https://example.com/pastila",
        note=None,
    )


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


@pytest.mark.asyncio
async def test_process_user_message_preserves_plain_single_item_text(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    parser = FakeParser(
        ParsedActions(
            new_items=[
                NewChecklistItem(
                    category="buy",
                    name="Пастила конфеты",
                    link=None,
                    note=None,
                )
            ],
            mark_done=[],
        )
    )

    result = await process_user_message(
        db,
        owner,
        "Пастила конфеты вкусвил для Евы",
        parser,
    )

    assert [item.name for item in result.added] == ["Пастила конфеты вкусвил для Евы"]


class FakeParser:
    def __init__(self, result):
        self.result = result
        self.seen_text = None
        self.seen_active_items = None

    async def parse_message(self, text, active_items):
        self.seen_text = text
        self.seen_active_items = active_items
        return self.result
