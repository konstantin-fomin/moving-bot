from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from typing import Any, Protocol

from app.database import ChecklistItem, NewChecklistItem


ALLOWED_CATEGORIES = {"buy", "take", "important"}


@dataclass(frozen=True)
class MarkDoneAction:
    item_id: int
    name: str | None = None


@dataclass(frozen=True)
class ParsedActions:
    new_items: list[NewChecklistItem]
    mark_done: list[MarkDoneAction]

    @property
    def is_empty(self) -> bool:
        return not self.new_items and not self.mark_done


class ChecklistParser(Protocol):
    async def parse_message(
        self,
        text: str,
        active_items: list[ChecklistItem],
    ) -> ParsedActions:
        ...


class GeminiChecklistParser:
    def __init__(self, api_key: str, model: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def parse_message(
        self,
        text: str,
        active_items: list[ChecklistItem],
    ) -> ParsedActions:
        response_text = await asyncio.to_thread(
            self._generate_content,
            text,
            active_items,
        )
        return parse_gemini_response(response_text)

    def _generate_content(self, text: str, active_items: list[ChecklistItem]) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._model,
            contents=_user_prompt(text, active_items),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        return response.text or "[]"


SYSTEM_PROMPT = """
Ты помощник Telegram-бота для организации переезда.
Разбирай русские пользовательские сообщения в строгий JSON-массив действий.
Не добавляй markdown, пояснения или текст вне JSON.

Если пользователь перечисляет вещи, которые нужно купить, взять или помнить,
верни объекты:
{"action":"add","name":"...","category":"buy|take|important","link":"... или null","note":"... или null"}
Для новых вещей сохраняй название без сокращений и пересказа. Не выбрасывай
бренды, магазины, получателей, назначения и уточнения из пользовательского
текста. Если всё сообщение пользователя — одна новая вещь без команды, скопируй
это сообщение в name дословно. Не переноси часть названия в note.

Если сообщение означает, что уже выполнена существующая вещь
("купила подгузники", "готово с курткой", "заказал коробки"), верни:
{"action":"mark_done","item_id":123,"name":"название существующей вещи"}

Для mark_done используй только id из списка активных вещей в пользовательском
промпте. Если уверенного совпадения нет, верни [].
Категория buy — купить/заказать. Категория take — взять/упаковать/не забыть
вещи. Категория important — документы, сроки, адреса, договоренности и риски.
Ссылки магазинов клади в link. Короткие уточнения клади в note.
""".strip()


def parse_gemini_response(response_text: str) -> ParsedActions:
    payload = json.loads(_strip_json_fence(response_text))
    if not isinstance(payload, list):
        raise ValueError("Gemini должен вернуть JSON-массив")

    new_items: list[NewChecklistItem] = []
    mark_done: list[MarkDoneAction] = []

    for raw in payload:
        if not isinstance(raw, dict):
            continue
        action = str(raw.get("action") or "add").strip()
        if action == "mark_done":
            item_id = raw.get("item_id", raw.get("id"))
            if isinstance(item_id, int):
                mark_done.append(
                    MarkDoneAction(
                        item_id=item_id,
                        name=_optional_string(raw.get("name")),
                    )
                )
            continue

        name = _optional_string(raw.get("name"))
        category = _optional_string(raw.get("category"))
        if not name or category not in ALLOWED_CATEGORIES:
            continue
        new_items.append(
            NewChecklistItem(
                category=category,  # type: ignore[arg-type]
                name=name,
                link=_optional_string(raw.get("link")),
                note=_optional_string(raw.get("note")),
            )
        )

    return ParsedActions(new_items=new_items, mark_done=mark_done)


def _user_prompt(text: str, active_items: list[ChecklistItem]) -> str:
    active_payload = [
        {"id": item.id, "name": item.name, "category": item.category}
        for item in active_items
    ]
    return (
        "Активные вещи для сопоставления mark_done:\n"
        f"{json.dumps(active_payload, ensure_ascii=False)}\n\n"
        "Сообщение пользователя:\n"
        f"{text}"
    )


def _strip_json_fence(value: str) -> str:
    value = value.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or value.lower() == "null":
        return None
    return value
