"""Soukromé tikety pro podporu (platby, aktivace, dotazy)."""

from __future__ import annotations

import asyncio
import re
import unicodedata
from typing import TYPE_CHECKING

import discord

from .layout import MOD, TICKET_CATEGORY

if TYPE_CHECKING:
    from .client import TradingBot

CLOSE_DELAY = 5


def channel_slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug[:40] or "clen"


def _is_staff(bot: TradingBot, member: discord.Member) -> bool:
    mod_role = bot.lookup_role(member.guild, MOD)
    return member.guild_permissions.manage_messages or (mod_role is not None and mod_role in member.roles)


async def open_ticket(interaction: discord.Interaction) -> None:
    from .views import TicketCloseView

    bot: TradingBot = interaction.client  # type: ignore[assignment]
    guild = interaction.guild
    member = interaction.user
    if guild is None or not isinstance(member, discord.Member):
        return

    existing_id = bot.db.find_open_ticket(guild.id, member.id)
    if existing_id is not None:
        existing = guild.get_channel(existing_id)
        if existing is not None:
            await interaction.response.send_message(
                f"Už máš otevřený tiket: {existing.mention}", ephemeral=True
            )
            return
        bot.db.close_ticket(existing_id)  # kanál někdo smazal ručně

    await interaction.response.defer(ephemeral=True, thinking=True)

    mod_role = bot.lookup_role(guild, MOD)
    allow = dict(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)
    overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(**allow),
        guild.me: discord.PermissionOverwrite(**allow, manage_channels=True),
    }
    if mod_role is not None:
        overwrites[mod_role] = discord.PermissionOverwrite(**allow)

    category = bot.lookup_category(guild, TICKET_CATEGORY)
    channel = await guild.create_text_channel(
        f"tiket-{channel_slug(member.name)}",
        category=category,
        overwrites=overwrites,
        topic=f"Tiket uživatele {member} ({member.id})",
        reason=f"Tiket pro {member}",
    )
    bot.db.open_ticket(guild.id, member.id, channel.id)

    embed = discord.Embed(
        title="🎫 Tiket otevřen",
        description=(
            "Napiš, s čím potřebuješ pomoct – co nejpřesněji.\n"
            "• **Platba převodem:** napiš, o jaký přístup máš zájem, pošleme ti platební údaje.\n"
            "• **Problém s kódem:** vlož kód a popiš, co se stalo.\n\n"
            "Až bude vyřešeno, klikni na **🔒 Zavřít tiket**."
        ),
        colour=discord.Colour.blurple(),
    )
    mentions = member.mention + (f" {mod_role.mention}" if mod_role else "")
    await channel.send(
        mentions,
        embed=embed,
        view=TicketCloseView(),
        allowed_mentions=discord.AllowedMentions(users=True, roles=True),
    )
    await interaction.followup.send(f"✅ Tiket je otevřený: {channel.mention}", ephemeral=True)
    await bot.log(guild, f"🎫 {member.mention} otevřel/a tiket {channel.mention}")


async def close_ticket(interaction: discord.Interaction) -> None:
    bot: TradingBot = interaction.client  # type: ignore[assignment]
    channel = interaction.channel
    member = interaction.user
    if interaction.guild is None or not isinstance(member, discord.Member) or channel is None:
        return

    owner_id = bot.db.ticket_owner(channel.id)
    if owner_id is None:
        await interaction.response.send_message("Tenhle kanál není otevřený tiket.", ephemeral=True)
        return
    if member.id != owner_id and not _is_staff(bot, member):
        await interaction.response.send_message("Tiket může zavřít jen jeho autor nebo tým.", ephemeral=True)
        return

    bot.db.close_ticket(channel.id)
    await interaction.response.send_message(f"🔒 Tiket se za {CLOSE_DELAY} sekund zavře…")
    name = getattr(channel, "name", channel.id)
    await bot.log(interaction.guild, f"🔒 {member.mention} zavřel/a tiket `#{name}` (autor <@{owner_id}>)")
    await asyncio.sleep(CLOSE_DELAY)
    await channel.delete(reason=f"Tiket zavřel {member}")  # type: ignore[union-attr]
