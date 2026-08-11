from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from api.models.identity import Org, User
from api.models.session import PasswordResetToken, RefreshToken
from api.services import auth
from api.services.passwords import PasswordPolicyError, hash_password
from sqlalchemy import event
from sqlmodel import Session, select

VALID_PASSWORD = "Xk9$mQvL2pTz"
OTHER_VALID_PASSWORD = "Zp4#nWxR7bHq"


@pytest.fixture(autouse=True)
def _disable_hibp(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("HIBP_ENABLED", "false")
    yield
    get_settings.cache_clear()


class FakeMailer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def send_reset_link(self, email: str, token: str) -> None:
        self.calls.append((email, token))


def _seed_user(session: Session, *, password: str = VALID_PASSWORD) -> User:
    org = Org(name="Acme")
    session.add(org)
    session.commit()
    session.refresh(org)
    user = User(
        org_id=org.id,
        email="alice@corp.com",
        password_hash=hash_password(password),
        role="admin",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _read_activity_fresh(
    session: Session, *, user_id
) -> tuple[datetime | None, datetime | None]:
    with Session(session.get_bind()) as fresh_session:
        user = fresh_session.get(User, user_id)
        assert user is not None
        return user.last_login_at, user.last_seen_at


def test_password_login_stamps_both_activity_facts_and_commits(
    administrative_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _seed_user(administrative_session)
    stamp_at = datetime(2026, 8, 11, 12, tzinfo=UTC)
    monkeypatch.setattr(auth, "utc_now", lambda: stamp_at)

    auth.login(
        administrative_session, email="alice@corp.com", password=VALID_PASSWORD
    )

    assert _read_activity_fresh(
        administrative_session, user_id=user.id
    ) == (stamp_at, stamp_at)


def test_refresh_strictly_advances_only_last_seen_and_commits(
    administrative_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _seed_user(administrative_session)
    login_at = datetime(2026, 8, 11, 12, tzinfo=UTC)
    refresh_at = login_at + timedelta(minutes=15)
    activity_times = iter((login_at, refresh_at))
    monkeypatch.setattr(auth, "utc_now", lambda: next(activity_times))
    _, refresh_token, _ = auth.login(
        administrative_session, email="alice@corp.com", password=VALID_PASSWORD
    )

    auth.refresh_session(administrative_session, refresh_token=refresh_token)

    refreshed_login_at, refreshed_seen_at = _read_activity_fresh(
        administrative_session, user_id=user.id
    )
    assert refreshed_login_at == login_at
    assert refreshed_seen_at == refresh_at
    assert refreshed_seen_at > refreshed_login_at


def test_refresh_token_reuse_leaves_activity_unchanged(
    administrative_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _seed_user(administrative_session)
    login_at = datetime(2026, 8, 11, 12, tzinfo=UTC)
    refresh_at = login_at + timedelta(minutes=15)
    activity_times = iter((login_at, refresh_at))
    monkeypatch.setattr(auth, "utc_now", lambda: next(activity_times))
    _, used_refresh_token, _ = auth.login(
        administrative_session, email="alice@corp.com", password=VALID_PASSWORD
    )
    auth.refresh_session(
        administrative_session, refresh_token=used_refresh_token
    )
    activity_after_success = _read_activity_fresh(
        administrative_session, user_id=user.id
    )

    with pytest.raises(auth.RefreshTokenError):
        auth.refresh_session(
            administrative_session, refresh_token=used_refresh_token
        )

    assert (
        _read_activity_fresh(administrative_session, user_id=user.id)
        == activity_after_success
    )


def test_activity_updates_name_only_the_intended_columns(
    administrative_session: Session,
) -> None:
    _seed_user(administrative_session)
    user_updates: list[str] = []
    engine = administrative_session.get_bind()

    def _capture_user_updates(
        conn, cursor, statement, parameters, context, executemany
    ) -> None:
        normalized = statement.strip().lower()
        if normalized.startswith("update users set "):
            user_updates.append(normalized)

    event.listen(engine, "before_cursor_execute", _capture_user_updates)
    try:
        _, refresh_token, _ = auth.login(
            administrative_session,
            email="alice@corp.com",
            password=VALID_PASSWORD,
        )
        login_updates = user_updates.copy()
        user_updates.clear()
        auth.refresh_session(
            administrative_session, refresh_token=refresh_token
        )
        refresh_updates = user_updates.copy()
    finally:
        event.remove(engine, "before_cursor_execute", _capture_user_updates)

    assert len(login_updates) == 1
    assert len(refresh_updates) == 1

    def _set_columns(statement: str) -> set[str]:
        set_clause = statement.split(" set ", 1)[1].split(" where ", 1)[0]
        return {
            assignment.split("=", 1)[0].strip().rsplit(".", 1)[-1]
            for assignment in set_clause.split(",")
        }

    assert _set_columns(login_updates[0]) == {"last_login_at", "last_seen_at"}
    assert _set_columns(refresh_updates[0]) == {"last_seen_at"}


def test_login_with_valid_credentials_issues_tokens(
    administrative_session: Session,
) -> None:
    _seed_user(administrative_session)

    access_token, refresh_token, expires_in = auth.login(
        administrative_session, email="alice@corp.com", password=VALID_PASSWORD
    )

    assert access_token
    assert refresh_token
    assert expires_in > 0
    rows = administrative_session.exec(select(RefreshToken)).all()
    assert len(rows) == 1


def test_login_with_bad_password_raises_and_issues_no_tokens(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)

    with pytest.raises(auth.InvalidCredentialsError):
        auth.login(
            administrative_session, email="alice@corp.com", password="wrong-pass"
        )

    rows = administrative_session.exec(select(RefreshToken)).all()
    assert rows == []
    assert _read_activity_fresh(
        administrative_session, user_id=user.id
    ) == (None, None)


def test_login_with_unknown_email_raises(administrative_session: Session) -> None:
    with pytest.raises(auth.InvalidCredentialsError):
        auth.login(
            administrative_session, email="nobody@corp.com", password=VALID_PASSWORD
        )


def test_logout_revokes_the_current_family_without_changing_activity(
    administrative_session: Session,
) -> None:
    from api.services.tokens import issue_refresh_token

    user = _seed_user(administrative_session)
    login_at = datetime(2026, 8, 10, 9, tzinfo=UTC)
    seen_at = login_at + timedelta(hours=1)
    user.last_login_at = login_at
    user.last_seen_at = seen_at
    administrative_session.add(user)
    raw = issue_refresh_token(administrative_session, user_id=user.id)

    auth.logout(administrative_session, refresh_token=raw)

    row = administrative_session.exec(select(RefreshToken)).one()
    assert row.revoked_at is not None
    assert _read_activity_fresh(
        administrative_session, user_id=user.id
    ) == (login_at, seen_at)


def test_change_password_wrong_current_raises_distinct_error(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)

    with pytest.raises(auth.WrongCurrentPasswordError):
        auth.change_password(
            administrative_session,
            user=user,
            current_password="wrong-pass",
            new_password=OTHER_VALID_PASSWORD,
        )

    assert not issubclass(auth.WrongCurrentPasswordError, PasswordPolicyError)
    assert not issubclass(
        auth.WrongCurrentPasswordError, auth.InvalidCredentialsError
    )


def test_change_password_weak_new_password_raises_policy_error(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)

    with pytest.raises(PasswordPolicyError):
        auth.change_password(
            administrative_session,
            user=user,
            current_password=VALID_PASSWORD,
            new_password="short",
        )

    assert not issubclass(PasswordPolicyError, auth.WrongCurrentPasswordError)
    assert not issubclass(PasswordPolicyError, auth.InvalidCredentialsError)


def test_change_password_success_updates_hash_and_leaves_sessions(
    administrative_session: Session,
) -> None:
    from api.services.tokens import issue_refresh_token

    user = _seed_user(administrative_session)
    issue_refresh_token(administrative_session, user_id=user.id)
    old_hash = user.password_hash
    old_changed_at = user.password_changed_at

    auth.change_password(
        administrative_session,
        user=user,
        current_password=VALID_PASSWORD,
        new_password=OTHER_VALID_PASSWORD,
    )

    administrative_session.refresh(user)
    assert user.password_hash != old_hash
    assert user.password_changed_at != old_changed_at
    rows = administrative_session.exec(select(RefreshToken)).all()
    assert len(rows) == 1
    assert rows[0].revoked_at is None


def test_forgot_password_known_email_sends_mail_and_creates_row(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)
    mailer = FakeMailer()

    auth.forgot_password(
        administrative_session, email="alice@corp.com", mailer=mailer
    )

    assert len(mailer.calls) == 1
    assert mailer.calls[0][0] == "alice@corp.com"
    rows = administrative_session.exec(select(PasswordResetToken)).all()
    assert len(rows) == 1
    assert rows[0].user_id == user.id


def test_forgot_password_unknown_email_is_silent(
    administrative_session: Session,
) -> None:
    mailer = FakeMailer()

    auth.forgot_password(
        administrative_session, email="nobody@corp.com", mailer=mailer
    )

    assert mailer.calls == []
    rows = administrative_session.exec(select(PasswordResetToken)).all()
    assert rows == []


def test_reset_password_consumes_token_once_without_changing_activity(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)
    login_at = datetime(2026, 8, 10, 9, tzinfo=UTC)
    seen_at = login_at + timedelta(hours=1)
    user.last_login_at = login_at
    user.last_seen_at = seen_at
    administrative_session.add(user)
    administrative_session.commit()
    mailer = FakeMailer()
    auth.forgot_password(
        administrative_session, email="alice@corp.com", mailer=mailer
    )
    raw_token = mailer.calls[0][1]

    auth.reset_password(
        administrative_session, token=raw_token, new_password=OTHER_VALID_PASSWORD
    )

    with pytest.raises(auth.InvalidResetTokenError):
        auth.reset_password(
            administrative_session, token=raw_token, new_password=VALID_PASSWORD
        )

    administrative_session.refresh(user)
    assert _read_activity_fresh(
        administrative_session, user_id=user.id
    ) == (login_at, seen_at)


def test_reset_password_weak_password_raises_policy_error(
    administrative_session: Session,
) -> None:
    _seed_user(administrative_session)
    mailer = FakeMailer()
    auth.forgot_password(
        administrative_session, email="alice@corp.com", mailer=mailer
    )
    raw_token = mailer.calls[0][1]

    with pytest.raises(PasswordPolicyError):
        auth.reset_password(
            administrative_session, token=raw_token, new_password="short"
        )


def test_reset_password_revokes_all_refresh_rows(
    administrative_session: Session,
) -> None:
    from api.services.tokens import issue_refresh_token

    user = _seed_user(administrative_session)
    issue_refresh_token(administrative_session, user_id=user.id)
    issue_refresh_token(administrative_session, user_id=user.id)
    mailer = FakeMailer()
    auth.forgot_password(
        administrative_session, email="alice@corp.com", mailer=mailer
    )
    raw_token = mailer.calls[0][1]

    auth.reset_password(
        administrative_session, token=raw_token, new_password=OTHER_VALID_PASSWORD
    )

    rows = administrative_session.exec(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    ).all()
    assert len(rows) == 2
    assert all(r.revoked_at is not None for r in rows)


def test_reset_password_bogus_token_raises(
    administrative_session: Session,
) -> None:
    with pytest.raises(auth.InvalidResetTokenError):
        auth.reset_password(
            administrative_session, token="bogus", new_password=VALID_PASSWORD
        )
