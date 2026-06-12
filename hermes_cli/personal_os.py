"""CLI for read-only Personal OS vault retrieval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from hermes_cli.personal_os_index import PersonalOSIndex, scope_names


def _index_from_args(args: argparse.Namespace) -> PersonalOSIndex:
    return PersonalOSIndex(
        vault_root=Path(args.vault_root).expanduser() if getattr(args, "vault_root", None) else None,
        db_path=Path(args.db_path).expanduser() if getattr(args, "db_path", None) else None,
    )


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _ensure_vault_available(idx: PersonalOSIndex, *, json_output: bool) -> bool:
    if idx.vault_root.exists() and idx.vault_root.is_dir():
        return True
    message = f"Personal OS vault root not found: {idx.vault_root}"
    if json_output:
        _print_json({"error": "vault_root_missing", "message": message, "vault_root": str(idx.vault_root)})
    else:
        print(f"error: {message}", file=sys.stderr)
    return False


def _cmd_index(args: argparse.Namespace) -> int:
    idx = _index_from_args(args)
    stats = idx.rebuild() if args.rebuild else idx.index_changed()
    data = stats.to_dict() | {"vault_root": str(idx.vault_root), "db_path": str(idx.db_path)}
    if args.json:
        _print_json(data)
        return 0
    print(f"Personal OS index: {idx.vault_root}")
    print(f"DB: {idx.db_path}")
    print(
        "Indexed {indexed_files} changed file(s), {unchanged_files} unchanged, "
        "{removed_files} removed, {skipped_files} skipped, {chunks} chunk(s).".format(**data)
    )
    if data["warnings"]:
        print("Warnings:")
        for warning in data["warnings"][:20]:
            print(f"- {warning['path']}: {warning['reason']}")
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    idx = _index_from_args(args)
    if not _ensure_vault_available(idx, json_output=args.json):
        return 1
    result = idx.search(args.query, scope=args.scope, limit=args.limit)
    if args.json:
        _print_json(result)
        return 0
    print(f"Query: {result['query']}")
    print(f"Scope: {result['scope']}")
    print(f"Indexed at: {result.get('last_indexed_at') or 'never'}")
    if not result["matches"]:
        print("No matches.")
    for i, match in enumerate(result["matches"], 1):
        stale = " possibly stale" if match["stale"] else ""
        print(f"\n{i}. {match['path']} — {match['heading']} (score {match['score']}; {match['age_days']}d old{stale})")
        print(f"   {match['snippet']}")
    if result["warnings"]:
        print("\nWarnings:")
        for warning in result["warnings"][:10]:
            print(f"- {warning['rel_path']}: {warning['reason']}")
    return 0


def _cmd_context(args: argparse.Namespace) -> int:
    idx = _index_from_args(args)
    if not _ensure_vault_available(idx, json_output=args.json):
        return 1
    result = idx.search(args.query, scope=args.scope, limit=args.limit, stale_days=args.stale_days)
    if args.json:
        _print_json(result)
        return 0
    print("## Retrieved Personal OS context")
    print(f"Query: {result['query']}")
    print(f"Scope: {result['scope']}")
    print(f"Indexed at: {result.get('last_indexed_at') or 'never'}")
    if not result["matches"]:
        print("\nNo matching context found. Run `hermes personal-os index` if the index is stale.")
    else:
        print("\n### Strongest matches")
        for i, match in enumerate(result["matches"], 1):
            stale = " — possibly stale" if match["stale"] else ""
            print(f"\n{i}. `{match['path']}`{stale}")
            print(f"   Heading: {match['heading']}")
            print(f"   Modified: {match['modified']} ({match['age_days']} days old)")
            print(f"   Snippet: {match['snippet']}")
    stale_matches = [m for m in result["matches"] if m["stale"]]
    if stale_matches:
        print("\n### Possibly stale")
        for match in stale_matches[:5]:
            print(f"- `{match['path']}` last changed {match['age_days']} days ago")
    if result["warnings"]:
        print("\n### Skipped / possibly unsynced files")
        for warning in result["warnings"][:10]:
            print(f"- `{warning['rel_path']}`: {warning['reason']}")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    idx = _index_from_args(args)
    data = idx.doctor()
    if args.json:
        _print_json(data)
        return 0
    print("Personal OS retrieval doctor")
    print(f"Vault root: {data['vault_root']}")
    print(f"Vault exists/readable: {data['vault_exists']} / {data['vault_readable']}")
    print(f"DB: {data['db_path']} (exists: {data['db_exists']})")
    print(f"FTS available: {data['fts_available']}")
    print(f"Indexed files: {data['indexed_files']}")
    print(f"Chunks: {data['chunks']}")
    print(f"Skipped files: {data['skipped_files']}")
    print(f"Last indexed: {data.get('last_indexed_at') or 'never'}")
    print(f"Scopes: {', '.join(data['scopes'])}")
    return 0 if data["vault_exists"] else 1


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--vault-root", help="Personal OS vault root (defaults to OBSIDIAN_VAULT_PATH or the macOS iCloud Personal OS path)")
    parser.add_argument("--db-path", help="SQLite index DB path (defaults under HERMES_HOME)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")


def register_cli(parent: argparse.ArgumentParser) -> None:
    parent.set_defaults(func=lambda _args: (parent.print_help(), 0)[1])
    sub = parent.add_subparsers(dest="personal_os_command")

    index_p = sub.add_parser("index", help="Index changed Personal OS markdown files")
    _add_common_args(index_p)
    index_p.add_argument("--rebuild", action="store_true", help="Delete and rebuild the disposable local index")
    index_p.set_defaults(func=_cmd_index)

    search_p = sub.add_parser("search", help="Search the local Personal OS index")
    _add_common_args(search_p)
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--scope", choices=scope_names(), default="default", help="Privacy scope to search")
    search_p.add_argument("--limit", type=int, default=10, help="Maximum matches to return")
    search_p.set_defaults(func=_cmd_search)

    context_p = sub.add_parser("context", help="Render briefing-oriented context with citations")
    _add_common_args(context_p)
    context_p.add_argument("query", help="Context query")
    context_p.add_argument("--scope", choices=scope_names(), default="default", help="Privacy scope to search")
    context_p.add_argument("--limit", type=int, default=8, help="Maximum matches to return")
    context_p.add_argument("--stale-days", type=int, default=120, help="Mark matches older than N days as possibly stale")
    context_p.set_defaults(func=_cmd_context)

    doctor_p = sub.add_parser("doctor", help="Check vault/index health")
    _add_common_args(doctor_p)
    doctor_p.set_defaults(func=_cmd_doctor)


def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes personal-os")
    register_cli(parser)
    args = parser.parse_args(argv)
    fn = getattr(args, "func", None)
    if fn is None:
        parser.print_help()
        return 0
    try:
        return int(fn(args) or 0)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli_main())
