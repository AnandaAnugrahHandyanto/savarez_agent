from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins.memory.holographic.store import MemoryStore

SOURCE_TAG = 'source:businessos-doc-sync'
SYNC_KEY_PREFIX = 'sync_key:'
DOC_TAG_PREFIX = 'doc:'


@dataclass(frozen=True)
class SyncFact:
    key: str
    content: str
    category: str = 'project'
    doc: str = 'unknown'
    tags: tuple[str, ...] = field(default_factory=tuple)

    def normalized_tags(self) -> str:
        ordered: list[str] = []
        for tag in (SOURCE_TAG, f'{SYNC_KEY_PREFIX}{self.key}', f'{DOC_TAG_PREFIX}{self.doc}', *self.tags):
            clean = tag.strip()
            if clean and clean not in ordered:
                ordered.append(clean)
        return ','.join(ordered)


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding='utf-8').splitlines()


def _strip_bullet(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith('- '):
        return stripped[2:].strip()
    return None


def _extract_code_value(text: str) -> str:
    match = re.search(r'`([^`]+)`', text)
    if match:
        return match.group(1).strip()
    return text.strip().strip('-').strip()


def _extract_single_value_after_label(lines: Sequence[str], label: str) -> str:
    for index, line in enumerate(lines):
        if line.strip() != label:
            continue
        for candidate in lines[index + 1 : index + 6]:
            stripped = candidate.strip()
            if not stripped:
                continue
            bullet = _strip_bullet(stripped)
            if bullet is not None:
                return _extract_code_value(bullet)
            return _extract_code_value(stripped)
    raise ValueError(f'Could not find value after label: {label}')


def _extract_heading_bullets(lines: Sequence[str], heading: str) -> list[str]:
    collecting = False
    items: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not collecting:
            if stripped == heading:
                collecting = True
            continue
        if stripped.startswith('## '):
            break
        bullet = _strip_bullet(stripped)
        if bullet is not None:
            items.append(bullet)
    return items


def _extract_label_bullets(lines: Sequence[str], label: str, stop_markers: Sequence[str] | None = None) -> list[str]:
    collecting = False
    items: list[str] = []
    stop_markers = tuple(stop_markers or ())
    for line in lines:
        stripped = line.strip()
        if not collecting:
            if stripped == label:
                collecting = True
            continue
        if stripped.startswith('## '):
            break
        if stripped in stop_markers:
            break
        bullet = _strip_bullet(stripped)
        if bullet is not None:
            items.append(bullet)
    return items


def _join_fact_items(items: Iterable[str]) -> str:
    cleaned = [item.strip().rstrip('.') for item in items if item.strip()]
    return '; '.join(cleaned)


def _decision_facts(decisions_path: Path) -> list[SyncFact]:
    text = decisions_path.read_text(encoding='utf-8')
    blocks = re.split(r'(?m)^##\s+', text)
    facts: list[SyncFact] = []
    for block in blocks:
        block = block.strip()
        if not block or not block.startswith('D-'):
            continue
        lines = block.splitlines()
        title_line = lines[0].strip()
        code, _, title = title_line.partition(':')
        decision_lines: list[str] = []
        capture = False
        for raw in lines[1:]:
            stripped = raw.strip()
            if stripped == 'Decision:':
                capture = True
                continue
            if stripped == 'Why:':
                break
            if capture:
                bullet = _strip_bullet(stripped)
                if bullet is not None:
                    decision_lines.append(bullet)
        if decision_lines:
            summary = _join_fact_items(decision_lines)
            facts.append(
                SyncFact(
                    key=f'decision-{code.lower()}',
                    content=f'BusinessOS decision {code}: {summary}.',
                    doc='decisions.md',
                    tags=(f'decision:{code.lower()}', title.strip().lower().replace(' ', '-')),
                )
            )
    return facts


def collect_sync_facts(businessos_root: str | Path | None = None) -> list[SyncFact]:
    businessos_root = Path(businessos_root or Path(__file__).resolve().parents[2])
    project_path = businessos_root / 'PROJECT.md'
    architecture_path = businessos_root / 'docs' / 'architecture.md'
    decisions_path = businessos_root / 'docs' / 'decisions.md'

    project_lines = _read_lines(project_path)
    architecture_lines = _read_lines(architecture_path)

    purpose = _join_fact_items(_extract_heading_bullets(project_lines, '## Purpose'))
    core_scope = _join_fact_items(_extract_heading_bullets(project_lines, '## Core scope'))
    invariants = _extract_heading_bullets(project_lines, '## Invariants')
    customer_lanes = _extract_label_bullets(project_lines, 'Customer-facing lanes:', ('Internal/ops lanes:',))
    internal_lanes = _extract_label_bullets(project_lines, 'Internal/ops lanes:', ('## Invariants',))

    design_principles = _extract_heading_bullets(architecture_lines, '## Design principles')
    current_stack = _extract_label_bullets(
        architecture_lines,
        'What the current on-disk stack supports:',
        ('What is still a later restoration step:',),
    )
    current_live_mailbox = _extract_label_bullets(
        architecture_lines,
        'Current live mailbox account:',
        ('Routing is alias-based across:',),
    )
    configured_sources = _extract_label_bullets(
        architecture_lines,
        'Configured source accounts:',
        ('## Lane separation model',),
    )

    facts: list[SyncFact] = [
        SyncFact(
            key='workspace-root',
            content=f"BusinessOS canonical workspace root is {_extract_single_value_after_label(project_lines, 'Canonical workspace root:')}.",
            doc='PROJECT.md',
            tags=('paths', 'canonical-root'),
        ),
        SyncFact(
            key='dropbox-root',
            content=f"BusinessOS Dropbox mirror root is {_extract_single_value_after_label(project_lines, 'Dropbox mirror root:')}.",
            doc='PROJECT.md',
            tags=('paths', 'dropbox-root'),
        ),
        SyncFact(
            key='purpose-summary',
            content=f'BusinessOS purpose: {purpose}.',
            doc='PROJECT.md',
            tags=('purpose',),
        ),
        SyncFact(
            key='core-scope-summary',
            content=f'BusinessOS current scope includes: {core_scope}.',
            doc='PROJECT.md',
            tags=('scope',),
        ),
        SyncFact(
            key='design-principles',
            content=f'BusinessOS design principles: {_join_fact_items(design_principles)}.',
            doc='architecture.md',
            tags=('architecture', 'principles'),
        ),
        SyncFact(
            key='current-stack-summary',
            content=f'Current on-disk BusinessOS stack supports: {_join_fact_items(current_stack)}.',
            doc='architecture.md',
            tags=('architecture', 'current-state'),
        ),
    ]

    for index, lane in enumerate(customer_lanes, start=1):
        facts.append(
            SyncFact(
                key=f'customer-lane-{index}',
                content=f'BusinessOS customer-facing lane is {lane}.',
                doc='PROJECT.md',
                tags=('lane', 'customer-facing'),
            )
        )

    for index, lane in enumerate(internal_lanes, start=1):
        facts.append(
            SyncFact(
                key=f'operator-lane-{index}',
                content=f'BusinessOS internal or ops lane is {lane}.',
                doc='PROJECT.md',
                tags=('lane', 'internal-ops'),
            )
        )

    for index, invariant in enumerate(invariants, start=1):
        facts.append(
            SyncFact(
                key=f'invariant-{index}',
                content=f'BusinessOS invariant: {invariant}.',
                doc='PROJECT.md',
                tags=('invariant',),
            )
        )

    for index, mailbox in enumerate(current_live_mailbox, start=1):
        facts.append(
            SyncFact(
                key=f'live-mailbox-{index}',
                content=f'BusinessOS current live mailbox account is {mailbox}.',
                doc='architecture.md',
                tags=('email', 'live-mailbox'),
            )
        )

    for index, source in enumerate(configured_sources, start=1):
        facts.append(
            SyncFact(
                key=f'telegram-source-{index}',
                content=f'BusinessOS configured Telegram source account: {source}.',
                doc='architecture.md',
                tags=('telegram', 'source-account'),
            )
        )

    facts.extend(_decision_facts(decisions_path))

    deduped: dict[str, SyncFact] = {}
    seen_content: set[str] = set()
    for fact in facts:
        content = fact.content.strip()
        if not content or content in seen_content:
            continue
        deduped[fact.key] = fact
        seen_content.add(content)
    return list(deduped.values())


def _parse_tags(tags: str | None) -> set[str]:
    return {part.strip() for part in (tags or '').split(',') if part.strip()}


def _managed_key(fact: dict) -> str | None:
    for tag in _parse_tags(fact.get('tags')):
        if tag.startswith(SYNC_KEY_PREFIX):
            return tag[len(SYNC_KEY_PREFIX) :]
    return None


def sync_fact_store(
    store: MemoryStore,
    desired_facts: Sequence[SyncFact],
    *,
    dry_run: bool = False,
    list_limit: int = 5000,
) -> dict[str, object]:
    existing = store.list_facts(limit=list_limit)
    managed_existing = {
        key: fact for fact in existing if SOURCE_TAG in _parse_tags(fact.get('tags')) if (key := _managed_key(fact))
    }
    existing_by_content = {fact['content']: fact for fact in existing}

    added: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    removed: list[str] = []

    desired_keys = {fact.key for fact in desired_facts}
    for fact in desired_facts:
        desired_tags = fact.normalized_tags()
        current = managed_existing.get(fact.key) or existing_by_content.get(fact.content)
        if current is None:
            if not dry_run:
                store.add_fact(fact.content, category=fact.category, tags=desired_tags)
            added.append(fact.key)
            continue

        current_tags = current.get('tags') or ''
        tags_changed = _parse_tags(current_tags) != _parse_tags(desired_tags)
        content_changed = (current.get('content') or '') != fact.content
        category_changed = (current.get('category') or '') != fact.category
        if tags_changed or content_changed or category_changed:
            if not dry_run:
                store.update_fact(
                    int(current['fact_id']),
                    content=fact.content,
                    tags=desired_tags,
                    category=fact.category,
                )
            updated.append(fact.key)
        else:
            unchanged.append(fact.key)

    for key, current in managed_existing.items():
        if key in desired_keys:
            continue
        if not dry_run:
            store.remove_fact(int(current['fact_id']))
        removed.append(key)

    return {
        'desired_count': len(desired_facts),
        'managed_existing_count': len(managed_existing),
        'added': added,
        'updated': updated,
        'unchanged': unchanged,
        'removed': removed,
        'dry_run': dry_run,
    }


def sync_businessos_memory(
    businessos_root: str | Path | None = None,
    db_path: str | Path | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, object]:
    businessos_root = Path(businessos_root or Path(__file__).resolve().parents[2])
    desired_facts = collect_sync_facts(businessos_root)
    store = MemoryStore(db_path=db_path) if db_path else MemoryStore()
    result = sync_fact_store(store, desired_facts, dry_run=dry_run)
    result['businessos_root'] = str(businessos_root)
    result['db_path'] = str(store.db_path)
    result['source_tag'] = SOURCE_TAG
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description='Sync canonical BusinessOS markdown facts into Holographic memory.')
    parser.add_argument('--businessos-root', type=Path)
    parser.add_argument('--db-path', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    result = sync_businessos_memory(
        businessos_root=args.businessos_root,
        db_path=args.db_path,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
