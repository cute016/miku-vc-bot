from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, first_seen TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY, title TEXT, language TEXT DEFAULT 'en', first_seen TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS auth_users (chat_id INTEGER, user_id INTEGER, PRIMARY KEY(chat_id,user_id));
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chat_settings (chat_id INTEGER, key TEXT, value TEXT NOT NULL, PRIMARY KEY(chat_id,key));
CREATE TABLE IF NOT EXISTS blacklist (target_id INTEGER PRIMARY KEY, reason TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS stats (day TEXT PRIMARY KEY, songs INTEGER DEFAULT 0);
"""

DEFAULTS = {
    "maintenance": False, "logger": True, "bot_name": "Miku", "start_caption": "",
    "help_caption": "", "watermark": "@mikuvcrobot", "theme": "neon",
    "support_group": "", "update_channel": "", "owner_username": "",
    "force_subscribe": "", "assistant_username": "", "sudo_users": [],
}

EMOJI_DEFAULTS = {
    "play": "▶️", "pause": "⏸️", "stop": "⏹️", "skip": "⏭️", "queue": "📜",
    "owner": "👑", "support": "💬", "music": "🎵", "heart": "💗", "loading": "⏳",
    "success": "✅", "error": "❌",
}


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        for key, value in DEFAULTS.items():
            await self.conn.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (key, json.dumps(value)))
        for key, value in EMOJI_DEFAULTS.items():
            await self.conn.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (f"emoji:{key}", json.dumps(value)))
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def get(self, key: str, default: Any = None) -> Any:
        assert self.conn
        row = await (await self.conn.execute("SELECT value FROM settings WHERE key=?", (key,))).fetchone()
        return json.loads(row[0]) if row else default

    async def set(self, key: str, value: Any) -> None:
        assert self.conn
        await self.conn.execute("INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))
        await self.conn.commit()

    async def chat_get(self, chat_id: int, key: str, default: Any = None) -> Any:
        assert self.conn
        row = await (await self.conn.execute("SELECT value FROM chat_settings WHERE chat_id=? AND key=?", (chat_id, key))).fetchone()
        return json.loads(row[0]) if row else default

    async def chat_set(self, chat_id: int, key: str, value: Any) -> None:
        assert self.conn
        await self.conn.execute("INSERT INTO chat_settings VALUES (?,?,?) ON CONFLICT(chat_id,key) DO UPDATE SET value=excluded.value", (chat_id, key, json.dumps(value)))
        await self.conn.commit()

    async def touch(self, user_id: int, name: str, chat_id: int | None = None, title: str = "") -> None:
        assert self.conn
        await self.conn.execute("INSERT INTO users(user_id,name) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET name=excluded.name", (user_id, name[:128]))
        if chat_id:
            await self.conn.execute("INSERT INTO chats(chat_id,title) VALUES (?,?) ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title", (chat_id, title[:128]))
        await self.conn.commit()

    async def auth_add(self, chat_id: int, user_id: int) -> None:
        assert self.conn
        await self.conn.execute("INSERT OR IGNORE INTO auth_users VALUES (?,?)", (chat_id, user_id)); await self.conn.commit()

    async def auth_remove(self, chat_id: int, user_id: int) -> None:
        assert self.conn
        await self.conn.execute("DELETE FROM auth_users WHERE chat_id=? AND user_id=?", (chat_id, user_id)); await self.conn.commit()

    async def is_auth(self, chat_id: int, user_id: int) -> bool:
        assert self.conn
        row = await (await self.conn.execute("SELECT 1 FROM auth_users WHERE chat_id=? AND user_id=?", (chat_id, user_id))).fetchone()
        return bool(row)

    async def auth_list(self, chat_id: int) -> list[int]:
        assert self.conn
        rows = await (await self.conn.execute("SELECT user_id FROM auth_users WHERE chat_id=?", (chat_id,))).fetchall()
        return [r[0] for r in rows]

    async def count(self, table: str) -> int:
        if table not in {"users", "chats", "blacklist"}: raise ValueError("invalid table")
        assert self.conn
        return (await (await self.conn.execute(f"SELECT COUNT(*) FROM {table}")).fetchone())[0]

    async def all_ids(self, table: str) -> list[int]:
        if table not in {"users", "chats"}: raise ValueError("invalid table")
        column = "user_id" if table == "users" else "chat_id"
        assert self.conn
        return [r[0] for r in await (await self.conn.execute(f"SELECT {column} FROM {table}")).fetchall()]

    async def is_blacklisted(self, *target_ids: int) -> bool:
        ids=[x for x in target_ids if x]
        if not ids: return False
        assert self.conn
        marks=",".join("?" for _ in ids)
        row=await (await self.conn.execute(f"SELECT 1 FROM blacklist WHERE target_id IN ({marks}) LIMIT 1",ids)).fetchone()
        return bool(row)

    async def song_played(self) -> None:
        assert self.conn
        today = date.today().isoformat()
        await self.conn.execute("INSERT INTO stats VALUES (?,1) ON CONFLICT(day) DO UPDATE SET songs=songs+1", (today,)); await self.conn.commit()

    async def song_stats(self) -> tuple[int, int]:
        assert self.conn
        today = date.today().isoformat()
        daily = await (await self.conn.execute("SELECT songs FROM stats WHERE day=?", (today,))).fetchone()
        total = await (await self.conn.execute("SELECT COALESCE(SUM(songs),0) FROM stats")).fetchone()
        return (daily[0] if daily else 0, total[0])
