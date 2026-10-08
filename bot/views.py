"""Tlačítka pod zprávami. Mají pevné custom_id, takže fungují i po restartu bota."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from . import premium, tickets
from .layout import MEMBER

if TYPE_CHECKING:
    from .client import TradingBot
    from .config import Settings

log = logging.getLogger(__name__)


class PersistentView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        log.error("Chyba v tlačítku %r", item, exc_info=error)
        message = "❗ Něco se pokazilo. Zkus to znovu, případně otevři tiket v podpoře."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class VerifyView(PersistentView):
    @discord.ui.button(
        label="Souhlasím a vstupuji", emoji="✅", style=discord.ButtonStyle.success, custom_id="tm:verify"
    )
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot: TradingBot = interaction.client  # type: ignore[assignment]
        member = interaction.user
        if interaction.guild is None or not isinstance(member, discord.Member):
            return
        role = bot.lookup_role(interaction.guild, MEMBER)
        if role is None:
            await interaction.response.send_message(
                "Server ještě není nastavený. Dej prosím vědět adminovi.", ephemeral=True
            )
            return
        if role in member.roles:
            await interaction.response.send_message("Už jsi ověřený/á ✅", ephemeral=True)
            return
        await member.add_roles(role, reason="Souhlas s pravidly")

        links = [
            channel.mention
            for key in ("chat", "otazky", "cenik")
            if (channel := bot.lookup_channel(interaction.guild, key)) is not None
        ]
        await interaction.response.send_message(
            "◇ Jsi uvnitř. Odemkly se ti nové kanály. Začni tady: " + " · ".join(links),
            ephemeral=True,
        )


class RedeemModal(discord.ui.Modal, title="Aktivace Premium"):
    code = discord.ui.TextInput(
        label="Aktivační kód",
        placeholder="TM-XXXX-XXXX-XXXX",
        min_length=4,
        max_length=40,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await premium.redeem(interaction, self.code.value)


class PricingView(PersistentView):
    def __init__(self, monthly_url: str | None, lifetime_url: str | None = None) -> None:
        super().__init__()
        if monthly_url and lifetime_url:
            self.add_item(discord.ui.Button(label="Koupit měsíční", emoji="🛒", url=monthly_url))
            self.add_item(discord.ui.Button(label="Koupit doživotní", emoji="💎", url=lifetime_url))
        elif monthly_url or lifetime_url:
            self.add_item(discord.ui.Button(label="Koupit Premium", emoji="🛒", url=monthly_url or lifetime_url))
        redeem = discord.ui.Button(
            label="Aktivovat kód", emoji="🔑", style=discord.ButtonStyle.primary, custom_id="tm:redeem"
        )
        redeem.callback = self.redeem_button
        self.add_item(redeem)

    async def redeem_button(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(RedeemModal())


class TicketPanelView(PersistentView):
    @discord.ui.button(
        label="Otevřít tiket", emoji="🎫", style=discord.ButtonStyle.primary, custom_id="tm:ticket:open"
    )
    async def open_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await tickets.open_ticket(interaction)


class TicketCloseView(PersistentView):
    @discord.ui.button(
        label="Zavřít tiket", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="tm:ticket:close"
    )
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await tickets.close_ticket(interaction)


def panel_view(panel: str, settings: Settings) -> discord.ui.View | None:
    """Tlačítka, která patří pod daný panel (podle klíče textu)."""
    if panel == "vitej":
        return VerifyView()
    if panel == "cenik":
        return PricingView(settings.payment_url, settings.payment_url_lifetime)
    if panel == "podpora":
        return TicketPanelView()
    return None


def persistent_views(settings: Settings) -> list[discord.ui.View]:
    pricing = PricingView(settings.payment_url, settings.payment_url_lifetime)
    return [VerifyView(), pricing, TicketPanelView(), TicketCloseView()]
