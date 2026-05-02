#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from people_manager.migration import migrate_peopleos_from_miya

DEFAULT_SOURCE = Path("/Users/michael.wu/.hermes/profiles/miya/projects/people-manager.archived-2026-05-02")
DEFAULT_DESTINATION = Path("/Users/michael.wu/.PeopleOS/data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate Miya's PeopleOS data into the canonical standalone PeopleOS data root.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help=f"Source Miya PeopleOS root (default: {DEFAULT_SOURCE})")
    parser.add_argument("--destination", default=str(DEFAULT_DESTINATION), help=f"Canonical PeopleOS data root (default: {DEFAULT_DESTINATION})")
    parser.add_argument("--force", action="store_true", help="Overwrite a non-empty destination")
    parser.add_argument("--migrated-by", default="jack3")
    args = parser.parse_args(argv)

    manifest = migrate_peopleos_from_miya(args.source, args.destination, force=args.force, migrated_by=args.migrated_by)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
