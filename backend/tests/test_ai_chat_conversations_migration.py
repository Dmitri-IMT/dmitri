from uuid import uuid4

import sqlalchemy as sa
from conftest import _migrate
from read_factories import seed_read_graph


def test_legacy_messages_stay_together_and_survive_round_trip(
    postgres_engine, administrative_session, actor_headers,
):
    seeded = seed_read_graph(administrative_session)
    scan_id = seeded['scan'].scan_id
    host_id = seeded['host'].id
    actor_headers(seeded['org'].id, 'viewer')
    user_id = administrative_session.execute(sa.text(
        'SELECT id FROM users WHERE org_id = :org_id'
    ), {'org_id': seeded['org'].id}).scalar_one()
    administrative_session.close()
    _migrate(postgres_engine, '20261024_47')
    try:
        with postgres_engine.begin() as connection:
            for index in range(14):
                connection.execute(sa.text('''
                    INSERT INTO ai_chat_messages (
                        message_id, scan_id, user_id, scope_type, scope_id,
                        question, answer, uncertainties_json,
                        referenced_finding_ids_json, created_at
                    ) VALUES (
                        :id, :scan, :user_id, :scope, :context_id,
                        'A previous question', 'A previous answer', '[]', '[]', now()
                    )
                '''), {'id': uuid4(), 'scan': scan_id,
                      'user_id': user_id, 'scope': 'scan' if index < 12 else 'host',
                      'context_id': scan_id if index < 12 else host_id})
        _migrate(postgres_engine, 'head')
        with postgres_engine.connect() as connection:
            groups = connection.execute(sa.text('''
                SELECT scope_type, count(*), count(DISTINCT conversation_id)
                FROM ai_chat_messages GROUP BY scope_type ORDER BY scope_type
            ''')).all()
            assert groups == [('host', 2, 1), ('scan', 12, 1)]
        _migrate(postgres_engine, '20261024_47')
        with postgres_engine.connect() as connection:
            assert connection.execute(sa.text(
                'SELECT count(*) FROM ai_chat_messages'
            )).scalar_one() == 14
    finally:
        _migrate(postgres_engine, 'head')
