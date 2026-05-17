"""Apple Notes source provider — uses memo CLI tool."""
import subprocess
import json
from datetime import datetime, timezone
from typing import List, Optional
from providers.base import SourceProvider
from models import Document


class AppleNotesProvider(SourceProvider):
    source_id = "apple-notes"

    def fetch_changes(self, since: Optional[datetime] = None) -> List[Document]:
        docs = []
        try:
            cmd = ["memo", "search", "--format", "json", ""]
            if since:
                cmd = ["memo", "search", "--format", "json", "--after",
                       since.strftime("%Y-%m-%d"), ""]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return docs

            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    note = json.loads(line)
                except json.JSONDecodeError:
                    continue
                docs.append(Document(
                    source_id=self.source_id,
                    source_path=note.get("id", "unknown"),
                    content=note.get("body", note.get("title", "")),
                    title=note.get("title", "Untitled")
                ))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # memo CLI not available
        return docs

    def health_check(self) -> bool:
        try:
            result = subprocess.run(["memo", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
