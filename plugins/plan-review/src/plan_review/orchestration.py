"""Deterministic helpers for the /ship skill, so it never has to eyeball these decisions."""

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Literal

Verdict = Literal["PASS", "FINDINGS"]


class MalformedReview(ValueError):
    pass


def verdict(review: Path) -> Verdict:
    """The verdict on a review's last non-blank line, as reviewer agents are told to write it."""
    lines = [line.strip() for line in review.read_text().splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    if last == "VERDICT: PASS":
        return "PASS"
    if last == "VERDICT: FINDINGS":
        return "FINDINGS"
    raise MalformedReview(f"{review}: last line is not 'VERDICT: PASS' or 'VERDICT: FINDINGS'")


def slugify(title: str, words: int = 5) -> str:
    """A branch-safe slug: the title's first few words, lowercased, joined by dashes."""
    cleaned = re.sub(r"[^a-z0-9\s-]", "", title.lower())
    return "-".join(cleaned.split()[:words])


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True).stdout


def tree_hash(repo: Path) -> str:
    """A fingerprint of every uncommitted change git can see (gitignored files excluded).

    /ship takes it before and after each review: reviewers keep Bash to run tests, and
    plugin agents cannot be sandboxed, so this is how a review that edited files is caught.
    """
    digest = hashlib.sha256()
    digest.update(_git(repo, "diff", "HEAD", "--binary"))
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "-z")
    for name in sorted(filter(None, untracked.split(b"\0"))):
        digest.update(name + b"\0")
        digest.update((repo / name.decode()).read_bytes())
    return digest.hexdigest()
