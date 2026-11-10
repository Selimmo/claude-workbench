"""Every file a run keeps in its work folder, named once."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    folder: Path

    @property
    def plan(self) -> Path:
        return self.folder / "plan.json"

    @property
    def comments(self) -> Path:
        return self.folder / "comments.json"

    @property
    def drafts(self) -> Path:
        return self.folder / "drafts.json"

    @property
    def status(self) -> Path:
        return self.folder / "status.json"

    @property
    def grill(self) -> Path:
        return self.folder / "grill.json"

    @property
    def grill_drafts(self) -> Path:
        return self.folder / "grill_drafts.json"

    @property
    def last_event(self) -> Path:
        return self.folder / "last_event.json"

    @property
    def events(self) -> Path:
        return self.folder / "events.json"

    @property
    def approved(self) -> Path:
        return self.folder / "approved.json"

    @property
    def viewer(self) -> Path:
        return self.folder / "viewer.json"

    @property
    def viewer_log(self) -> Path:
        return self.folder / "viewer.log"

    @property
    def decisions(self) -> Path:
        return self.folder / "decisions.md"
