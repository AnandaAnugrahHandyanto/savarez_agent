import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / '04_AUTOMATIONS' / 'scripts'
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from plugins.memory.holographic.store import MemoryStore
import sync_businessos_memory


def test_collect_sync_facts_includes_expected_businessos_truths():
    businessos_root = Path(__file__).resolve().parents[1]
    facts = sync_businessos_memory.collect_sync_facts(businessos_root)
    by_key = {fact.key: fact for fact in facts}

    assert 'workspace-root' in by_key
    assert by_key['workspace-root'].content.endswith('/home/yuiop/.hermes/hermes-agent/BusinessOS.')
    assert 'decision-d-005' in by_key
    assert 'customer-facing support intake and owner/operator control traffic must remain separate' in by_key['decision-d-005'].content.lower()
    assert any('support@helixsystems.cc' in fact.content for fact in facts)
    assert any('telegram-steady-support' in fact.content for fact in facts)


def test_sync_fact_store_adds_updates_and_removes_managed_facts(tmp_path):
    db_path = tmp_path / 'memory_store.db'
    store = MemoryStore(db_path=db_path)

    old_record = sync_businessos_memory.SyncFact(
        key='decision-d-001',
        content='Old decision text.',
        doc='decisions.md',
    )
    store.add_fact(old_record.content, category=old_record.category, tags=old_record.normalized_tags())
    store.add_fact('Untouched external fact.', category='project', tags='manual-seed')

    desired = [
        sync_businessos_memory.SyncFact(
            key='decision-d-001',
            content='Updated decision text.',
            doc='decisions.md',
        ),
        sync_businessos_memory.SyncFact(
            key='workspace-root',
            content='BusinessOS canonical workspace root is /tmp/BusinessOS.',
            doc='PROJECT.md',
        ),
    ]

    result = sync_businessos_memory.sync_fact_store(store, desired)

    assert result['added'] == ['workspace-root']
    assert result['updated'] == ['decision-d-001']
    assert result['removed'] == []

    facts = store.list_facts(limit=20)
    contents = {fact['content'] for fact in facts}
    tags = {fact['content']: fact['tags'] for fact in facts}

    assert 'Updated decision text.' in contents
    assert 'BusinessOS canonical workspace root is /tmp/BusinessOS.' in contents
    assert 'Untouched external fact.' in contents
    assert sync_businessos_memory.SOURCE_TAG in tags['Updated decision text.']

    followup = [
        sync_businessos_memory.SyncFact(
            key='workspace-root',
            content='BusinessOS canonical workspace root is /tmp/BusinessOS.',
            doc='PROJECT.md',
        )
    ]
    result2 = sync_businessos_memory.sync_fact_store(store, followup)
    assert result2['removed'] == ['decision-d-001']
    contents2 = {fact['content'] for fact in store.list_facts(limit=20)}
    assert 'Updated decision text.' not in contents2
    assert 'Untouched external fact.' in contents2
