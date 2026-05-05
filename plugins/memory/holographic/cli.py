"""CLI commands for the holographic memory provider.

Exposes:
  hermes holographic status
  hermes holographic reindex
  hermes holographic inspect <fact_id>
  hermes holographic query-debug <query>
"""

from __future__ import annotations

import json
from pathlib import Path

from hermes_constants import get_hermes_home

from .embeddings import build_embedding_provider
from .ingestion import drain_understanding_ingest, ingest_settings
from .retrieval import FactRetriever
from .store import MemoryStore


def _load_plugin_config() -> dict:
    config_path = get_hermes_home() / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml

        with open(config_path, encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return payload.get("plugins", {}).get("hermes-memory-store", {}) or {}
    except Exception:
        return {}


def _open_store() -> MemoryStore:
    cfg = _load_plugin_config()
    hermes_home = str(get_hermes_home())
    db_path = cfg.get("db_path", hermes_home + "/memory_store.db")
    if isinstance(db_path, str):
        db_path = db_path.replace("$HERMES_HOME", hermes_home)
        db_path = db_path.replace("${HERMES_HOME}", hermes_home)

    return MemoryStore(
        db_path=Path(db_path).expanduser(),
        default_trust=float(cfg.get("default_trust", 0.5)),
        hrr_dim=int(cfg.get("hrr_dim", 1024)),
        embedding_provider=build_embedding_provider(cfg),
        link_threshold=float(cfg.get("link_threshold", 0.36)),
    )


def cmd_status(_args) -> None:
    cfg = _load_plugin_config()
    settings = ingest_settings(cfg)
    store = _open_store()
    try:
        status = store.index_status()
    finally:
        store.close()

    print("\nHolographic memory index status\n" + "-" * 40)
    print(f"  Database:            {status['db_path']}")
    print(f"  Facts:               {status['facts']}")
    print(f"  Enriched facts:      {status['enriched_facts']}")
    print(f"  HRR-ready facts:     {status['hrr_ready_facts']}")
    print(f"  Embedded facts:      {status['embedded_facts']}")
    print(f"  Related links:       {status['links']}")
    print(f"  Embedding provider:  {status['embedding_provider'] or 'none'}")
    print(f"  Embedding available: {'yes' if status['embedding_available'] else 'no'}")
    print(f"  Embedding model:     {status['embedding_model'] or '-'}")
    print(f"  Link threshold:      {status['link_threshold']}")
    print(f"  Latest update:       {status['latest_update'] or '-'}")
    print(f"  Deferred ingest:     {'on' if settings['deferred_ingest'] else 'off'}")
    print(f"  Turn understanding:  {'on' if settings['turn_understanding'] else 'off'}")
    print(f"  Ingest batch size:   {settings['ingest_batch_size']}")
    print(f"  Max pending queue:   {settings['ingest_max_pending']}")
    print(f"  Pending ingest:      {status['pending_ingest_items']}")
    print(f"  Failed ingest:       {status['failed_ingest_items']}")
    print(f"  Processing ingest:   {status['processing_ingest_items']}")
    print(f"  Oldest pending:      {status['oldest_pending_ingest'] or '-'}")
    print(f"  Last ingest success: {status['last_ingest_success'] or '-'}")
    print(f"  Last ingest error:   {status['last_ingest_error'] or '-'}")
    print(f"  Queue rejects:       {status['ingest_enqueue_rejected']}")
    print(f"  Reindex status:      {status['reindex_status']}")
    print(f"  Reindex started:     {status['reindex_started_at'] or '-'}")
    print(f"  Reindex completed:   {status['reindex_completed_at'] or '-'}")
    print(f"  Reindex error:       {status['reindex_error'] or '-'}")
    print()


def cmd_reindex(args) -> None:
    cfg = _load_plugin_config()
    store = _open_store()
    try:
        if args.drain_pending:
            settings = ingest_settings(cfg)
            drain_understanding_ingest(
                store,
                cfg,
                limit=settings["ingest_max_pending"],
                reason="cli_reindex",
            )
        result = store.rebuild_understanding_index(
            include_embeddings=bool(args.include_embeddings),
            refresh_links=bool(args.refresh_links),
        )
        status = store.index_status()
    finally:
        store.close()

    print("\nHolographic memory reindex\n" + "-" * 40)
    print(f"  Facts reindexed:   {result['facts_reindexed']}")
    print(f"  Embedded facts:    {result['embedded_facts']}")
    print(f"  Links rebuilt:     {'yes' if result['links_rebuilt'] else 'no'}")
    print(f"  Embedding provider:{' '}{result['embedding_provider'] or 'none'}")
    print(f"  Started at:        {result['reindex_started_at']}")
    print(f"  Completed at:      {result['reindex_completed_at']}")
    print(f"  Pending ingest:    {status['pending_ingest_items']}")
    print(f"  Failed ingest:     {status['failed_ingest_items']}")
    print()


def cmd_inspect(args) -> None:
    store = _open_store()
    try:
        fact = store.get_fact(int(args.fact_id))
    finally:
        store.close()

    if not fact:
        print(f"\nFact {args.fact_id} not found.\n")
        return

    metadata = fact.get("metadata", {})
    print(f"\nHolographic memory inspect: {fact['fact_id']}\n" + "-" * 52)
    print(f"  Content:            {fact['content']}")
    print(f"  Category:           {fact.get('category', '-')}")
    print(f"  Intent:             {fact.get('intent_type', '-')}")
    print(f"  Source channel:     {fact.get('source_channel', '-')}")
    print(f"  Trust:              {fact.get('trust_score', 0.0):.2f}")
    print(f"  Salience:           {fact.get('salience_score', 0.0):.2f}")
    print(f"  Source confidence:  {fact.get('source_confidence', 0.0):.2f}")
    print(f"  Updated at:         {fact.get('updated_at', '-')}")
    print(f"  Entities:           {', '.join(metadata.get('entities', [])) or '-'}")
    print(f"  Entity keys:        {', '.join(metadata.get('entity_keys', [])) or '-'}")
    print(f"  People:             {', '.join(metadata.get('people', [])) or '-'}")
    print(f"  Person keys:        {', '.join(metadata.get('person_keys', [])) or '-'}")
    print(f"  Projects:           {', '.join(metadata.get('projects', [])) or '-'}")
    print(f"  Project keys:       {', '.join(metadata.get('project_keys', [])) or '-'}")
    print(f"  Topics:             {', '.join(metadata.get('topics', [])) or '-'}")
    print(f"  Topic keys:         {', '.join(metadata.get('topic_keys', [])) or '-'}")
    print(f"  Cluster keys:       {', '.join(metadata.get('cluster_keys', [])) or '-'}")
    print(f"  Dates:              {', '.join(metadata.get('dates', [])) or '-'}")
    print(f"  Times:              {', '.join(metadata.get('times', [])) or '-'}")
    print(f"  Locations:          {', '.join(metadata.get('locations', [])) or '-'}")

    links = fact.get("links", [])
    print("  Related memories:")
    if not links:
        print("    - none")
    else:
        for link in links[:10]:
            print(
                f"    - #{link['linked_fact_id']} [{link['link_type']}] "
                f"{link['strength']:.2f} :: {link['reason']}"
            )
    print()


def cmd_query_debug(args) -> None:
    cfg = _load_plugin_config()
    store = _open_store()
    retriever = FactRetriever(
        store=store,
        temporal_decay_half_life=int(cfg.get("temporal_decay_half_life", 45)),
        hrr_dim=int(cfg.get("hrr_dim", 1024)),
        semantic_weight=float(cfg.get("rank_semantic_weight", 0.35)),
        keyword_weight=float(cfg.get("rank_keyword_weight", 0.25)),
        recency_weight=float(cfg.get("rank_recency_weight", 0.15)),
        salience_weight=float(cfg.get("rank_salience_weight", 0.15)),
        confidence_weight=float(cfg.get("rank_confidence_weight", 0.10)),
    )
    try:
        results = retriever.search(
            args.query,
            category=args.category,
            min_trust=float(args.min_trust),
            limit=int(args.limit),
            debug=True,
        )
    finally:
        store.close()

    print("\nHolographic memory query debug\n" + "-" * 40)
    print(f"  Query: {args.query}")
    print(f"  Results: {len(results)}\n")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print()


def register_cli(parser) -> None:
    sub = parser.add_subparsers(dest="holographic_action")

    sub.add_parser("status", help="Show understanding-index status")

    reindex = sub.add_parser("reindex", help="Rebuild enrichment, vectors, embeddings, and links")
    reindex.add_argument(
        "--include-embeddings",
        action="store_true",
        default=True,
        help="Recompute embeddings when an embedding provider is configured (default: on)",
    )
    reindex.add_argument(
        "--no-embeddings",
        dest="include_embeddings",
        action="store_false",
        help="Skip embedding recomputation",
    )
    reindex.add_argument(
        "--refresh-links",
        action="store_true",
        default=True,
        help="Rebuild related-memory links (default: on)",
    )
    reindex.add_argument(
        "--no-links",
        dest="refresh_links",
        action="store_false",
        help="Skip link rebuilding",
    )
    reindex.add_argument(
        "--drain-pending",
        action="store_true",
        default=True,
        help="Process pending deferred-ingest items before reindexing (default: on)",
    )
    reindex.add_argument(
        "--no-drain-pending",
        dest="drain_pending",
        action="store_false",
        help="Skip draining deferred-ingest backlog before reindexing",
    )

    inspect_parser = sub.add_parser("inspect", help="Inspect one stored memory by fact ID")
    inspect_parser.add_argument("fact_id", help="Fact ID to inspect")

    query_parser = sub.add_parser("query-debug", help="Run explainable retrieval and print JSON debug output")
    query_parser.add_argument("query", help="Search query")
    query_parser.add_argument("--category", help="Optional category filter")
    query_parser.add_argument("--min-trust", type=float, default=0.3, help="Minimum trust threshold")
    query_parser.add_argument("--limit", type=int, default=5, help="Number of results to return")

    parser.set_defaults(func=holographic_command)


def holographic_command(args) -> None:
    action = getattr(args, "holographic_action", None) or "status"
    if action == "status":
        cmd_status(args)
    elif action == "reindex":
        cmd_reindex(args)
    elif action == "inspect":
        cmd_inspect(args)
    elif action == "query-debug":
        cmd_query_debug(args)
    else:
        cmd_status(args)
