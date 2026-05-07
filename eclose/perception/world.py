import httpx
from eclose.perception.base import BasePerceptionAgent
from eclose.events.events import PerceptionSource


class WorldPerceptionAgent(BasePerceptionAgent):
    """Perception agent that monitors the external world for new technologies."""

    def __init__(self):
        super().__init__(name="WorldPerception", source=PerceptionSource.WORLD)

    async def _感知(self) -> dict:
        """Perceive world events - new technologies, tools, best practices."""
        return {
            "trending_projects": await self._fetch_github_trending(),
            "new_releases": await self._check_package_updates(),
            "tech_news": await self._fetch_tech_news(),
        }

    async def _fetch_github_trending(self) -> list[dict]:
        """Fetch GitHub trending projects."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.github.com/search/repositories",
                    params={"q": "created:>2026-01-01", "sort": "stars", "per_page": 5},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    items = response.json().get("items", [])
                    return [
                        {"name": r["full_name"], "stars": r["stargazers_count"]}
                        for r in items
                    ]
        except Exception:
            pass
        return []

    async def _check_package_updates(self) -> list[dict]:
        """Check for major package updates."""
        # TODO: Implement for npm, PyPI, etc.
        return []

    async def _fetch_tech_news(self) -> list[dict]:
        """Fetch latest tech news."""
        # TODO: Integrate with HackerNews API or similar
        return []
