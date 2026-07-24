from __future__ import annotations

import hashlib
from datetime import timedelta
from uuid import uuid4

import pytest
from api.core.config import get_settings
from api.models.identity import Org, User
from api.models.persistence import utc_now
from api.models.session import RefreshToken
from api.services import tokens
from sqlmodel import Session, select


def test_access_token_round_trips_claims() -> None:
    user_id = uuid4()
    org_id = uuid4()
    before = utc_now()

    token = tokens.create_access_token(user_id=user_id, org_id=org_id, role="admin")
    claims = tokens.decode_access_token(token)

    assert claims["sub"] == str(user_id)
    assert claims["org_id"] == str(org_id)
    assert claims["role"] == "admin"

    ttl = get_settings().access_token_ttl_minutes
    exp_minus_iat = claims["exp"] - claims["iat"]
    assert exp_minus_iat == ttl * 60
    assert claims["iat"] >= int(before.timestamp())


def _seed_user(session: Session) -> User:
    org = Org(name="Acme")
    session.add(org)
    session.commit()
    session.refresh(org)
    user = User(
        org_id=org.id,
        email="alice@corp.com",
        password_hash="x",
        role="admin",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_issue_refresh_token_creates_family_row(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)

    raw = tokens.issue_refresh_token(administrative_session, user_id=user.id)

    rows = administrative_session.exec(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.token_hash == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert row.rotated_at is None
    assert row.revoked_at is None


def test_rotate_retires_old_row_and_copies_family_expiry(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)
    raw = tokens.issue_refresh_token(administrative_session, user_id=user.id)
    original = administrative_session.exec(select(RefreshToken)).one()

    rotated_user_id, new_raw = tokens.rotate_refresh_token(
        administrative_session, raw_token=raw
    )

    administrative_session.refresh(original)
    assert original.rotated_at is not None
    assert new_raw != raw
    assert rotated_user_id == user.id

    rows = administrative_session.exec(
        select(RefreshToken).where(RefreshToken.family_id == original.family_id)
    ).all()
    assert len(rows) == 2
    new_row = next(r for r in rows if r.id != original.id)
    assert new_row.family_expires_at == original.family_expires_at
    assert new_row.rotated_at is None
    assert new_row.revoked_at is None


def test_reusing_rotated_hash_revokes_whole_family(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)
    raw = tokens.issue_refresh_token(administrative_session, user_id=user.id)
    tokens.rotate_refresh_token(administrative_session, raw_token=raw)

    with pytest.raises(tokens.RefreshTokenError):
        tokens.rotate_refresh_token(administrative_session, raw_token=raw)

    original = administrative_session.exec(select(RefreshToken)).all()
    rows = [r for r in original if r.user_id == user.id]
    assert len(rows) == 2
    assert all(r.revoked_at is not None for r in rows)


def test_reusing_revoked_hash_revokes_whole_family(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)
    raw = tokens.issue_refresh_token(administrative_session, user_id=user.id)
    tokens.revoke_refresh_token(administrative_session, raw_token=raw)

    with pytest.raises(tokens.RefreshTokenError):
        tokens.rotate_refresh_token(administrative_session, raw_token=raw)

    row = administrative_session.exec(select(RefreshToken)).one()
    assert row.revoked_at is not None


def test_rotate_past_family_expiry_is_rejected(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)
    raw = tokens.issue_refresh_token(administrative_session, user_id=user.id)
    row = administrative_session.exec(select(RefreshToken)).one()
    row.family_expires_at = utc_now() - timedelta(seconds=1)
    administrative_session.add(row)
    administrative_session.commit()

    with pytest.raises(tokens.RefreshTokenError):
        tokens.rotate_refresh_token(administrative_session, raw_token=raw)


def test_revoke_refresh_token_marks_rows_revoked(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)
    raw = tokens.issue_refresh_token(administrative_session, user_id=user.id)

    tokens.revoke_refresh_token(administrative_session, raw_token=raw)

    row = administrative_session.exec(select(RefreshToken)).one()
    assert row.revoked_at is not None


def test_revoke_all_refresh_tokens_marks_every_row(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)
    tokens.issue_refresh_token(administrative_session, user_id=user.id)
    tokens.issue_refresh_token(administrative_session, user_id=user.id)

    tokens.revoke_all_refresh_tokens(administrative_session, user_id=user.id)

    rows = administrative_session.exec(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    ).all()
    assert len(rows) == 2
    assert all(r.revoked_at is not None for r in rows)
