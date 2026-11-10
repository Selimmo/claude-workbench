"""RunPaths names every file a run keeps, once."""

from pathlib import Path

from plan_review.paths.run_paths import RunPaths


def test_run_paths_names_every_run_file_in_the_run_folder(tmp_path: Path) -> None:
    paths = RunPaths(tmp_path)

    assert {
        "plan": paths.plan,
        "comments": paths.comments,
        "drafts": paths.drafts,
        "status": paths.status,
        "grill": paths.grill,
        "grill_drafts": paths.grill_drafts,
        "last_event": paths.last_event,
        "events": paths.events,
        "approved": paths.approved,
        "viewer": paths.viewer,
        "viewer_log": paths.viewer_log,
        "decisions": paths.decisions,
    } == {
        "plan": tmp_path / "plan.json",
        "comments": tmp_path / "comments.json",
        "drafts": tmp_path / "drafts.json",
        "status": tmp_path / "status.json",
        "grill": tmp_path / "grill.json",
        "grill_drafts": tmp_path / "grill_drafts.json",
        "last_event": tmp_path / "last_event.json",
        "events": tmp_path / "events.json",
        "approved": tmp_path / "approved.json",
        "viewer": tmp_path / "viewer.json",
        "viewer_log": tmp_path / "viewer.log",
        "decisions": tmp_path / "decisions.md",
    }
