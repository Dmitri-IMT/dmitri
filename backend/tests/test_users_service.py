from __future__ import annotations

from uuid import uuid4

import pytest
from api.models.identity import Org, User
from api.services import users
from api.services.passwords import hash_password
from sqlmodel import Session, select

VALID_PASSWORD = "Xk9$mQvL2pTz"


def _seed_org(session: Session, name: str = "Acme") -> Org:
    org = Org(name=name)
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def _seed_user(session: Session, *, org_id, email: str, role: str = "viewer") -> User:
    user = User(
        org_id=org_id,
        email=email,
        password_hash=hash_password(VALID_PASSWORD),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_count_org_admins_counts_only_admins_of_the_given_org(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session, "Org A")
    other = _seed_org(administrative_session, "Org B")
    _seed_user(administrative_session, org_id=org.id, email="a1@corp.com", role="admin")
    _seed_user(administrative_session, org_id=org.id, email="a2@corp.com", role="admin")
    _seed_user(administrative_session, org_id=org.id, email="v@corp.com")
    _seed_user(
        administrative_session, org_id=other.id, email="b1@corp.com", role="admin"
    )

    assert users.count_org_admins(administrative_session, org_id=org.id) == 2


def test_delete_self_sole_admin_raises_last_admin_and_keeps_the_row(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    admin = _seed_user(
        administrative_session, org_id=org.id, email="a@corp.com", role="admin"
    )
    _seed_user(administrative_session, org_id=org.id, email="v@corp.com")

    with pytest.raises(users.LastAdminError):
        users.delete_self(administrative_session, user=admin)

    assert administrative_session.get(User, admin.id) is not None


def test_delete_self_viewer_succeeds_in_an_org_with_one_admin(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    _seed_user(administrative_session, org_id=org.id, email="a@corp.com", role="admin")
    viewer = _seed_user(administrative_session, org_id=org.id, email="v@corp.com")
    viewer_id = viewer.id

    users.delete_self(administrative_session, user=viewer)

    assert administrative_session.get(User, viewer_id) is None
    assert users.count_org_admins(administrative_session, org_id=org.id) == 1


def test_delete_self_admin_succeeds_once_a_second_admin_exists(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    admin = _seed_user(
        administrative_session, org_id=org.id, email="a1@corp.com", role="admin"
    )
    _seed_user(administrative_session, org_id=org.id, email="a2@corp.com", role="admin")
    admin_id = admin.id

    users.delete_self(administrative_session, user=admin)

    assert administrative_session.get(User, admin_id) is None
    assert users.count_org_admins(administrative_session, org_id=org.id) == 1


def test_delete_self_sole_member_of_a_one_member_org_is_locked_out(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    admin = _seed_user(
        administrative_session, org_id=org.id, email="only@corp.com", role="admin"
    )

    with pytest.raises(users.LastAdminError):
        users.delete_self(administrative_session, user=admin)

    assert administrative_session.exec(select(User)).all() == [admin]


def test_delete_member_removes_a_peer_admin_leaving_one_admin(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    _seed_user(administrative_session, org_id=org.id, email="a1@corp.com", role="admin")
    peer = _seed_user(
        administrative_session, org_id=org.id, email="a2@corp.com", role="admin"
    )
    peer_id = peer.id

    assert users.delete_member(administrative_session, user_id=peer_id, org_id=org.id)

    assert administrative_session.get(User, peer_id) is None
    assert users.count_org_admins(administrative_session, org_id=org.id) == 1


def test_delete_member_unknown_id_returns_false(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)

    assert not users.delete_member(
        administrative_session, user_id=uuid4(), org_id=org.id
    )


def test_delete_member_foreign_org_id_returns_false_and_leaves_the_row(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session, "Org A")
    other = _seed_org(administrative_session, "Org B")
    outsider = _seed_user(administrative_session, org_id=other.id, email="b@corp.com")

    assert not users.delete_member(
        administrative_session, user_id=outsider.id, org_id=org.id
    )

    assert administrative_session.get(User, outsider.id) is not None
