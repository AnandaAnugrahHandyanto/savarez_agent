"""Thin HTTP client for the GitHub-compatible Issues API at git.clawmem.ai."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://git.clawmem.ai/api/v3"
_TIMEOUT = 8


class GitHubIssueClient:
    """Wraps the GitHub-compatible REST API used by ClawMem."""

    def __init__(self, base_url: str, token: str = "", auth_scheme: str = "token"):
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._auth_scheme = auth_scheme  # "token" or "bearer"

    # -- low-level --------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict | None = None,
        params: dict | None = None,
        allow_status: tuple[int, ...] = (),
        omit_auth: bool = False,
    ) -> Any:
        url = f"{self._base_url}/{path.lstrip('/')}"
        if params:
            qs = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}
            )
            url = f"{url}?{qs}"

        data = json.dumps(body).encode() if body else None
        headers = {
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }
        if not omit_auth and self._token:
            auth_value = (
                f"Bearer {self._token}"
                if self._auth_scheme == "bearer"
                else f"token {self._token}"
            )
            headers["Authorization"] = auth_value
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in allow_status:
                return None
            body_text = ""
            try:
                body_text = e.read().decode()[:500]
            except Exception:
                pass
            logger.warning("ClawMem API %s %s -> %s: %s", method, path, e.code, body_text)
            raise

    def _get(self, path: str, **kwargs) -> Any:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, body: dict | None = None, **kwargs) -> Any:
        return self._request("POST", path, body=body, **kwargs)

    def _patch(self, path: str, body: dict, **kwargs) -> Any:
        return self._request("PATCH", path, body=body, **kwargs)

    # -- agent provisioning -----------------------------------------------

    def register_agent(self, prefix_login: str, default_repo_name: str) -> dict:
        """POST /agents — auto-provision agent identity and repo (unauthenticated)."""
        return self._post(
            "agents",
            {"prefix_login": prefix_login, "default_repo_name": default_repo_name},
            omit_auth=True,
        )

    def anonymous_session(self, locale: str = "") -> dict:
        """POST /anonymous/session — fallback provisioning (unauthenticated)."""
        body = {"locale": locale} if locale else None
        return self._post("anonymous/session", body, omit_auth=True)

    # -- repos ------------------------------------------------------------

    def list_repos(self) -> list:
        return self._get("user/repos", params={"limit": "50"}) or []

    def create_repo(self, name: str, description: str = "", private: bool = True) -> dict:
        return self._post(
            "user/repos",
            {"name": name, "description": description, "private": private},
        )

    # -- issues (memory + conversation) -----------------------------------

    def list_issues(
        self,
        repo: str,
        *,
        labels: str = "",
        state: str = "open",
        page: int = 1,
        per_page: int = 20,
    ) -> list:
        return (
            self._get(
                f"repos/{repo}/issues",
                params={
                    "labels": labels,
                    "state": state,
                    "page": str(page),
                    "per_page": str(per_page),
                    "type": "issues",
                },
            )
            or []
        )

    def get_issue(self, repo: str, number: int) -> dict | None:
        return self._get(f"repos/{repo}/issues/{number}", allow_status=(404,))

    def create_issue(
        self,
        repo: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict:
        payload: Dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        return self._post(f"repos/{repo}/issues", payload)

    def update_issue(
        self,
        repo: str,
        number: int,
        *,
        title: str | None = None,
        body: str | None = None,
        state: str | None = None,
        labels: list[str] | None = None,
    ) -> dict:
        payload: Dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if state is not None:
            payload["state"] = state
        if labels is not None:
            payload["labels"] = labels
        return self._patch(f"repos/{repo}/issues/{number}", payload)

    def create_comment(self, repo: str, number: int, body: str) -> dict:
        return self._post(f"repos/{repo}/issues/{number}/comments", {"body": body})

    # -- search -----------------------------------------------------------

    def search_issues(self, query: str, repo: str, extra_qualifiers: str = "") -> list:
        q = f"{query} repo:{repo} is:issue {extra_qualifiers}".strip()
        result = self._get("search/issues", params={"q": q})
        if isinstance(result, dict):
            return result.get("items", [])
        return result or []

    # -- labels -----------------------------------------------------------

    def list_labels(self, repo: str) -> list:
        return self._get(f"repos/{repo}/labels", params={"per_page": "100"}) or []

    def ensure_label(self, repo: str, name: str, color: str = "5319e7") -> None:
        self._post(
            f"repos/{repo}/labels",
            {"name": name, "color": color},
            allow_status=(422,),  # already exists
        )
