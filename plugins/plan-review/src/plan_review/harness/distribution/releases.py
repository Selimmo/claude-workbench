"""Finding plan-review's newest release on GitHub."""

import json
import re
import urllib.request
from typing import Any

REPO = "Selimmo/claude-workbench"
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=100"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
TAG_PREFIX = "plan-review--v"


def _version(tag: str) -> tuple[int, ...] | None:
    if not tag.startswith(TAG_PREFIX):
        return None
    numbers = re.fullmatch(r"\d+(\.\d+)*", tag.removeprefix(TAG_PREFIX))
    return tuple(int(n) for n in numbers.group().split(".")) if numbers else None


def newest_wheel(releases: list[dict[str, Any]]) -> str | None:
    """The download link of the newest plan-review release's wheel; other tools' tags and
    releases without a wheel are skipped."""
    found: list[tuple[tuple[int, ...], str]] = []
    for item in releases:
        version = _version(str(item.get("tag_name", "")))
        if version is None:
            continue
        assets: list[dict[str, Any]] = item.get("assets") or []
        for asset in assets:
            if re.fullmatch(r"plan_review-.*\.whl", str(asset.get("name", ""))):
                found.append((version, str(asset["browser_download_url"])))
    return max(found)[1] if found else None


def fetch_releases() -> list[dict[str, Any]]:
    request = urllib.request.Request(
        RELEASES_URL, headers={"Accept": "application/vnd.github+json", "User-Agent": "plan-review"}
    )
    with urllib.request.urlopen(request, timeout=20) as reply:
        return json.load(reply)
