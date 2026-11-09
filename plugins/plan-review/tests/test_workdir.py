"""`.plan-review/work/`: where every issue's files live, kept out of the project's git."""

from datetime import date
from pathlib import Path

from plan_review.workdir import ensure_work_dir, new_prompt_work_dir


def test_creates_the_issues_work_folder(tmp_path: Path) -> None:
    work = ensure_work_dir(tmp_path, "42")

    assert work == tmp_path / ".plan-review" / "work" / "42"
    assert work.is_dir()


def test_a_work_folder_is_named_by_its_text_id(tmp_path: Path) -> None:
    work = ensure_work_dir(tmp_path, "PROJ-123")

    assert work == tmp_path / ".plan-review" / "work" / "PROJ-123"
    assert work.is_dir()


def test_ignores_everything_in_the_work_folder_on_first_use(tmp_path: Path) -> None:
    ensure_work_dir(tmp_path, "42")

    assert (tmp_path / ".plan-review" / "work" / ".gitignore").read_text() == "*\n"


def test_keeps_a_gitignore_the_project_already_has_there(tmp_path: Path) -> None:
    ignore = tmp_path / ".plan-review" / "work" / ".gitignore"
    ignore.parent.mkdir(parents=True)
    ignore.write_text("*\n!decisions.md\n")

    ensure_work_dir(tmp_path, "42")

    assert ignore.read_text() == "*\n!decisions.md\n"


def test_a_prompt_run_is_named_and_dated(tmp_path: Path) -> None:
    work = new_prompt_work_dir(tmp_path, "add-dark-mode", date(2026, 11, 5))

    assert work == tmp_path / ".plan-review" / "work" / "add-dark-mode-2026-11-05"
    assert work.is_dir()
    assert (tmp_path / ".plan-review" / "work" / ".gitignore").read_text() == "*\n"


def test_a_prompt_run_that_clashes_gets_the_next_free_suffix(tmp_path: Path) -> None:
    today = date(2026, 11, 5)
    first = new_prompt_work_dir(tmp_path, "add-dark-mode", today)

    second = new_prompt_work_dir(tmp_path, "add-dark-mode", today)
    third = new_prompt_work_dir(tmp_path, "add-dark-mode", today)

    assert first.name == "add-dark-mode-2026-11-05"
    assert second.name == "add-dark-mode-2026-11-05-2"
    assert third.name == "add-dark-mode-2026-11-05-3"


def test_the_projects_own_gitignore_is_untouched(tmp_path: Path) -> None:
    ignore = tmp_path / ".gitignore"
    ignore.write_bytes(b"node_modules/\r\n")

    ensure_work_dir(tmp_path, "42")

    assert ignore.read_bytes() == b"node_modules/\r\n"
