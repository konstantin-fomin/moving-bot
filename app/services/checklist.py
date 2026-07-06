from __future__ import annotations

from dataclasses import replace
import re

from app.database import ActionResult, Category, Database, NewChecklistItem, User
from app.services.gemini import ChecklistParser, ParsedActions


URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


async def process_user_message(
    db: Database,
    user: User,
    text: str,
    parser: ChecklistParser,
) -> ActionResult:
    parsed = await parse_user_message(db, text, parser)
    mark_done_ids = [action.item_id for action in parsed.mark_done]
    return await db.apply_actions(
        user_id=user.id,
        new_items=parsed.new_items,
        mark_done_ids=mark_done_ids,
    )


async def parse_user_message(
    db: Database,
    text: str,
    parser: ChecklistParser,
) -> ParsedActions:
    active_items = await db.list_items(status="active")
    parsed = await parser.parse_message(text, active_items)
    return preserve_plain_single_item_text(text, parsed)


def clean_manual_items(items: list[NewChecklistItem]) -> list[NewChecklistItem]:
    return [item for item in items if item.name.strip()]


def build_manual_item(category: Category, text: str) -> NewChecklistItem | None:
    value = text.strip()
    if not value:
        return None

    match = URL_RE.search(value)
    link = match.group(0).rstrip(".,)") if match else None
    name = URL_RE.sub(" ", value)
    name = " ".join(name.split()).strip(" -")
    if not name:
        return None

    return NewChecklistItem(category=category, name=name, link=link, note=None)


def preserve_plain_single_item_text(text: str, parsed: ParsedActions) -> ParsedActions:
    plain_item = _plain_single_item_text(text)
    if plain_item is None or parsed.mark_done or len(parsed.new_items) != 1:
        return parsed

    item = parsed.new_items[0]
    return ParsedActions(
        new_items=[replace(item, name=plain_item)],
        mark_done=parsed.mark_done,
    )


def _plain_single_item_text(text: str) -> str | None:
    value = text.strip()
    if not value:
        return None
    lowered = value.casefold()
    if "\n" in value or "http://" in lowered or "https://" in lowered:
        return None
    if any(separator in value for separator in (",", ";", "•")):
        return None
    if lowered.startswith(_INTENT_PREFIXES):
        return None
    return value


_INTENT_PREFIXES = (
    "добавить ",
    "добавь ",
    "заказал ",
    "заказала ",
    "заказали ",
    "заказать ",
    "закажи ",
    "запиши ",
    "купил ",
    "купила ",
    "купили ",
    "купить ",
    "купи ",
    "надо ",
    "найти ",
    "не забыть ",
    "нужно ",
    "отметить ",
    "отметь ",
    "оформить ",
    "сделал ",
    "сделала ",
    "сделали ",
    "сделано",
    "сделать ",
    "упаковать ",
    "упакуй ",
    "взять ",
    "возьми ",
    "готово",
)
