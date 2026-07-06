from __future__ import annotations

from app.database import ActionResult, ChecklistItem


CATEGORY_TITLES = {
    "buy": "🛒 Что купить",
    "take": "🎒 Что взять",
    "important": "⚠️ Важное",
}

STATUS_MARKERS = {
    "active": "□",
    "done": "✓",
}


def format_items(items: list[ChecklistItem], title: str | None = None) -> str:
    if not items:
        return "Список пока пуст."

    lines: list[str] = []
    if title:
        lines.extend([title, ""])

    for category in ("buy", "take", "important"):
        group = [item for item in items if item.category == category]
        if not group:
            continue
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(CATEGORY_TITLES[category])
        lines.extend(_format_item(item) for item in group)

    return "\n".join(lines).strip()


def format_action_result(result: ActionResult) -> str:
    if not result.has_changes:
        return "Я ничего не изменил. Если нужно, напишите вещь подробнее."

    lines: list[str] = []
    if result.added:
        lines.append("Добавлено:")
        lines.extend(_format_added_item(item) for item in result.added)
    if result.marked_done:
        if lines:
            lines.append("")
        lines.append("Отмечено выполненным:")
        lines.extend(f"✓ {item.name}" for item in result.marked_done)

    lines.append("")
    lines.append("Если я понял неправильно, нажмите «↩️ Отменить последнее».")
    return "\n".join(lines)


def format_undo_result(result: ActionResult | None) -> str:
    if result is None:
        return "Пока нечего отменять."
    if result.marked_done:
        restored = "\n".join(f"• {item.name}" for item in result.marked_done)
        return f"Отменила последнее действие. Снова активно:\n{restored}"
    return "Отменила последнее действие."


def _format_item(item: ChecklistItem) -> str:
    marker = STATUS_MARKERS[item.status]
    pieces = [f"{marker} #{item.id} {item.name}"]
    if item.link:
        pieces.append(item.link)
    if item.note:
        pieces.append(f"({item.note})")
    return " ".join(pieces)


def _format_added_item(item: ChecklistItem) -> str:
    pieces = [f"• {item.name}"]
    if item.link:
        pieces.append(item.link)
    if item.note:
        pieces.append(f"({item.note})")
    return " ".join(pieces)
