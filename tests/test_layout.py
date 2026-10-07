import re

import discord
import pytest

from bot.client import TradingBot
from bot.config import ConfigError, load_settings
from bot.layout import (
    BOT,
    CATEGORIES,
    CATEGORIES_BY_KEY,
    CHANNELS_BY_KEY,
    EVERYONE,
    LOG_CHANNEL,
    MEMBER,
    MOD,
    PREMIUM,
    ROLES,
    ROLES_BY_KEY,
    TICKET_CATEGORY,
    build_overwrites,
)
from bot.texts import TEXTS_DIR, load_text, placeholders, render

ALL_CHANNELS = [channel for category in CATEGORIES for channel in category.channels]


def test_keys_and_names_are_unique() -> None:
    assert len(CHANNELS_BY_KEY) == len(ALL_CHANNELS)
    assert len(CATEGORIES_BY_KEY) == len(CATEGORIES)
    assert len(ROLES_BY_KEY) == len(ROLES)
    names = [c.name for c in ALL_CHANNELS] + [c.name for c in CATEGORIES]
    assert len(set(names)) == len(names)
    assert TICKET_CATEGORY in CATEGORIES_BY_KEY
    assert LOG_CHANNEL in CHANNELS_BY_KEY


@pytest.mark.parametrize("channel", [c for c in ALL_CHANNELS if not c.voice], ids=lambda c: c.key)
def test_text_channel_names_survive_discord_normalisation(channel) -> None:
    # Discord převádí názvy textových kanálů na malá písmena a mezery na pomlčky.
    assert channel.name == channel.name.lower()
    assert " " not in channel.name
    assert len(channel.name) <= 100
    assert len(channel.topic) <= 1024


def test_role_permissions_are_valid() -> None:
    for role in ROLES:
        discord.Permissions(**dict.fromkeys(role.permissions, True))


@pytest.mark.parametrize("channel", ALL_CHANNELS + list(CATEGORIES), ids=lambda c: c.key)
def test_overwrites_use_valid_permissions_and_writers_can_read(channel) -> None:
    voice = getattr(channel, "voice", False)
    overwrites = build_overwrites(channel.access, voice=voice)
    for permissions in overwrites.values():
        discord.PermissionOverwrite(**permissions)
    readers = channel.access.view
    for writer in channel.access.send:
        assert writer in readers or EVERYONE in readers


def test_premium_channels_are_hidden_from_everyone_else() -> None:
    overwrites = build_overwrites(CHANNELS_BY_KEY["navod"].access)
    assert overwrites[EVERYONE]["view_channel"] is False
    assert overwrites[PREMIUM]["view_channel"] is True
    assert "send_messages" not in overwrites[PREMIUM]  # jen čtení
    assert MEMBER not in overwrites
    assert overwrites[MOD]["send_messages"] is True
    assert overwrites[BOT]["send_messages"] is True


def test_public_read_only_channel() -> None:
    overwrites = build_overwrites(CHANNELS_BY_KEY["cenik"].access)
    assert overwrites[EVERYONE]["view_channel"] is True
    assert overwrites[EVERYONE]["send_messages"] is False
    assert overwrites[EVERYONE]["create_private_threads"] is False


def test_reviews_public_but_only_premium_writes() -> None:
    overwrites = build_overwrites(CHANNELS_BY_KEY["recenze"].access)
    assert overwrites[EVERYONE]["view_channel"] is True
    assert overwrites[EVERYONE]["send_messages"] is False
    assert overwrites[PREMIUM] == {
        "send_messages": True,
        "send_messages_in_threads": True,
        "create_public_threads": True,
    }


def test_community_channels_for_members_and_premium() -> None:
    overwrites = build_overwrites(CHANNELS_BY_KEY["chat"].access)
    assert overwrites[EVERYONE]["view_channel"] is False
    for role in (MEMBER, PREMIUM):
        assert overwrites[role]["view_channel"] is True
        assert overwrites[role]["send_messages"] is True


def test_voice_channels_get_voice_permissions() -> None:
    overwrites = build_overwrites(CHANNELS_BY_KEY["live"].access, voice=True)
    assert overwrites[EVERYONE]["connect"] is False
    assert overwrites[PREMIUM]["connect"] is True
    assert overwrites[PREMIUM]["speak"] is True


@pytest.mark.parametrize("path", sorted(TEXTS_DIR.glob("*.md")), ids=lambda p: p.stem)
def test_texts_fit_into_embed_and_reference_existing_keys(path) -> None:
    text = load_text(path.stem)
    assert 0 < len(text.title) <= 256
    for kind, key in placeholders(text.title + text.body):
        assert key in (CHANNELS_BY_KEY if kind == "#" else ROLES_BY_KEY), f"{path.name}: neznámý klíč {key}"
    rendered = render(
        text.body,
        server="x" * 100,
        channel=lambda key: f"<#{'9' * 19}>",
        role=lambda key: f"<@&{'9' * 19}>",
    )
    assert len(rendered) <= 4096
    assert "<!--" not in rendered


def test_every_panel_has_a_text() -> None:
    for channel in ALL_CHANNELS:
        if channel.panel:
            assert (TEXTS_DIR / f"{channel.panel}.md").exists()


def test_slash_commands_are_valid_for_discord(bot: TradingBot) -> None:
    name_re = re.compile(r"^[-_a-z0-9]{1,32}$")
    payload = [command.to_dict(bot.tree) for command in bot.tree.get_commands()]

    def check(entry: dict) -> None:
        assert name_re.fullmatch(entry["name"]), entry["name"]
        assert 1 <= len(entry["description"]) <= 100, entry["description"]
        for option in entry.get("options", []):
            check(option)

    for entry in payload:
        check(entry)
    assert {entry["name"] for entry in payload} == {"setup", "kody", "premium", "aktivovat", "predplatne"}


def test_settings() -> None:
    settings = load_settings(
        {"DISCORD_TOKEN": "abc", "GUILD_ID": "123", "PAYMENT_URL": "https://pay.example/x"}
    )
    assert settings.guild_id == 123
    assert settings.payment_url == "https://pay.example/x"
    assert str(settings.database_path) == "data/bot.db"
    with pytest.raises(ConfigError):
        load_settings({})
    with pytest.raises(ConfigError):
        load_settings({"DISCORD_TOKEN": "abc", "GUILD_ID": "server"})
    with pytest.raises(ConfigError):
        load_settings({"DISCORD_TOKEN": "abc", "PAYMENT_URL": "pay.example"})
