import asyncio
import time

from bot import premium, tickets
from bot.client import TradingBot
from bot.db import DAY
from bot.layout import MEMBER, PREMIUM
from bot.server_setup import setup_guild
from bot.views import PricingView, RedeemModal, TicketCloseView, VerifyView, persistent_views

from .conftest import FakeGuild, make_interaction


def run(coro):
    return asyncio.run(coro)


def reply(interaction) -> str:
    sent = interaction.response.send_message.await_args or interaction.followup.send.await_args
    return sent.args[0]


def setup(bot: TradingBot, guild: FakeGuild) -> None:
    premium._failed_attempts.clear()
    run(setup_guild(bot, guild))


def test_redeem_code_gives_premium_and_member_roles(bot: TradingBot, guild: FakeGuild) -> None:
    setup(bot, guild)
    [code] = bot.db.create_codes(guild.id, 1, 30, note="objednávka 17")
    user = guild.add_member()
    interaction = make_interaction(bot, guild, user)

    run(premium.redeem(interaction, code))

    assert bot.lookup_role(guild, PREMIUM) in user.roles
    assert bot.lookup_role(guild, MEMBER) in user.roles
    assert "Premium je aktivní" in reply(interaction)
    log = bot.lookup_channel(guild, "modlog")
    assert any(code in m.content for m in log.messages.values())


def test_redeem_rejects_bad_and_used_codes_and_rate_limits(bot: TradingBot, guild: FakeGuild) -> None:
    setup(bot, guild)
    [code] = bot.db.create_codes(guild.id, 1, 30)
    run(premium.redeem(make_interaction(bot, guild, guild.add_member()), code))

    thief = guild.add_member()
    interaction = make_interaction(bot, guild, thief)
    run(premium.redeem(interaction, code))
    assert "už byl použitý" in reply(interaction)
    assert bot.lookup_role(guild, PREMIUM) not in thief.roles

    for _ in range(premium.MAX_FAILED_ATTEMPTS):
        run(premium.redeem(make_interaction(bot, guild, thief), "TM-AAAA-AAAA-AAAA"))
    [fresh] = bot.db.create_codes(guild.id, 1, 30)
    interaction = make_interaction(bot, guild, thief)
    run(premium.redeem(interaction, fresh))
    assert "Moc neúspěšných pokusů" in reply(interaction)


def test_expiry_removes_role_and_reminds(bot: TradingBot, guild: FakeGuild) -> None:
    setup(bot, guild)
    premium_role = bot.lookup_role(guild, PREMIUM)
    member_role = bot.lookup_role(guild, MEMBER)
    user = guild.add_member([premium_role, member_role])
    lifer = guild.add_member([premium_role, member_role])
    now = int(time.time())
    bot.db.grant(guild.id, user.id, 30, now=now)
    bot.db.grant(guild.id, lifer.id, 0, now=now)

    run(bot.process_subscriptions(now=now + 28 * DAY))
    assert user.send.await_count == 1
    assert "končí" in user.send.await_args.args[0]
    run(bot.process_subscriptions(now=now + 29 * DAY))
    assert user.send.await_count == 1  # připomínka jen jednou

    run(bot.process_subscriptions(now=now + 30 * DAY))
    assert premium_role not in user.roles
    assert member_role in user.roles  # do komunity má přístup dál
    assert bot.db.get_subscription(guild.id, user.id) is None
    assert premium_role in lifer.roles


def test_rejoining_member_gets_premium_back(bot: TradingBot, guild: FakeGuild) -> None:
    setup(bot, guild)
    user = guild.add_member()
    bot.db.grant(guild.id, user.id, 30)
    run(bot.on_member_join(user))
    assert bot.lookup_role(guild, PREMIUM) in user.roles


def test_ticket_open_and_close(bot: TradingBot, guild: FakeGuild, monkeypatch) -> None:
    setup(bot, guild)
    monkeypatch.setattr(tickets, "CLOSE_DELAY", 0)
    user = guild.add_member()

    run(tickets.open_ticket(make_interaction(bot, guild, user)))
    ticket_id = bot.db.find_open_ticket(guild.id, user.id)
    ticket = guild.get_channel(ticket_id)
    assert ticket.name.startswith("tiket-user")
    assert ticket.category_id == bot.lookup_category(guild, "podpora").id
    assert ticket.overwrites[guild.default_role].view_channel is False
    assert ticket.overwrites[user].view_channel is True
    [message] = ticket.messages.values()
    assert isinstance(message.view, TicketCloseView)

    again = make_interaction(bot, guild, user)
    run(tickets.open_ticket(again))
    assert "Už máš otevřený tiket" in reply(again)

    stranger = make_interaction(bot, guild, guild.add_member(), channel=ticket)
    run(tickets.close_ticket(stranger))
    assert guild.get_channel(ticket_id) is not None

    run(tickets.close_ticket(make_interaction(bot, guild, user, channel=ticket)))
    assert guild.get_channel(ticket_id) is None
    assert bot.db.find_open_ticket(guild.id, user.id) is None


def test_buttons_are_persistent_and_work(bot: TradingBot, guild: FakeGuild) -> None:
    async def scenario() -> None:
        for view in persistent_views("https://example.com/koupit"):
            bot.add_view(view)  # vyhodí ValueError, kdyby view nepřežil restart

        pricing = PricingView("https://example.com/koupit")
        assert [item.label for item in pricing.children] == ["Koupit Premium", "Aktivovat kód"]
        interaction = make_interaction(bot, guild, guild.add_member())
        await pricing.children[1].callback(interaction)
        assert isinstance(interaction.response.send_modal.await_args.args[0], RedeemModal)
        assert [item.label for item in PricingView(None).children] == ["Aktivovat kód"]

        user = guild.add_member()
        verify = VerifyView()
        interaction = make_interaction(bot, guild, user)
        await verify.children[0].callback(interaction)
        assert bot.lookup_role(guild, MEMBER) in user.roles
        assert bot.lookup_channel(guild, "chat").mention in reply(interaction)

        interaction = make_interaction(bot, guild, user)
        await verify.children[0].callback(interaction)
        assert "Už jsi ověřený" in reply(interaction)

    setup(bot, guild)
    run(scenario())
