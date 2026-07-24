from __future__ import annotations

import pytest
from api.models.identity import Org, User
from api.models.session import PasswordResetToken, RefreshToken
from api.services import auth
from api.services.passwords import PasswordPolicyError, hash_password
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
    _seed_user(administrative_session)

    with pytest.raises(auth.InvalidCredentialsError):
        auth.login(
            administrative_session, email="alice@corp.com", password="wrong-pass"
        )

    rows = administrative_session.exec(select(RefreshToken)).all()
    assert rows == []


def test_login_with_unknown_email_raises(administrative_session: Session) -> None:
    with pytest.raises(auth.InvalidCredentialsError):
        auth.login(
            administrative_session, email="nobody@corp.com", password=VALID_PASSWORD
        )


def test_logout_revokes_the_current_family(administrative_session: Session) -> None:
    from api.services.tokens import issue_refresh_token

    user = _seed_user(administrative_session)
    raw = issue_refresh_token(administrative_session, user_id=user.id)

    auth.logout(administrative_session, refresh_token=raw)

    row = administrative_session.exec(select(RefreshToken)).one()
    assert row.revoked_at is not None


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


def test_reset_password_consumes_token_once(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)
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
