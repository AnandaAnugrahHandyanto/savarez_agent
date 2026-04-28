#!/usr/bin/env python3
"""GitHub metadata sync service for Hermes Code Mode."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_cli.code.github_integration import GitHubIntegrationDB, GitHubIntegrationService


class GitHubSyncService:
    """Sync GitHub repositories and lightweight issue/PR metadata."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        *,
        api_client: Optional[Any] = None,
        realtime_hub=None,
    ) -> None:
        self._db_path = db_path
        self._api_client = api_client
        self._realtime_hub = realtime_hub

    def _db(self) -> GitHubIntegrationDB:
        return GitHubIntegrationDB(db_path=self._db_path)

    def _client(self, installation_id: Optional[int] = None):
        if self._api_client is not None:
            return self._api_client
        return GitHubIntegrationService(db_path=self._db_path).api_client(installation_id)

    def sync_repositories(
        self,
        installation_id: Optional[int] = None,
        dry_run: bool = False,
        limit: int = 100,
    ) -> Dict[str, Any]:
        client = self._client(installation_id)
        repositories = client.list_paginated("/installation/repositories")
        repositories = repositories[:limit]
        if dry_run:
            return {"dry_run": True, "synced": 0, "repositories": repositories}

        db = self._db()
        try:
            synced = [
                db.upsert_repository(repo, installation_id=installation_id)
                for repo in repositories
            ]
        finally:
            db.close()
        return {"dry_run": False, "synced": len(synced), "repositories": synced}

    def sync_issues(self, repo_full_name: str, limit: int = 100) -> Dict[str, Any]:
        client = self._client()
        issues = client.list_paginated(
            f"/repos/{repo_full_name}/issues",
            params={"state": "all"},
        )[:limit]
        issues = [issue for issue in issues if not issue.get("pull_request")]
        db = self._db()
        try:
            synced = [db.upsert_issue(repo_full_name, issue) for issue in issues]
        finally:
            db.close()
        return {"repo_full_name": repo_full_name, "synced": len(synced), "issues": synced}

    def sync_pull_requests(self, repo_full_name: str, limit: int = 100) -> Dict[str, Any]:
        client = self._client()
        pulls = client.list_paginated(
            f"/repos/{repo_full_name}/pulls",
            params={"state": "all"},
        )[:limit]
        db = self._db()
        try:
            synced = [db.upsert_pull_request(repo_full_name, pr) for pr in pulls]
        finally:
            db.close()
        return {"repo_full_name": repo_full_name, "synced": len(synced), "pull_requests": synced}

    def sync_branches(self, repo_full_name: str, limit: int = 100) -> Dict[str, Any]:
        client = self._client()
        branches = client.list_paginated(f"/repos/{repo_full_name}/branches")[:limit]
        db = self._db()
        try:
            synced = [db.upsert_branch(repo_full_name, branch) for branch in branches]
        finally:
            db.close()
        return {"repo_full_name": repo_full_name, "synced": len(synced), "branches": synced}

    def sync_repository_details(self, repo_full_name: str) -> Dict[str, Any]:
        issues = self.sync_issues(repo_full_name)
        pulls = self.sync_pull_requests(repo_full_name)
        branches = self.sync_branches(repo_full_name)
        return {
            "repo_full_name": repo_full_name,
            "issues": issues,
            "pull_requests": pulls,
            "branches": branches,
        }
