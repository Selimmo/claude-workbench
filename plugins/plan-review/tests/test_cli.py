import json
import queue
import socket
import subprocess
import threading
from datetime import date
from pathlib import Path
from typing import IO

import pytest
from conftest import PACKAGE_VERSION, PLUGIN, WindowsStylePath, version_of

from plan_review import cli
from plan_review.cli import main
from plan_review.pipeline import PipelineConfigError, load_pipeline
from plan_review.plan import PlanFileError, load_plan
from plan_review.status import StatusStore
from plan_review.threads import ThreadStore


@pytest.fixture
def windows_style_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    real_work_dir, real_ensure = cli.work_dir, cli.ensure_work_dir
    monkeypatch.setattr(cli, "work_dir", lambda r, i: WindowsStylePath(real_work_dir(r, i)))
    monkeypatch.setattr(cli, "ensure_work_dir", lambda r, i: WindowsStylePath(real_ensure(r, i)))


def test_version_flag_prints_version_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--version"])

    assert exit_code == 0
    assert capsys.readouterr().out == f"plan-review {PACKAGE_VERSION}\n"


def test_console_script_is_installed() -> None:
    result = subprocess.run(
        ["plan-review", "--version"], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0
    assert result.stdout == f"plan-review {PACKAGE_VERSION}\n"


def test_the_plugin_and_its_python_package_have_one_version() -> None:
    # Claude Code reads plugin.json's version; --version reports the package's.
    assert version_of(PLUGIN) == PACKAGE_VERSION


def test_schema_prints_the_plan_json_schema(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["schema"])

    schema = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert schema["title"] == "Plan"
    assert "from" in schema["$defs"]["Relation"]["properties"]


def write_plan(tmp_path: Path, plan: object) -> str:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    return str(path)


VALID_PLAN = {
    "issue": {"id": "7", "kind": "issue", "title": "Add hints"},
    "summary": "Hint button.",
}


def test_validate_accepts_a_valid_plan(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["validate", write_plan(tmp_path, VALID_PLAN)])

    assert exit_code == 0
    assert capsys.readouterr().out.startswith("OK")


def test_validate_reports_each_error_with_its_location(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = {**VALID_PLAN, "issue": {"number": "seven", "title": "Add hints"}, "sumary": "typo"}

    exit_code = main(["validate", write_plan(tmp_path, plan)])

    err = capsys.readouterr().err
    assert exit_code == 1
    assert "issue: 'number' must be a whole number" in err
    assert "sumary: Extra inputs are not permitted" in err


@pytest.mark.parametrize("issue", [5, None])
def test_validate_reports_an_issue_that_is_not_an_object(
    issue: object, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["validate", write_plan(tmp_path, {**VALID_PLAN, "issue": issue})])

    assert exit_code == 1
    assert "issue:" in capsys.readouterr().err


def test_validate_missing_file_exits_2_with_a_clear_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["validate", str(tmp_path / "nope.json")])

    assert exit_code == 2
    assert "nope.json: file not found" in capsys.readouterr().err


def test_validate_malformed_json_is_reported_not_raised(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "plan.json"
    path.write_text("{not json")

    exit_code = main(["validate", str(path)])

    assert exit_code == 1
    assert "Invalid JSON" in capsys.readouterr().err


class FakeServer:
    """Stands in for uvicorn and the browser so serve() can be tested without either."""

    def __init__(self) -> None:
        self.addresses: list[tuple[str, int]] = []
        self.opened: list[str] = []

    def run(self, app: object, sock: socket.socket) -> None:
        self.addresses.append(sock.getsockname())


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project root (the cwd) with a valid plan for issue 7 and a built page."""
    monkeypatch.chdir(tmp_path)
    work = tmp_path / ".claude" / "work" / "7"
    work.mkdir(parents=True)
    (work / "plan.json").write_text(json.dumps(VALID_PLAN))
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>plan-review</h1>")
    monkeypatch.setattr(cli, "STATIC_DIR", static)
    return tmp_path


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> FakeServer:
    fake = FakeServer()
    monkeypatch.setattr(cli, "run_server", fake.run)
    monkeypatch.setattr(cli.webbrowser, "open", fake.opened.append)
    return fake


def test_serve_without_a_plan_exits_2_and_starts_nothing(
    project: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["serve", "8"])

    assert exit_code == 2
    assert ".claude/work/8/plan.json: file not found" in capsys.readouterr().err
    assert server.addresses == []


def test_serve_binds_localhost_on_a_free_port_and_opens_the_browser(
    project: Path, server: FakeServer
) -> None:
    exit_code = main(["serve", "7"])

    host, port = server.addresses[0]
    assert exit_code == 0
    assert host == "127.0.0.1"
    assert port > 0
    assert server.opened == [f"http://127.0.0.1:{port}/"]


def test_serve_open_none_prints_the_url_instead_of_opening_a_browser(
    project: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["serve", "7", "--open", "none"])

    _, port = server.addresses[0]
    assert server.opened == []
    assert f"http://127.0.0.1:{port}/" in capsys.readouterr().out


def write_pipeline(project: Path, config: object) -> None:
    (project / ".claude" / "pipeline.json").write_text(json.dumps(config))


def test_serve_follows_viewer_open_from_pipeline_json(project: Path, server: FakeServer) -> None:
    write_pipeline(project, {"viewer": {"open": "none"}})

    main(["serve", "7"])

    assert server.opened == []


def test_serve_open_flag_overrides_pipeline_json(project: Path, server: FakeServer) -> None:
    write_pipeline(project, {"viewer": {"open": "none"}})

    main(["serve", "7", "--open", "browser"])

    assert len(server.opened) == 1


def test_the_missing_viewer_page_is_reported_with_forward_slashes(
    project: Path,
    server: FakeServer,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "STATIC_DIR", WindowsStylePath(project / "missing"))

    main(["serve", "7"])

    expected = f"{(project / 'missing').as_posix()}: viewer page not built"
    assert expected in capsys.readouterr().err


def test_serve_without_a_built_page_says_how_to_build_it(
    project: Path,
    server: FakeServer,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "STATIC_DIR", project / "missing")

    exit_code = main(["serve", "7"])

    assert exit_code == 2
    assert "npm --prefix web run build" in capsys.readouterr().err
    assert server.addresses == []


def read_line_within(stream: IO[str], seconds: float) -> str:
    """The next line of a pipe, read by a thread: select() only takes sockets on Windows."""
    lines: queue.Queue[str] = queue.Queue()
    threading.Thread(target=lambda: lines.put(stream.readline()), daemon=True).start()
    try:
        return lines.get(timeout=seconds)
    except queue.Empty:
        pytest.fail(f"no output within {seconds:g}s: is stdout buffered?")


def test_serve_prints_its_url_immediately_when_stdout_is_a_pipe(project: Path) -> None:
    # How /ship runs it: in the background, reading the URL from a pipe.
    proc = subprocess.Popen(
        ["plan-review", "serve", "7", "--open", "none"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        assert "http://127.0.0.1:" in read_line_within(proc.stdout, 10)
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def comments(project: Path) -> ThreadStore:
    return ThreadStore(project / ".claude" / "work" / "7" / "comments.json")


def test_reply_posts_as_claude(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    thread = comments(project).create("tab:files", "Why touch the config?")

    exit_code = main(["reply", "7", thread.id, "For max_hints."])

    (saved,) = comments(project).all()
    assert exit_code == 0
    assert (saved.messages[-1].author, saved.messages[-1].text) == ("claude", "For max_hints.")


def test_reply_to_unknown_thread_exits_1(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["reply", "7", "t-nope", "hi"])

    assert exit_code == 1
    assert "no thread 't-nope'" in capsys.readouterr().err


def test_threads_lists_open_threads_as_json(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    open_thread = comments(project).create("tab:files", "Open")
    done = comments(project).create("tab:risks", "Done")
    comments(project).set_resolved(done.id, True)

    exit_code = main(["threads", "7"])

    listed = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert [t["id"] for t in listed] == [open_thread.id]
    assert listed[0]["messages"][0]["text"] == "Open"


def test_blank_reply_exits_1_with_a_message(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    thread = comments(project).create("tab:files", "Q")

    exit_code = main(["reply", "7", thread.id, " "])

    assert exit_code == 1
    assert "comment text is empty" in capsys.readouterr().err


def test_config_prints_the_resolved_pipeline_settings(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_pipeline(project, {"checks": [{"name": "all", "run": "./check.sh"}]})

    exit_code = main(["config"])

    config = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert config["checks"] == [{"name": "all", "run": "./check.sh"}]
    assert config["max_review_rounds"] == 3


def test_config_with_a_bad_file_exits_1_with_readable_errors(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_pipeline(project, {"viewer": {"open": "tab"}})

    exit_code = main(["config"])

    assert exit_code == 1
    assert "viewer.open: Input should be 'browser' or 'none'" in capsys.readouterr().err


def status_of(project: Path) -> StatusStore:
    return StatusStore(project / ".claude" / "work" / "7" / "status.json")


def test_status_sets_what_claude_is_doing(project: Path) -> None:
    exit_code = main(["status", "7", "Answering questions"])

    status = status_of(project).get()
    assert exit_code == 0
    assert status is not None
    assert (status.text, status.done) == ("Answering questions", False)


def test_status_done_marks_it_finished(project: Path) -> None:
    main(["status", "7", "Replies posted", "--done"])

    status = status_of(project).get()
    assert status is not None
    assert (status.text, status.done) == ("Replies posted", True)


def test_status_clear_removes_it(project: Path) -> None:
    main(["status", "7", "Answering questions"])

    exit_code = main(["status", "7", "--clear"])

    assert exit_code == 0
    assert status_of(project).get() is None


def test_status_without_text_exits_1(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["status", "7"])

    assert exit_code == 1
    assert "status text is empty" in capsys.readouterr().err


def test_status_for_an_issue_without_a_work_folder_exits_1(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["status", "99", "Answering questions"])

    assert exit_code == 1
    assert "no .claude/work/99/" in capsys.readouterr().err


def test_init_creates_the_issues_work_folder_and_prints_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init", "42"])

    assert exit_code == 0
    assert (tmp_path / ".claude" / "work" / "42").is_dir()
    assert (tmp_path / ".claude" / "work" / ".gitignore").is_file()
    assert capsys.readouterr().out == ".claude/work/42\n"


def test_serve_keeps_the_work_folder_out_of_git(project: Path, server: FakeServer) -> None:
    # The page writes comments.json and drafts.json there, even for a hand-made folder.
    main(["serve", "7"])

    assert (project / ".claude" / "work" / ".gitignore").read_text() == "*\n"


@pytest.mark.usefixtures("windows_style_paths")
def test_paths_in_messages_use_forward_slashes_on_every_os(
    project: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["serve", "8"]) == 2
    assert main(["status", "99", "Answering questions"]) == 1
    assert main(["init", "42"]) == 0

    captured = capsys.readouterr()
    assert ".claude/work/8/plan.json: file not found" in captured.err
    assert "no .claude/work/99/ for #99" in captured.err
    assert captured.out == ".claude/work/42\n"


def test_a_plan_path_is_reported_with_forward_slashes(tmp_path: Path) -> None:
    missing = WindowsStylePath(tmp_path / "plan.json")

    with pytest.raises(PlanFileError) as error:
        load_plan(missing)

    assert error.value.errors == [f"{(tmp_path / 'plan.json').as_posix()}: file not found"]


def test_a_pipeline_path_is_reported_with_forward_slashes(tmp_path: Path) -> None:
    bad = WindowsStylePath(tmp_path / "pipeline.json")
    bad.write_text('{"viewer": 3}')

    with pytest.raises(PipelineConfigError) as error:
        load_pipeline(bad)

    assert error.value.errors[0].startswith(f"{(tmp_path / 'pipeline.json').as_posix()}: ")


def key_project(project: Path) -> Path:
    """The project with a second run, keyed `PROJ-123`, next to issue 7's."""
    work = project / ".claude" / "work" / "PROJ-123"
    work.mkdir()
    plan = {**VALID_PLAN, "issue": {"id": "PROJ-123", "kind": "issue", "title": "Add hints"}}
    (work / "plan.json").write_text(json.dumps(plan))
    (project / ".claude" / "pipeline.json").write_text(json.dumps({"branch": "{issue}-{slug}"}))
    return work


def run_command(name: str, run_id: str) -> int:
    commands = {
        "init": ["init", run_id],
        "serve": ["serve", run_id, "--open", "none"],
        "threads": ["threads", run_id],
        "reply": ["reply", run_id, "t-nope", "hi"],
        "status": ["status", run_id, "Working"],
        "branch": ["branch", run_id],
    }
    return main(commands[name])


COMMANDS = ["init", "serve", "threads", "reply", "status", "branch"]


@pytest.mark.parametrize(
    ("argv", "expected_out"),
    [
        (["init", "PROJ-123"], ".claude/work/PROJ-123\n"),
        (["branch", "PROJ-123"], "PROJ-123-add-hints\n"),
    ],
)
def test_run_commands_take_a_text_id(
    argv: list[str],
    expected_out: str,
    project: Path,
    server: FakeServer,
    capsys: pytest.CaptureFixture[str],
) -> None:
    key_project(project)

    exit_code = main(argv)

    out, err = capsys.readouterr()
    assert exit_code == 0, err
    assert out == expected_out


def test_status_writes_into_the_text_id_folder(project: Path) -> None:
    work = key_project(project)

    main(["status", "PROJ-123", "Working"])

    assert StatusStore(work / "status.json").get() is not None


def test_threads_reads_the_text_id_folder(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    work = key_project(project)
    thread = ThreadStore(work / "comments.json").create("step:1", "why?")

    exit_code = main(["threads", "PROJ-123"])

    assert exit_code == 0
    assert thread.id in capsys.readouterr().out


def test_reply_writes_into_the_text_id_folder(project: Path) -> None:
    work = key_project(project)
    store = ThreadStore(work / "comments.json")
    thread = store.create("step:1", "why?")

    exit_code = main(["reply", "PROJ-123", thread.id, "because"])

    assert exit_code == 0
    assert [m.text for m in store.all()[0].messages] == ["why?", "because"]


@pytest.mark.parametrize("name", COMMANDS)
@pytest.mark.parametrize("bad", ["../x", "#42"])
def test_a_bad_run_id_is_rejected_before_anything_runs(
    name: str, bad: str, project: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    before = sorted(p.name for p in (project / ".claude" / "work").iterdir())

    exit_code = run_command(name, bad)  # main() returns; it must not raise SystemExit

    out, err = capsys.readouterr()
    assert exit_code == 2
    assert out == ""
    assert len(err.splitlines()) == 1
    assert f"'{bad}'" in err
    assert "letters, digits" in err
    assert sorted(p.name for p in (project / ".claude" / "work").iterdir()) == before
    assert not (project / ".claude" / "x").exists()
    assert server.addresses == []


def test_init_prompt_creates_a_dated_run_and_prints_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "today", lambda: date(2026, 11, 5))

    first = main(["init", "--prompt", "add-dark-mode"])
    second = main(["init", "--prompt", "add-dark-mode"])

    assert (first, second) == (0, 0)
    assert capsys.readouterr().out.splitlines() == [
        ".claude/work/add-dark-mode-2026-11-05",
        ".claude/work/add-dark-mode-2026-11-05-2",
    ]


def test_init_prompt_rejects_a_name_that_cannot_make_a_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init", "--prompt", "../x"])

    assert exit_code == 2
    assert "invalid run id" in capsys.readouterr().err
    assert not (tmp_path / ".claude").exists()


def test_init_needs_either_a_run_id_or_a_prompt_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 2
    assert main(["init", "42", "--prompt", "x"]) == 2
    assert not (tmp_path / ".claude").exists()
    assert capsys.readouterr().err.count("plan-review init:") == 2


def test_serve_announces_the_run_by_its_label(
    project: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    key_project(project)

    main(["serve", "7", "--open", "none"])
    main(["serve", "PROJ-123", "--open", "none"])

    first, second = capsys.readouterr().out.splitlines()
    port = server.addresses[0][1]
    assert first == f"plan-review: #7 at http://127.0.0.1:{port}/ (Ctrl+C to stop)"
    assert second.startswith("plan-review: PROJ-123 at http://127.0.0.1:")


def test_cli_messages_use_the_label(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    prompt = {
        "issue": {"id": "add-dark-mode-2026-11-05", "kind": "prompt", "title": "Dark"},
        "summary": "s",
        "acceptance_criteria": ["Dark works"],
    }
    comments(project).create("tab:files", "Q")

    assert main(["validate", write_plan(project, VALID_PLAN)]) == 0
    assert main(["validate", write_plan(project, prompt)]) == 0
    assert main(["status", "99", "Working"]) == 1
    assert main(["reply", "7", "t-nope", "hi"]) == 1

    out, err = capsys.readouterr()
    assert out.splitlines() == [
        "OK: plan for #7 (0 elements)",
        "OK: plan for add-dark-mode-2026-11-05 (1 elements)",
    ]
    assert err.splitlines() == [
        "no .claude/work/99/ for #99: is this the project root?",
        "no thread 't-nope' for #7",
    ]
