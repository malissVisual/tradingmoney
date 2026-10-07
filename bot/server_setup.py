"""Vytvoření a srovnání struktury serveru podle layout.py (příkaz /setup)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import discord

from .layout import (
    BOT,
    CATEGORIES,
    EVERYONE,
    ROLES,
    Access,
    CategorySpec,
    ChannelSpec,
    RoleSpec,
    build_overwrites,
)
from .texts import UNFILLED, load_text, render
from .views import panel_view

if TYPE_CHECKING:
    from .client import TradingBot

REASON = "Nastavení serveru (/setup)"
BRAND_COLOUR = discord.Colour(0xF1C40F)

# Výchozí kanály, které Discord vytvoří u nového serveru (anglicky i česky).
DEFAULT_TEXT_CHANNELS = {"general", "obecné"}
DEFAULT_VOICE_CHANNELS = {"General", "Obecné"}
DEFAULT_CATEGORIES = {"Text Channels", "Voice Channels", "Textové kanály", "Hlasové kanály"}

Overwrites = dict[discord.Role | discord.Member, discord.PermissionOverwrite]


@dataclass
class SetupReport:
    ok: bool = True
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def render(self, limit: int = 1900) -> str:
        lines = ["**✅ Server je nastavený.**" if self.ok else "**❌ Nastavení se nepovedlo.**"]
        for label, items in (
            ("🆕 Vytvořeno", self.created),
            ("🔄 Aktualizováno", self.updated),
            ("🗑️ Smazáno", self.deleted),
        ):
            if items:
                lines.append(f"{label} ({len(items)}): " + ", ".join(items))
        if self.ok and not (self.created or self.updated or self.deleted):
            lines.append("Všechno už bylo v pořádku, nic se neměnilo.")
        lines.extend(f"⚠️ {warning}" for warning in self.warnings)
        text = "\n".join(lines)
        return text if len(text) <= limit else text[: limit - 1] + "…"


def to_discord_overwrites(
    guild: discord.Guild, roles: dict[str, discord.Role], access: Access, *, voice: bool
) -> Overwrites:
    result: Overwrites = {}
    for target_key, permissions in build_overwrites(access, voice=voice).items():
        if target_key == EVERYONE:
            target: discord.Role | discord.Member | None = guild.default_role
        elif target_key == BOT:
            target = guild.me
        else:
            target = roles.get(target_key)
        if target is not None:
            result[target] = discord.PermissionOverwrite(**permissions)
    return result


def build_embed(bot: TradingBot, guild: discord.Guild, key: str) -> discord.Embed:
    text = load_text(key)

    def channel(channel_key: str) -> str:
        found = bot.lookup_channel(guild, channel_key)
        return found.mention if found else f"#{channel_key}"

    def role(role_key: str) -> str:
        found = bot.lookup_role(guild, role_key)
        return found.mention if found else f"@{role_key}"

    title = render(text.title, server=guild.name, channel=channel, role=role)
    body = render(text.body, server=guild.name, channel=channel, role=role)
    embed = discord.Embed(title=title[:256], description=body[:4096], colour=BRAND_COLOUR)
    embed.set_footer(text=guild.name)
    return embed


async def setup_guild(bot: TradingBot, guild: discord.Guild) -> SetupReport:
    report = SetupReport()
    me = guild.me
    missing = [
        name
        for name in ("manage_roles", "manage_channels")
        if not getattr(me.guild_permissions, name)
    ]
    if missing:
        report.ok = False
        report.warnings.append(
            "Bot nemá oprávnění " + ", ".join(missing) + ". Pozvi ho znovu s oprávněním Administrator."
        )
        return report

    await _harden_guild(guild, report)

    roles: dict[str, discord.Role] = {}
    for spec in ROLES:
        roles[spec.key] = await _ensure_role(bot, guild, spec, report)
    for role in roles.values():
        if role >= me.top_role:
            report.warnings.append(
                f"Role {role.mention} je výš než role bota – v Nastavení serveru → Role přetáhni roli bota nahoru."
            )

    for category_spec in CATEGORIES:
        category = await _ensure_category(bot, guild, category_spec, roles, report)
        for channel_spec in category_spec.channels:
            await _ensure_channel(bot, guild, channel_spec, category, roles, report)

    for category_spec in CATEGORIES:
        for channel_spec in category_spec.channels:
            if channel_spec.panel:
                await _ensure_panel(bot, guild, channel_spec, report)

    if not (bot.settings.payment_url or bot.settings.payment_url_lifetime):
        report.warnings.append(
            "Není nastavená PAYMENT_URL (odkaz na platbu) – v ceníku chybí tlačítko „Koupit“."
        )
    return report


async def _harden_guild(guild: discord.Guild, report: SetupReport) -> None:
    """Základní ochrana proti spamu a scammerům."""
    everyone = guild.default_role
    if everyone.permissions.mention_everyone:
        permissions = discord.Permissions(everyone.permissions.value)
        permissions.mention_everyone = False
        await everyone.edit(permissions=permissions, reason=REASON)
        report.updated.append("@everyone už nemůže pingovat všechny")

    if not guild.me.guild_permissions.manage_guild:
        report.warnings.append("Bot nemá oprávnění Spravovat server – zabezpečení serveru přeskočeno.")
        return
    changes: dict = {}
    if guild.verification_level < discord.VerificationLevel.medium:
        changes["verification_level"] = discord.VerificationLevel.medium
    if guild.explicit_content_filter != discord.ContentFilter.all_members:
        changes["explicit_content_filter"] = discord.ContentFilter.all_members
    if guild.default_notifications != discord.NotificationLevel.only_mentions:
        changes["default_notifications"] = discord.NotificationLevel.only_mentions
    if changes:
        await guild.edit(**changes, reason=REASON)
        report.updated.append("zabezpečení serveru (ověření účtů, filtr obsahu, notifikace jen při zmínce)")


async def _ensure_role(
    bot: TradingBot, guild: discord.Guild, spec: RoleSpec, report: SetupReport
) -> discord.Role:
    role = bot.lookup_role(guild, spec.key)
    if role is None:
        role = await guild.create_role(
            name=spec.name,
            colour=discord.Colour(spec.color),
            hoist=spec.hoist,
            permissions=discord.Permissions(**dict.fromkeys(spec.permissions, True)),
            reason=REASON,
        )
        report.created.append(f"role {spec.name}")
    bot.db.set_object(guild.id, f"role:{spec.key}", role.id)
    return role


async def _ensure_category(
    bot: TradingBot,
    guild: discord.Guild,
    spec: CategorySpec,
    roles: dict[str, discord.Role],
    report: SetupReport,
) -> discord.CategoryChannel:
    overwrites = to_discord_overwrites(guild, roles, spec.access, voice=False)
    category = bot.lookup_category(guild, spec.key)
    if category is None:
        category = await guild.create_category(spec.name, overwrites=overwrites, reason=REASON)
        report.created.append(f"kategorie {spec.name}")
    elif category.overwrites != overwrites:
        await category.edit(overwrites=overwrites, reason=REASON)
        report.updated.append(f"kategorie {category.name}")
    bot.db.set_object(guild.id, f"category:{spec.key}", category.id)
    return category


async def _ensure_channel(
    bot: TradingBot,
    guild: discord.Guild,
    spec: ChannelSpec,
    category: discord.CategoryChannel,
    roles: dict[str, discord.Role],
    report: SetupReport,
) -> discord.abc.GuildChannel:
    overwrites = to_discord_overwrites(guild, roles, spec.access, voice=spec.voice)
    channel = bot.lookup_channel(guild, spec.key)
    if channel is None:
        if spec.voice:
            channel = await guild.create_voice_channel(
                spec.name, category=category, overwrites=overwrites, reason=REASON
            )
        else:
            channel = await guild.create_text_channel(
                spec.name,
                category=category,
                overwrites=overwrites,
                topic=spec.topic,
                slowmode_delay=spec.slowmode,
                reason=REASON,
            )
        report.created.append(f"#{channel.name}")
    else:
        changes: dict = {}
        if channel.category_id != category.id:
            changes["category"] = category
        if channel.overwrites != overwrites:
            changes["overwrites"] = overwrites
        if changes:
            await channel.edit(**changes, reason=REASON)  # type: ignore[call-arg]
            report.updated.append(f"#{channel.name}")
    bot.db.set_object(guild.id, f"channel:{spec.key}", channel.id)
    return channel


async def _ensure_panel(bot: TradingBot, guild: discord.Guild, spec: ChannelSpec, report: SetupReport) -> None:
    assert spec.panel is not None
    channel = bot.lookup_channel(guild, spec.key)
    if not isinstance(channel, discord.TextChannel):
        return
    embed = build_embed(bot, guild, spec.panel)
    if UNFILLED in (embed.description or ""):
        report.warnings.append(f"V textu texts/{spec.panel}.md jsou ještě nevyplněné hodnoty ({UNFILLED}).")
    view = panel_view(spec.panel, bot.settings)

    message: discord.Message | None = None
    stored = bot.db.get_panel(guild.id, spec.panel)
    if stored is not None and stored[0] == channel.id:
        try:
            message = await channel.fetch_message(stored[1])
        except discord.NotFound:
            message = None

    if message is None:
        message = await channel.send(embed=embed, view=view)
        bot.db.set_panel(guild.id, spec.panel, channel.id, message.id)
        report.created.append(f"zpráva v #{channel.name}")
    else:
        old = message.embeds[0] if message.embeds else None
        await message.edit(embed=embed, view=view)
        if old is None or old.title != embed.title or old.description != embed.description:
            report.updated.append(f"zpráva v #{channel.name}")


def plan_cleanup(bot: TradingBot, guild: discord.Guild) -> list[discord.abc.GuildChannel]:
    """Výchozí kanály nového serveru (#general apod.), které bot nevytvořil."""
    known = bot.db.object_ids(guild.id)
    doomed: list[discord.abc.GuildChannel] = [
        channel
        for channel in guild.channels
        if channel.id not in known
        and (
            (isinstance(channel, discord.TextChannel) and channel.name in DEFAULT_TEXT_CHANNELS)
            or (isinstance(channel, discord.VoiceChannel) and channel.name in DEFAULT_VOICE_CHANNELS)
        )
    ]
    doomed_ids = {channel.id for channel in doomed}
    doomed.extend(
        category
        for category in guild.categories
        if category.id not in known
        and category.name in DEFAULT_CATEGORIES
        and all(child.id in doomed_ids for child in category.channels)
    )
    return doomed
