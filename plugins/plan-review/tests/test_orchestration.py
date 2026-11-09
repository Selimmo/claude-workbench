"""Small deterministic helpers the /ship skill calls instead of judging things itself."""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import WindowsStylePath

from plan_review.cli import main
from plan_review.orchestration import MalformedReview, branch_name, slugify, tree_hash, verdict
from plan_review.plan import Issue, load_plan

EXAMPLE = Path(__file__).parents[1] / "examples" / "plan.json"


@pytest.mark.parametrize(
    ("last_line", "exit_code", "printed"),
    [("VERDICT: PASS", 0, "PASS"), ("VERDICT: FINDINGS", 1, "FINDINGS")],
)
def test_verdict_reads_a_reviews_last_line(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    last_line: str,
    exit_code: int,
    printed: str,
) -> None:
    review = tmp_path / "test-review.md"
    review.write_text(f"# Test review\n\n1. [should-fix] x\n\n{last_line}\n\n")

    assert main(["verdict", str(review)]) == exit_code
    assert capsys.readouterr().out.strip() == printed


def test_a_review_without_a_verdict_line_is_malformed_not_a_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    review = tmp_path / "code-review.md"
    review.write_text("# Code review\n\nLooks good to me!\n")

    assert main(["verdict", str(review)]) == 2
    assert "last line is not 'VERDICT: PASS' or 'VERDICT: FINDINGS'" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("Let candidates request a hint during an interview", "let-candidates-request-a-hint"),
        ("Frontend: API client & setup screen", "frontend-api-client-setup-screen"),
        ("Fix  #12's   crash!", "fix-12s-crash"),
    ],
)
def test_slug_is_the_titles_first_five_words_lowercased_and_dashed(title: str, slug: str) -> None:
    assert slugify(title) == slug


def test_an_issue_branch_follows_the_pattern_with_the_text_id() -> None:
    issue = Issue(id="PROJ-123", kind="issue", title="Add dark mode")

    assert branch_name("PROJ-123", issue, "feat/{issue}-{slug}") == "feat/PROJ-123-add-dark-mode"


@pytest.mark.parametrize("pattern", ["{issue}-{slug}", "feat/{issue}-{slug}"])
def test_a_prompt_branch_is_its_id_whatever_the_pattern(pattern: str) -> None:
    run_id = "add-dark-mode-2026-11-05"
    prompt = Issue(id=run_id, kind="prompt", title="Add dark mode")

    assert branch_name(run_id, prompt, pattern) == run_id


@pytest.fixture
def branch_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project root (the cwd) with the example plan for issue 42 and a branch pattern."""
    monkeypatch.chdir(tmp_path)
    work = tmp_path / ".plan-review" / "work" / "42"
    work.mkdir(parents=True)
    (work / "plan.json").write_text(EXAMPLE.read_text())
    (tmp_path / ".plan-review" / "config.json").write_text(
        json.dumps({"branch": "feat/{issue}-{slug}"})
    )
    return work / "plan.json"


def test_branch_follows_the_pipeline_pattern(
    branch_project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["branch", "42"]) == 0
    assert capsys.readouterr().out.strip() == "feat/42-let-candidates-request-a-hint"


def test_branch_records_its_name_in_the_plan(
    branch_project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["branch", "42"])

    assert load_plan(branch_project).branch == "feat/42-let-candidates-request-a-hint"


def test_branch_reuses_the_recorded_branch(
    branch_project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = json.loads(branch_project.read_text())
    branch_project.write_text(json.dumps({**raw, "branch": "old-name"}))
    before = branch_project.read_text()

    assert main(["branch", "42"]) == 0

    assert capsys.readouterr().out.strip() == "old-name"
    assert branch_project.read_text() == before


def test_branch_reuses_the_recorded_branch_even_with_a_broken_pipeline(
    branch_project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = json.loads(branch_project.read_text())
    branch_project.write_text(json.dumps({**raw, "branch": "old-name"}))
    (branch_project.parents[2] / "config.json").write_text('{"viewer": 3}')

    assert main(["branch", "42"]) == 0

    assert capsys.readouterr().out.strip() == "old-name"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / ".gitignore").write_text(".plan-review/work/\n")
    (tmp_path / "app.py").write_text("x = 1\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def test_tree_hash_is_stable_when_nothing_changes(repo: Path) -> None:
    assert tree_hash(repo) == tree_hash(repo)


@pytest.mark.parametrize(
    "change",
    [
        lambda r: (r / "app.py").write_text("x = 2\n"),  # tracked file edited
        lambda r: (r / "new.py").write_text("y = 1\n"),  # untracked file added
    ],
)
def test_tree_hash_changes_with_any_edit_a_reviewer_could_make(repo: Path, change) -> None:  # noqa: ANN001
    before = tree_hash(repo)
    change(repo)

    assert tree_hash(repo) != before


def test_tree_hash_sees_edits_inside_an_already_untracked_file(repo: Path) -> None:
    (repo / "new.py").write_text("y = 1\n")
    before = tree_hash(repo)
    (repo / "new.py").write_text("y = 2\n")

    assert tree_hash(repo) != before


def test_tree_hash_ignores_gitignored_files_such_as_the_pipelines_reports(repo: Path) -> None:
    before = tree_hash(repo)
    (repo / ".plan-review" / "work").mkdir(parents=True)
    (repo / ".plan-review" / "work" / "test-review.md").write_text("VERDICT: PASS\n")

    assert tree_hash(repo) == before


def test_tree_hash_command_prints_the_current_repos_hash(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(repo)

    assert main(["tree-hash"]) == 0
    assert capsys.readouterr().out.strip() == tree_hash(repo)


def test_a_malformed_reviews_path_is_reported_with_forward_slashes(tmp_path: Path) -> None:
    review = WindowsStylePath(tmp_path / "review.md")
    review.write_text("no verdict here\n")

    with pytest.raises(MalformedReview) as error:
        verdict(review)

    expected = (tmp_path / "review.md").as_posix()
    assert str(error.value).startswith(f"{expected}: last line is not")
