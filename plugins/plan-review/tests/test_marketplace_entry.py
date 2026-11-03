"""scripts/set-marketplace-entry.sh: point the marketplace at a released zip."""

import json
import subprocess
from pathlib import Path

PLUGIN = Path(__file__).parents[1]
SCRIPT = PLUGIN / "scripts" / "set-marketplace-entry.sh"
URL = "https://github.com/o/r/releases/download/plan-review--v0.2.0/plan-review-0.2.0.zip"
SHA = "ab" * 32


def marketplace(tmp_path: Path, plugins: list[dict[str, object]]) -> Path:
    path = tmp_path / "marketplace.json"
    path.write_text(json.dumps({"name": "claude-workbench", "plugins": plugins}, indent=2))
    return path


def set_entry(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), str(path), "0.2.0", URL, SHA], capture_output=True, text=True, check=False
    )


def test_points_the_entry_at_the_zip_and_keeps_its_other_fields(tmp_path: Path) -> None:
    other: dict[str, object] = {"name": "other", "source": "./plugins/other"}
    path = marketplace(
        tmp_path,
        [
            {"name": "plan-review", "source": "./plugins/plan-review", "category": "engineering"},
            other,
        ],
    )

    result = set_entry(path)

    assert result.returncode == 0, result.stderr
    entry, *others = json.loads(path.read_text())["plugins"]
    assert others == [other]
    assert entry == {
        "name": "plan-review",
        "source": {"source": "archive", "url": URL, "sha256": SHA},
        "version": "0.2.0",
        "category": "engineering",
    }


def test_fails_when_the_marketplace_lists_no_plan_review(tmp_path: Path) -> None:
    path = marketplace(tmp_path, [{"name": "other", "source": "./plugins/other"}])
    before = path.read_text()

    result = set_entry(path)

    assert result.returncode == 1
    assert "no plan-review entry" in result.stderr
    assert path.read_text() == before
