import io
import json
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import IO

import pytest
from conftest import PACKAGE_VERSION, PLUGIN, WindowsStylePath, version_of

from plan_review.cli import main
from plan_review.cli.runtime import Runtime
from plan_review.events.status import StatusStore
from plan_review.grill.drafts import GrillDraftStore
from plan_review.grill.grill import GrillStore, SubmittedAnswer
from plan_review.plan.plan import PlanFileError, load_plan
from plan_review.review.threads import ThreadStore
from plan_review.settings.pipeline_config import PipelineConfigError, load_pipeline


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
    path = Path(write_plan(tmp_path, plan)).as_posix()
    assert exit_code == 1
    assert f"{path}: issue: 'number' must be a whole number" in err
    assert f"{path}: sumary: Extra inputs are not permitted" in err
    assert all(line.startswith(f"{path}: ") for line in err.splitlines())


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
    assert (
        capsys.readouterr().err
        == f"{path.as_posix()}: Invalid JSON: key must be a string at line 1 column 2\n"
    )


class FakeServer:
    """Stands in for uvicorn and the browser so serve() can be tested without either."""

    def __init__(self, static_dir: Path) -> None:
        self.addresses: list[tuple[str, int]] = []
        self.opened: list[str] = []
        self.runtime = Runtime(
            static_dir=static_dir, run_server=self.run, open_browser=self.opened.append
        )

    def run(self, app: object, sock: socket.socket) -> None:
        self.addresses.append(sock.getsockname())


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project root (the cwd) with a valid plan for issue 7 and a built page."""
    monkeypatch.chdir(tmp_path)
    work = tmp_path / ".plan-review" / "work" / "7"
    work.mkdir(parents=True)
    (work / "plan.json").write_text(json.dumps(VALID_PLAN))
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>plan-review</h1>")
    return tmp_path


@pytest.fixture
def server(project: Path) -> FakeServer:
    return FakeServer(project / "static")


@pytest.fixture
def windows_style_paths(server: FakeServer) -> Runtime:
    real = server.runtime
    return replace(
        real,
        work_dir=lambda r, i: WindowsStylePath(real.work_dir(r, i)),
        ensure_work_dir=lambda r, i: WindowsStylePath(real.ensure_work_dir(r, i)),
    )


def test_serve_without_a_plan_exits_2_and_starts_nothing(
    project: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["serve", "8"], runtime=server.runtime)

    assert exit_code == 2
    assert ".plan-review/work/8/plan.json: file not found" in capsys.readouterr().err
    assert server.addresses == []


def test_serve_binds_localhost_on_a_free_port_and_opens_the_browser(
    project: Path, server: FakeServer
) -> None:
    exit_code = main(["serve", "7"], runtime=server.runtime)

    host, port = server.addresses[0]
    assert exit_code == 0
    assert host == "127.0.0.1"
    assert port > 0
    assert server.opened == [f"http://127.0.0.1:{port}/"]


def test_serve_open_none_prints_the_url_instead_of_opening_a_browser(
    project: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["serve", "7", "--open", "none"], runtime=server.runtime)

    _, port = server.addresses[0]
    assert server.opened == []
    assert f"http://127.0.0.1:{port}/" in capsys.readouterr().out


def write_pipeline(project: Path, config: object) -> None:
    (project / ".plan-review" / "config.json").write_text(json.dumps(config))


def test_serve_follows_viewer_open_from_pipeline_json(project: Path, server: FakeServer) -> None:
    write_pipeline(project, {"viewer": {"open": "none"}})

    main(["serve", "7"], runtime=server.runtime)

    assert server.opened == []


def test_serve_with_open_flag_does_not_read_a_broken_config(
    project: Path, server: FakeServer
) -> None:
    (project / ".plan-review" / "config.json").write_text("{bad")

    assert main(["serve", "7", "--open", "none"], runtime=server.runtime) == 0
    assert len(server.addresses) == 1


def test_serve_open_flag_overrides_pipeline_json(project: Path, server: FakeServer) -> None:
    write_pipeline(project, {"viewer": {"open": "none"}})

    main(["serve", "7", "--open", "browser"], runtime=server.runtime)

    assert len(server.opened) == 1


def test_the_missing_viewer_page_is_reported_with_forward_slashes(
    project: Path,
    server: FakeServer,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runtime = replace(server.runtime, static_dir=WindowsStylePath(project / "missing"))

    main(["serve", "7"], runtime=runtime)

    expected = f"{(project / 'missing').as_posix()}: viewer page not built"
    assert expected in capsys.readouterr().err


def test_serve_without_a_built_page_says_how_to_build_it(
    project: Path,
    server: FakeServer,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runtime = replace(server.runtime, static_dir=project / "missing")

    exit_code = main(["serve", "7"], runtime=runtime)

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
    return ThreadStore(project / ".plan-review" / "work" / "7" / "comments.json")


def test_reply_is_signed_agent(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    thread = comments(project).create("tab:files", "Why touch the config?")
    comments(project).reply(thread.id, "Old reply.", author="claude")

    exit_code = main(["reply", "7", thread.id, "For max_hints."])

    (saved,) = comments(project).all()
    assert exit_code == 0
    assert [(m.author, m.text) for m in saved.messages][1:] == [
        ("claude", "Old reply."),
        ("agent", "For max_hints."),
    ]


def test_reply_to_unknown_thread_exits_1(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["reply", "7", "t-nope", "hi"])

    assert exit_code == 1
    assert "no thread 't-nope'" in capsys.readouterr().err


def test_threads_lists_open_threads_as_json(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    open_thread = comments(project).create("tab:files", "Open")
    done = comments(project).create("tab:risks", "Done")
    comments(project).reply(done.id, "Noted.", author="agent")
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
    write_pipeline(project, {"checks": [{"name": "all", "run": "./check.sh"}], "grill": "chat"})

    exit_code = main(["config"])

    config = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert config["checks"] == [{"name": "all", "run": "./check.sh"}]
    assert config["max_review_rounds"] == 3
    assert config["grill"] == "chat"


def test_config_with_a_bad_file_exits_1_with_readable_errors(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_pipeline(project, {"viewer": {"open": "tab"}})

    exit_code = main(["config"])

    assert exit_code == 1
    assert "viewer.open: Input should be 'browser' or 'none'" in capsys.readouterr().err


def status_of(project: Path) -> StatusStore:
    return StatusStore(project / ".plan-review" / "work" / "7" / "status.json")


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
    assert "no .plan-review/work/99/" in capsys.readouterr().err


def test_init_creates_the_issues_work_folder_and_prints_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init", "42"])

    assert exit_code == 0
    assert (tmp_path / ".plan-review" / "work" / "42").is_dir()
    assert (tmp_path / ".plan-review" / "work" / ".gitignore").is_file()
    assert capsys.readouterr().out == ".plan-review/work/42\n"


def test_serve_keeps_the_work_folder_out_of_git(project: Path, server: FakeServer) -> None:
    # The page writes comments.json and drafts.json there, even for a hand-made folder.
    main(["serve", "7"], runtime=server.runtime)

    assert (project / ".plan-review" / "work" / ".gitignore").read_text() == "*\n"


def test_paths_in_messages_use_forward_slashes_on_every_os(
    windows_style_paths: Runtime, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["serve", "8"], runtime=windows_style_paths) == 2
    assert main(["status", "99", "Answering questions"], runtime=windows_style_paths) == 1
    assert main(["init", "42"], runtime=windows_style_paths) == 0

    captured = capsys.readouterr()
    assert ".plan-review/work/8/plan.json: file not found" in captured.err
    assert "no .plan-review/work/99/ for #99" in captured.err
    assert captured.out == ".plan-review/work/42\n"


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
    work = project / ".plan-review" / "work" / "PROJ-123"
    work.mkdir()
    plan = {**VALID_PLAN, "issue": {"id": "PROJ-123", "kind": "issue", "title": "Add hints"}}
    (work / "plan.json").write_text(json.dumps(plan))
    (project / ".plan-review" / "config.json").write_text(json.dumps({"branch": "{issue}-{slug}"}))
    return work


def run_command(name: str, run_id: str, runtime: Runtime) -> int:
    commands = {
        "init": ["init", run_id],
        "serve": ["serve", run_id, "--open", "none"],
        "threads": ["threads", run_id],
        "reply": ["reply", run_id, "t-nope", "hi"],
        "status": ["status", run_id, "Working"],
        "branch": ["branch", run_id],
    }
    return main(commands[name], runtime=runtime)


COMMANDS = ["init", "serve", "threads", "reply", "status", "branch"]


@pytest.mark.parametrize(
    ("argv", "expected_out"),
    [
        (["init", "PROJ-123"], ".plan-review/work/PROJ-123\n"),
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
    before = sorted(p.name for p in (project / ".plan-review" / "work").iterdir())

    # main() returns; it must not raise SystemExit
    exit_code = run_command(name, bad, server.runtime)

    out, err = capsys.readouterr()
    assert exit_code == 2
    assert out == ""
    assert len(err.splitlines()) == 1
    assert f"'{bad}'" in err
    assert "letters, digits" in err
    assert sorted(p.name for p in (project / ".plan-review" / "work").iterdir()) == before
    assert not (project / ".plan-review" / "x").exists()
    assert server.addresses == []


def test_init_prompt_creates_a_dated_run_and_prints_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    runtime = Runtime(today=lambda: date(2026, 11, 5))

    first = main(["init", "--prompt", "add-dark-mode"], runtime=runtime)
    second = main(["init", "--prompt", "add-dark-mode"], runtime=runtime)

    assert (first, second) == (0, 0)
    assert capsys.readouterr().out.splitlines() == [
        ".plan-review/work/add-dark-mode-2026-11-05",
        ".plan-review/work/add-dark-mode-2026-11-05-2",
    ]


def test_init_prompt_rejects_a_name_that_cannot_make_a_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init", "--prompt", "../x"])

    assert exit_code == 2
    assert "invalid run id" in capsys.readouterr().err
    assert not (tmp_path / ".plan-review").exists()


def test_init_needs_either_a_run_id_or_a_prompt_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 2
    assert main(["init", "42", "--prompt", "x"]) == 2
    assert not (tmp_path / ".plan-review").exists()
    assert capsys.readouterr().err.count("plan-review init:") == 2


def test_serve_announces_the_run_by_its_label(
    project: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    key_project(project)

    main(["serve", "7", "--open", "none"], runtime=server.runtime)
    main(["serve", "PROJ-123", "--open", "none"], runtime=server.runtime)

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
        "no .plan-review/work/99/ for #99: is this the project root?",
        "no thread 't-nope' for #7",
    ]


def test_prefs_command_sets_and_prints_the_grill_mode(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["prefs", "grill"]) == 3
    assert "no grill mode chosen" in capsys.readouterr().err

    assert main(["prefs", "grill", "chat"]) == 0
    assert json.loads((project / ".plan-review" / "work" / "preferences.json").read_text()) == {
        "grill": "chat"
    }
    capsys.readouterr()

    assert main(["prefs", "grill"]) == 0
    assert capsys.readouterr().out == "chat\n"

    write_pipeline(project, {"grill": "page"})  # the team's setting wins
    assert main(["prefs", "grill"]) == 0
    assert capsys.readouterr().out == "page\n"

    assert main(["prefs", "grill", "tab"]) == 2
    assert "page or chat" in capsys.readouterr().err

    write_pipeline(project, {"grill": "tab"})
    assert main(["prefs", "grill"]) == 1
    assert "grill: Input should be 'page' or 'chat'" in capsys.readouterr().err


@pytest.mark.parametrize("content", ["{bad", '{"grill": "pagex"}'])
def test_prefs_grill_with_an_unreadable_preferences_file_exits_1(
    project: Path, capsys: pytest.CaptureFixture[str], content: str
) -> None:
    (project / ".plan-review" / "work" / "preferences.json").write_text(content)
    assert main(["prefs", "grill"]) == 1
    err = capsys.readouterr().err
    assert "preferences.json" in err
    assert "Traceback" not in err


def write_turn(project: Path, turn: object, name: str = "turn.json") -> Path:
    path = project / name
    path.write_text(json.dumps(turn))
    return path


FIRST_TURN = {
    "title": "Add hints",
    "round": [
        {
            "id": "q1",
            "title": "Cost?",
            "explanation": "Why it matters.",
            "choices": [
                {"id": "a", "label": "Free", "description": "No cost."},
                {"id": "b", "label": "Points", "description": "Costs points."},
            ],
        }
    ],
}


def test_grill_post_appends_a_turn_and_reports_a_bad_one_readably(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["grill", "post", "7", str(write_turn(project, FIRST_TURN))]) == 0
    saved = json.loads((project / ".plan-review" / "work" / "7" / "grill.json").read_text())
    assert saved["rounds"][0]["questions"][0]["id"] == "q1"
    capsys.readouterr()

    bad = write_turn(project, {"round": [{**FIRST_TURN["round"][0], "choices": []}]}, "bad.json")
    assert main(["grill", "post", "7", str(bad)]) == 1
    assert "round.0.choices: needs at least two choices" in capsys.readouterr().err

    assert main(["grill", "post", "7", str(project / "nope.json")]) == 2
    assert "nope.json: file not found" in capsys.readouterr().err


def test_grill_post_refuses_a_misspelled_turn_key(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    typo = write_turn(project, {**FIRST_TURN, "decsions": []}, "typo.json")

    assert main(["grill", "post", "7", str(typo)]) == 1

    assert "decsions: Extra inputs are not permitted" in capsys.readouterr().err


def grill_store(project: Path) -> GrillStore:
    return GrillStore(project / ".plan-review" / "work" / "7" / "grill.json")


def test_grill_pending_prints_whether_confirmed_and_what_is_pending(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["grill", "pending", "7"]) == 1
    assert "grill.json: file not found" in capsys.readouterr().err

    main(["grill", "post", "7", str(write_turn(project, FIRST_TURN))])
    grill_store(project).submit([SubmittedAnswer(question_id="q1", kind="choice", choice_id="b")])
    capsys.readouterr()

    assert main(["grill", "pending", "7"]) == 0

    printed = json.loads(capsys.readouterr().out)
    assert printed["confirmed"] is False
    assert printed["pending"][0]["answers"][0]["choice"] == "Points"


def test_grill_decisions_writes_decisions_md_only_once_confirmed(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    decided = {
        **FIRST_TURN,
        "decisions": [
            {
                "id": "d1",
                "topic": "Cost",
                "decision": "Hints cost",
                "choice": "Points",
                "question_id": "q1",
            }
        ],
    }
    assert main(["grill", "decisions", "7"]) == 1
    assert "grill.json: file not found" in capsys.readouterr().err

    main(["grill", "post", "7", str(write_turn(project, decided))])
    store = grill_store(project)
    decisions = project / ".plan-review" / "work" / "7" / "decisions.md"

    assert main(["grill", "decisions", "7"]) == 1
    assert "not confirmed" in capsys.readouterr().err
    assert not decisions.exists()

    store.submit([SubmittedAnswer(question_id="q1", kind="choice", choice_id="b")])
    main(["grill", "post", "7", str(write_turn(project, {"done": True}, "done.json"))])
    store.confirm()

    assert main(["grill", "decisions", "7"]) == 0
    assert decisions.read_text() == (
        "# Decisions for #7: Add hints\n\n## Cost\n- **Hints cost**: Points\n"
    )


def test_grill_schema_prints_the_turn_schema(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["grill", "schema"]) == 0

    schema = json.loads(capsys.readouterr().out)
    assert {"replies", "decisions", "out_of_scope", "round", "done"} <= set(schema["properties"])


def test_serve_starts_from_grill_json_and_points_at_the_grill_page(
    project: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / ".plan-review" / "work" / "7" / "plan.json").unlink()
    assert main(["serve", "7"], runtime=server.runtime) == 2  # neither a plan nor a grill
    assert ".plan-review/work/7/plan.json: file not found" in capsys.readouterr().err
    assert server.addresses == []

    main(["grill", "post", "7", str(write_turn(project, FIRST_TURN))])
    capsys.readouterr()

    assert main(["serve", "7"], runtime=server.runtime) == 0

    _, port = server.addresses[0]
    url = f"http://127.0.0.1:{port}/grill"
    assert f"plan-review: #7 at {url} (Ctrl+C to stop)" in capsys.readouterr().out
    assert server.opened == [url]


def test_serve_with_an_invalid_plan_still_exits_1_even_with_a_grill(
    project: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["grill", "post", "7", str(write_turn(project, FIRST_TURN))])
    (project / ".plan-review" / "work" / "7" / "plan.json").write_text("{}")

    assert main(["serve", "7"], runtime=server.runtime) == 1
    assert server.addresses == []


def test_serve_with_an_invalid_plan_names_the_file(
    project: Path, server: FakeServer, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / ".plan-review" / "work" / "7" / "plan.json").write_text("{bad")

    assert main(["serve", "7"], runtime=server.runtime) == 1

    err = capsys.readouterr().err
    assert err.splitlines() == [
        ".plan-review/work/7/plan.json: Invalid JSON: key must be a string at line 1 column 2"
    ]
    assert server.addresses == []


def test_grill_with_no_subcommand_prints_help_and_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["grill"]) == 2

    assert "post" in capsys.readouterr().err


def test_grill_pending_with_an_unreadable_grill_json_exits_1(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / ".plan-review" / "work" / "7").mkdir(parents=True, exist_ok=True)
    (project / ".plan-review" / "work" / "7" / "grill.json").write_text("{bad")

    assert main(["grill", "pending", "7"]) == 1

    assert capsys.readouterr().err == (
        ".plan-review/work/7/grill.json: Invalid JSON: key must be a string at line 1 column 2\n"
    )


@pytest.mark.parametrize("argv", [["threads", "7"], ["reply", "7", "t-1", "hi"]])
def test_commands_print_a_broken_files_named_lines_and_exit_1(
    argv: list[str], project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    comments = project / ".plan-review" / "work" / "7" / "comments.json"
    comments.write_bytes(b"{bad")

    assert main(argv) == 1

    err = capsys.readouterr().err
    assert err == (
        ".plan-review/work/7/comments.json: Invalid JSON: key must be a string at line 1 column 2\n"
    )
    assert comments.read_bytes() == b"{bad"


@pytest.mark.parametrize("extra", [["working"], ["--clear"]])
def test_status_over_a_broken_status_json_says_where_it_was_moved(
    extra: list[str], project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    work = project / ".plan-review" / "work" / "7"
    (work / "status.json").write_bytes(b"{bad")

    assert main(["status", "7", *extra]) == 0

    assert capsys.readouterr().err == (
        ".plan-review/work/7/status.json was broken: "
        "moved to .plan-review/work/7/status.json.broken\n"
    )
    assert (work / "status.json.broken").read_bytes() == b"{bad"
    assert (work / "status.json").exists() == (extra == ["working"])


def test_blank_status_text_over_a_broken_status_json_moves_nothing(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    work = project / ".plan-review" / "work" / "7"
    (work / "status.json").write_bytes(b"{bad")

    assert main(["status", "7", "  "]) == 1

    assert capsys.readouterr().err == "status text is empty\n"
    assert (work / "status.json").read_bytes() == b"{bad"
    assert not (work / "status.json.broken").exists()


def test_grill_post_keeps_only_the_drafts_of_questions_still_open(project: Path) -> None:
    work = project / ".plan-review" / "work" / "7"
    q1 = FIRST_TURN["round"][0]
    first = {**FIRST_TURN, "round": [q1, {**q1, "id": "q2", "title": "Where?"}]}
    assert main(["grill", "post", "7", str(write_turn(project, first))]) == 0
    GrillStore(work / "grill.json").submit(
        [
            SubmittedAnswer(question_id="q1", kind="other", text="Mine"),
            SubmittedAnswer(question_id="q2", kind="other", text="Also mine"),
        ]
    )
    drafts = work / "grill_drafts.json"
    draft = {"kind": "choice", "choice_id": "a", "text": "maybe"}
    drafts.write_text(json.dumps({"q1": draft, "q2": draft}))

    turn = {
        "replies": [{"question_id": "q2", "text": "Tell me more"}],
        "decisions": [
            {"id": "d1", "topic": "T", "decision": "Mine", "choice": "Mine", "question_id": "q1"}
        ],
    }
    assert main(["grill", "post", "7", str(write_turn(project, turn, "t2.json"))]) == 0

    assert json.loads(drafts.read_text()) == {"q2": draft}


def test_grill_post_leaves_a_drafts_file_alone_when_all_its_drafts_are_still_open(
    project: Path,
) -> None:
    work = project / ".plan-review" / "work" / "7"
    q1 = FIRST_TURN["round"][0]
    first = {**FIRST_TURN, "round": [q1, {**q1, "id": "q2", "title": "Where?"}]}
    assert main(["grill", "post", "7", str(write_turn(project, first))]) == 0
    GrillStore(work / "grill.json").submit(
        [
            SubmittedAnswer(question_id="q1", kind="other", text="Mine"),
            SubmittedAnswer(question_id="q2", kind="other", text="Also mine"),
        ]
    )
    drafts = work / "grill_drafts.json"
    drafts.write_text(
        json.dumps({"q2": {"kind": "choice", "choice_id": "a", "text": "maybe"}}, indent=4)
    )
    before = drafts.read_bytes()
    mtime = drafts.stat().st_mtime_ns
    time.sleep(0.05)

    turn = {
        "replies": [{"question_id": "q2", "text": "Tell me more"}],
        "decisions": [
            {"id": "d1", "topic": "T", "decision": "Mine", "choice": "Mine", "question_id": "q1"}
        ],
    }
    assert main(["grill", "post", "7", str(write_turn(project, turn, "t2.json"))]) == 0

    assert drafts.read_bytes() == before
    assert drafts.stat().st_mtime_ns == mtime


def test_grill_post_does_not_create_grill_drafts_json(project: Path) -> None:
    work = project / ".plan-review" / "work" / "7"

    assert main(["grill", "post", "7", str(write_turn(project, FIRST_TURN))]) == 0

    assert (work / "grill.json").exists()
    assert not (work / "grill_drafts.json").exists()


def test_grill_post_waits_for_the_drafts_lock(project: Path) -> None:
    work = project / ".plan-review" / "work" / "7"
    turn = write_turn(project, FIRST_TURN)
    codes: list[int] = []
    thread = threading.Thread(target=lambda: codes.append(main(["grill", "post", "7", str(turn)])))

    with GrillDraftStore(work / "grill_drafts.json").held():  # a submit in progress
        thread.start()
        time.sleep(0.3)  # the post is now waiting for the lock
        posted_early = (work / "grill.json").exists()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert not posted_early
    assert codes == [0]


def test_grill_post_still_succeeds_when_grill_drafts_json_is_broken(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    work = project / ".plan-review" / "work" / "7"
    work.mkdir(parents=True, exist_ok=True)
    (work / "grill_drafts.json").write_text("{nope")

    assert main(["grill", "post", "7", str(write_turn(project, FIRST_TURN))]) == 0

    err = capsys.readouterr().err
    assert err.splitlines() == [
        ".plan-review/work/7/grill_drafts.json: "
        "Invalid JSON: key must be a string at line 1 column 2"
    ]
    assert json.loads((work / "grill.json").read_text())["rounds"][0]["questions"][0]["id"] == "q1"
    assert (work / "grill_drafts.json").read_bytes() == b"{nope"


FIXTURES = Path(__file__).parent / "fixtures"


def test_validate_reports_each_shape_problem_with_the_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    old = FIXTURES / "plan-0.1.11.json"

    assert main(["validate", str(old)]) == 1

    lines = capsys.readouterr().err.splitlines()
    assert lines
    assert all(line.startswith(f"{old.as_posix()}: class:") for line in lines)
    assert f"{old.as_posix()}: class:HintPolicy: side is required (front or back)" in lines

    new = Path(__file__).parents[1] / "examples" / "plan.json"
    assert main(["validate", str(new)]) == 0
    assert capsys.readouterr().out.startswith("OK")


def test_schema_says_validate_requires_side_name_and_kind(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["schema"]) == 0

    defs = json.loads(capsys.readouterr().out)["$defs"]
    for field in (
        defs["PlanClass"]["properties"]["side"],
        defs["Member"]["properties"]["name"],
        defs["Member"]["properties"]["kind"],
    ):
        assert "validate` requires it" in field["description"]


def write_old_config(project: Path, config: object) -> Path:
    old = project / ".claude" / "pipeline.json"
    old.parent.mkdir(exist_ok=True)
    old.write_text(json.dumps(config))
    return old


def snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None
        for p in sorted(root.rglob("*"))
    }


def test_config_reads_the_new_file(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_pipeline(project, {"max_review_rounds": 5})

    assert main(["config"]) == 0

    out, err = capsys.readouterr()
    assert json.loads(out)["max_review_rounds"] == 5
    assert err == ""


def test_config_with_only_the_old_file_keeps_stdout_clean_and_hints_on_stderr(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_old_config(project, {"max_review_rounds": 4})

    assert main(["config"]) == 0

    out, err = capsys.readouterr()
    assert json.loads(out)["max_review_rounds"] == 4
    assert len(err.splitlines()) == 1
    assert ".claude/pipeline.json" in err
    assert ".plan-review/config.json" in err


def test_prefs_grill_with_the_old_file_and_no_mode_still_prints_the_move_hint(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_old_config(project, {"max_review_rounds": 4})

    assert main(["prefs", "grill"]) == 3

    err = capsys.readouterr().err
    assert ".claude/pipeline.json" in err
    assert ".plan-review/config.json" in err


def test_reading_the_old_config_writes_and_moves_nothing(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_old_config(project, {"max_review_rounds": 4})
    shutil.rmtree(project / ".plan-review")
    before = snapshot(project)

    main(["config"])

    assert snapshot(project) == before
    assert not (project / ".plan-review").exists()


def test_a_broken_new_config_is_an_error_even_with_an_old_file(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_pipeline(project, {"viewer": 3})
    write_old_config(project, {"max_review_rounds": 4})

    assert main(["config"]) == 1

    err = capsys.readouterr().err
    assert ".plan-review/config.json" in err
    assert "pipeline.json" not in err


def test_a_broken_old_config_is_reported_under_its_own_name(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_old_config(project, {"viewer": 3})

    assert main(["config"]) == 1

    assert ".claude/pipeline.json" in capsys.readouterr().err


def test_branch_uses_the_old_config_and_prints_only_the_branch_on_stdout(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_old_config(project, {"branch": "feat/{issue}-{slug}"})

    assert main(["branch", "7"]) == 0

    out, err = capsys.readouterr()
    assert out.startswith("feat/7-")
    assert len(out.splitlines()) == 1
    assert ".claude/pipeline.json" in err


def test_serve_prints_its_url_line_before_the_hint(
    project: Path, server: FakeServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_old_config(project, {"viewer": {"open": "none"}})
    combined = io.StringIO()
    monkeypatch.setattr(sys, "stdout", combined)
    monkeypatch.setattr(sys, "stderr", combined)

    assert main(["serve", "7"], runtime=server.runtime) == 0

    lines = combined.getvalue().splitlines()
    assert server.opened == []
    assert lines[0].startswith("plan-review: #7 at http://127.0.0.1:")
    assert ".claude/pipeline.json" in lines[1]
    assert len(lines) == 2


def test_prefs_grill_reads_the_old_file_when_it_is_the_only_one(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old = project / ".claude" / "work" / "preferences.json"
    old.parent.mkdir(parents=True)
    old.write_text('{"grill": "chat"}')
    before = snapshot(project)

    assert main(["prefs", "grill"]) == 0

    out, err = capsys.readouterr()
    assert out == "chat\n"
    assert len(err.splitlines()) == 1
    assert "plan-review prefs grill" in err
    assert snapshot(project) == before


def test_prefs_grill_from_the_old_config_hints_on_stderr(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_old_config(project, {"grill": "page"})

    assert main(["prefs", "grill"]) == 0

    out, err = capsys.readouterr()
    assert out == "page\n"
    assert ".claude/pipeline.json" in err
    assert ".plan-review/config.json" in err


def test_a_broken_old_preferences_file_is_reported_under_its_own_name(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old = project / ".claude" / "work" / "preferences.json"
    old.parent.mkdir(parents=True)
    old.write_text("{bad")

    assert main(["prefs", "grill"]) == 1

    assert ".claude/work/preferences.json" in capsys.readouterr().err


def test_prefs_grill_set_writes_the_new_file_and_leaves_the_old_one(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old = project / ".claude" / "work" / "preferences.json"
    old.parent.mkdir(parents=True)
    old.write_text('{"grill": "chat"}')

    assert main(["prefs", "grill", "page"]) == 0
    capsys.readouterr()

    assert old.read_text() == '{"grill": "chat"}'
    assert json.loads((project / ".plan-review" / "work" / "preferences.json").read_text()) == {
        "grill": "page"
    }
    assert main(["prefs", "grill"]) == 0
    out, err = capsys.readouterr()
    assert (out, err) == ("page\n", "")


def test_an_old_run_folder_is_left_alone(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    old = project / ".claude" / "work" / "42"
    old.mkdir(parents=True)
    (old / "plan.json").write_text("{}")

    assert main(["init", "42"]) == 0

    assert (project / ".plan-review" / "work" / "42").is_dir()
    assert snapshot(old) == {"plan.json": b"{}"}
    assert [p.name for p in old.parent.iterdir()] == ["42"]


def _help(capsys: pytest.CaptureFixture[str], command: list[str]) -> str:
    with pytest.raises(SystemExit):
        main([*command, "--help"])
    return capsys.readouterr().out


def test_help_texts_say_the_agent(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLUMNS", "200")
    top = _help(capsys, [])
    serve_help = _help(capsys, ["serve"])

    assert "answer a comment thread as the agent" in top
    assert "what the agent is doing" in top
    assert "Claude" not in top
    assert ".plan-review/config.json" in serve_help
    assert ".claude" not in serve_help


def test_help_does_not_list_the_internal_viewer_process(
    capsys: pytest.CaptureFixture[str],
) -> None:
    top = _help(capsys, [])

    assert "viewer-process" not in top
    assert "SUPPRESS" not in top


HELP_TEXTS = json.loads((PLUGIN / "tests" / "fixtures" / "help-0.4.0.json").read_text("utf-8"))


@pytest.mark.parametrize("command", sorted(HELP_TEXTS), ids=lambda c: c or "plan-review")
def test_every_help_text_is_the_same_as_before(
    command: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COLUMNS", "80")
    monkeypatch.setenv("PYTHON_COLORS", "0")

    with pytest.raises(SystemExit) as exited:
        main([*command.split(), "--help"])

    assert exited.value.code == 0
    assert capsys.readouterr().out == HELP_TEXTS[command]


def test_runs_as_python_m_plan_review_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "plan_review.cli", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == f"plan-review {PACKAGE_VERSION}\n"
