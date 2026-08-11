from __future__ import annotations

from datetime import datetime, timezone
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


def test_change_member_role_promotes_a_viewer(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    viewer = _seed_user(
        administrative_session, org_id=org.id, email="viewer@corp.com"
    )

    changed = users.change_member_role(
        administrative_session,
        user_id=viewer.id,
        org_id=org.id,
        role="admin",
    )

    assert changed is not None
    assert changed.id == viewer.id
    assert changed.role == "admin"
    administrative_session.expire_all()
    assert administrative_session.get(User, viewer.id).role == "admin"


def test_change_member_role_demotes_an_admin_when_another_admin_exists(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    target = _seed_user(
        administrative_session,
        org_id=org.id,
        email="target@corp.com",
        role="admin",
    )
    _seed_user(
        administrative_session,
        org_id=org.id,
        email="remaining@corp.com",
        role="admin",
    )

    changed = users.change_member_role(
        administrative_session,
        user_id=target.id,
        org_id=org.id,
        role="viewer",
    )

    assert changed is not None
    assert changed.id == target.id
    assert changed.role == "viewer"
    administrative_session.expire_all()
    assert administrative_session.get(User, target.id).role == "viewer"


def test_change_member_role_is_idempotent_for_the_current_role(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    admin = _seed_user(
        administrative_session,
        org_id=org.id,
        email="admin@corp.com",
        role="admin",
    )

    changed = users.change_member_role(
        administrative_session,
        user_id=admin.id,
        org_id=org.id,
        role="admin",
    )

    assert changed is not None
    assert changed.id == admin.id
    assert changed.role == "admin"


def test_change_member_role_refuses_to_demote_the_orgs_last_admin(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session, "Org A")
    other_org = _seed_org(administrative_session, "Org B")
    last_admin = _seed_user(
        administrative_session,
        org_id=org.id,
        email="last@corp.com",
        role="admin",
    )
    other_admin = _seed_user(
        administrative_session,
        org_id=other_org.id,
        email="other@corp.com",
        role="admin",
    )

    with pytest.raises(users.LastAdminError):
        users.change_member_role(
            administrative_session,
            user_id=last_admin.id,
            org_id=org.id,
            role="viewer",
        )

    assert administrative_session.get(User, last_admin.id).role == "admin"
    assert administrative_session.get(User, other_admin.id).role == "admin"


def test_change_member_role_unknown_user_returns_none(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)

    assert (
        users.change_member_role(
            administrative_session,
            user_id=uuid4(),
            org_id=org.id,
            role="admin",
        )
        is None
    )


def test_change_member_role_foreign_user_returns_none_and_preserves_the_row(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session, "Org A")
    other_org = _seed_org(administrative_session, "Org B")
    outsider = _seed_user(
        administrative_session,
        org_id=other_org.id,
        email="outsider@corp.com",
        role="viewer",
    )

    changed = users.change_member_role(
        administrative_session,
        user_id=outsider.id,
        org_id=org.id,
        role="admin",
    )

    assert changed is None
    administrative_session.expire_all()
    preserved = administrative_session.get(User, outsider.id)
    assert preserved is not None
    assert preserved.org_id == other_org.id
    assert preserved.role == "viewer"


def test_list_org_members_scopes_to_org_and_orders_null_last(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session, "Org A")
    other_org = _seed_org(administrative_session, "Org B")
    recent = _seed_user(
        administrative_session, org_id=org.id, email="recent@corp.com"
    )
    older = _seed_user(
        administrative_session, org_id=org.id, email="older@corp.com"
    )
    never_seen = _seed_user(
        administrative_session, org_id=org.id, email="never@corp.com"
    )
    foreign = _seed_user(
        administrative_session, org_id=other_org.id, email="foreign@corp.com"
    )
    recent.last_seen_at = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    older.last_seen_at = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
    foreign.last_seen_at = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    administrative_session.add_all([recent, older, foreign])
    administrative_session.commit()

    members = users.list_org_members(administrative_session, org_id=org.id)

    assert [member.id for member in members] == [
        recent.id,
        older.id,
        never_seen.id,
    ]
    assert foreign.id not in {member.id for member in members}
    assert members[-1].last_seen_at is None


def test_list_org_members_uses_ascending_id_as_a_stable_tiebreak(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    seen_at = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    later_id = User(
        id=uuid4(),
        org_id=org.id,
        email="later@corp.com",
        password_hash=hash_password(VALID_PASSWORD),
        role="viewer",
        last_seen_at=seen_at,
    )
    earlier_id = User(
        id=uuid4(),
        org_id=org.id,
        email="earlier@corp.com",
        password_hash=hash_password(VALID_PASSWORD),
        role="viewer",
        last_seen_at=seen_at,
    )
    if earlier_id.id > later_id.id:
        earlier_id, later_id = later_id, earlier_id
    administrative_session.add_all([later_id, earlier_id])
    administrative_session.commit()

    first = users.list_org_members(administrative_session, org_id=org.id)
    second = users.list_org_members(administrative_session, org_id=org.id)

    assert [member.id for member in first] == [earlier_id.id, later_id.id]
    assert [member.id for member in second] == [earlier_id.id, later_id.id]
