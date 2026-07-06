from __future__ import annotations

from app.database import ActionResult, Database, NewChecklistItem, User
from app.services.gemini import ChecklistParser


async def process_user_message(
    db: Database,
    user: User,
    text: str,
    parser: ChecklistParser,
) -> ActionResult:
    active_items = await db.list_items(status="active")
    parsed = await parser.parse_message(text, active_items)
    mark_done_ids = [action.item_id for action in parsed.mark_done]
    return await db.apply_actions(
        user_id=user.id,
        new_items=parsed.new_items,
        mark_done_ids=mark_done_ids,
    )


def clean_manual_items(items: list[NewChecklistItem]) -> list[NewChecklistItem]:
    return [item for item in items if item.name.strip()]
