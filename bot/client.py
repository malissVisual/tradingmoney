"""Discord klient: události, připomínky a hlídání konce předplatného."""

from __future__ import annotations

import logging
import time

import discord
from discord import app_commands
from discord.ext import tasks

from . import premium
from .commands import register_commands
from .config import Settings
from .db import DAY, Database
from .layout import CATEGORIES_BY_KEY, CHANNELS_BY_KEY, LOG_CHANNEL, ROLES_BY_KEY
from .views import persistent_views

log = logging.getLogger(__name__)

REMINDER_WINDOW = 3 * DAY


class TradingBot(discord.Client):
    def __init__(self, settings: Settings, db: Database) -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(
            intents=intents,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
        )
        self.settings = settings
        self.db = db
        self.tree = app_commands.CommandTree(self)
        self.tree.error(self.handle_command_error)
        register_commands(self.tree)

    async def setup_hook(self) -> None:
        for view in persistent_views(self.settings):
            self.add_view(view)

        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()
        log.info("Zaregistrováno %d příkazů", len(synced))
        self.subscription_loop.start()

    async def on_ready(self) -> None:
        assert self.user is not None
        log.info("Přihlášen jako %s (%s) na %d serverech", self.user, self.user.id, len(self.guilds))

    # --- Vyhledání rolí a kanálů z layout.py ------------------------------

    def lookup_role(self, guild: discord.Guild, key: str) -> discord.Role | None:
        role_id = self.db.get_object(guild.id, f"role:{key}")
        role = guild.get_role(role_id) if role_id else None
        if role is None and key in ROLES_BY_KEY:
            role = discord.utils.get(guild.roles, name=ROLES_BY_KEY[key].name)
        return role

    def lookup_channel(self, guild: discord.Guild, key: str) -> discord.abc.GuildChannel | None:
        channel_id = self.db.get_object(guild.id, f"channel:{key}")
        channel = guild.get_channel(channel_id) if channel_id else None
        if channel is None and key in CHANNELS_BY_KEY:
            spec = CHANNELS_BY_KEY[key]
            pool = guild.voice_channels if spec.voice else guild.text_channels
            channel = discord.utils.get(pool, name=spec.name)
        return channel

    def lookup_category(self, guild: discord.Guild, key: str) -> discord.CategoryChannel | None:
        category_id = self.db.get_object(guild.id, f"category:{key}")
        category = guild.get_channel(category_id) if category_id else None
        if not isinstance(category, discord.CategoryChannel):
            category = None
            if key in CATEGORIES_BY_KEY:
                category = discord.utils.get(guild.categories, name=CATEGORIES_BY_KEY[key].name)
        return category

    async def log(self, guild: discord.Guild, message: str) -> None:
        log.info("[%s] %s", guild.name, message)
        channel = self.lookup_channel(guild, LOG_CHANNEL)
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(message[:2000], allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                log.warning("Nepodařilo se zapsat do mod-logu na %s", guild.name)

    # --- Události ---------------------------------------------------------

    async def on_member_join(self, member: discord.Member) -> None:
        subscription = self.db.get_subscription(member.guild.id, member.id)
        if subscription is not None and subscription.is_active():
            try:
                await premium.add_premium_roles(self, member)
                await self.log(member.guild, f"↩️ {member.mention} se vrátil/a – obnoveno Premium.")
            except discord.HTTPException:
                await self.log(member.guild, f"❗ {member.mention} má Premium, ale nešlo mu/jí vrátit roli.")
            return
        await self.log(member.guild, f"📥 Nový člen: {member.mention} ({member})")

    async def handle_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            message = "⛔ Na tohle nemáš oprávnění."
        else:
            log.error("Chyba v příkazu %s", interaction.command and interaction.command.qualified_name, exc_info=error)
            message = "❗ Něco se pokazilo. Zkus to znovu, případně se podívej do logu bota."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    # --- Předplatné -------------------------------------------------------

    @tasks.loop(minutes=30)
    async def subscription_loop(self) -> None:
        try:
            await self.process_subscriptions()
        except Exception:  # smyčka nesmí kvůli jedné chybě přestat běžet
            log.exception("Chyba při kontrole předplatného")

    @subscription_loop.before_loop
    async def _before_subscription_loop(self) -> None:
        await self.wait_until_ready()

    async def process_subscriptions(self, now: int | None = None) -> None:
        now = int(time.time()) if now is None else now

        for subscription in self.db.due_reminders(REMINDER_WINDOW, now=now):
            guild = self.get_guild(subscription.guild_id)
            if guild is None:
                continue
            self.db.mark_reminded(guild.id, subscription.user_id)
            member = guild.get_member(subscription.user_id)
            if member is None:
                continue
            pricing = self.lookup_channel(guild, "cenik")
            where = f" Prodloužit ho můžeš tady: {pricing.jump_url}" if pricing else ""
            await _send_dm(
                member,
                f"◆ Tvůj přístup do The Edge na serveru **{guild.name}** končí <t:{subscription.expires_at}:R>."
                f" Když si včas aktivuješ nový kód, dny se přičtou a o nic nepřijdeš.{where}",
            )

        for subscription in self.db.expired_subscriptions(now=now):
            guild = self.get_guild(subscription.guild_id)
            if guild is None:
                continue
            self.db.revoke(guild.id, subscription.user_id)
            member = guild.get_member(subscription.user_id)
            if member is None:
                await self.log(guild, f"⌛ Vypršelo Premium: <@{subscription.user_id}> (už není na serveru)")
                continue
            try:
                await premium.remove_premium_role(self, member)
            except discord.HTTPException:
                await self.log(
                    guild, f"❗ Vypršelo Premium {member.mention}, ale roli se nepodařilo odebrat – odeber ji ručně."
                )
                continue
            await self.log(guild, f"⌛ Vypršelo Premium: {member.mention}")
            pricing = self.lookup_channel(guild, "cenik")
            where = f" Obnovit ho můžeš tady: {pricing.jump_url}" if pricing else ""
            await _send_dm(
                member,
                f"Tvůj přístup do The Edge na serveru **{guild.name}** skončil. Díky, že jsi byl/a s námi.{where}",
            )


async def _send_dm(member: discord.Member, message: str) -> None:
    try:
        await member.send(message)
    except discord.HTTPException:
        pass  # uživatel má vypnuté soukromé zprávy
