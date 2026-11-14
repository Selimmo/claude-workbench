"""Where the user's own settings folder is, on every OS and on the Windows CI job itself."""

import os
import sys
from pathlib import Path

import pytest

from plan_review.settings.user_folder import user_config_dir


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_the_user_folder_is_dot_plan_review_in_the_home_folder(platform: str) -> None:
    home = Path("/home/me")

    assert user_config_dir(platform=platform, environ={}, home=lambda: home) == (
        home / ".plan-review"
    )


def test_the_user_folder_on_windows_is_appdata_plan_review() -> None:
    appdata = Path("C:/Users/me/AppData/Roaming")

    found = user_config_dir(platform="win32", environ={"APPDATA": str(appdata)})

    assert found == appdata / "plan-review"


def test_windows_without_appdata_falls_back_to_the_roaming_folder_in_home() -> None:
    home = Path("C:/Users/me")

    found = user_config_dir(platform="win32", environ={}, home=lambda: home)

    assert found == home / "AppData" / "Roaming" / "plan-review"


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows CI job runs this one")
def test_the_user_folder_on_this_windows_machine() -> None:
    assert user_config_dir() == Path(os.environ["APPDATA"]) / "plan-review"
