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
        "🛡️ Moderátor",
        0x3498DB,
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
    RoleSpec(PREMIUM, "💎 Premium", 0xF1C40F, hoist=True),
    RoleSpec(MEMBER, "✅ Člen", 0x2ECC71),
)

CATEGORIES: tuple[CategorySpec, ...] = (
    CategorySpec(
        "start",
        "📌 ZAČNI TADY",
        READ_ONLY,
        (
            ChannelSpec(
                "vitej",
                "👋┃vítej",
                READ_ONLY,
                topic="Začni tady – potvrď pravidla a odemkni si komunitu.",
                panel="vitej",
            ),
            ChannelSpec("pravidla", "📜┃pravidla", READ_ONLY, topic="Pravidla serveru.", panel="pravidla"),
            ChannelSpec(
                "riziko",
                "⚠️┃upozornění-o-riziku",
                READ_ONLY,
                topic="Obchodování je rizikové. Nic tady není investiční doporučení.",
                panel="riziko",
            ),
            ChannelSpec("oznameni", "📢┃oznámení", READ_ONLY, topic="Novinky ze serveru a ze strategie."),
        ),
    ),
    CategorySpec(
        "prodej",
        "💎 STRATEGIE",
        READ_ONLY,
        (
            ChannelSpec(
                "cenik",
                "💰┃ceník",
                READ_ONLY,
                topic="Co obsahuje Premium, kolik stojí a jak ho aktivovat.",
                panel="cenik",
            ),
            ChannelSpec(
                "recenze",
                "⭐┃recenze",
                Access(view=PUBLIC, send=PREMIUM_ONLY),
                topic="Zkušenosti členů Premium. Psát sem můžou jen Premium členové.",
                slowmode=300,
            ),
            ChannelSpec("faq", "❓┃faq", READ_ONLY, topic="Nejčastější otázky.", panel="faq"),
        ),
    ),
    CategorySpec(
        "komunita",
        "💬 KOMUNITA",
        MEMBERS_CHAT,
        (
            ChannelSpec("chat", "💬┃obecný-chat", MEMBERS_CHAT, topic="Pokec o trzích i o všem ostatním."),
            ChannelSpec(
                "grafy",
                "📈┃grafy-a-analýzy",
                MEMBERS_CHAT,
                topic="Sdílej své grafy a analýzy – vždy s popisem, co na grafu vidíš.",
            ),
            ChannelSpec("trhy", "📰┃trhy-a-zprávy", MEMBERS_CHAT, topic="Makro, zprávy, výsledky firem, kalendář."),
            ChannelSpec(
                "psychologie",
                "🧠┃psychologie-a-risk",
                MEMBERS_CHAT,
                topic="Disciplína, risk management a práce s emocemi.",
            ),
            ChannelSpec("otazky", "🙋┃otázky", MEMBERS_CHAT, topic="Žádná otázka není hloupá. Pomáháme si."),
            ChannelSpec("lounge", "🔊 Lounge", MEMBERS_CHAT, voice=True),
        ),
    ),
    CategorySpec(
        "premium",
        "🔒 PREMIUM",
        PREMIUM_CHAT,
        (
            ChannelSpec(
                "navod",
                "📘┃strategie",
                PREMIUM_READ,
                topic="Kompletní strategie krok za krokem. Začni od nejstaršího příspěvku.",
                panel="premium",
            ),
            ChannelSpec(
                "signaly",
                "🎯┃signály",
                PREMIUM_READ,
                topic="Obchodní nápady v reálném čase. Nejde o investiční doporučení.",
            ),
            ChannelSpec("webinare", "🎥┃webináře-a-záznamy", PREMIUM_READ, topic="Záznamy webinářů a rozbory obchodů."),
            ChannelSpec(
                "obchody",
                "📊┃moje-obchody",
                PREMIUM_CHAT,
                topic="Sdílej své obchody podle strategie – vstup, SL, TP, výsledek.",
            ),
            ChannelSpec("premiumchat", "💎┃premium-chat", PREMIUM_CHAT, topic="Chat jen pro Premium členy."),
            ChannelSpec("live", "🔊 Live trading", PREMIUM_CHAT, voice=True),
        ),
    ),
    CategorySpec(
        "podpora",
        "🛟 PODPORA",
        READ_ONLY,
        (
            ChannelSpec(
                "podpora",
                "🎫┃podpora",
                READ_ONLY,
                topic="Platby, aktivace kódu, dotazy – otevři si soukromý tiket.",
                panel="podpora",
            ),
        ),
    ),
    CategorySpec(
        "tym",
        "🛠️ TÝM",
        STAFF,
        (
            ChannelSpec("modlog", "📋┃mod-log", STAFF, topic="Automatický log bota: nákupy, tikety, noví členové."),
            ChannelSpec("tymchat", "🛠┃admin-chat", STAFF, topic="Interní chat týmu."),
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
