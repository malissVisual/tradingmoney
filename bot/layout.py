"""Struktura serveru: role, kategorie a kanály.

Kanály tady můžeš přidávat, mazat nebo přejmenovávat. Po změně stačí v Discordu
znovu spustit ``/setup`` – bot chybějící role a kanály vytvoří a oprávnění srovná.
Kanály, které už existují, bot nepřejmenovává (najde je podle uloženého ID).
"""

from __future__ import annotations

from dataclasses import dataclass

# Kdo kanál vidí / kdo do něj píše. Moderátoři a bot můžou vždy obojí.
EVERYONE = "everyone"  # všichni včetně neověřených nováčků
MEMBER = "member"  # ověření členové (souhlasili s pravidly)
PREMIUM = "premium"  # platící členové
MOD = "mod"
BOT = "bot"

PUBLIC = frozenset({EVERYONE})
MEMBERS = frozenset({MEMBER, PREMIUM})
PREMIUM_ONLY = frozenset({PREMIUM})
STAFF_ONLY: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Access:
    view: frozenset[str]
    send: frozenset[str] = STAFF_ONLY


@dataclass(frozen=True)
class RoleSpec:
    key: str
    name: str
    color: int
    hoist: bool = False  # zobrazit členy role zvlášť v seznamu vpravo
    permissions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChannelSpec:
    key: str
    name: str
    access: Access
    topic: str = ""
    voice: bool = False
    slowmode: int = 0
    panel: str | None = None  # text z texts/<panel>.md, který bot do kanálu pošle


@dataclass(frozen=True)
class CategorySpec:
    key: str
    name: str
    access: Access  # výchozí oprávnění pro kanály, které do kategorie přidáš ručně
    channels: tuple[ChannelSpec, ...]


READ_ONLY = Access(view=PUBLIC)
MEMBERS_CHAT = Access(view=MEMBERS, send=MEMBERS)
PREMIUM_READ = Access(view=PREMIUM_ONLY)
PREMIUM_CHAT = Access(view=PREMIUM_ONLY, send=PREMIUM_ONLY)
STAFF = Access(view=STAFF_ONLY)

# Od nejvyšší po nejnižší.
ROLES: tuple[RoleSpec, ...] = (
    RoleSpec(
        MOD,
        "◈ Tým",
        0xB8BCC6,
        hoist=True,
        permissions=(
            "kick_members",
            "ban_members",
            "moderate_members",
            "manage_messages",
            "manage_threads",
            "manage_nicknames",
            "mute_members",
            "deafen_members",
            "move_members",
            "view_audit_log",
        ),
    ),
    RoleSpec(PREMIUM, "◆ Kruh", 0xC9A227, hoist=True),
    RoleSpec(MEMBER, "◇ Člen", 0x8E9AAF),
)

CATEGORIES: tuple[CategorySpec, ...] = (
    CategorySpec(
        "start",
        "◇ VSTUP",
        READ_ONLY,
        (
            ChannelSpec(
                "vitej",
                "✦・vstup",
                READ_ONLY,
                topic="Začni tady. Přijmi kodex a vstup dál.",
                panel="vitej",
            ),
            ChannelSpec(
                "pravidla", "✦・kodex", READ_ONLY, topic="Pravidla, která tu platí pro všechny.", panel="pravidla"
            ),
            ChannelSpec(
                "riziko",
                "✦・riziko",
                READ_ONLY,
                topic="Obchodování je rizikové. Nic tady není investiční doporučení.",
                panel="riziko",
            ),
            ChannelSpec("oznameni", "✦・oznámení", READ_ONLY, topic="Novinky ze serveru a ze systému."),
        ),
    ),
    CategorySpec(
        "prodej",
        "◇ SYSTÉM",
        READ_ONLY,
        (
            ChannelSpec(
                "cenik",
                "◆・přístup",
                READ_ONLY,
                topic="Co je v Uzavřeném kruhu, kolik stojí vstup a jak ho aktivovat.",
                panel="cenik",
            ),
            ChannelSpec(
                "vysledky",
                "◆・výsledky",
                READ_ONLY,
                topic="Výsledky systému. Všechny, i ztrátové. Píše sem jen tým.",
                panel="vysledky",
            ),
            ChannelSpec(
                "recenze",
                "◆・zkušenosti",
                Access(view=PUBLIC, send=PREMIUM_ONLY),
                topic="Zkušenosti členů Kruhu. Psát sem můžou jen oni.",
                slowmode=300,
            ),
            ChannelSpec("faq", "◆・otázky-a-odpovědi", READ_ONLY, topic="Nejčastější otázky.", panel="faq"),
        ),
    ),
    CategorySpec(
        "komunita",
        "◇ KOMUNITA",
        MEMBERS_CHAT,
        (
            ChannelSpec("chat", "・chat", MEMBERS_CHAT, topic="Trhy i všechno kolem nich."),
            ChannelSpec(
                "grafy",
                "・grafy",
                MEMBERS_CHAT,
                topic="Sdílej své grafy a analýzy – vždy s popisem, co na grafu vidíš.",
            ),
            ChannelSpec("trhy", "・trhy-a-zprávy", MEMBERS_CHAT, topic="Makro, zprávy, výsledky firem, kalendář."),
            ChannelSpec(
                "psychologie",
                "・mindset-a-risk",
                MEMBERS_CHAT,
                topic="Disciplína, risk management a práce s emocemi.",
            ),
            ChannelSpec("otazky", "・dotazy", MEMBERS_CHAT, topic="Žádná otázka není hloupá."),
            ChannelSpec("lounge", "◇ Lounge", MEMBERS_CHAT, voice=True),
        ),
    ),
    CategorySpec(
        "premium",
        "◆ UZAVŘENÝ KRUH",
        PREMIUM_CHAT,
        (
            ChannelSpec(
                "navod",
                "◆・systém",
                PREMIUM_READ,
                topic="Celý systém krok za krokem. Začni od nejstaršího příspěvku.",
                panel="premium",
            ),
            ChannelSpec(
                "signaly",
                "◆・signály",
                PREMIUM_READ,
                topic="Obchodní nápady v reálném čase. Nejde o investiční doporučení.",
            ),
            ChannelSpec("webinare", "◆・záznamy", PREMIUM_READ, topic="Záznamy webinářů a rozbory obchodů."),
            ChannelSpec(
                "obchody",
                "◆・deník-obchodů",
                PREMIUM_CHAT,
                topic="Tvoje obchody podle systému – vstup, SL, TP, výsledek v R.",
            ),
            ChannelSpec("premiumchat", "◆・kruh", PREMIUM_CHAT, topic="Jen pro členy Kruhu."),
            ChannelSpec("live", "◆ Live", PREMIUM_CHAT, voice=True),
        ),
    ),
    CategorySpec(
        "podpora",
        "◇ PODPORA",
        READ_ONLY,
        (
            ChannelSpec(
                "podpora",
                "・podpora",
                READ_ONLY,
                topic="Platby, aktivace kódu, dotazy – otevři si soukromý tiket.",
                panel="podpora",
            ),
        ),
    ),
    CategorySpec(
        "tym",
        "◈ TÝM",
        STAFF,
        (
            ChannelSpec("modlog", "・mod-log", STAFF, topic="Automatický log bota: nákupy, tikety, noví členové."),
            ChannelSpec("tymchat", "・porada", STAFF, topic="Interní chat týmu."),
        ),
    ),
)

TICKET_CATEGORY = "podpora"  # kategorie, do které se zakládají tikety
LOG_CHANNEL = "modlog"

ROLES_BY_KEY = {role.key: role for role in ROLES}
CATEGORIES_BY_KEY = {category.key: category for category in CATEGORIES}
CHANNELS_BY_KEY = {channel.key: channel for category in CATEGORIES for channel in category.channels}

_TEXT_VIEW = ("view_channel", "read_message_history")
_TEXT_SEND = ("send_messages", "send_messages_in_threads", "create_public_threads")
_TEXT_DENY = _TEXT_SEND + ("create_private_threads",)
_VOICE_VIEW = ("view_channel", "connect", "read_message_history")
_VOICE_SEND = ("speak", "stream", "use_voice_activation", "send_messages")
_BOT_EXTRA = ("embed_links", "attach_files", "manage_messages")


def build_overwrites(access: Access, *, voice: bool = False) -> dict[str, dict[str, bool]]:
    """Přeloží ``Access`` na oprávnění kanálu: {cíl: {oprávnění: povoleno/zakázáno}}.

    Cíle jsou ``EVERYONE``, klíče rolí a ``BOT``; převod na objekty Discordu
    dělá ``server_setup``.
    """
    view = _VOICE_VIEW if voice else _TEXT_VIEW
    send = _VOICE_SEND if voice else _TEXT_SEND
    send_deny = _VOICE_SEND if voice else _TEXT_DENY

    everyone_view = EVERYONE in access.view
    everyone_send = EVERYONE in access.send
    result: dict[str, dict[str, bool]] = {
        EVERYONE: {
            **dict.fromkeys(view, everyone_view),
            **dict.fromkeys(send if everyone_send else send_deny, everyone_send),
        }
    }
    for role in (MEMBER, PREMIUM):
        overwrite: dict[str, bool] = {}
        if role in access.view and not everyone_view:
            overwrite.update(dict.fromkeys(view, True))
        if role in access.send and not everyone_send:
            overwrite.update(dict.fromkeys(send, True))
        if overwrite:
            result[role] = overwrite
    result[MOD] = dict.fromkeys(view + send, True)
    result[BOT] = dict.fromkeys(view + send + _BOT_EXTRA, True)
    return result
