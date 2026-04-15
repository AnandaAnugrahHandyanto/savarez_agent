from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol


class BrowserBoundaryShim(Protocol):
    def get_session_info(self, task_id: Optional[str] = None, authority: Any = None) -> Dict[str, Any]:
        ...

    def run_command(
        self,
        task_id: str,
        command: str,
        args: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        authority: Any = None,
    ) -> Dict[str, Any]:
        ...

    def cleanup_session(self, task_id: Optional[str] = None, authority: Any = None) -> None:
        ...


@dataclass
class InProcessBrowserBoundaryShim:
    session_getter: Callable[..., Dict[str, Any]]
    command_runner: Callable[..., Dict[str, Any]]
    cleanup_runner: Callable[..., None]

    def get_session_info(self, task_id: Optional[str] = None, authority: Any = None) -> Dict[str, Any]:
        return self.session_getter(task_id=task_id, authority=authority)

    def run_command(
        self,
        task_id: str,
        command: str,
        args: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        authority: Any = None,
    ) -> Dict[str, Any]:
        return self.command_runner(task_id=task_id, command=command, args=args, timeout=timeout, authority=authority)

    def cleanup_session(self, task_id: Optional[str] = None, authority: Any = None) -> None:
        self.cleanup_runner(task_id=task_id, authority=authority)
