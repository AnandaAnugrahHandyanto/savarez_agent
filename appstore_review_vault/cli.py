from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the App Store Review Vault web UI")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default="data/appstore_reviews.sqlite")
    parser.add_argument("--apps", default="data/apps.yaml")
    args = parser.parse_args()

    import uvicorn

    from .main import create_app

    uvicorn.run(create_app(Path(args.db), Path(args.apps)), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
