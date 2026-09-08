from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from threading import Barrier, Event
from uuid import UUID

import pytest
from api.models.identity import Org, User
from api.services.invites import INVITE_LOCK_NAMESPACE
from api.services.org_lock import ORG_ADMIN_LOCK_NAMESPACE, lock_org_admins
from api.services.users import LastAdminError, change_member_role, count_org_admins
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

# delete_self/delete_member stay unlocked; DMI-105 owns adoption and
# mixed-race coverage.

BLOCKED_TIMEOUT = 0.2
CONCURRENCY_TIMEOUT = 7.0
DATABASE_LOCK_TIMEOUT_MS = 5_000


def _seed_org(session: Session, name: str) -> Org:
    org = Org(name=name)
    session.add(org)
    session.flush()
    return org


def _seed_user(
    session: Session, *, org_id: UUID, email: str, role: str = "viewer"
) -> User:
    user = User(
        org_id=org_id,
        email=email,
        password_hash="x",  # unused: these tests never authenticate
        role=role,
    )
    session.add(user)
    session.flush()
    return user


def _set_lock_timeout(session: Session) -> None:
    session.execute(
        text(f"SET LOCAL statement_timeout = '{DATABASE_LOCK_TIMEOUT_MS}ms'")
    )


def _acquire_org_lock(
    engine: Engine, *, org_id: UUID, ready: Event | None = None
) -> None:
    with Session(engine) as session:
        _set_lock_timeout(session)
        if ready is not None:
            ready.set()
        lock_org_admins(session, org_id=org_id)
        session.rollback()


def _change_role(
    engine: Engine,
    *,
    barrier: Barrier,
    user_id: UUID,
    org_id: UUID,
    role: str,
    actor_user_id: UUID,
    actor_email: str,
) -> None:
    with Session(engine) as session:
        _set_lock_timeout(session)
        # The actor row belongs to this thread's session, so load it here rather
        # than handing a User across threads.
        actor = session.get(User, actor_user_id)
        assert actor is not None and actor.email == actor_email
        barrier.wait(timeout=CONCURRENCY_TIMEOUT)
        changed = change_member_role(
            session,
            user_id=user_id,
            org_id=org_id,
            role=role,
            actor=actor,
        )
        assert changed is not None


def test_same_org_lock_blocks_until_the_holding_transaction_commits(
    migrated_database: Engine,
) -> None:
    with Session(migrated_database) as seed:
        org = _seed_org(seed, "Same org")
        seed.commit()
        org_id = org.id

    holder = Session(migrated_database)
    executor = ThreadPoolExecutor(max_workers=1)
    ready = Event()
    try:
        lock_org_admins(holder, org_id=org_id)
        contender = executor.submit(
            _acquire_org_lock,
            migrated_database,
            org_id=org_id,
            ready=ready,
        )
        assert ready.wait(timeout=CONCURRENCY_TIMEOUT)

        with pytest.raises(FutureTimeoutError):
            contender.result(timeout=BLOCKED_TIMEOUT)

        holder.commit()
        contender.result(timeout=CONCURRENCY_TIMEOUT)
    finally:
        holder.close()
        executor.shutdown(wait=True, cancel_futures=True)


def test_different_org_locks_do_not_block_each_other(
    migrated_database: Engine,
) -> None:
    with Session(migrated_database) as seed:
        first_org = _seed_org(seed, "First org")
        second_org = _seed_org(seed, "Second org")
        seed.commit()
        first_org_id = first_org.id
        second_org_id = second_org.id

    holder = Session(migrated_database)
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        lock_org_admins(holder, org_id=first_org_id)
        contender = executor.submit(
            _acquire_org_lock,
            migrated_database,
            org_id=second_org_id,
        )
        contender.result(timeout=CONCURRENCY_TIMEOUT)
    finally:
        holder.rollback()
        holder.close()
        executor.shutdown(wait=True, cancel_futures=True)


@pytest.mark.parametrize("release", ["commit", "rollback"])
def test_org_lock_is_released_at_transaction_end(
    migrated_database: Engine, release: str
) -> None:
    with Session(migrated_database) as seed:
        org = _seed_org(seed, f"Release by {release}")
        seed.commit()
        org_id = org.id

    holder = Session(migrated_database)
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        lock_org_admins(holder, org_id=org_id)
        if release == "commit":
            holder.commit()
        else:
            holder.rollback()

        contender = executor.submit(
            _acquire_org_lock, migrated_database, org_id=org_id
        )
        contender.result(timeout=CONCURRENCY_TIMEOUT)
    finally:
        holder.close()
        executor.shutdown(wait=True, cancel_futures=True)


def test_org_admin_lock_is_separate_from_the_invite_lock_namespace(
    migrated_database: Engine,
) -> None:
    assert ORG_ADMIN_LOCK_NAMESPACE != INVITE_LOCK_NAMESPACE

    with Session(migrated_database) as seed:
        org = _seed_org(seed, "Namespace org")
        seed.commit()
        org_id = org.id

    holder = Session(migrated_database)
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        holder.execute(
            text(
                "SELECT pg_advisory_xact_lock("
                ":namespace, hashtext(:org_id || :email))"
            ),
            {
                "namespace": INVITE_LOCK_NAMESPACE,
                "org_id": str(org_id),
                "email": "person@example.com",
            },
        )
        contender = executor.submit(
            _acquire_org_lock, migrated_database, org_id=org_id
        )
        contender.result(timeout=CONCURRENCY_TIMEOUT)
    finally:
        holder.rollback()
        holder.close()
        executor.shutdown(wait=True, cancel_futures=True)


def test_concurrent_promotions_both_succeed(migrated_database: Engine) -> None:
    with Session(migrated_database) as seed:
        org = _seed_org(seed, "Promotion org")
        _seed_user(seed, org_id=org.id, email="admin@example.com", role="admin")
        first_viewer = _seed_user(
            seed, org_id=org.id, email="first@example.com"
        )
        second_viewer = _seed_user(
            seed, org_id=org.id, email="second@example.com"
        )
        seed.commit()
        org_id = org.id
        viewer_ids = (first_viewer.id, second_viewer.id)
        admin_id = seed.exec(
            select(User).where(User.org_id == org.id, User.email == "admin@example.com")
        ).one().id

    barrier = Barrier(2)
    executor = ThreadPoolExecutor(max_workers=2)
    try:
        futures = [
            executor.submit(
                _change_role,
                migrated_database,
                barrier=barrier,
                user_id=user_id,
                org_id=org_id,
                role="admin",
                actor_user_id=admin_id,
                actor_email="admin@example.com",
            )
            for user_id in viewer_ids
        ]
        for future in futures:
            future.result(timeout=CONCURRENCY_TIMEOUT)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)

    with Session(migrated_database) as check:
        assert count_org_admins(check, org_id=org_id) == 3
        for user_id in viewer_ids:
            promoted = check.get(User, user_id)
            assert promoted is not None
            assert promoted.role == "admin"


def test_concurrent_mutual_demotion_leaves_exactly_one_admin(
    migrated_database: Engine,
) -> None:
    with Session(migrated_database) as seed:
        org = _seed_org(seed, "Demotion org")
        first_admin = _seed_user(
            seed, org_id=org.id, email="first-admin@example.com", role="admin"
        )
        second_admin = _seed_user(
            seed, org_id=org.id, email="second-admin@example.com", role="admin"
        )
        seed.commit()
        org_id = org.id
        demotions = (
            (first_admin.id, second_admin.id, first_admin.email),
            (second_admin.id, first_admin.id, second_admin.email),
        )

    barrier = Barrier(2)
    executor = ThreadPoolExecutor(max_workers=2)
    try:
        futures = [
            executor.submit(
                _change_role,
                migrated_database,
                barrier=barrier,
                user_id=target_id,
                org_id=org_id,
                role="viewer",
                actor_user_id=actor_id,
                actor_email=actor_email,
            )
            for actor_id, target_id, actor_email in demotions
        ]
        outcomes: list[str] = []
        for future in futures:
            try:
                future.result(timeout=CONCURRENCY_TIMEOUT)
            except LastAdminError:
                outcomes.append("last_admin")
            else:
                outcomes.append("success")
    finally:
        executor.shutdown(wait=True, cancel_futures=True)

    assert sorted(outcomes) == ["last_admin", "success"]
    with Session(migrated_database) as check:
        assert count_org_admins(check, org_id=org_id) == 1
