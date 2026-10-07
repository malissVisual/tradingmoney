"""Slash příkazy bota."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from . import premium
from .server_setup import plan_cleanup, setup_guild

if TYPE_CHECKING:
    from .client import TradingBot

ADMIN = discord.Permissions(administrator=True)
MESSAGE_LIMIT = 1900


def _bot(interaction: discord.Interaction) -> TradingBot:
    return interaction.client  # type: ignore[return-value]


def _truncate_lines(lines: list[str], limit: int = MESSAGE_LIMIT) -> str:
    out: list[str] = []
    length = 0
    for index, line in enumerate(lines):
        if length + len(line) + 1 > limit - 40:
            out.append(f"… a dalších {len(lines) - index}")
            break
        out.append(line)
        length += len(line) + 1
    return "\n".join(out)


# --- /setup -----------------------------------------------------------------


@app_commands.command(name="setup", description="Vytvoří nebo opraví role, kanály a panely serveru.")
@app_commands.describe(
    uklidit_vychozi="Smazat výchozí kanály nového serveru (#general / Obecné). Doporučeno u nového serveru."
)
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def setup_command(interaction: discord.Interaction, uklidit_vychozi: bool = False) -> None:
    bot = _bot(interaction)
    guild = interaction.guild
    assert guild is not None
    await interaction.response.defer(ephemeral=True, thinking=True)

    report = await setup_guild(bot, guild)
    doomed = plan_cleanup(bot, guild) if uklidit_vychozi and report.ok else []
    report.deleted.extend(f"#{channel.name}" for channel in doomed)

    text = report.render()
    await interaction.followup.send(text, ephemeral=True)
    await bot.log(guild, f"🛠️ {interaction.user.mention} spustil/a /setup\n{text}")

    # Mazání až nakonec – /setup se často spouští právě v #general.
    for channel in doomed:
        try:
            await channel.delete(reason="Úklid výchozích kanálů (/setup)")
        except discord.HTTPException:
            await bot.log(guild, f"❗ Nepodařilo se smazat #{channel.name}")


# --- /kody ------------------------------------------------------------------

codes_group = app_commands.Group(
    name="kody",
    description="Aktivační kódy pro Premium",
    guild_only=True,
    default_permissions=ADMIN,
)


@codes_group.command(name="vytvorit", description="Vygeneruje aktivační kódy pro Premium.")
@app_commands.describe(
    dni="Na kolik dní kód Premium odemkne (0 = doživotně)",
    pocet="Kolik kódů vytvořit (výchozí 1)",
    poznamka="Poznámka pro tebe, např. jméno kupujícího nebo číslo objednávky",
)
@app_commands.checks.has_permissions(administrator=True)
async def codes_create(
    interaction: discord.Interaction,
    dni: app_commands.Range[int, 0, 3650],
    pocet: app_commands.Range[int, 1, 100] = 1,
    poznamka: app_commands.Range[str, 1, 100] | None = None,
) -> None:
    bot = _bot(interaction)
    guild = interaction.guild
    assert guild is not None
    codes = bot.db.create_codes(guild.id, pocet, dni, note=poznamka, created_by=interaction.user.id)
    header = f"🔑 **{len(codes)}× kód na {premium.describe_days(dni)}**" + (f" ({poznamka})" if poznamka else "")
    body = "\n".join(codes)
    if len(body) < MESSAGE_LIMIT - 200:
        await interaction.response.send_message(
            f"{header}\n```\n{body}\n```Kód pošli kupujícímu – aktivuje ho tlačítkem **🔑 Aktivovat kód** v ceníku "
            "nebo příkazem `/aktivovat`.",
            ephemeral=True,
        )
    else:
        file = discord.File(io.BytesIO(body.encode()), filename="kody.txt")
        await interaction.response.send_message(header, file=file, ephemeral=True)
    await bot.log(
        guild,
        f"🔑 {interaction.user.mention} vytvořil/a {len(codes)}× kód na {premium.describe_days(dni)}"
        + (f" ({poznamka})" if poznamka else ""),
    )


@codes_group.command(name="seznam", description="Ukáže nepoužité aktivační kódy.")
@app_commands.checks.has_permissions(administrator=True)
async def codes_list(interaction: discord.Interaction) -> None:
    bot = _bot(interaction)
    assert interaction.guild is not None
    codes = bot.db.unused_codes(interaction.guild.id, limit=100)
    if not codes:
        await interaction.response.send_message("Žádné nepoužité kódy.", ephemeral=True)
        return
    lines = [
        f"`{code.code}` – {premium.describe_days(code.days)}" + (f" – {code.note}" if code.note else "")
        for code in codes
    ]
    await interaction.response.send_message(_truncate_lines(lines), ephemeral=True)


@codes_group.command(name="zrusit", description="Zruší nepoužitý aktivační kód.")
@app_commands.describe(kod="Kód, který chceš zrušit")
@app_commands.checks.has_permissions(administrator=True)
async def codes_delete(interaction: discord.Interaction, kod: str) -> None:
    bot = _bot(interaction)
    assert interaction.guild is not None
    if bot.db.delete_code(interaction.guild.id, kod):
        await interaction.response.send_message(f"🗑️ Kód `{kod}` je zrušený.", ephemeral=True)
    else:
        await interaction.response.send_message("Takový nepoužitý kód neexistuje.", ephemeral=True)


# --- /premium ---------------------------------------------------------------

premium_group = app_commands.Group(
    name="premium",
    description="Ruční správa Premium členů",
    guild_only=True,
    default_permissions=ADMIN,
)


@premium_group.command(name="pridat", description="Ručně přidá Premium (např. po platbě převodem).")
@app_commands.describe(clen="Komu", dni="Na kolik dní (0 = doživotně). Zbývající čas se nepropadá.")
@app_commands.checks.has_permissions(administrator=True)
async def premium_add(
    interaction: discord.Interaction, clen: discord.Member, dni: app_commands.Range[int, 0, 3650]
) -> None:
    bot = _bot(interaction)
    guild = interaction.guild
    assert guild is not None
    subscription = bot.db.grant(guild.id, clen.id, dni)
    try:
        await premium.add_premium_roles(bot, clen)
    except discord.HTTPException:
        await interaction.response.send_message(
            f"Předplatné je uložené, ale nepodařilo se přidat roli {clen.mention}. Zkontroluj pořadí rolí.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        f"💎 {clen.mention} má Premium {premium.describe_expiry(subscription)}.", ephemeral=True
    )
    await bot.log(
        guild,
        f"💎 {interaction.user.mention} přidal/a Premium {clen.mention} ({premium.describe_days(dni)}), "
        f"platí {premium.describe_expiry(subscription)}.",
    )


@premium_group.command(name="odebrat", description="Odebere Premium.")
@app_commands.describe(clen="Komu")
@app_commands.checks.has_permissions(administrator=True)
async def premium_remove(interaction: discord.Interaction, clen: discord.Member) -> None:
    bot = _bot(interaction)
    guild = interaction.guild
    assert guild is not None
    had_subscription = bot.db.revoke(guild.id, clen.id)
    await premium.remove_premium_role(bot, clen)
    suffix = "" if had_subscription else " (v databázi předplatné neměl/a, odebral jsem jen roli)"
    await interaction.response.send_message(f"Premium odebráno: {clen.mention}{suffix}", ephemeral=True)
    await bot.log(guild, f"🚫 {interaction.user.mention} odebral/a Premium {clen.mention}")


@premium_group.command(name="seznam", description="Seznam aktivních Premium členů.")
@app_commands.checks.has_permissions(administrator=True)
async def premium_list(interaction: discord.Interaction) -> None:
    bot = _bot(interaction)
    assert interaction.guild is not None
    subscriptions = bot.db.active_subscriptions(interaction.guild.id)
    if not subscriptions:
        await interaction.response.send_message("Zatím nikdo nemá Premium.", ephemeral=True)
        return
    lines = [f"**{len(subscriptions)} aktivních Premium členů**"] + [
        f"<@{sub.user_id}> – {'doživotně' if sub.lifetime else f'do <t:{sub.expires_at}:d>'}"
        for sub in subscriptions
    ]
    await interaction.response.send_message(_truncate_lines(lines), ephemeral=True)


# --- Pro členy --------------------------------------------------------------


@app_commands.command(name="aktivovat", description="Aktivuje Premium pomocí kódu, který jsi dostal/a po zaplacení.")
@app_commands.describe(kod="Aktivační kód, např. TM-ABCD-EFGH-JKMN")
@app_commands.guild_only()
async def redeem_command(interaction: discord.Interaction, kod: app_commands.Range[str, 4, 40]) -> None:
    await premium.redeem(interaction, kod)


@app_commands.command(name="predplatne", description="Ukáže, do kdy ti platí Premium.")
@app_commands.guild_only()
async def subscription_command(interaction: discord.Interaction) -> None:
    bot = _bot(interaction)
    assert interaction.guild is not None
    subscription = bot.db.get_subscription(interaction.guild.id, interaction.user.id)
    if subscription is not None and subscription.is_active():
        await interaction.response.send_message(
            f"💎 Máš Premium {premium.describe_expiry(subscription)}.", ephemeral=True
        )
        return
    pricing = bot.lookup_channel(interaction.guild, "cenik")
    where = f" Mrkni do {pricing.mention}." if pricing else ""
    await interaction.response.send_message(f"Nemáš aktivní Premium.{where}", ephemeral=True)


def register_commands(tree: app_commands.CommandTree) -> None:
    for command in (setup_command, codes_group, premium_group, redeem_command, subscription_command):
        tree.add_command(command)
