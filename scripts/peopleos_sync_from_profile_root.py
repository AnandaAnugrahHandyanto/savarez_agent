#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from people_manager.migration import sync_peopleos_from_profile_root

DEFAULT_SOURCE = Path("/Users/michael.wu/.hermes/profiles/miya/projects/people-manager.archived-2026-05-02")
DEFAULT_DESTINATION = Path("/Users/michael.wu/.PeopleOS/data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync new PeopleOS reports from a profile-scoped root into canonical standalone PeopleOS data.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help=f"Source profile-scoped PeopleOS root (default: {DEFAULT_SOURCE})")
    parser.add_argument("--destination", default=str(DEFAULT_DESTINATION), help=f"Canonical PeopleOS data root (default: {DEFAULT_DESTINATION})")
    parser.add_argument("--overwrite-existing", action="store_true", help="Overwrite reports that already exist in canonical PeopleOS")
    parser.add_argument("--synced-by", default="jack3")
    args = parser.parse_args(argv)

    manifest = sync_peopleos_from_profile_root(
        args.source,
        args.destination,
        synced_by=args.synced_by,
        overwrite_existing=args.overwrite_existing,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
