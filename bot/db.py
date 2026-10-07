"""SQLite úložiště: aktivační kódy, předplatné, tikety a ID kanálů/rolí/panelů."""

from __future__ import annotations

import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

DAY = 24 * 60 * 60
CODE_PREFIX = "TM"
# Bez znaků, které se pletou (0/O, 1/I/L).
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

SCHEMA = """
CREATE TABLE IF NOT EXISTS objects (
    guild_id  INTEGER NOT NULL,
    key       TEXT    NOT NULL,
    object_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, key)
);
CREATE TABLE IF NOT EXISTS panels (
    guild_id   INTEGER NOT NULL,
    key        TEXT    NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, key)
);
CREATE TABLE IF NOT EXISTS codes (
    code        TEXT    PRIMARY KEY,
    guild_id    INTEGER NOT NULL,
    days        INTEGER NOT NULL,
    note        TEXT,
    created_at  INTEGER NOT NULL,
    created_by  INTEGER,
    redeemed_by INTEGER,
    redeemed_at INTEGER
);
CREATE TABLE IF NOT EXISTS subscriptions (
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    expires_at INTEGER,
    reminded   INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS tickets (
    channel_id INTEGER PRIMARY KEY,
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    opened_at  INTEGER NOT NULL,
    closed_at  INTEGER
);
"""


class RedeemError(Exception):
    """Kód nejde uplatnit."""


class CodeNotFound(RedeemError):
    pass


class CodeAlreadyUsed(RedeemError):
    pass


@dataclass(frozen=True)
class Subscription:
    guild_id: int
    user_id: int
    expires_at: int | None  # None = doživotně
    reminded: bool

    @property
    def lifetime(self) -> bool:
        return self.expires_at is None

    def is_active(self, now: int | None = None) -> bool:
        return self.expires_at is None or self.expires_at > _now(now)


@dataclass(frozen=True)
class Code:
    code: str
    days: int  # 0 = doživotně
    note: str | None
    created_at: int
    redeemed_by: int | None
    redeemed_at: int | None


def _now(now: int | None) -> int:
    return int(time.time()) if now is None else now


def normalize_code(raw: str) -> str:
    """Převede vstup typu ``tm abcd-efgh jkmn`` na kanonické ``TM-ABCD-EFGH-JKMN``."""
    chars = re.sub(r"[^A-Z0-9]", "", raw.upper())
    if chars.startswith(CODE_PREFIX) and len(chars) == len(CODE_PREFIX) + 12:
        body = chars[len(CODE_PREFIX):]
        return f"{CODE_PREFIX}-{body[0:4]}-{body[4:8]}-{body[8:12]}"
    return chars


def generate_code() -> str:
    body = "".join(secrets.choice(CODE_ALPHABET) for _ in range(12))
    return f"{CODE_PREFIX}-{body[0:4]}-{body[4:8]}-{body[8:12]}"


class Database:
    def __init__(self, path: str | Path) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # --- ID rolí a kanálů vytvořených přes /setup -------------------------

    def set_object(self, guild_id: int, key: str, object_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO objects (guild_id, key, object_id) VALUES (?, ?, ?) "
                "ON CONFLICT (guild_id, key) DO UPDATE SET object_id = excluded.object_id",
                (guild_id, key, object_id),
            )

    def get_object(self, guild_id: int, key: str) -> int | None:
        row = self.conn.execute(
            "SELECT object_id FROM objects WHERE guild_id = ? AND key = ?", (guild_id, key)
        ).fetchone()
        return row["object_id"] if row else None

    def object_ids(self, guild_id: int) -> set[int]:
        rows = self.conn.execute("SELECT object_id FROM objects WHERE guild_id = ?", (guild_id,))
        return {row["object_id"] for row in rows}

    # --- Zprávy s tlačítky (panely) ---------------------------------------

    def set_panel(self, guild_id: int, key: str, channel_id: int, message_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO panels (guild_id, key, channel_id, message_id) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (guild_id, key) DO UPDATE SET "
                "channel_id = excluded.channel_id, message_id = excluded.message_id",
                (guild_id, key, channel_id, message_id),
            )

    def get_panel(self, guild_id: int, key: str) -> tuple[int, int] | None:
        row = self.conn.execute(
            "SELECT channel_id, message_id FROM panels WHERE guild_id = ? AND key = ?",
            (guild_id, key),
        ).fetchone()
        return (row["channel_id"], row["message_id"]) if row else None

    # --- Aktivační kódy ---------------------------------------------------

    def create_codes(
        self,
        guild_id: int,
        count: int,
        days: int,
        *,
        note: str | None = None,
        created_by: int | None = None,
        now: int | None = None,
    ) -> list[str]:
        if count < 1:
            raise ValueError("count musí být alespoň 1")
        if days < 0:
            raise ValueError("days nesmí být záporné")
        created: list[str] = []
        with self.conn:
            while len(created) < count:
                code = generate_code()
                cursor = self.conn.execute(
                    "INSERT OR IGNORE INTO codes (code, guild_id, days, note, created_at, created_by) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (code, guild_id, days, note, _now(now), created_by),
                )
                if cursor.rowcount:
                    created.append(code)
        return created

    def unused_codes(self, guild_id: int, limit: int = 50) -> list[Code]:
        rows = self.conn.execute(
            "SELECT * FROM codes WHERE guild_id = ? AND redeemed_by IS NULL "
            "ORDER BY created_at DESC, code LIMIT ?",
            (guild_id, limit),
        )
        return [_code(row) for row in rows]

    def delete_code(self, guild_id: int, raw_code: str) -> bool:
        """Smaže nepoužitý kód. Vrací False, když neexistuje nebo už byl uplatněn."""
        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM codes WHERE code = ? AND guild_id = ? AND redeemed_by IS NULL",
                (normalize_code(raw_code), guild_id),
            )
        return cursor.rowcount > 0

    def redeem_code(
        self, guild_id: int, user_id: int, raw_code: str, *, now: int | None = None
    ) -> tuple[Code, Subscription]:
        code = normalize_code(raw_code)
        now = _now(now)
        with self.conn:
            row = self.conn.execute(
                "SELECT * FROM codes WHERE code = ? AND guild_id = ?", (code, guild_id)
            ).fetchone()
            if row is None:
                raise CodeNotFound(code)
            if row["redeemed_by"] is not None:
                raise CodeAlreadyUsed(code)
            self.conn.execute(
                "UPDATE codes SET redeemed_by = ?, redeemed_at = ? WHERE code = ?",
                (user_id, now, code),
            )
            subscription = self._grant(guild_id, user_id, row["days"], now)
        return _code(row), subscription

    # --- Předplatné -------------------------------------------------------

    def grant(self, guild_id: int, user_id: int, days: int, *, now: int | None = None) -> Subscription:
        """Přidá ``days`` dní Premium (0 = doživotně). Zbývající čas se nepropadá."""
        with self.conn:
            return self._grant(guild_id, user_id, days, _now(now))

    def _grant(self, guild_id: int, user_id: int, days: int, now: int) -> Subscription:
        current = self.get_subscription(guild_id, user_id)
        if current is not None and current.lifetime:
            return current
        if days == 0:
            expires_at = None
        else:
            start = max(now, current.expires_at) if current is not None else now
            expires_at = start + days * DAY
        self.conn.execute(
            "INSERT INTO subscriptions (guild_id, user_id, expires_at, reminded, updated_at) "
            "VALUES (?, ?, ?, 0, ?) ON CONFLICT (guild_id, user_id) DO UPDATE SET "
            "expires_at = excluded.expires_at, reminded = 0, updated_at = excluded.updated_at",
            (guild_id, user_id, expires_at, now),
        )
        return Subscription(guild_id, user_id, expires_at, False)

    def revoke(self, guild_id: int, user_id: int) -> bool:
        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM subscriptions WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
            )
        return cursor.rowcount > 0

    def get_subscription(self, guild_id: int, user_id: int) -> Subscription | None:
        row = self.conn.execute(
            "SELECT * FROM subscriptions WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        ).fetchone()
        return _subscription(row) if row else None

    def active_subscriptions(self, guild_id: int, *, now: int | None = None) -> list[Subscription]:
        rows = self.conn.execute(
            "SELECT * FROM subscriptions WHERE guild_id = ? AND (expires_at IS NULL OR expires_at > ?) "
            "ORDER BY expires_at IS NULL, expires_at",
            (guild_id, _now(now)),
        )
        return [_subscription(row) for row in rows]

    def expired_subscriptions(self, *, now: int | None = None) -> list[Subscription]:
        rows = self.conn.execute(
            "SELECT * FROM subscriptions WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (_now(now),),
        )
        return [_subscription(row) for row in rows]

    def due_reminders(self, within: int, *, now: int | None = None) -> list[Subscription]:
        now = _now(now)
        rows = self.conn.execute(
            "SELECT * FROM subscriptions WHERE reminded = 0 AND expires_at IS NOT NULL "
            "AND expires_at > ? AND expires_at <= ?",
            (now, now + within),
        )
        return [_subscription(row) for row in rows]

    def mark_reminded(self, guild_id: int, user_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE subscriptions SET reminded = 1 WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )

    # --- Tikety -----------------------------------------------------------

    def open_ticket(self, guild_id: int, user_id: int, channel_id: int, *, now: int | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO tickets (channel_id, guild_id, user_id, opened_at) VALUES (?, ?, ?, ?)",
                (channel_id, guild_id, user_id, _now(now)),
            )

    def find_open_ticket(self, guild_id: int, user_id: int) -> int | None:
        row = self.conn.execute(
            "SELECT channel_id FROM tickets WHERE guild_id = ? AND user_id = ? AND closed_at IS NULL",
            (guild_id, user_id),
        ).fetchone()
        return row["channel_id"] if row else None

    def ticket_owner(self, channel_id: int) -> int | None:
        row = self.conn.execute(
            "SELECT user_id FROM tickets WHERE channel_id = ? AND closed_at IS NULL", (channel_id,)
        ).fetchone()
        return row["user_id"] if row else None

    def close_ticket(self, channel_id: int, *, now: int | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE tickets SET closed_at = ? WHERE channel_id = ? AND closed_at IS NULL",
                (_now(now), channel_id),
            )


def _code(row: sqlite3.Row) -> Code:
    return Code(
        code=row["code"],
        days=row["days"],
        note=row["note"],
        created_at=row["created_at"],
        redeemed_by=row["redeemed_by"],
        redeemed_at=row["redeemed_at"],
    )


def _subscription(row: sqlite3.Row) -> Subscription:
    return Subscription(
        guild_id=row["guild_id"],
        user_id=row["user_id"],
        expires_at=row["expires_at"],
        reminded=bool(row["reminded"]),
    )
