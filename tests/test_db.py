import re

import pytest

from bot.db import DAY, CodeAlreadyUsed, CodeNotFound, Database, normalize_code

GUILD = 1
USER = 42
NOW = 1_700_000_000


def test_codes_have_expected_format_and_are_unique(db: Database) -> None:
    codes = db.create_codes(GUILD, 50, 30, now=NOW)
    assert len(set(codes)) == 50
    assert all(re.fullmatch(r"TM-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", code) for code in codes)
    assert len(db.unused_codes(GUILD)) == 50


def test_normalize_code_accepts_sloppy_input() -> None:
    assert normalize_code(" tm abcd-efgh jkmn ") == "TM-ABCD-EFGH-JKMN"
    assert normalize_code("TMABCDEFGHJKMN") == "TM-ABCD-EFGH-JKMN"


def test_redeem_grants_days_and_marks_code_used(db: Database) -> None:
    [code] = db.create_codes(GUILD, 1, 30, note="Petr", now=NOW)
    redeemed, subscription = db.redeem_code(GUILD, USER, code.lower(), now=NOW)
    assert redeemed.note == "Petr"
    assert subscription.expires_at == NOW + 30 * DAY
    assert db.unused_codes(GUILD) == []
    with pytest.raises(CodeAlreadyUsed):
        db.redeem_code(GUILD, 7, code, now=NOW)


def test_redeem_unknown_or_foreign_code_fails(db: Database) -> None:
    [code] = db.create_codes(GUILD, 1, 30)
    with pytest.raises(CodeNotFound):
        db.redeem_code(GUILD, USER, "TM-AAAA-BBBB-CCCC")
    with pytest.raises(CodeNotFound):
        db.redeem_code(GUILD + 1, USER, code)
    assert db.get_subscription(GUILD, USER) is None


def test_grant_extends_remaining_time(db: Database) -> None:
    db.grant(GUILD, USER, 30, now=NOW)
    later = NOW + 10 * DAY
    subscription = db.grant(GUILD, USER, 30, now=later)
    assert subscription.expires_at == NOW + 60 * DAY


def test_grant_after_expiry_starts_from_now(db: Database) -> None:
    db.grant(GUILD, USER, 30, now=NOW)
    later = NOW + 40 * DAY
    assert db.grant(GUILD, USER, 30, now=later).expires_at == later + 30 * DAY


def test_lifetime_is_never_shortened(db: Database) -> None:
    db.grant(GUILD, USER, 0, now=NOW)
    subscription = db.grant(GUILD, USER, 30, now=NOW)
    assert subscription.lifetime
    assert subscription.is_active(NOW + 10_000 * DAY)
    assert db.expired_subscriptions(now=NOW + 10_000 * DAY) == []


def test_reminders_and_expiry(db: Database) -> None:
    db.grant(GUILD, USER, 30, now=NOW)
    db.grant(GUILD, 7, 0, now=NOW)

    assert db.due_reminders(3 * DAY, now=NOW) == []
    due = db.due_reminders(3 * DAY, now=NOW + 28 * DAY)
    assert [s.user_id for s in due] == [USER]
    db.mark_reminded(GUILD, USER)
    assert db.due_reminders(3 * DAY, now=NOW + 28 * DAY) == []

    expired = db.expired_subscriptions(now=NOW + 30 * DAY)
    assert [s.user_id for s in expired] == [USER]
    assert [s.user_id for s in db.active_subscriptions(GUILD, now=NOW + 30 * DAY)] == [7]


def test_extending_resets_reminder(db: Database) -> None:
    db.grant(GUILD, USER, 30, now=NOW)
    db.mark_reminded(GUILD, USER)
    db.grant(GUILD, USER, 30, now=NOW + 28 * DAY)
    assert not db.get_subscription(GUILD, USER).reminded


def test_delete_only_unused_codes(db: Database) -> None:
    first, second = db.create_codes(GUILD, 2, 30)
    db.redeem_code(GUILD, USER, first)
    assert not db.delete_code(GUILD, first)
    assert db.delete_code(GUILD, second.lower())
    assert db.unused_codes(GUILD) == []


def test_tickets(db: Database) -> None:
    db.open_ticket(GUILD, USER, 555)
    assert db.find_open_ticket(GUILD, USER) == 555
    assert db.ticket_owner(555) == USER
    db.close_ticket(555)
    assert db.find_open_ticket(GUILD, USER) is None
    assert db.ticket_owner(555) is None


def test_objects_and_panels(db: Database) -> None:
    db.set_object(GUILD, "role:premium", 1)
    db.set_object(GUILD, "role:premium", 2)
    assert db.get_object(GUILD, "role:premium") == 2
    assert db.object_ids(GUILD) == {2}
    db.set_panel(GUILD, "cenik", 10, 20)
    assert db.get_panel(GUILD, "cenik") == (10, 20)
