import asyncio

from bot.client import TradingBot
from bot.commands import codes_create, premium_add, setup_command, subscription_command
from bot.layout import CATEGORIES, PREMIUM

from .conftest import FakeGuild, make_interaction


def run(coro):
    return asyncio.run(coro)


def test_setup_command_reports_and_cleans_defaults(bot: TradingBot, guild: FakeGuild) -> None:
    guild.add_default_channels()
    general = next(c for c in guild.text_channels if c.name == "general")
    interaction = make_interaction(bot, guild, guild.add_member(), channel=general)

    run(setup_command.callback(interaction, uklidit_vychozi=True))

    report = interaction.followup.send.await_args.args[0]
    assert "Server je nastavený" in report
    assert "#general" in report
    assert {c.name for c in guild.categories} == {c.name for c in CATEGORIES}
    log = bot.lookup_channel(guild, "modlog")
    assert any("spustil/a /setup" in m.content for m in log.messages.values())


def test_admin_creates_code_and_member_checks_status(bot: TradingBot, guild: FakeGuild) -> None:
    run(setup_command.callback(make_interaction(bot, guild, guild.add_member())))

    admin = make_interaction(bot, guild, guild.add_member())
    run(codes_create.callback(admin, dni=30, pocet=3, poznamka="Jan Novák"))
    message = admin.response.send_message.await_args.args[0]
    codes = bot.db.unused_codes(guild.id)
    assert len(codes) == 3
    assert all(code.code in message for code in codes)
    assert "30 dní" in message

    user = guild.add_member()
    status = make_interaction(bot, guild, user)
    run(subscription_command.callback(status))
    assert "Nemáš aktivní Premium" in status.response.send_message.await_args.args[0]

    run(premium_add.callback(make_interaction(bot, guild, guild.add_member()), clen=user, dni=0))
    assert bot.lookup_role(guild, PREMIUM) in user.roles
    status = make_interaction(bot, guild, user)
    run(subscription_command.callback(status))
    assert "doživotně" in status.response.send_message.await_args.args[0]
