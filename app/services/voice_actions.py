from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from app.database import Category, ChecklistItem, Database, NewChecklistItem, User


VoiceAction = Literal["add", "mark_done", "delete", "edit"]


@dataclass(frozen=True)
class VoiceCommand:
    action: VoiceAction
    item_id: int | None = None
    category: Category | None = None
    name: str | None = None
    link: str | None = None
    note: str | None = None
    new_name: str | None = None
    new_link: str | None = None
    new_note: str | None = None


@dataclass(frozen=True)
class VoiceApplyResult:
    added: list[ChecklistItem]
    marked_done: list[ChecklistItem]
    edited: list[ChecklistItem]
    deleted: list[ChecklistItem]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.marked_done or self.edited or self.deleted)


def voice_commands_to_dicts(commands: list[VoiceCommand]) -> list[dict[str, Any]]:
    return [asdict(command) for command in commands]


def voice_commands_from_dicts(values: list[dict[str, Any]]) -> list[VoiceCommand]:
    commands: list[VoiceCommand] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        command = _command_from_dict(value)
        if command is not None:
            commands.append(command)
    return commands


def format_voice_confirmation(
    commands: list[VoiceCommand],
    items: list[ChecklistItem],
) -> str:
    item_names = {item.id: item.name for item in items}
    lines = ["Я поняла так:"]
    for command in commands:
        lines.append(f"• {_format_command(command, item_names)}")
    lines.append("")
    lines.append("Применить это действие?")
    return "\n".join(lines)


def format_voice_apply_result(result: VoiceApplyResult) -> str:
    if not result.has_changes:
        return "Ничего не изменила."

    lines = ["Готово:"]
    lines.extend(f"• Добавлено: {item.name}" for item in result.added)
    lines.extend(f"• Отмечено выполненным: {item.name}" for item in result.marked_done)
    lines.extend(f"• Обновлено: {item.name}" for item in result.edited)
    lines.extend(f"• Удалено: {item.name}" for item in result.deleted)
    return "\n".join(lines)


async def apply_voice_commands(
    db: Database,
    user: User,
    commands: list[VoiceCommand],
) -> VoiceApplyResult:
    new_items = [
        NewChecklistItem(
            category=command.category,
            name=command.name or "",
            link=command.link,
            note=command.note,
        )
        for command in commands
        if command.action == "add" and command.category is not None and command.name
    ]
    mark_done_ids = [
        command.item_id
        for command in commands
        if command.action == "mark_done" and command.item_id is not None
    ]

    action_result = await db.apply_actions(user.id, new_items, mark_done_ids)
    edited: list[ChecklistItem] = []
    deleted: list[ChecklistItem] = []

    for command in commands:
        if command.action == "edit" and command.item_id is not None and command.new_name:
            existing = await db.get_item(command.item_id)
            if existing is None:
                continue
            updated = await db.update_item(
                existing.id,
                command.new_name,
                command.new_link if command.new_link is not None else existing.link,
                command.new_note if command.new_note is not None else existing.note,
            )
            if updated is not None:
                edited.append(updated)
        elif command.action == "delete" and command.item_id is not None:
            removed = await db.delete_item(command.item_id)
            if removed is not None:
                deleted.append(removed)

    return VoiceApplyResult(
        added=action_result.added,
        marked_done=action_result.marked_done,
        edited=edited,
        deleted=deleted,
    )


def _format_command(command: VoiceCommand, item_names: dict[int, str]) -> str:
    if command.action == "add":
        category = _category_title(command.category)
        return f"добавить в {category}: {command.name}"
    if command.action == "mark_done":
        return f"отметить выполненным: {_item_name(command.item_id, item_names)}"
    if command.action == "delete":
        return f"удалить: {_item_name(command.item_id, item_names)}"
    if command.action == "edit":
        return (
            f"изменить: {_item_name(command.item_id, item_names)}"
            f" → {command.new_name}"
        )
    return "неизвестное действие"


def _item_name(item_id: int | None, item_names: dict[int, str]) -> str:
    if item_id is None:
        return "неизвестный пункт"
    name = item_names.get(item_id)
    return f"{name} (#{item_id})" if name else f"#{item_id}"


def _category_title(category: Category | None) -> str:
    return {
        "buy": "покупки",
        "take": "что взять",
        "important": "важное",
    }.get(category, "список")


def _command_from_dict(value: dict[str, Any]) -> VoiceCommand | None:
    action = value.get("action")
    if action not in ("add", "mark_done", "delete", "edit"):
        return None
    category = value.get("category")
    if category not in ("buy", "take", "important", None):
        category = None
    return VoiceCommand(
        action=action,
        item_id=value.get("item_id") if isinstance(value.get("item_id"), int) else None,
        category=category,
        name=_optional_string(value.get("name")),
        link=_optional_string(value.get("link")),
        note=_optional_string(value.get("note")),
        new_name=_optional_string(value.get("new_name")),
        new_link=_optional_string(value.get("new_link")),
        new_note=_optional_string(value.get("new_note")),
    )


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
