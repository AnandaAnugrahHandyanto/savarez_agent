from __future__ import annotations

import email
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from email import policy
from pathlib import Path
from typing import Any


KNOWN_VENDORS = {
    'cloudflare': 'cloudflare',
    'zoho': 'zoho',
    'google': 'google',
    'gmail': 'google',
    'apple': 'apple',
    'stripe': 'stripe',
    'paypal': 'paypal',
    'openai': 'openai',
    'notion': 'notion',
    'slack': 'slack',
    'github': 'github',
    'vercel': 'vercel',
    'aws': 'aws',
    'amazon web services': 'aws',
    'namecheap': 'namecheap',
    'dun & bradstreet': 'dun-and-bradstreet',
    'dun and bradstreet': 'dun-and-bradstreet',
    'd-u-n-s': 'dun-and-bradstreet',
    'duns': 'dun-and-bradstreet',
}

EXPENSE_CATEGORY_RULES = [
    ('web-hosting-and-domains', ('cloudflare', 'domain', 'hosting', 'dns', 'registrar', 'namecheap', 'vercel')),
    ('software-subscriptions', ('zoho', 'openai', 'slack', 'notion', 'github', 'subscription', 'saas')),
    ('payment-processing-fees', ('stripe', 'paypal', 'processing fee')),
    ('app-store-fees', ('app store', 'play store', 'google play', 'apple developer', 'developer registration fee')),
    ('advertising-and-marketing', ('ads', 'advertising', 'marketing campaign')),
    ('legal-and-professional', ('legal', 'lawyer', 'attorney', 'accountant', 'cpa')),
]

DOCUMENT_KEYWORDS = (
    'invoice',
    'receipt',
    'statement',
    'contract',
    'agreement',
    'renewal',
    'subscription',
    'payment',
    'expense',
    'income',
    'payout',
    'deposit',
    'purchase',
    'order number',
    'registration fee',
    'd-u-n-s',
    'duns number',
    'dun & bradstreet',
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', (value or '').lower()).strip('-')
    return slug or 'item'


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _table_columns(con: sqlite3.Connection, table_name: str) -> set[str]:
    rows = con.execute(f'pragma table_info({table_name})').fetchall()
    names: set[str] = set()
    for row in rows:
        if isinstance(row, sqlite3.Row):
            names.add(row['name'])
        else:
            names.add(row[1])
    return names


def _ensure_columns(con: sqlite3.Connection, table_name: str, columns: dict[str, str]) -> None:
    existing = _table_columns(con, table_name)
    for name, definition in columns.items():
        if name not in existing:
            con.execute(f'alter table {table_name} add column {name} {definition}')


def ensure_business_ops_tables(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.executescript(
        '''
        create table if not exists documents (
            id text primary key,
            original_filename text,
            stored_filename text,
            document_type text,
            status text,
            document_date text,
            due_date text,
            paid_date text,
            amount real,
            currency text,
            vendor_name text,
            client_name text,
            service_id text,
            website_id text,
            domain_id text,
            email_account_id text,
            source_channel text,
            local_path text,
            dropbox_path text,
            extracted_text_path text,
            sha256 text,
            tags_json text,
            review_state text,
            notes text,
            created_at text,
            updated_at text
        );
        create table if not exists processing_log (
            id integer primary key autoincrement,
            source_path text,
            document_id text,
            event_type text,
            message text,
            created_at text default current_timestamp
        );
        create table if not exists expense_tax_treatment (
            document_id text primary key,
            tax_relevance text,
            tax_category_federal text,
            tax_category_nj text,
            deduction_confidence real,
            tax_year integer,
            schedule_or_return_section text,
            evidence_status text,
            business_purpose_note text,
            mixed_use_flag integer,
            business_use_percent real,
            nj_adjustment_required integer,
            nj_review_required integer,
            reviewed_by_human integer,
            review_notes text,
            created_at text,
            updated_at text
        );
        create table if not exists reminders (
            id integer primary key autoincrement,
            item_type text,
            item_id text,
            reminder_type text,
            due_date text,
            status text,
            notes text,
            created_at text default current_timestamp
        );
        create table if not exists task_items (
            id text primary key,
            title text not null,
            description text,
            status text not null default 'created',
            priority text not null default 'medium',
            app_id text,
            source_channel text,
            source_account text,
            source_message_id text,
            source_thread_id text,
            author_handle text,
            due_at text,
            reminder_at text,
            tags_json text default '[]',
            created_at text not null,
            updated_at text not null,
            latest_comment_at text
        );
        create table if not exists task_comments (
            id text primary key,
            task_id text not null,
            author_handle text,
            source_channel text,
            source_account text,
            source_message_id text,
            body text not null,
            created_at text not null
        );
        create table if not exists task_documents (
            task_id text not null,
            document_id text not null,
            relationship_type text not null default 'reference',
            linked_at text not null,
            primary key (task_id, document_id)
        );
        create table if not exists task_events (
            id text primary key,
            task_id text not null,
            event_type text not null,
            source_channel text,
            source_account text,
            source_message_id text,
            source_thread_id text,
            summary text,
            payload_json text,
            created_at text not null
        );
        create table if not exists daily_priorities (
            id text primary key,
            focus_date text not null,
            task_id text,
            title text not null,
            notes text,
            status text not null default 'active',
            source_channel text,
            source_account text,
            source_message_id text,
            source_thread_id text,
            author_handle text,
            created_at text not null,
            updated_at text not null
        );
        create table if not exists task_suggestions (
            id text primary key,
            source_channel text not null,
            source_account text,
            source_message_id text,
            source_thread_id text,
            message_id text,
            task_id text,
            title text not null,
            rationale text,
            category text,
            assigned_queue text,
            status text not null default 'suggested',
            created_at text not null,
            updated_at text not null
        );
        '''
    )
    _ensure_columns(
        con,
        'documents',
        {
            'finance_direction': 'text',
            'source_account': 'text',
            'source_reference': 'text',
        },
    )
    _ensure_columns(
        con,
        'task_items',
        {
            'description': 'text',
            'priority': "text not null default 'medium'",
            'app_id': 'text',
            'source_channel': 'text',
            'source_account': 'text',
            'source_message_id': 'text',
            'source_thread_id': 'text',
            'author_handle': 'text',
            'due_at': 'text',
            'reminder_at': 'text',
            'tags_json': "text default '[]'",
            'latest_comment_at': 'text',
        },
    )
    _ensure_columns(
        con,
        'task_events',
        {
            'source_channel': 'text',
            'source_account': 'text',
            'source_message_id': 'text',
            'source_thread_id': 'text',
            'payload_json': 'text',
        },
    )
    con.commit()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_text_from_eml(path: Path) -> str:
    message = email.message_from_bytes(path.read_bytes(), policy=policy.default)
    parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get_filename():
                continue
            if part.get_content_type() != 'text/plain':
                continue
            payload = part.get_payload(decode=True) or b''
            charset = part.get_content_charset() or 'utf-8'
            parts.append(payload.decode(charset, errors='replace').strip())
    else:
        payload = message.get_payload(decode=True) or b''
        charset = message.get_content_charset() or 'utf-8'
        parts.append(payload.decode(charset, errors='replace').strip())
    return '\n'.join(part for part in parts if part).strip()


def extract_text_from_path(path: Path, fallback_text: str | None = None) -> str:
    suffix = path.suffix.lower()
    if suffix in {'.txt', '.md', '.json', '.yaml', '.yml', '.csv', '.html', '.htm', '.log'}:
        return path.read_text(encoding='utf-8', errors='replace')
    if suffix == '.eml':
        return _extract_text_from_eml(path)
    if suffix == '.pdf':
        pdftotext = shutil.which('pdftotext')
        if pdftotext:
            proc = subprocess.run(
                [pdftotext, str(path), '-'],
                check=False,
                capture_output=True,
                text=True,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout
    if fallback_text:
        return fallback_text
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ''


def _detect_document_date(text: str, filename: str, fallback_dt: datetime | None = None) -> str:
    combined = f'{filename}\n{text}'
    match = re.search(r'\b(20\d{2}-\d{2}-\d{2})\b', combined)
    if match:
        return match.group(1)
    fallback_dt = fallback_dt or datetime.now(timezone.utc)
    return fallback_dt.date().isoformat()


def _detect_amount(text: str, filename: str) -> float | None:
    combined = f'{filename}\n{text}'
    for pattern in [r'\$\s*([0-9]+(?:\.[0-9]{2})?)', r'\bUSD\s*([0-9]+(?:\.[0-9]{2})?)\b']:
        match = re.search(pattern, combined, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def _detect_vendor(text: str, filename: str) -> str:
    combined = f'{filename}\n{text}'.lower()
    for needle, vendor in KNOWN_VENDORS.items():
        if needle in combined:
            return vendor
    stem = Path(filename).stem
    tokens = [token for token in re.split(r'[^a-zA-Z0-9]+', stem) if token]
    if tokens:
        return slugify(tokens[0])
    return 'unknown'


def _extract_business_identity(text: str, filename: str) -> dict[str, Any] | None:
    combined = f'{filename}\n{text}'
    normalized = combined.lower()
    if not any(signal in normalized for signal in ('dun & bradstreet', 'dun and bradstreet', 'd-u-n-s', 'duns number')):
        return None

    duns_match = re.search(r'd\s*-?u\s*-?n\s*-?s(?:®)?\s*(?:number)?\s*[:#]?\s*\*?([0-9]{9})\*?', combined, flags=re.IGNORECASE)
    company_match = re.search(
        r'd\s*-?u\s*-?n\s*-?s(?:®)?\s+number\s+for\s+\*?([^*\r\n]+?)\*?(?:[\r\n]|\.)',
        combined,
        flags=re.IGNORECASE,
    )

    company_name = None
    if company_match:
        company_name = company_match.group(1).strip(' *\t\r\n')

    return {
        'issuer': 'dun-and-bradstreet',
        'identifier_type': 'duns-number',
        'duns_number': duns_match.group(1) if duns_match else None,
        'company_name': company_name,
    }


def _detect_document_type(text: str, filename: str) -> str:
    combined = f'{filename}\n{text}'.lower()
    if _extract_business_identity(text, filename):
        return 'business-identity-record'
    if 'contract' in combined or 'agreement' in combined:
        return 'contract'
    if 'statement' in combined:
        return 'statement'
    if 'receipt' in combined:
        return 'receipt'
    if any(signal in combined for signal in ('purchase from google', "you've made a purchase", 'order number', 'registration fee')):
        return 'receipt'
    if 'invoice' in combined or 'bill' in combined:
        return 'invoice'
    if 'payout' in combined or 'deposit' in combined:
        return 'income-record'
    return 'document'


def _detect_finance_direction(text: str, filename: str, document_type: str) -> str | None:
    combined = f'{filename}\n{text}'.lower()
    income_signals = ('income', 'payout', 'deposit', 'payment received', 'revenue received')
    expense_signals = (
        'invoice',
        'receipt',
        'charged',
        'amount due',
        'renewal',
        'subscription',
        'hosting',
        'domain',
        'purchase',
        'order number',
        'registration fee',
        'developer registration fee',
    )
    if any(signal in combined for signal in income_signals) or document_type == 'income-record':
        return 'income'
    if any(signal in combined for signal in expense_signals) or document_type in {'invoice', 'receipt', 'statement'}:
        return 'expense'
    return None


def _detect_tax_category(text: str, filename: str, vendor_name: str) -> tuple[str, float, str]:
    combined = f'{filename}\n{text}\n{vendor_name}'.lower()
    for category, needles in EXPENSE_CATEGORY_RULES:
        if any(needle in combined for needle in needles):
            return category, 0.93, f'Keyword match for {category}'
    return 'general-business-expense', 0.6, 'Generic business-expense heuristic'


def classify_document(path: Path, text: str, source_channel: str) -> dict[str, Any]:
    fallback_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    document_date = _detect_document_date(text, path.name, fallback_dt=fallback_dt)
    amount = _detect_amount(text, path.name)
    vendor_name = _detect_vendor(text, path.name)
    document_type = _detect_document_type(text, path.name)
    finance_direction = _detect_finance_direction(text, path.name, document_type)
    business_identity = _extract_business_identity(text, path.name)
    tags = [document_type, vendor_name]
    if finance_direction:
        tags.append(f'finance:{finance_direction}')
    if business_identity:
        tags.append('business-identity')
        if business_identity.get('duns_number'):
            tags.append('duns-number')

    category = None
    confidence = None
    purpose = None
    if finance_direction == 'expense':
        category, confidence, purpose = _detect_tax_category(text, path.name, vendor_name)

    return {
        'document_type': document_type,
        'document_date': document_date,
        'amount': amount,
        'currency': 'USD' if amount is not None else None,
        'vendor_name': vendor_name,
        'client_name': None,
        'finance_direction': finance_direction,
        'tags': tags,
        'business_identity': business_identity,
        'tax': {
            'tax_relevance': 'deductible' if finance_direction == 'expense' else None,
            'tax_category_federal': category,
            'tax_category_nj': category,
            'deduction_confidence': confidence,
            'tax_year': int(document_date[:4]),
            'evidence_status': 'invoice-and-proof' if finance_direction == 'expense' else None,
            'business_purpose_note': purpose,
            'mixed_use_flag': False,
            'business_use_percent': 100.0 if finance_direction == 'expense' else None,
            'nj_adjustment_required': False,
            'nj_review_required': False,
        },
    }


def _document_destination_root(document_type: str, finance_direction: str | None, document_date: str) -> tuple[list[str], str]:
    year = document_date[:4]
    if finance_direction == 'expense':
        return ['01_DOCUMENTS', 'finance', 'expenses', year], year
    if finance_direction == 'income':
        return ['01_DOCUMENTS', 'finance', 'income', year], year
    if document_type == 'contract':
        return ['01_DOCUMENTS', 'legal', 'contracts', year], year
    if document_type == 'statement':
        return ['01_DOCUMENTS', 'finance', 'statements', year], year
    if document_type == 'business-identity-record':
        return ['01_DOCUMENTS', 'operations', 'business-identity', year], year
    return ['01_DOCUMENTS', 'operations', 'reference', year], year


def _stored_filename(path: Path, classification: dict[str, Any], source_channel: str) -> str:
    amount = classification.get('amount')
    amount_part = f"{amount:.2f}".replace('.', '-') if isinstance(amount, (int, float)) else 'na'
    return '__'.join(
        [
            classification['document_date'],
            slugify(classification['document_type']),
            slugify(classification['vendor_name']),
            amount_part,
            slugify(source_channel),
        ]
    ) + path.suffix.lower()


def _dedupe_destination(path: Path, sha256_value: str) -> Path:
    if not path.exists():
        return path
    existing_sha = _sha256_path(path)
    if existing_sha == sha256_value:
        return path
    return path.with_name(f'{path.stem}-{sha256_value[:8]}{path.suffix}')


def _document_row_by_id(con: sqlite3.Connection, document_id: str) -> dict[str, Any]:
    con.row_factory = sqlite3.Row
    row = con.execute('select * from documents where id = ?', (document_id,)).fetchone()
    return _row_to_dict(row) or {}


def _upsert_task_reminder(con: sqlite3.Connection, task_id: str, due_date: str, reminder_type: str = 'task-reminder') -> None:
    con.execute('delete from reminders where item_type = ? and item_id = ?', ('task', task_id))
    con.execute(
        'insert into reminders (item_type, item_id, reminder_type, due_date, status, notes, created_at) values (?, ?, ?, ?, ?, ?, ?)',
        ('task', task_id, reminder_type, due_date, 'pending', 'Task reminder', utc_now_iso()),
    )


def _append_task_event(
    con: sqlite3.Connection,
    *,
    task_id: str,
    event_type: str,
    summary: str,
    source_channel: str | None,
    source_account: str | None,
    source_message_id: str | None,
    source_thread_id: str | None,
    payload: dict[str, Any] | None = None,
) -> None:
    event_id = f'{task_id}-{event_type}-{slugify(summary)[:24]}-{utc_now_iso().replace(":", "").replace("+", "").replace("-", "")[-10:]}'
    con.execute(
        '''
        insert into task_events (
            id, task_id, event_type, source_channel, source_account, source_message_id,
            source_thread_id, summary, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            event_id,
            task_id,
            event_type,
            source_channel,
            source_account,
            source_message_id,
            source_thread_id,
            summary,
            json.dumps(payload or {}, sort_keys=True),
            utc_now_iso(),
        ),
    )


def process_document_file(
    *,
    businessos_root: str | Path,
    db_path: str | Path,
    input_path: str | Path,
    source_channel: str,
    source_account: str | None = None,
    source_reference: str | None = None,
    related_task_id: str | None = None,
    fallback_text: str | None = None,
    move_source: bool = False,
) -> dict[str, Any]:
    businessos_root = Path(businessos_root)
    db_path = Path(db_path)
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(str(input_path))

    sha256_value = _sha256_path(input_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ensure_business_ops_tables(con)

    existing = con.execute('select * from documents where sha256 = ?', (sha256_value,)).fetchone()
    if existing:
        document = _row_to_dict(existing) or {}
        if related_task_id:
            link_document_to_task(
                db_path=db_path,
                task_id=related_task_id,
                document_id=document['id'],
                source_channel=source_channel,
                source_account=source_account,
                source_message_id=source_reference,
            )
        if move_source and input_path.exists():
            input_path.unlink()
        con.close()
        return {'status': 'existing', 'document': document}

    text = extract_text_from_path(input_path, fallback_text=fallback_text)
    classification = classify_document(input_path, text, source_channel)
    stored_filename = _stored_filename(input_path, classification, source_channel)
    destination_parts, _ = _document_destination_root(
        classification['document_type'],
        classification['finance_direction'],
        classification['document_date'],
    )
    destination_dir = businessos_root.joinpath(*destination_parts)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_path = _dedupe_destination(destination_dir / stored_filename, sha256_value)

    document_id = f'doc-{classification["document_date"]}-{sha256_value[:8]}'
    if move_source:
        input_path.replace(destination_path)
        source_for_metadata = destination_path
    else:
        shutil.copy2(input_path, destination_path)
        source_for_metadata = input_path

    extracted_dir = businessos_root / '03_DATA' / 'extracted-text'
    extracted_dir.mkdir(parents=True, exist_ok=True)
    extracted_path = extracted_dir / f'{document_id}.txt'
    extracted_path.write_text(text, encoding='utf-8')

    metadata_dir = businessos_root / '03_DATA' / 'metadata'
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / f'{document_id}.json'

    metadata = {
        'document_id': document_id,
        'original_filename': source_for_metadata.name if move_source else input_path.name,
        'stored_filename': destination_path.name,
        'document_type': classification['document_type'],
        'status': 'recorded',
        'date': classification['document_date'],
        'due_date': None,
        'amount': classification['amount'],
        'currency': classification['currency'],
        'vendor': classification['vendor_name'],
        'service': None,
        'website': None,
        'email_account': None,
        'source_channel': source_channel,
        'source_account': source_account,
        'source_reference': source_reference,
        'finance_direction': classification['finance_direction'],
        'tags': classification['tags'],
        'text_path': str(extracted_path.relative_to(businessos_root)),
        'dropbox_path': None,
        'local_path': str(destination_path),
        'sha256': sha256_value,
        'linked_entities': [],
        'business_identity': classification['business_identity'],
        'notes': 'Auto-classified from BusinessOS intake',
        'tax': classification['tax'],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')

    con.execute(
        '''
        insert into documents (
            id, original_filename, stored_filename, document_type, status, document_date, due_date,
            paid_date, amount, currency, vendor_name, client_name, service_id, website_id, domain_id,
            email_account_id, source_channel, local_path, dropbox_path, extracted_text_path, sha256,
            tags_json, review_state, notes, created_at, updated_at, finance_direction, source_account,
            source_reference
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            document_id,
            input_path.name,
            destination_path.name,
            classification['document_type'],
            'recorded',
            classification['document_date'],
            None,
            None,
            classification['amount'],
            classification['currency'],
            classification['vendor_name'],
            None,
            None,
            None,
            None,
            None,
            source_channel,
            str(destination_path),
            None,
            str(extracted_path),
            sha256_value,
            json.dumps(classification['tags']),
            'auto-recorded',
            'Auto-classified from inbox',
            utc_now_iso(),
            utc_now_iso(),
            classification['finance_direction'],
            source_account,
            source_reference,
        ),
    )

    if classification['finance_direction'] == 'expense':
        tax = classification['tax']
        con.execute(
            '''
            insert into expense_tax_treatment (
                document_id, tax_relevance, tax_category_federal, tax_category_nj, deduction_confidence,
                tax_year, schedule_or_return_section, evidence_status, business_purpose_note,
                mixed_use_flag, business_use_percent, nj_adjustment_required, nj_review_required,
                reviewed_by_human, review_notes, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                document_id,
                tax['tax_relevance'],
                tax['tax_category_federal'],
                tax['tax_category_nj'],
                tax['deduction_confidence'],
                tax['tax_year'],
                None,
                tax['evidence_status'],
                tax['business_purpose_note'],
                1 if tax['mixed_use_flag'] else 0,
                tax['business_use_percent'],
                1 if tax['nj_adjustment_required'] else 0,
                1 if tax['nj_review_required'] else 0,
                0,
                None,
                utc_now_iso(),
                utc_now_iso(),
            ),
        )

    con.execute(
        'insert into processing_log (source_path, document_id, event_type, message, created_at) values (?, ?, ?, ?, ?)',
        (str(input_path), document_id, 'document_processed', f'Processed via {source_channel}', utc_now_iso()),
    )
    con.commit()
    con.close()

    document = {
        'id': document_id,
        'original_filename': input_path.name,
        'stored_filename': destination_path.name,
        'document_type': classification['document_type'],
        'document_date': classification['document_date'],
        'amount': classification['amount'],
        'currency': classification['currency'],
        'vendor_name': classification['vendor_name'],
        'finance_direction': classification['finance_direction'],
        'local_path': str(destination_path),
        'metadata_path': str(metadata_path),
        'extracted_text_path': str(extracted_path),
        'source_channel': source_channel,
        'source_account': source_account,
        'source_reference': source_reference,
    }

    if related_task_id:
        link_document_to_task(
            db_path=db_path,
            task_id=related_task_id,
            document_id=document_id,
            source_channel=source_channel,
            source_account=source_account,
            source_message_id=source_reference,
        )

    return {'status': 'processed', 'document': document}


def process_document_inbox(*, businessos_root: str | Path, db_path: str | Path) -> dict[str, Any]:
    businessos_root = Path(businessos_root)
    db_path = Path(db_path)
    inbox_dir = businessos_root / '00_INBOX' / 'manual-drop'
    inbox_dir.mkdir(parents=True, exist_ok=True)

    processed: list[dict[str, Any]] = []
    for path in sorted(p for p in inbox_dir.rglob('*') if p.is_file()):
        result = process_document_file(
            businessos_root=businessos_root,
            db_path=db_path,
            input_path=path,
            source_channel='manual-drop',
            move_source=True,
        )
        processed.append(result['document'])
    return {'processed_count': len(processed), 'documents': processed, 'status': 'completed'}


def _next_task_id(con: sqlite3.Connection) -> str:
    count = con.execute('select count(*) from task_items').fetchone()[0]
    return f'task-{count + 1:04d}'


def create_task(
    *,
    db_path: str | Path,
    title: str,
    description: str | None,
    source_channel: str,
    author_handle: str | None,
    priority: str = 'medium',
    due_at: str | None = None,
    reminder_at: str | None = None,
    source_account: str | None = None,
    source_message_id: str | None = None,
    source_thread_id: str | None = None,
    app_id: str | None = None,
) -> dict[str, Any]:
    db_path = Path(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ensure_business_ops_tables(con)
    task_id = _next_task_id(con)
    now = utc_now_iso()
    con.execute(
        '''
        insert into task_items (
            id, title, description, status, priority, app_id, source_channel, source_account,
            source_message_id, source_thread_id, author_handle, due_at, reminder_at,
            tags_json, created_at, updated_at, latest_comment_at
        ) values (?, ?, ?, 'created', ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?)
        ''',
        (
            task_id,
            title,
            description,
            priority,
            app_id,
            source_channel,
            source_account,
            source_message_id,
            source_thread_id,
            author_handle,
            due_at,
            reminder_at,
            now,
            now,
            None,
        ),
    )
    if reminder_at:
        _upsert_task_reminder(con, task_id, reminder_at)
    elif due_at:
        _upsert_task_reminder(con, task_id, due_at, reminder_type='task-due-date')
    _append_task_event(
        con,
        task_id=task_id,
        event_type='task_created',
        summary=title,
        source_channel=source_channel,
        source_account=source_account,
        source_message_id=source_message_id,
        source_thread_id=source_thread_id,
        payload={'description': description, 'priority': priority, 'due_at': due_at, 'reminder_at': reminder_at},
    )
    con.commit()
    task = _documentless_task_row(con, task_id)
    con.close()
    return task


def _documentless_task_row(con: sqlite3.Connection, task_id: str) -> dict[str, Any]:
    row = con.execute('select * from task_items where id = ?', (task_id,)).fetchone()
    return _row_to_dict(row) or {}


def update_task_status(
    *,
    db_path: str | Path,
    task_id: str,
    status: str,
    source_channel: str,
    author_handle: str | None,
    source_account: str | None = None,
    source_message_id: str | None = None,
    source_thread_id: str | None = None,
) -> dict[str, Any]:
    db_path = Path(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ensure_business_ops_tables(con)
    con.execute('update task_items set status = ?, updated_at = ? where id = ?', (status, utc_now_iso(), task_id))
    _append_task_event(
        con,
        task_id=task_id,
        event_type='status_changed',
        summary=f'{author_handle or "system"} -> {status}',
        source_channel=source_channel,
        source_account=source_account,
        source_message_id=source_message_id,
        source_thread_id=source_thread_id,
        payload={'status': status},
    )
    con.commit()
    task = _documentless_task_row(con, task_id)
    con.close()
    return task


def add_task_comment(
    *,
    db_path: str | Path,
    task_id: str,
    body: str,
    source_channel: str,
    author_handle: str | None,
    source_account: str | None = None,
    source_message_id: str | None = None,
) -> dict[str, Any]:
    db_path = Path(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ensure_business_ops_tables(con)
    comment_id = f'{task_id}-comment-{slugify(body)[:18]}-{utc_now_iso().replace(":", "").replace("+", "").replace("-", "")[-10:]}'
    now = utc_now_iso()
    con.execute(
        '''
        insert into task_comments (
            id, task_id, author_handle, source_channel, source_account, source_message_id, body, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (comment_id, task_id, author_handle, source_channel, source_account, source_message_id, body, now),
    )
    con.execute('update task_items set updated_at = ?, latest_comment_at = ? where id = ?', (now, now, task_id))
    _append_task_event(
        con,
        task_id=task_id,
        event_type='comment_added',
        summary=body,
        source_channel=source_channel,
        source_account=source_account,
        source_message_id=source_message_id,
        source_thread_id=None,
        payload={'author_handle': author_handle},
    )
    con.commit()
    row = con.execute('select * from task_comments where id = ?', (comment_id,)).fetchone()
    comment = _row_to_dict(row) or {}
    con.close()
    return comment


def record_daily_priority(
    *,
    db_path: str | Path,
    title: str | None,
    source_channel: str,
    author_handle: str | None,
    focus_date: str | None = None,
    task_id: str | None = None,
    notes: str | None = None,
    source_account: str | None = None,
    source_message_id: str | None = None,
    source_thread_id: str | None = None,
) -> dict[str, Any]:
    db_path = Path(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ensure_business_ops_tables(con)
    now = utc_now_iso()
    effective_focus_date = focus_date or now.split('T', 1)[0]

    if task_id:
        task_row = con.execute('select title from task_items where id = ?', (task_id,)).fetchone()
        if task_row is None:
            con.close()
            raise KeyError(task_id)
        title = title or str(task_row['title'] or '').strip()

    if not title:
        con.close()
        raise ValueError('Daily priority requires a title or task_id')

    priority_id = f"focus-{effective_focus_date}-{slugify(task_id or title)[:24]}-{slugify(source_message_id or now)[-10:]}"
    con.execute(
        '''
        insert into daily_priorities (
            id, focus_date, task_id, title, notes, status, source_channel, source_account,
            source_message_id, source_thread_id, author_handle, created_at, updated_at
        ) values (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
        on conflict(id) do update set
            focus_date = excluded.focus_date,
            task_id = excluded.task_id,
            title = excluded.title,
            notes = excluded.notes,
            status = 'active',
            source_channel = excluded.source_channel,
            source_account = excluded.source_account,
            source_message_id = excluded.source_message_id,
            source_thread_id = excluded.source_thread_id,
            author_handle = excluded.author_handle,
            updated_at = excluded.updated_at
        ''',
        (
            priority_id,
            effective_focus_date,
            task_id,
            title,
            notes,
            source_channel,
            source_account,
            source_message_id,
            source_thread_id,
            author_handle,
            now,
            now,
        ),
    )
    if task_id:
        _append_task_event(
            con,
            task_id=task_id,
            event_type='daily_priority_set',
            summary=title,
            source_channel=source_channel,
            source_account=source_account,
            source_message_id=source_message_id,
            source_thread_id=source_thread_id,
            payload={'focus_date': effective_focus_date, 'notes': notes},
        )
    con.commit()
    row = con.execute('select * from daily_priorities where id = ?', (priority_id,)).fetchone()
    result = _row_to_dict(row) or {}
    con.close()
    return result


def suggested_task_payload(
    *,
    subject: str | None,
    summary: str | None,
    category: str | None,
    assigned_queue: str | None,
    task_operation: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if task_operation:
        return None
    category_value = str(category or '').strip()
    queue_value = str(assigned_queue or '').strip()
    subject_value = str(subject or '').strip() or str(summary or '').strip() or 'New item'

    if category_value == 'internal-test' or queue_value == 'operator-control':
        return None
    if category_value == 'billing' or queue_value == 'billing-support':
        title = f'Respond to billing issue: {subject_value}'
        rationale = 'Billing-related intake was captured and likely needs follow-up.'
    elif category_value == 'business-expense-record' or queue_value == 'finance-review':
        title = f'Review business expense: {subject_value}'
        rationale = 'Expense intake was captured and may need bookkeeping or tax follow-up.'
    elif category_value == 'business-identity-record':
        title = f'Review business identity record: {subject_value}'
        rationale = 'Business identity/compliance intake was captured and may need follow-up.'
    elif 'legal' in category_value or queue_value == 'legal-review':
        title = f'Review legal item: {subject_value}'
        rationale = 'Legal intake was captured and likely needs review.'
    elif 'privacy' in category_value or queue_value == 'privacy-review':
        title = f'Review privacy request: {subject_value}'
        rationale = 'Privacy-related intake was captured and likely needs follow-up.'
    else:
        title = f'Review support request: {subject_value}'
        rationale = 'Non-task intake was captured and may need a human follow-up task.'

    return {
        'title': title,
        'rationale': rationale,
        'category': category_value or 'support-request',
        'assigned_queue': queue_value or 'general',
        'status': 'suggested',
    }


def record_task_suggestion(
    *,
    db_path: str | Path,
    source_channel: str,
    source_account: str | None,
    source_message_id: str | None,
    source_thread_id: str | None,
    message_id: str | None,
    subject: str | None,
    summary: str | None,
    category: str | None,
    assigned_queue: str | None,
    task_operation: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    suggestion = suggested_task_payload(
        subject=subject,
        summary=summary,
        category=category,
        assigned_queue=assigned_queue,
        task_operation=task_operation,
    )
    if not suggestion:
        return None

    db_path = Path(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ensure_business_ops_tables(con)
    now = utc_now_iso()
    identifier = message_id or source_message_id or suggestion['title']
    suggestion_id = f"suggestion-{slugify(source_channel)}-{slugify(identifier)[:40]}"
    con.execute(
        '''
        insert into task_suggestions (
            id, source_channel, source_account, source_message_id, source_thread_id, message_id,
            task_id, title, rationale, category, assigned_queue, status, created_at, updated_at
        ) values (?, ?, ?, ?, ?, ?, null, ?, ?, ?, ?, ?, ?, ?)
        on conflict(id) do update set
            source_account = excluded.source_account,
            source_message_id = excluded.source_message_id,
            source_thread_id = excluded.source_thread_id,
            message_id = excluded.message_id,
            title = excluded.title,
            rationale = excluded.rationale,
            category = excluded.category,
            assigned_queue = excluded.assigned_queue,
            status = excluded.status,
            updated_at = excluded.updated_at
        ''',
        (
            suggestion_id,
            source_channel,
            source_account,
            source_message_id,
            source_thread_id,
            message_id,
            suggestion['title'],
            suggestion['rationale'],
            suggestion['category'],
            suggestion['assigned_queue'],
            suggestion['status'],
            now,
            now,
        ),
    )
    con.commit()
    row = con.execute('select * from task_suggestions where id = ?', (suggestion_id,)).fetchone()
    result = _row_to_dict(row) or {}
    con.close()
    return result


def link_document_to_task(
    *,
    db_path: str | Path,
    task_id: str,
    document_id: str,
    relationship_type: str = 'reference',
    source_channel: str | None = None,
    source_account: str | None = None,
    source_message_id: str | None = None,
) -> None:
    db_path = Path(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ensure_business_ops_tables(con)
    con.execute(
        '''
        insert into task_documents (task_id, document_id, relationship_type, linked_at)
        values (?, ?, ?, ?)
        on conflict(task_id, document_id) do update set
            relationship_type = excluded.relationship_type,
            linked_at = excluded.linked_at
        ''',
        (task_id, document_id, relationship_type, utc_now_iso()),
    )
    document = con.execute('select stored_filename from documents where id = ?', (document_id,)).fetchone()
    _append_task_event(
        con,
        task_id=task_id,
        event_type='document_linked',
        summary=document['stored_filename'] if document else document_id,
        source_channel=source_channel,
        source_account=source_account,
        source_message_id=source_message_id,
        source_thread_id=None,
        payload={'document_id': document_id, 'relationship_type': relationship_type},
    )
    con.commit()
    con.close()


def message_looks_like_document(subject: str | None, text: str | None) -> bool:
    combined = f'{subject or ""}\n{text or ""}'.lower()
    return any(keyword in combined for keyword in DOCUMENT_KEYWORDS)


def parse_task_command(*, subject: str | None = None, text: str | None = None) -> dict[str, Any] | None:
    subject = (subject or '').strip()
    text = (text or '').strip()
    reminder_match = re.search(r'(?im)^reminder:\s*(.+)$', text)
    due_match = re.search(r'(?im)^due:\s*(.+)$', text)
    reminder_at = reminder_match.group(1).strip() if reminder_match else None
    due_at = due_match.group(1).strip() if due_match else None

    if subject.lower().startswith('todo:') or subject.lower().startswith('task:'):
        title = subject.split(':', 1)[1].strip()
        return {'action': 'create', 'title': title, 'description': text, 'reminder_at': reminder_at, 'due_at': due_at}
    if subject.lower().startswith('focus:') or subject.lower().startswith('priority:'):
        payload = subject.split(':', 1)[1].strip()
        task_match = re.match(r'(?i)^(task-\d+)\b(?:\s*[:\-]\s*|\s+)?(.*)$', payload)
        if task_match:
            task_id, notes = task_match.groups()
            return {'action': 'focus', 'task_id': task_id.lower(), 'notes': notes.strip() or text or None}
        return {'action': 'focus', 'title': payload, 'notes': text or None}

    first_line = text.splitlines()[0].strip() if text else ''
    match = re.match(r'(?i)^(?:/todo|todo:|task:|#todo|#newtask)\s*(.+)$', first_line)
    if match:
        title = match.group(1).strip()
        description_lines = text.splitlines()[1:]
        description = '\n'.join(description_lines).strip() or None
        return {'action': 'create', 'title': title, 'description': description, 'reminder_at': reminder_at, 'due_at': due_at}

    focus_match = re.match(r'(?i)^(?:/focus|focus:|#focus|/priority|priority:)\s*(.+)$', first_line)
    if focus_match:
        payload = focus_match.group(1).strip()
        details = '\n'.join(text.splitlines()[1:]).strip() or None
        task_match = re.match(r'(?i)^(task-\d+)\b(?:\s*[:\-]\s*|\s+)?(.*)$', payload)
        if task_match:
            task_id, notes = task_match.groups()
            return {'action': 'focus', 'task_id': task_id.lower(), 'notes': notes.strip() or details}
        return {'action': 'focus', 'title': payload, 'notes': details}

    update_match = re.match(r'(?i)^(?:/task|task)\s+([a-z0-9\-]+)\s+(start|in-progress|complete|completed|done|comment|note)\b[: ]?(.*)$', first_line)
    if update_match:
        task_id, verb, remainder = update_match.groups()
        verb = verb.lower()
        if verb in {'start', 'in-progress'}:
            return {'action': 'status', 'task_id': task_id, 'status': 'in_progress'}
        if verb in {'complete', 'completed', 'done'}:
            return {'action': 'status', 'task_id': task_id, 'status': 'completed'}
        return {'action': 'comment', 'task_id': task_id, 'body': remainder.strip() or '\n'.join(text.splitlines()[1:]).strip()}
    return None


def apply_task_command(
    *,
    db_path: str | Path,
    command: dict[str, Any],
    source_channel: str,
    source_account: str | None,
    source_message_id: str | None,
    source_thread_id: str | None,
    author_handle: str | None,
    app_id: str | None,
    linked_document_ids: list[str] | None = None,
) -> dict[str, Any]:
    linked_document_ids = linked_document_ids or []
    action = command.get('action')
    if action == 'create':
        task = create_task(
            db_path=db_path,
            title=command['title'],
            description=command.get('description'),
            source_channel=source_channel,
            source_account=source_account,
            source_message_id=source_message_id,
            source_thread_id=source_thread_id,
            author_handle=author_handle,
            due_at=command.get('due_at'),
            reminder_at=command.get('reminder_at'),
            app_id=app_id,
        )
        for document_id in linked_document_ids:
            link_document_to_task(
                db_path=db_path,
                task_id=task['id'],
                document_id=document_id,
                source_channel=source_channel,
                source_account=source_account,
                source_message_id=source_message_id,
            )
        return {'task_id': task['id'], 'action': 'create'}
    if action == 'status':
        task = update_task_status(
            db_path=db_path,
            task_id=command['task_id'],
            status=command['status'],
            source_channel=source_channel,
            source_account=source_account,
            source_message_id=source_message_id,
            source_thread_id=source_thread_id,
            author_handle=author_handle,
        )
        return {'task_id': task['id'], 'action': 'status'}
    if action == 'comment':
        add_task_comment(
            db_path=db_path,
            task_id=command['task_id'],
            body=command['body'],
            source_channel=source_channel,
            source_account=source_account,
            source_message_id=source_message_id,
            author_handle=author_handle,
        )
        return {'task_id': command['task_id'], 'action': 'comment'}
    if action == 'focus':
        priority = record_daily_priority(
            db_path=db_path,
            title=command.get('title'),
            task_id=command.get('task_id'),
            notes=command.get('notes'),
            source_channel=source_channel,
            source_account=source_account,
            source_message_id=source_message_id,
            source_thread_id=source_thread_id,
            author_handle=author_handle,
        )
        return {'task_id': priority.get('task_id'), 'priority_id': priority.get('id'), 'action': 'focus'}
    raise ValueError(f'Unsupported task command: {command!r}')


def render_task_transcript(*, db_path: str | Path, task_id: str) -> str:
    db_path = Path(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ensure_business_ops_tables(con)
    task = con.execute('select * from task_items where id = ?', (task_id,)).fetchone()
    if task is None:
        raise KeyError(task_id)
    links = con.execute(
        '''
        select td.relationship_type, d.id, d.stored_filename
        from task_documents td
        join documents d on d.id = td.document_id
        where td.task_id = ?
        order by td.linked_at asc
        ''',
        (task_id,),
    ).fetchall()
    events = con.execute('select * from task_events where task_id = ? order by created_at asc', (task_id,)).fetchall()
    con.close()

    lines = [
        f'# Task Transcript: {task["id"]}',
        '',
        f'Title: {task["title"]}',
        f'Status: {task["status"]}',
        f'Priority: {task["priority"]}',
        f'Created: {task["created_at"]}',
    ]
    if task['description']:
        lines.extend(['', 'Description:', task['description']])
    if task['due_at'] or task['reminder_at']:
        lines.extend(['', f'Due: {task["due_at"] or ""}', f'Reminder: {task["reminder_at"] or ""}'])
    if links:
        lines.extend(['', '## Linked documents'])
        for link in links:
            lines.append(f'- {link["id"]} | {link["relationship_type"]} | {link["stored_filename"]}')
    lines.extend(['', '## Activity'])
    for event in events:
        lines.append(f'- {event["created_at"]} | {event["event_type"]} | {event["summary"]}')
    return '\n'.join(lines) + '\n'


def write_task_transcript_report(*, businessos_root: str | Path, db_path: str | Path, task_id: str) -> Path:
    businessos_root = Path(businessos_root)
    output_dir = businessos_root / '05_REPORTS' / 'tasks' / 'transcripts'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f'{task_id}.md'
    output_path.write_text(render_task_transcript(db_path=db_path, task_id=task_id), encoding='utf-8')
    return output_path


def build_task_dashboard_report(*, businessos_root: str | Path, db_path: str | Path) -> Path:
    businessos_root = Path(businessos_root)
    db_path = Path(db_path)
    output_dir = businessos_root / '05_REPORTS' / 'tasks'
    output_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ensure_business_ops_tables(con)
    tasks = con.execute(
        '''
        select id, title, status, priority, due_at, reminder_at, updated_at
        from task_items
        order by
            case when status in ('created', 'in_progress') then 0 else 1 end,
            coalesce(reminder_at, due_at, updated_at) asc,
            created_at asc
        '''
    ).fetchall()
    reminders = con.execute(
        "select item_id, due_date, status from reminders where item_type = 'task' order by due_date asc"
    ).fetchall()
    today = datetime.now(timezone.utc).date().isoformat()
    priorities = con.execute(
        '''
        select focus_date, task_id, title, notes, status
        from daily_priorities
        where focus_date = ? and status = 'active'
        order by created_at asc, id asc
        ''',
        (today,),
    ).fetchall()
    suggestions = con.execute(
        '''
        select title, rationale, category, assigned_queue, status
        from task_suggestions
        where status = 'suggested'
        order by created_at desc, id desc
        limit 10
        '''
    ).fetchall()
    task_ids = [row['id'] for row in tasks]
    con.close()

    for task_id in task_ids:
        write_task_transcript_report(businessos_root=businessos_root, db_path=db_path, task_id=task_id)

    output_path = output_dir / f'{today}-task-dashboard.md'
    lines = ['# Task Dashboard', '', f'Generated: {utc_now_iso()}', '']
    lines.extend(['## Open tasks', '', '| Task ID | Status | Priority | Reminder | Due | Title |', '|---|---|---|---|---|---|'])
    for row in tasks:
        lines.append(
            f"| {row['id']} | {row['status']} | {row['priority']} | {row['reminder_at'] or ''} | {row['due_at'] or ''} | {row['title']} |"
        )
    if priorities:
        lines.extend(['', "## Today's priorities", '', '| Task ID | Title | Notes |', '|---|---|---|'])
        for row in priorities:
            lines.append(f"| {row['task_id'] or ''} | {row['title']} | {row['notes'] or ''} |")
    else:
        lines.extend(['', "## Today's priorities", '', '- No priorities recorded for today yet.'])
    if suggestions:
        lines.extend(['', '## Suggested follow-up items', '', '| Category | Queue | Title | Rationale |', '|---|---|---|---|'])
        for row in suggestions:
            lines.append(
                f"| {row['category'] or ''} | {row['assigned_queue'] or ''} | {row['title']} | {row['rationale'] or ''} |"
            )
    else:
        lines.extend(['', '## Suggested follow-up items', '', '- No suggested follow-up items currently pending.'])
    if reminders:
        lines.extend(['', '## Pending reminders', '', '| Task ID | Reminder at | Status |', '|---|---|---|'])
        for row in reminders:
            lines.append(f"| {row['item_id']} | {row['due_date']} | {row['status']} |")
    output_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return output_path


def build_finance_reports(*, businessos_root: str | Path, db_path: str | Path) -> dict[str, Path]:
    businessos_root = Path(businessos_root)
    db_path = Path(db_path)
    monthly_dir = businessos_root / '05_REPORTS' / 'monthly'
    monthly_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ensure_business_ops_tables(con)
    docs = con.execute(
        '''
        select d.id, d.document_date, d.vendor_name, d.amount, d.finance_direction, d.document_type,
               d.local_path, ett.tax_category_federal, ett.tax_relevance
        from documents d
        left join expense_tax_treatment ett on ett.document_id = d.id
        order by d.document_date asc, d.id asc
        '''
    ).fetchall()
    con.close()

    def inferred_direction(row: sqlite3.Row) -> str | None:
        if row['finance_direction']:
            return row['finance_direction']
        local_path = (row['local_path'] or '').lower()
        if row['tax_relevance'] or '/expenses/' in local_path:
            return 'expense'
        if '/income/' in local_path:
            return 'income'
        return None

    today = datetime.now(timezone.utc).date().isoformat()
    finance_summary_path = monthly_dir / f'{today}-finance-summary.md'
    deductible_summary_path = monthly_dir / f'{today}-deductible-summary.md'

    income_total = sum(float(row['amount'] or 0) for row in docs if inferred_direction(row) == 'income')
    expense_total = sum(float(row['amount'] or 0) for row in docs if inferred_direction(row) == 'expense')

    finance_lines = [
        '# Finance Summary',
        '',
        f'Generated: {today}',
        '',
        f'- Total income: ${income_total:.2f}',
        f'- Total expenses: ${expense_total:.2f}',
        '',
        '| Date | Direction | Type | Vendor | Amount | Tax category |',
        '|---|---|---|---|---:|---|',
    ]
    for row in docs:
        amount = float(row['amount'] or 0)
        direction = inferred_direction(row)
        finance_lines.append(
            f"| {row['document_date'] or ''} | {direction or ''} | {row['document_type'] or ''} | {row['vendor_name'] or ''} | ${amount:.2f} | {row['tax_category_federal'] or ''} |"
        )
    finance_summary_path.write_text('\n'.join(finance_lines) + '\n', encoding='utf-8')

    category_totals: dict[str, float] = {}
    for row in docs:
        if inferred_direction(row) != 'expense':
            continue
        category = row['tax_category_federal'] or 'uncategorized'
        category_totals[category] = category_totals.get(category, 0.0) + float(row['amount'] or 0)
    deductible_lines = [
        '# Deductible Expense Summary',
        '',
        f'Generated: {today}',
        '',
        '| Federal category | Items | Estimated deductible total |',
        '|---|---:|---:|',
    ]
    for category, total in sorted(category_totals.items()):
        items = sum(1 for row in docs if inferred_direction(row) == 'expense' and (row['tax_category_federal'] or 'uncategorized') == category)
        deductible_lines.append(f'| {category} | {items} | ${total:.2f} |')
    deductible_summary_path.write_text('\n'.join(deductible_lines) + '\n', encoding='utf-8')

    return {
        'finance_summary_path': finance_summary_path,
        'deductible_summary_path': deductible_summary_path,
    }


def save_email_attachments(message: Any, attachments_dir: str | Path) -> list[dict[str, Any]]:
    attachments_dir = Path(attachments_dir)
    attachments_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for part in message.walk():
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True) or b''
        safe_name = slugify(Path(filename).stem) + Path(filename).suffix.lower()
        saved_path = attachments_dir / safe_name
        if saved_path.exists() and saved_path.read_bytes() != payload:
            saved_path = attachments_dir / f'{saved_path.stem}-{hashlib.sha256(payload).hexdigest()[:8]}{saved_path.suffix}'
        saved_path.write_bytes(payload)
        manifest.append(
            {
                'filename': filename,
                'content_type': part.get_content_type(),
                'size_bytes': len(payload),
                'saved_path': str(saved_path),
            }
        )
    return manifest
