"""How file changes are noticed: polled, then announced to the open pages."""

import asyncio
from pathlib import Path

from plan_review.events.subscribers import Subscribers


class FileWatcher:
    """Announces `files[path]` to the pages whenever that file changes.

    Polling rather than OS file events: no extra dependency, and these files change rarely.
    """

    def __init__(self, files: dict[Path, str], interval: float, pages: Subscribers) -> None:
        self._files = files
        self._interval = interval
        self._pages = pages

    async def watch(self) -> None:
        last = {path: self._signature(path) for path in self._files}
        while True:
            await asyncio.sleep(self._interval)
            for path, event in self._files.items():
                current = self._signature(path)
                if current != last[path]:
                    last[path] = current
                    await self._pages.send({"type": event})

    @staticmethod
    def _signature(path: Path) -> tuple[int, int] | None:
        """What we compare to notice a change: modification time and size, or None if missing."""
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        return stat.st_mtime_ns, stat.st_size
