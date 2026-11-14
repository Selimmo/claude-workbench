"""The project root: where `.plan-review/` is, found from any folder inside the project."""

from pathlib import Path

from plan_review.paths.project_root import project_root


def make(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_from_a_subfolder_finds_the_folder_with_plan_review(tmp_path: Path) -> None:
    make(tmp_path / ".git")
    make(tmp_path / ".plan-review")
    deep = make(tmp_path / "plugins" / "tool" / "src")

    assert project_root(deep, user_dir=tmp_path / "home" / ".plan-review") == tmp_path


def test_without_plan_review_the_git_root_is_the_project(tmp_path: Path) -> None:
    make(tmp_path / ".git")
    deep = make(tmp_path / "plugins" / "tool")

    assert project_root(deep, user_dir=tmp_path / "home" / ".plan-review") == tmp_path


def test_a_git_file_marks_the_root_too(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("gitdir: /elsewhere\n")  # a worktree or submodule
    deep = make(tmp_path / "sub")

    assert project_root(deep, user_dir=tmp_path / "home" / ".plan-review") == tmp_path


def test_outside_git_the_current_folder_is_the_project(tmp_path: Path) -> None:
    make(tmp_path / ".plan-review")  # above the start, but no git to bound the search
    start = make(tmp_path / "loose")

    assert project_root(start, user_dir=tmp_path / "home" / ".plan-review") == start


def test_never_looks_above_the_git_root(tmp_path: Path) -> None:
    make(tmp_path / ".plan-review")
    repo = make(tmp_path / "repo")
    make(repo / ".git")
    deep = make(repo / "src")

    assert project_root(deep, user_dir=tmp_path / "home" / ".plan-review") == repo


def test_the_owners_own_settings_folder_is_not_a_project(tmp_path: Path) -> None:
    make(tmp_path / ".git")  # the git root sits above the home folder
    home = make(tmp_path / "home")
    user_dir = make(home / ".plan-review")
    start = make(home / "notes")

    assert project_root(start, user_dir=user_dir) == tmp_path
