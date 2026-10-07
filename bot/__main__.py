"""Spuštění: python -m bot"""

from __future__ import annotations

import logging
import sys

import discord

from .client import TradingBot
from .config import ConfigError, load_settings
from .db import Database

log = logging.getLogger("bot")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    try:
        settings = load_settings()
    except ConfigError as error:
        log.error("%s", error)
        return 1

    db = Database(settings.database_path)
    bot = TradingBot(settings, db)
    try:
        bot.run(settings.token, log_handler=None)
    except discord.LoginFailure:
        log.error("Discord odmítl token. Zkontroluj DISCORD_TOKEN v .env (případně ho v Developer Portalu resetuj).")
        return 1
    except discord.PrivilegedIntentsRequired:
        log.error(
            "Zapni v Developer Portalu → tvoje aplikace → Bot → „Server Members Intent“ a spusť bota znovu."
        )
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
