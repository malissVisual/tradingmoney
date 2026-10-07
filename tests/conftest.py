"""Jednoduchý falešný Discord server pro testy bez připojení k internetu."""

from __future__ import annotations

import itertools
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from bot.client import TradingBot
from bot.config import Settings
from bot.db import Database

_ids = itertools.count(1000)
# Výchozí práva @everyone na nově založeném serveru (zjednodušeně).
NEW_SERVER_EVERYONE = discord.Permissions(
    view_channel=True, send_messages=True, read_message_history=True, add_reactions=True, mention_everyone=True
)


class FakeRole:
    def __init__(self, name: str, position: int, **attrs) -> None:
        self.id = next(_ids)
        self.name = name
        self.position = position
        self.permissions = attrs.get("permissions", discord.Permissions.none())
        self.colour = attrs.get("colour")
        self.hoist = attrs.get("hoist", False)

    @property
    def mention(self) -> str:
        return f"<@&{self.id}>"

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FakeRole) and other.id == self.id

    async def edit(self, *, permissions=None, reason=None) -> None:
        if permissions is not None:
            self.permissions = permissions

    def __ge__(self, other: FakeRole) -> bool:
        return self.position >= other.position

    def __lt__(self, other: FakeRole) -> bool:
        return self.position < other.position


class FakeBotMember:
    def __init__(self, top_role: FakeRole) -> None:
        self.id = next(_ids)
        self.top_role = top_role
        self.guild_permissions = discord.Permissions.all()
        self.mention = f"<@{self.id}>"

    def __hash__(self) -> int:
        return hash(self.id)


class FakeMessage:
    def __init__(self, embed: discord.Embed | None, view: discord.ui.View | None) -> None:
        self.id = next(_ids)
        self.embeds = [embed] if embed else []
        self.view = view
        self.edit = AsyncMock(side_effect=self._edit)

    async def _edit(self, *, embed=None, view=None) -> None:
        self.embeds = [embed] if embed else []
        self.view = view


def _not_found() -> discord.NotFound:
    return discord.NotFound(MagicMock(status=404, reason="Not Found"), "Unknown Message")


class FakeGuild:
    def __init__(self, name: str = "Trading CZ") -> None:
        self.id = next(_ids)
        self.name = name
        self.default_role = FakeRole("@everyone", 0, permissions=NEW_SERVER_EVERYONE)
        self.verification_level = discord.VerificationLevel.none
        self.explicit_content_filter = discord.ContentFilter.disabled
        self.default_notifications = discord.NotificationLevel.all_messages
        self.bot_role = FakeRole("TradingBot", 1)
        self.roles: list[FakeRole] = [self.default_role, self.bot_role]
        self.channels: list[MagicMock] = []
        self.members: dict[int, MagicMock] = {}
        self.me = FakeBotMember(self.bot_role)

    # --- dotazy -----------------------------------------------------------

    @property
    def text_channels(self) -> list[MagicMock]:
        return [c for c in self.channels if isinstance(c, discord.TextChannel)]

    @property
    def voice_channels(self) -> list[MagicMock]:
        return [c for c in self.channels if isinstance(c, discord.VoiceChannel)]

    @property
    def categories(self) -> list[MagicMock]:
        return [c for c in self.channels if isinstance(c, discord.CategoryChannel)]

    def get_role(self, role_id: int) -> FakeRole | None:
        return next((r for r in self.roles if r.id == role_id), None)

    def get_channel(self, channel_id: int) -> MagicMock | None:
        return next((c for c in self.channels if c.id == channel_id), None)

    def get_member(self, user_id: int) -> MagicMock | None:
        return self.members.get(user_id)

    # --- vytváření --------------------------------------------------------

    async def edit(self, *, reason=None, **changes) -> None:
        for name, value in changes.items():
            setattr(self, name, value)

    async def create_role(self, *, name, colour, hoist, permissions, reason) -> FakeRole:
        for role in self.roles:  # Discord vkládá novou roli hned nad @everyone
            if role.position >= 1:
                role.position += 1
        role = FakeRole(name, 1, colour=colour, hoist=hoist, permissions=permissions)
        self.roles.append(role)
        return role

    async def create_category(self, name, *, overwrites, reason) -> MagicMock:
        return self._add_channel(discord.CategoryChannel, name, None, overwrites)

    async def create_text_channel(self, name, *, category, overwrites, reason, topic="", slowmode_delay=0):
        channel = self._add_channel(discord.TextChannel, name, category, overwrites)
        channel.topic = topic
        channel.slowmode_delay = slowmode_delay
        return channel

    async def create_voice_channel(self, name, *, category, overwrites, reason) -> MagicMock:
        return self._add_channel(discord.VoiceChannel, name, category, overwrites)

    def add_default_channels(self) -> None:
        text_cat = self._add_channel(discord.CategoryChannel, "Text Channels", None, {})
        voice_cat = self._add_channel(discord.CategoryChannel, "Voice Channels", None, {})
        self._add_channel(discord.TextChannel, "general", text_cat, {})
        self._add_channel(discord.VoiceChannel, "General", voice_cat, {})

    def _add_channel(self, kind, name, category, overwrites) -> MagicMock:
        channel = MagicMock(spec=kind)
        channel.id = next(_ids)
        channel.name = name
        channel.guild = self
        channel.category_id = category.id if category is not None else None
        channel.overwrites = dict(overwrites)
        channel.mention = f"<#{channel.id}>"
        channel.jump_url = f"https://discord.com/channels/{self.id}/{channel.id}"
        channel.messages = {}

        async def send(content=None, *, embed=None, view=None, **kwargs):
            message = FakeMessage(embed, view)
            message.content = content
            channel.messages[message.id] = message
            return message

        async def fetch_message(message_id):
            if message_id not in channel.messages:
                raise _not_found()
            return channel.messages[message_id]

        async def edit(*, reason=None, category=None, overwrites=None, **kwargs):
            if category is not None:
                channel.category_id = category.id
            if overwrites is not None:
                channel.overwrites = dict(overwrites)

        async def delete(*, reason=None):
            self.channels.remove(channel)

        channel.send = AsyncMock(side_effect=send)
        channel.fetch_message = AsyncMock(side_effect=fetch_message)
        channel.edit = AsyncMock(side_effect=edit)
        channel.delete = AsyncMock(side_effect=delete)
        if kind is discord.CategoryChannel:
            type(channel).channels = property(lambda _: [c for c in self.channels if c.category_id == channel.id])
        self.channels.append(channel)
        return channel

    def add_member(self, roles: list[FakeRole] | None = None) -> MagicMock:
        member = MagicMock(spec=discord.Member)
        member.id = next(_ids)
        member.name = f"user{member.id}"
        member.mention = f"<@{member.id}>"
        member.guild = self
        member.roles = list(roles or [])
        member.guild_permissions = discord.Permissions.none()

        async def add_roles(*roles, reason=None):
            member.roles.extend(r for r in roles if r not in member.roles)

        async def remove_roles(*roles, reason=None):
            member.roles = [r for r in member.roles if r not in roles]

        member.add_roles = AsyncMock(side_effect=add_roles)
        member.remove_roles = AsyncMock(side_effect=remove_roles)
        member.send = AsyncMock()
        self.members[member.id] = member
        return member


def make_interaction(bot: TradingBot, guild: FakeGuild, user: MagicMock, channel=None) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.client = bot
    interaction.guild = guild
    interaction.user = user
    interaction.channel = channel
    interaction.response.is_done.return_value = False
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture
def db() -> Database:
    database = Database(":memory:")
    yield database
    database.close()


@pytest.fixture
def guild() -> FakeGuild:
    return FakeGuild()


@pytest.fixture
def bot(db: Database, guild: FakeGuild) -> TradingBot:
    settings = Settings(token="test", guild_id=None, database_path=None, payment_url="https://example.com/koupit")
    client = TradingBot(settings, db)
    client.get_guild = lambda guild_id: guild if guild_id == guild.id else None  # type: ignore[method-assign]
    return client
