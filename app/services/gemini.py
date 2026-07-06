from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from typing import Any, Protocol

from app.database import ChecklistItem, NewChecklistItem
from app.services.voice_actions import VoiceCommand


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

    async def parse_voice_message(
        self,
        audio: bytes,
        mime_type: str,
        active_items: list[ChecklistItem],
    ) -> list[VoiceCommand]:
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

    async def parse_voice_message(
        self,
        audio: bytes,
        mime_type: str,
        active_items: list[ChecklistItem],
    ) -> list[VoiceCommand]:
        response_text = await asyncio.to_thread(
            self._generate_voice_content,
            audio,
            mime_type,
            active_items,
        )
        return parse_voice_gemini_response(response_text)

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

    def _generate_voice_content(
        self,
        audio: bytes,
        mime_type: str,
        active_items: list[ChecklistItem],
    ) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                _voice_user_prompt(active_items),
                types.Part.from_bytes(data=audio, mime_type=mime_type),
            ],
            config=types.GenerateContentConfig(
                system_instruction=VOICE_SYSTEM_PROMPT,
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


VOICE_SYSTEM_PROMPT = """
Ты помощник Telegram-бота для организации переезда.
Разбирай голосовое сообщение пользователя в строгий JSON-массив действий.
Не добавляй markdown, пояснения или текст вне JSON.

Пользователь может голосом:
- надиктовать список новых вещей;
- попросить удалить существующую вещь;
- попросить изменить существующую вещь;
- сказать, что вещь уже куплена, взята, сделана или больше не нужна.

Для новых вещей верни:
{"action":"add","name":"полное название без сокращений","category":"buy|take|important","link":null,"note":null}

Если пользователь надиктовал несколько новых пунктов, верни несколько add-объектов.
Сохраняй бренды, магазины, получателей и уточнения в name. Не сокращай name.

Для отметки выполненным верни:
{"action":"mark_done","item_id":123,"name":"название существующей вещи"}

Для удаления верни:
{"action":"delete","item_id":123,"name":"название существующей вещи"}

Для редактирования верни:
{"action":"edit","item_id":123,"name":"старое название","new_name":"новое полное название","new_link":null,"new_note":null}

Для mark_done, delete и edit используй только id из списка текущих вещей.
Если уверенного совпадения нет, не придумывай id и верни [].
Категория buy — купить/заказать. Категория take — взять/упаковать/не забыть
вещи. Категория important — документы, сроки, адреса, договоренности и риски.
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


def parse_voice_gemini_response(response_text: str) -> list[VoiceCommand]:
    payload = json.loads(_strip_json_fence(response_text))
    if not isinstance(payload, list):
        raise ValueError("Gemini должен вернуть JSON-массив")

    commands: list[VoiceCommand] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        command = _voice_command_from_raw(raw)
        if command is not None:
            commands.append(command)
    return commands


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


def _voice_user_prompt(active_items: list[ChecklistItem]) -> str:
    active_payload = [
        {
            "id": item.id,
            "name": item.name,
            "category": item.category,
            "status": item.status,
        }
        for item in active_items
    ]
    return (
        "Текущие вещи для сопоставления действий:\n"
        f"{json.dumps(active_payload, ensure_ascii=False)}\n\n"
        "Распознай голосовое сообщение и верни JSON-массив действий."
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


def _voice_command_from_raw(raw: dict[str, Any]) -> VoiceCommand | None:
    action = _optional_string(raw.get("action"))
    if action == "add":
        category = _optional_string(raw.get("category"))
        name = _optional_string(raw.get("name"))
        if category not in ALLOWED_CATEGORIES or not name:
            return None
        return VoiceCommand(
            action="add",
            category=category,  # type: ignore[arg-type]
            name=name,
            link=_optional_string(raw.get("link")),
            note=_optional_string(raw.get("note")),
        )

    if action in ("mark_done", "delete"):
        item_id = raw.get("item_id", raw.get("id"))
        if not isinstance(item_id, int):
            return None
        return VoiceCommand(action=action, item_id=item_id)  # type: ignore[arg-type]

    if action == "edit":
        item_id = raw.get("item_id", raw.get("id"))
        new_name = _optional_string(raw.get("new_name"))
        if not isinstance(item_id, int) or not new_name:
            return None
        return VoiceCommand(
            action="edit",
            item_id=item_id,
            new_name=new_name,
            new_link=_optional_string(raw.get("new_link")),
            new_note=_optional_string(raw.get("new_note")),
        )

    return None
