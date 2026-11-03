"""`.claude/work/`: where every issue's files live, kept out of the project's git."""

from pathlib import Path

from plan_review.workdir import ensure_work_dir


def test_creates_the_issues_work_folder(tmp_path: Path) -> None:
    work = ensure_work_dir(tmp_path, 42)

    assert work == tmp_path / ".claude" / "work" / "42"
    assert work.is_dir()


def test_ignores_everything_in_the_work_folder_on_first_use(tmp_path: Path) -> None:
    ensure_work_dir(tmp_path, 42)

    assert (tmp_path / ".claude" / "work" / ".gitignore").read_text() == "*\n"


def test_keeps_a_gitignore_the_project_already_has_there(tmp_path: Path) -> None:
    ignore = tmp_path / ".claude" / "work" / ".gitignore"
    ignore.parent.mkdir(parents=True)
    ignore.write_text("*\n!decisions.md\n")

    ensure_work_dir(tmp_path, 42)

    assert ignore.read_text() == "*\n!decisions.md\n"
