from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import secrets
import sqlite3
from typing import Literal


Role = Literal["owner", "member"]
Category = Literal["buy", "take", "important"]
Status = Literal["active", "done"]


@dataclass(frozen=True)
class User:
    id: int
    telegram_id: int
    name: str
    role: Role
    created_at: str


@dataclass(frozen=True)
class Invitation:
    id: int
    code: str
    created_by_user_id: int
    used_by_user_id: int | None
    created_at: str
    used_at: str | None


@dataclass(frozen=True)
class NewChecklistItem:
    category: Category
    name: str
    link: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class ChecklistItem:
    id: int
    category: Category
    status: Status
    name: str
    link: str | None
    note: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ActionResult:
    added: list[ChecklistItem]
    marked_done: list[ChecklistItem]
    undone: bool = False

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.marked_done)


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._connection: sqlite3.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.commit()

    async def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    async def init_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL UNIQUE,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('owner', 'member')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_users_telegram_id
                ON users (telegram_id);

            CREATE TABLE IF NOT EXISTS invitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                created_by_user_id INTEGER NOT NULL,
                used_by_user_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                used_at TEXT,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id),
                FOREIGN KEY (used_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_invitations_code
                ON invitations (code);

            CREATE TABLE IF NOT EXISTS checklist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL CHECK (category IN ('buy', 'take', 'important')),
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'done')),
                name TEXT NOT NULL,
                link TEXT,
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_checklist_items_category_status
                ON checklist_items (category, status);

            CREATE TABLE IF NOT EXISTS action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                undone INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_action_logs_user
                ON action_logs (user_id, undone, id);

            CREATE TABLE IF NOT EXISTS action_log_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_log_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                operation TEXT NOT NULL CHECK (operation IN ('add', 'mark_done')),
                previous_status TEXT CHECK (
                    previous_status IS NULL OR previous_status IN ('active', 'done')
                ),
                FOREIGN KEY (action_log_id) REFERENCES action_logs(id) ON DELETE CASCADE,
                FOREIGN KEY (item_id) REFERENCES checklist_items(id) ON DELETE CASCADE
            );
            """
        )
        self._db.commit()

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        row = self._fetchone(
            "SELECT id, telegram_id, name, role, created_at FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        return _user_from_row(row) if row else None

    async def users_count(self) -> int:
        row = self._fetchone("SELECT COUNT(*) AS count FROM users")
        return int(row["count"])

    async def create_owner_if_first(self, telegram_id: int, name: str) -> User | None:
        db = self._db
        db.execute("BEGIN IMMEDIATE")
        try:
            row = self._fetchone("SELECT COUNT(*) AS count FROM users")
            if int(row["count"]) > 0:
                db.rollback()
                return None

            db.execute(
                "INSERT INTO users (telegram_id, name, role) VALUES (?, ?, 'owner')",
                (telegram_id, name),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        user = await self.get_user_by_telegram_id(telegram_id)
        if user is None:
            raise RuntimeError("Не удалось создать владельца")
        return user

    async def list_users(self) -> list[User]:
        cursor = self._db.execute(
            """
            SELECT id, telegram_id, name, role, created_at
            FROM users
            ORDER BY
                CASE role WHEN 'owner' THEN 0 ELSE 1 END,
                created_at,
                id
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        return [_user_from_row(row) for row in rows]

    async def create_invitation(self, owner_user_id: int) -> Invitation:
        code = secrets.token_urlsafe(8)
        self._db.execute(
            "INSERT INTO invitations (code, created_by_user_id) VALUES (?, ?)",
            (code, owner_user_id),
        )
        self._db.commit()
        invitation = await self.get_invitation(code)
        if invitation is None:
            raise RuntimeError("Не удалось создать приглашение")
        return invitation

    async def get_invitation(self, code: str) -> Invitation | None:
        row = self._fetchone(
            """
            SELECT id, code, created_by_user_id, used_by_user_id, created_at, used_at
            FROM invitations
            WHERE code = ?
            """,
            (code,),
        )
        return _invitation_from_row(row) if row else None

    async def consume_invitation(self, code: str, telegram_id: int, name: str) -> User | None:
        db = self._db
        db.execute("BEGIN IMMEDIATE")
        try:
            existing_user = self._fetchone(
                "SELECT id, telegram_id, name, role, created_at FROM users WHERE telegram_id = ?",
                (telegram_id,),
            )
            if existing_user is not None:
                db.rollback()
                return _user_from_row(existing_user)

            invitation = self._fetchone(
                """
                SELECT id
                FROM invitations
                WHERE code = ? AND used_by_user_id IS NULL
                """,
                (code,),
            )
            if invitation is None:
                db.rollback()
                return None

            cursor = db.execute(
                "INSERT INTO users (telegram_id, name, role) VALUES (?, ?, 'member')",
                (telegram_id, name),
            )
            new_user_id = int(cursor.lastrowid)
            cursor.close()
            db.execute(
                """
                UPDATE invitations
                SET used_by_user_id = ?, used_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_user_id, invitation["id"]),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        return await self.get_user_by_telegram_id(telegram_id)

    async def list_items(
        self,
        category: Category | None = None,
        status: Status | None = None,
    ) -> list[ChecklistItem]:
        clauses: list[str] = []
        params: list[str] = []
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cursor = self._db.execute(
            f"""
            SELECT id, category, status, name, link, note, created_at, updated_at
            FROM checklist_items
            {where}
            ORDER BY
                CASE category WHEN 'buy' THEN 0 WHEN 'take' THEN 1 ELSE 2 END,
                CASE status WHEN 'active' THEN 0 ELSE 1 END,
                id
            """,
            tuple(params),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [_item_from_row(row) for row in rows]

    async def get_item(self, item_id: int) -> ChecklistItem | None:
        row = self._fetchone(
            """
            SELECT id, category, status, name, link, note, created_at, updated_at
            FROM checklist_items
            WHERE id = ?
            """,
            (item_id,),
        )
        return _item_from_row(row) if row else None

    async def apply_actions(
        self,
        user_id: int,
        new_items: list[NewChecklistItem],
        mark_done_ids: list[int],
    ) -> ActionResult:
        db = self._db
        added_ids: list[int] = []
        marked_ids: list[int] = []
        unique_mark_ids = list(dict.fromkeys(mark_done_ids))

        db.execute("BEGIN IMMEDIATE")
        try:
            action_id = self._create_action_log(user_id)

            for item in new_items:
                cursor = db.execute(
                    """
                    INSERT INTO checklist_items (category, status, name, link, note)
                    VALUES (?, 'active', ?, ?, ?)
                    """,
                    (
                        item.category,
                        item.name.strip(),
                        _blank_to_none(item.link),
                        _blank_to_none(item.note),
                    ),
                )
                item_id = int(cursor.lastrowid)
                cursor.close()
                added_ids.append(item_id)
                db.execute(
                    """
                    INSERT INTO action_log_items
                        (action_log_id, item_id, operation, previous_status)
                    VALUES (?, ?, 'add', NULL)
                    """,
                    (action_id, item_id),
                )

            for item_id in unique_mark_ids:
                row = self._fetchone(
                    """
                    SELECT id, status FROM checklist_items
                    WHERE id = ? AND status = 'active'
                    """,
                    (item_id,),
                )
                if row is None:
                    continue
                db.execute(
                    """
                    UPDATE checklist_items
                    SET status = 'done', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (item_id,),
                )
                marked_ids.append(item_id)
                db.execute(
                    """
                    INSERT INTO action_log_items
                        (action_log_id, item_id, operation, previous_status)
                    VALUES (?, ?, 'mark_done', ?)
                    """,
                    (action_id, item_id, row["status"]),
                )

            if not added_ids and not marked_ids:
                db.execute("DELETE FROM action_logs WHERE id = ?", (action_id,))

            db.commit()
        except Exception:
            db.rollback()
            raise

        return ActionResult(
            added=[item for item_id in added_ids if (item := await self.get_item(item_id))],
            marked_done=[
                item for item_id in marked_ids if (item := await self.get_item(item_id))
            ],
        )

    async def undo_last_action(self, user_id: int) -> ActionResult | None:
        action = self._fetchone(
            """
            SELECT id FROM action_logs
            WHERE user_id = ? AND undone = 0
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        if action is None:
            return None

        rows = self._fetchall(
            """
            SELECT item_id, operation, previous_status
            FROM action_log_items
            WHERE action_log_id = ?
            ORDER BY id DESC
            """,
            (action["id"],),
        )
        restored_ids: list[int] = []

        db = self._db
        db.execute("BEGIN IMMEDIATE")
        try:
            for row in rows:
                if row["operation"] == "add":
                    db.execute("DELETE FROM checklist_items WHERE id = ?", (row["item_id"],))
                elif row["operation"] == "mark_done" and row["previous_status"]:
                    db.execute(
                        """
                        UPDATE checklist_items
                        SET status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (row["previous_status"], row["item_id"]),
                    )
                    restored_ids.append(int(row["item_id"]))

            db.execute("UPDATE action_logs SET undone = 1 WHERE id = ?", (action["id"],))
            db.commit()
        except Exception:
            db.rollback()
            raise

        return ActionResult(
            added=[],
            marked_done=[
                item for item_id in restored_ids if (item := await self.get_item(item_id))
            ],
            undone=True,
        )

    @property
    def _db(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("База данных не подключена")
        return self._connection

    def _fetchone(
        self,
        query: str,
        params: tuple = (),
    ) -> sqlite3.Row | None:
        cursor = self._db.execute(query, params)
        row = cursor.fetchone()
        cursor.close()
        return row

    def _fetchall(
        self,
        query: str,
        params: tuple = (),
    ) -> list[sqlite3.Row]:
        cursor = self._db.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def _create_action_log(self, user_id: int) -> int:
        cursor = self._db.execute(
            "INSERT INTO action_logs (user_id) VALUES (?)",
            (user_id,),
        )
        action_id = int(cursor.lastrowid)
        cursor.close()
        return action_id


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _user_from_row(row: sqlite3.Row) -> User:
    return User(
        id=int(row["id"]),
        telegram_id=int(row["telegram_id"]),
        name=str(row["name"]),
        role=row["role"],
        created_at=str(row["created_at"]),
    )


def _invitation_from_row(row: sqlite3.Row) -> Invitation:
    return Invitation(
        id=int(row["id"]),
        code=str(row["code"]),
        created_by_user_id=int(row["created_by_user_id"]),
        used_by_user_id=(
            int(row["used_by_user_id"]) if row["used_by_user_id"] is not None else None
        ),
        created_at=str(row["created_at"]),
        used_at=str(row["used_at"]) if row["used_at"] is not None else None,
    )


def _item_from_row(row: sqlite3.Row) -> ChecklistItem:
    return ChecklistItem(
        id=int(row["id"]),
        category=row["category"],
        status=row["status"],
        name=str(row["name"]),
        link=str(row["link"]) if row["link"] is not None else None,
        note=str(row["note"]) if row["note"] is not None else None,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
