"""Nastavení bota z proměnných prostředí (nebo ze souboru .env)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    token: str
    guild_id: int | None
    database_path: Path
    payment_url: str | None


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None:
        load_dotenv()
        env = os.environ

    token = env.get("DISCORD_TOKEN", "").strip()
    if not token or token.startswith("sem-"):
        raise ConfigError(
            "Chybí DISCORD_TOKEN. Zkopíruj .env.example do .env a vlož token bota "
            "z https://discord.com/developers/applications (sekce Bot → Reset Token)."
        )

    guild_raw = env.get("GUILD_ID", "").strip()
    try:
        guild_id = int(guild_raw) if guild_raw else None
    except ValueError:
        raise ConfigError(f"GUILD_ID musí být číslo (ID serveru), ne {guild_raw!r}.") from None

    payment_url = env.get("PAYMENT_URL", "").strip() or None
    if payment_url and not payment_url.startswith(("https://", "http://")):
        raise ConfigError("PAYMENT_URL musí být celý odkaz začínající https://")

    return Settings(
        token=token,
        guild_id=guild_id,
        database_path=Path(env.get("DATABASE_PATH", "").strip() or "data/bot.db"),
        payment_url=payment_url,
    )
