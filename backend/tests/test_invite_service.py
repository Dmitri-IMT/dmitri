from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest
from api.models.identity import Invite, Org, User
from api.models.persistence import utc_now
from api.services import auth as auth_module
from api.services import invites
from api.services import passwords as passwords_module
from api.services.passwords import PasswordPolicyError, hash_password
from sqlmodel import Session, select

VALID_PASSWORD = "Xk9$mQvL2pTz"


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

    def send_invite_link(self, email: str, token: str) -> None:
        self.calls.append((email, token))

    def send_reset_link(self, email: str, token: str) -> None:
        raise AssertionError("not expected")


def _seed_org(session: Session, name: str = "Acme") -> Org:
    org = Org(name=name)
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def _seed_user(session: Session, *, org_id, email: str) -> User:
    user = User(
        org_id=org_id,
        email=email,
        password_hash=hash_password(VALID_PASSWORD),
        role="viewer",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_create_invite_returns_raw_token_and_stores_only_hash(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    mailer = FakeMailer()

    raw_token, expires_at = invites.create_invite(
        administrative_session,
        org_id=org.id,
        email="new@corp.com",
        role="viewer",
        mailer=mailer,
    )

    row = administrative_session.exec(select(Invite)).one()
    assert row.token_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    assert row.consumed_at is None
    assert expires_at == row.expires_at
    delta = expires_at - utc_now()
    assert timedelta(hours=47) < delta < timedelta(hours=49)
    assert mailer.calls == [("new@corp.com", raw_token)]
    for value in row.model_dump().values():
        assert value != raw_token


def test_create_invite_expiry_derives_from_setting(
    administrative_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from api.core.config import get_settings

    monkeypatch.setenv("INVITE_TTL_HOURS", "5")
    get_settings.cache_clear()
    org = _seed_org(administrative_session)

    _raw_token, expires_at = invites.create_invite(
        administrative_session,
        org_id=org.id,
        email="new@corp.com",
        role="viewer",
        mailer=FakeMailer(),
    )

    delta = expires_at - utc_now()
    assert timedelta(hours=4) < delta < timedelta(hours=6)
    get_settings.cache_clear()


def test_invites_uses_shared_password_and_session_functions() -> None:
    assert invites.validate_policy is passwords_module.validate_policy
    assert invites.hash_password is passwords_module.hash_password
    assert invites.issue_session is auth_module.issue_session


def test_create_invite_same_org_member_raises_already_member(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    _seed_user(administrative_session, org_id=org.id, email="existing@corp.com")

    with pytest.raises(invites.AlreadyMemberError):
        invites.create_invite(
            administrative_session,
            org_id=org.id,
            email="existing@corp.com",
            role="viewer",
            mailer=FakeMailer(),
        )

    assert administrative_session.exec(select(Invite)).all() == []


def test_create_invite_live_invite_raises_pending_invite_error_and_mints_none(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    mailer = FakeMailer()
    invites.create_invite(
        administrative_session,
        org_id=org.id,
        email="new@corp.com",
        role="viewer",
        mailer=mailer,
    )

    with pytest.raises(invites.PendingInviteError):
        invites.create_invite(
            administrative_session,
            org_id=org.id,
            email="new@corp.com",
            role="admin",
            mailer=mailer,
        )

    rows = administrative_session.exec(select(Invite)).all()
    assert len(rows) == 1
    assert len(mailer.calls) == 1


def test_create_invite_pending_check_is_case_insensitive(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    mailer = FakeMailer()
    invites.create_invite(
        administrative_session,
        org_id=org.id,
        email="bob@corp.com",
        role="viewer",
        mailer=mailer,
    )

    with pytest.raises(invites.PendingInviteError):
        invites.create_invite(
            administrative_session,
            org_id=org.id,
            email="Bob@corp.com",
            role="admin",
            mailer=mailer,
        )

    rows = administrative_session.exec(select(Invite)).all()
    assert len(rows) == 1
    assert len(mailer.calls) == 1


def test_create_invite_consumed_invite_can_be_reissued(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    invite, _raw = _seed_invite(administrative_session, org_id=org.id, consumed=True)

    raw_token, _expires_at = invites.create_invite(
        administrative_session,
        org_id=org.id,
        email=invite.email,
        role="viewer",
        mailer=FakeMailer(),
    )

    assert raw_token
    rows = administrative_session.exec(select(Invite)).all()
    assert len(rows) == 2


def test_create_invite_expired_invite_can_be_reissued(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    invite, _raw = _seed_invite(
        administrative_session, org_id=org.id, expires_delta=timedelta(hours=-1)
    )

    raw_token, _expires_at = invites.create_invite(
        administrative_session,
        org_id=org.id,
        email=invite.email,
        role="viewer",
        mailer=FakeMailer(),
    )

    assert raw_token
    rows = administrative_session.exec(select(Invite)).all()
    assert len(rows) == 2


def test_create_invite_other_org_member_still_creates_invite(
    administrative_session: Session,
) -> None:
    org_a = _seed_org(administrative_session, "Org A")
    org_b = _seed_org(administrative_session, "Org B")
    _seed_user(administrative_session, org_id=org_b.id, email="shared@corp.com")

    raw_token, expires_at = invites.create_invite(
        administrative_session,
        org_id=org_a.id,
        email="shared@corp.com",
        role="viewer",
        mailer=FakeMailer(),
    )

    assert raw_token
    row = administrative_session.exec(
        select(Invite).where(Invite.email == "shared@corp.com")
    ).one()
    assert row.token_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    assert row.expires_at == expires_at
    assert row.org_id == org_a.id


def _seed_invite(
    session: Session,
    *,
    org_id,
    email: str = "invitee@corp.com",
    role: str = "viewer",
    expires_delta: timedelta = timedelta(hours=48),
    consumed: bool = False,
) -> tuple[Invite, str]:
    raw = "test-raw-invite-token-1234567890"
    invite = Invite(
        org_id=org_id,
        email=email,
        role=role,
        token_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        expires_at=utc_now() + expires_delta,
        consumed_at=utc_now() if consumed else None,
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite, raw


def test_accept_invite_creates_user_and_issues_session(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    invite, raw = _seed_invite(administrative_session, org_id=org.id, role="admin")

    access_token, refresh_token, expires_in = invites.accept_invite(
        administrative_session,
        token=raw,
        password=VALID_PASSWORD,
    )

    assert access_token
    assert refresh_token
    assert expires_in > 0
    user = administrative_session.exec(select(User)).one()
    assert user.org_id == org.id
    assert user.role == "admin"
    assert user.email == "invitee@corp.com"
    administrative_session.refresh(invite)
    assert invite.consumed_at is not None


def test_accept_invite_unknown_token_raises_invite_token_error(
    administrative_session: Session,
) -> None:
    with pytest.raises(invites.InviteTokenError):
        invites.accept_invite(
            administrative_session,
            token="does-not-exist",
            password=VALID_PASSWORD,
        )
    assert administrative_session.exec(select(User)).all() == []


def test_accept_invite_expired_raises_invite_token_error(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    invite, raw = _seed_invite(
        administrative_session, org_id=org.id, expires_delta=timedelta(hours=-1)
    )

    with pytest.raises(invites.InviteTokenError):
        invites.accept_invite(
            administrative_session,
            token=raw,
            password=VALID_PASSWORD,
        )
    administrative_session.refresh(invite)
    assert invite.consumed_at is None
    assert administrative_session.exec(select(User)).all() == []


def test_accept_invite_already_consumed_raises_invite_token_error(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    _invite, raw = _seed_invite(administrative_session, org_id=org.id, consumed=True)

    with pytest.raises(invites.InviteTokenError):
        invites.accept_invite(
            administrative_session,
            token=raw,
            password=VALID_PASSWORD,
        )
    assert administrative_session.exec(select(User)).all() == []


def test_accept_invite_weak_password_raises_policy_error_and_leaves_invite_unconsumed(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    invite, raw = _seed_invite(administrative_session, org_id=org.id)

    with pytest.raises(PasswordPolicyError):
        invites.accept_invite(
            administrative_session,
            token=raw,
            password="short",
        )

    administrative_session.refresh(invite)
    assert invite.consumed_at is None
    assert administrative_session.exec(select(User)).all() == []


def test_accept_invite_password_policy_still_receives_the_invited_address(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    invite, raw = _seed_invite(
        administrative_session, org_id=org.id, email="ferdinand@corp.com"
    )

    with pytest.raises(PasswordPolicyError) as excinfo:
        invites.accept_invite(
            administrative_session,
            token=raw,
            password="ferdinand-Xk9$mQvL",
        )

    assert excinfo.value.violations == ["must not contain your email"]
    administrative_session.refresh(invite)
    assert invite.consumed_at is None
    assert administrative_session.exec(select(User)).all() == []


def test_accept_invite_duplicate_email_same_org_raises_duplicate_user_error(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    _seed_user(administrative_session, org_id=org.id, email="invitee@corp.com")
    invite, raw = _seed_invite(administrative_session, org_id=org.id)

    with pytest.raises(invites.DuplicateUserError):
        invites.accept_invite(
            administrative_session,
            token=raw,
            password=VALID_PASSWORD,
        )

    administrative_session.refresh(invite)
    assert invite.consumed_at is None
    users = administrative_session.exec(select(User)).all()
    assert len(users) == 1


def test_accept_invite_duplicate_email_other_org_raises_duplicate_user_error(
    administrative_session: Session,
) -> None:
    org_a = _seed_org(administrative_session, "Org A")
    org_b = _seed_org(administrative_session, "Org B")
    _seed_user(administrative_session, org_id=org_b.id, email="invitee@corp.com")
    invite, raw = _seed_invite(administrative_session, org_id=org_a.id)

    with pytest.raises(invites.DuplicateUserError):
        invites.accept_invite(
            administrative_session,
            token=raw,
            password=VALID_PASSWORD,
        )

    administrative_session.refresh(invite)
    assert invite.consumed_at is None
    users = administrative_session.exec(select(User)).all()
    assert len(users) == 1


def test_accept_invite_losing_a_concurrent_signup_race_raises_duplicate_user_error(
    administrative_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    org = _seed_org(administrative_session)
    invite, raw = _seed_invite(administrative_session, org_id=org.id)

    # validate_policy runs after accept_invite's duplicate lookup and before it
    # inserts, so a rival committing here lands inside the real race window. The
    # rival uses its own session to commit independently, as a concurrent request
    # would.
    def _rival_registers_first(password: str, *, email: str | None = None) -> None:
        with Session(administrative_session.get_bind()) as rival:
            _seed_user(rival, org_id=org.id, email="invitee@corp.com")

    monkeypatch.setattr(invites, "validate_policy", _rival_registers_first)

    with pytest.raises(invites.DuplicateUserError):
        invites.accept_invite(
            administrative_session,
            token=raw,
            password=VALID_PASSWORD,
        )

    administrative_session.refresh(invite)
    assert invite.consumed_at is None
    users = administrative_session.exec(select(User)).all()
    assert len(users) == 1


def test_accept_invite_breached_password_raises_policy_error(
    administrative_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from api.core.config import get_settings
    from api.services import passwords as passwords_module

    monkeypatch.setenv("HIBP_ENABLED", "true")
    get_settings.cache_clear()

    breached_password = "correcthorsebatterystaple"
    sha1 = hashlib.sha1(breached_password.encode("utf-8")).hexdigest().upper()
    suffix = sha1[5:]

    class FakeResponse:
        text = f"{suffix}:5\n"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(passwords_module.httpx, "Client", FakeClient)

    org = _seed_org(administrative_session)
    invite, raw = _seed_invite(administrative_session, org_id=org.id)

    with pytest.raises(PasswordPolicyError):
        invites.accept_invite(
            administrative_session,
            token=raw,
            password=breached_password,
        )

    administrative_session.refresh(invite)
    assert invite.consumed_at is None
    assert administrative_session.exec(select(User)).all() == []
    get_settings.cache_clear()


def test_accept_invite_first_commit_is_atomic_for_user_and_invite(
    administrative_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    org = _seed_org(administrative_session)
    invite, raw = _seed_invite(administrative_session, org_id=org.id)

    real_commit = administrative_session.commit
    calls = {"n": 0}

    def _commit_then_boom_on_second_call() -> None:
        calls["n"] += 1
        if calls["n"] >= 2:
            raise RuntimeError("simulated commit failure")
        real_commit()

    monkeypatch.setattr(
        administrative_session, "commit", _commit_then_boom_on_second_call
    )

    with pytest.raises(RuntimeError):
        invites.accept_invite(
            administrative_session,
            token=raw,
            password=VALID_PASSWORD,
        )

    administrative_session.rollback()
    users = administrative_session.exec(select(User)).all()
    assert len(users) == 1
    administrative_session.refresh(invite)
    assert invite.consumed_at is not None


GONE_MESSAGE = "invalid or expired invite token"


def test_read_invite_returns_email_role_and_org_name(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session, "Acme Corp")
    _invite, raw = _seed_invite(administrative_session, org_id=org.id, role="admin")

    assert invites.read_invite(administrative_session, token=raw) == (
        "invitee@corp.com",
        "admin",
        "Acme Corp",
    )


def test_read_invite_unknown_token_raises_invite_token_error(
    administrative_session: Session,
) -> None:
    with pytest.raises(invites.InviteTokenError) as excinfo:
        invites.read_invite(administrative_session, token="does-not-exist")

    assert str(excinfo.value) == GONE_MESSAGE


def test_read_invite_expired_raises_same_error_as_unknown(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    _invite, raw = _seed_invite(
        administrative_session, org_id=org.id, expires_delta=timedelta(hours=-1)
    )

    with pytest.raises(invites.InviteTokenError) as excinfo:
        invites.read_invite(administrative_session, token=raw)

    assert str(excinfo.value) == GONE_MESSAGE


def test_read_invite_consumed_raises_same_error_as_unknown(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    _invite, raw = _seed_invite(administrative_session, org_id=org.id, consumed=True)

    with pytest.raises(invites.InviteTokenError) as excinfo:
        invites.read_invite(administrative_session, token=raw)

    assert str(excinfo.value) == GONE_MESSAGE


def test_read_invite_does_not_mutate_the_invite(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    invite, raw = _seed_invite(administrative_session, org_id=org.id)
    expires_at = invite.expires_at

    invites.read_invite(administrative_session, token=raw)

    administrative_session.refresh(invite)
    assert invite.consumed_at is None
    assert invite.expires_at == expires_at
    assert administrative_session.exec(select(User)).all() == []


def test_read_invite_is_repeatable(administrative_session: Session) -> None:
    org = _seed_org(administrative_session)
    _invite, raw = _seed_invite(administrative_session, org_id=org.id)

    first = invites.read_invite(administrative_session, token=raw)
    second = invites.read_invite(administrative_session, token=raw)

    assert first == second
