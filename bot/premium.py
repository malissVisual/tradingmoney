"""Aktivace Premium přes kód a práce s rolemi předplatitelů."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import TYPE_CHECKING

import discord

from .db import CodeAlreadyUsed, CodeNotFound, Subscription
from .layout import MEMBER, PREMIUM

if TYPE_CHECKING:
    from .client import TradingBot

MAX_FAILED_ATTEMPTS = 5
FAILED_WINDOW = 10 * 60

_failed_attempts: dict[int, deque[float]] = defaultdict(deque)


def describe_expiry(subscription: Subscription) -> str:
    if subscription.expires_at is None:
        return "**doživotně** ♾️"
    ts = subscription.expires_at
    return f"do <t:{ts}:f> (<t:{ts}:R>)"


def describe_days(days: int) -> str:
    if days == 0:
        return "doživotně"
    if days == 1:
        return "1 den"
    if days < 5:
        return f"{days} dny"
    return f"{days} dní"


def _too_many_attempts(user_id: int, now: float) -> bool:
    attempts = _failed_attempts[user_id]
    while attempts and attempts[0] <= now - FAILED_WINDOW:
        attempts.popleft()
    return len(attempts) >= MAX_FAILED_ATTEMPTS


async def add_premium_roles(bot: TradingBot, member: discord.Member) -> None:
    roles = [r for r in (bot.lookup_role(member.guild, PREMIUM), bot.lookup_role(member.guild, MEMBER)) if r]
    missing = [r for r in roles if r not in member.roles]
    if missing:
        await member.add_roles(*missing, reason="Aktivní Premium předplatné")


async def remove_premium_role(bot: TradingBot, member: discord.Member) -> None:
    role = bot.lookup_role(member.guild, PREMIUM)
    if role and role in member.roles:
        await member.remove_roles(role, reason="Premium předplatné skončilo")


async def redeem(interaction: discord.Interaction, raw_code: str) -> None:
    bot: TradingBot = interaction.client  # type: ignore[assignment]
    guild = interaction.guild
    member = interaction.user
    if guild is None or not isinstance(member, discord.Member):
        await interaction.response.send_message("Kód se aktivuje přímo na serveru.", ephemeral=True)
        return

    now = time.time()
    if _too_many_attempts(member.id, now):
        await interaction.response.send_message(
            "⏳ Moc neúspěšných pokusů. Zkus to za pár minut, nebo otevři tiket v podpoře.", ephemeral=True
        )
        return

    try:
        code, subscription = bot.db.redeem_code(guild.id, member.id, raw_code)
    except CodeNotFound:
        _failed_attempts[member.id].append(now)
        await interaction.response.send_message(
            "❌ Tenhle kód neexistuje. Zkontroluj, že jsi ho opsal/a přesně (např. `TM-ABCD-EFGH-JKMN`).",
            ephemeral=True,
        )
        return
    except CodeAlreadyUsed:
        _failed_attempts[member.id].append(now)
        await interaction.response.send_message(
            "❌ Tenhle kód už byl použitý. Pokud jsi ho nepoužil/a ty, otevři tiket v podpoře.", ephemeral=True
        )
        return

    try:
        await add_premium_roles(bot, member)
    except discord.HTTPException:
        await interaction.response.send_message(
            "✅ Kód je přijatý, ale nepodařilo se mi přidat roli. Otevři prosím tiket v podpoře – vyřešíme to.",
            ephemeral=True,
        )
        await bot.log(guild, f"❗ {member.mention} aktivoval/a `{code.code}`, ale nešla přidat role Premium.")
        return

    premium_channel = bot.lookup_channel(guild, "navod")
    where = f" Začni v {premium_channel.mention}." if premium_channel else ""
    await interaction.response.send_message(
        f"◆ **Jsi uvnitř.** Přístup do Kruhu platí {describe_expiry(subscription)}.{where}", ephemeral=True
    )
    note = f" – {code.note}" if code.note else ""
    await bot.log(
        guild,
        f"💎 {member.mention} aktivoval/a kód `{code.code}` ({describe_days(code.days)}{note}). "
        f"Premium {describe_expiry(subscription)}.",
    )
