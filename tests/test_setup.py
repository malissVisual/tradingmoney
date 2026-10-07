import asyncio

import discord

from bot.client import TradingBot
from bot.layout import CATEGORIES, CHANNELS_BY_KEY, MEMBER, MOD, PREMIUM, ROLES
from bot.server_setup import plan_cleanup, setup_guild
from bot.views import PricingView, TicketPanelView, VerifyView

from .conftest import FakeGuild

CHANNEL_COUNT = sum(len(category.channels) for category in CATEGORIES)
PANELS = {c.key: c.panel for c in CHANNELS_BY_KEY.values() if c.panel}


def run(coro):
    return asyncio.run(coro)


def test_setup_builds_whole_server(bot: TradingBot, guild: FakeGuild) -> None:
    report = run(setup_guild(bot, guild))

    assert len(guild.roles) == 2 + len(ROLES)
    assert len(guild.categories) == len(CATEGORIES)
    assert len(guild.text_channels) + len(guild.voice_channels) == CHANNEL_COUNT
    assert all(role < guild.bot_role for role in guild.roles if role is not guild.bot_role)
    # pořadí rolí: Moderátor > Premium > Člen
    mod, prem, member = (bot.lookup_role(guild, key) for key in (MOD, PREMIUM, MEMBER))
    assert mod.position > prem.position > member.position

    for key, spec in CHANNELS_BY_KEY.items():
        channel = bot.lookup_channel(guild, key)
        assert channel is not None and channel.name == spec.name

    premium_channel = bot.lookup_channel(guild, "navod")
    assert premium_channel.overwrites[guild.default_role].view_channel is False
    assert premium_channel.overwrites[prem].view_channel is True

    for channel_key, panel in PANELS.items():
        channel = bot.lookup_channel(guild, channel_key)
        assert len(channel.messages) == 1, panel
        [message] = channel.messages.values()
        embed = message.embeds[0]
        assert "{" not in embed.title + embed.description, panel  # všechny značky nahrazené

    welcome = next(iter(bot.lookup_channel(guild, "vitej").messages.values()))
    assert isinstance(welcome.view, VerifyView)
    assert bot.lookup_channel(guild, "pravidla").mention in welcome.embeds[0].description
    pricing = next(iter(bot.lookup_channel(guild, "cenik").messages.values()))
    assert isinstance(pricing.view, PricingView)
    assert [item.url for item in pricing.view.children if getattr(item, "url", None)] == [
        "https://example.com/koupit"
    ]
    support = next(iter(bot.lookup_channel(guild, "podpora").messages.values()))
    assert isinstance(support.view, TicketPanelView)

    assert guild.default_role.permissions.mention_everyone is False
    assert guild.default_role.permissions.send_messages is True  # ostatní práva zůstala
    assert guild.verification_level == discord.VerificationLevel.medium
    assert guild.explicit_content_filter == discord.ContentFilter.all_members
    assert guild.default_notifications == discord.NotificationLevel.only_mentions

    # Ceny v šabloně ještě nejsou vyplněné – /setup na to upozorní.
    assert any("cenik.md" in warning for warning in report.warnings)
    assert "Server je nastavený" in report.render()


def test_setup_is_idempotent(bot: TradingBot, guild: FakeGuild) -> None:
    run(setup_guild(bot, guild))
    roles, channels = len(guild.roles), len(guild.channels)

    report = run(setup_guild(bot, guild))

    assert report.created == []
    assert report.updated == []
    assert (len(guild.roles), len(guild.channels)) == (roles, channels)
    for channel_key in PANELS:
        assert len(bot.lookup_channel(guild, channel_key).messages) == 1


def test_setup_repairs_permissions_and_reposts_deleted_panel(bot: TradingBot, guild: FakeGuild) -> None:
    run(setup_guild(bot, guild))
    chat = bot.lookup_channel(guild, "chat")
    chat.overwrites = {}
    pricing = bot.lookup_channel(guild, "cenik")
    pricing.messages.clear()

    report = run(setup_guild(bot, guild))

    assert f"#{chat.name}" in report.updated
    assert chat.overwrites[guild.default_role].view_channel is False
    assert len(pricing.messages) == 1
    assert f"zpráva v #{pricing.name}" in report.created


def test_setup_keeps_renamed_channels(bot: TradingBot, guild: FakeGuild) -> None:
    run(setup_guild(bot, guild))
    bot.lookup_channel(guild, "chat").name = "💬┃pokec"
    run(setup_guild(bot, guild))
    assert len(guild.text_channels) + len(guild.voice_channels) == CHANNEL_COUNT


def test_cleanup_removes_only_default_channels(bot: TradingBot, guild: FakeGuild) -> None:
    guild.add_default_channels()
    run(setup_guild(bot, guild))
    doomed = plan_cleanup(bot, guild)
    assert sorted(c.name for c in doomed) == ["General", "Text Channels", "Voice Channels", "general"]

    for channel in doomed:
        run(channel.delete())
    assert len(guild.categories) == len(CATEGORIES)
    assert plan_cleanup(bot, guild) == []


def test_setup_without_permissions_does_nothing(bot: TradingBot, guild: FakeGuild) -> None:
    guild.me.guild_permissions = discord.Permissions(send_messages=True)
    report = run(setup_guild(bot, guild))
    assert report.created == [] and not report.ok
    assert any("Administrator" in warning for warning in report.warnings)
    assert "nepovedlo" in report.render()
