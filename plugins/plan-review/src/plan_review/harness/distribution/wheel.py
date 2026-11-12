"""A tool whose files plan-review writes itself; plan-review comes from a release's wheel.

`plan-review` is installed with `uv tool install` from the wheel of a release, so an upgrade
installs the newest wheel and then writes the tool's files again. Several tools can use this:
they all see the same uv-installed copy, so each also needs its own marked files in place to
count it as its own.
"""

import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePath

from plan_review.harness.distribution import releases


@dataclass
class WheelInstall:
    """`files` is the folder inside the package that holds the files, `targets` says where
    each one (by its path inside `files`) goes, and `mark` is in every file this writes: only
    a file with it may be replaced."""

    key: str
    tool_name: str
    files: Path
    targets: Callable[[PurePath], Path]
    mark: str

    def installed_at(self, package_root: Path) -> bool:
        """A copy `uv tool install` made (a folder above it holds uv-receipt.toml), for a
        tool whose own files are in place."""
        from_uv = any(
            (folder / "uv-receipt.toml").is_file()
            for folder in [package_root, *package_root.parents]
        )
        return from_uv and self.files_in_place()

    def files_in_place(self) -> bool:
        """Whether one of this tool's files is where it goes and holds the mark."""
        return any(
            target.is_file() and self.mark in target.read_text("utf-8", "replace")
            for target in self._targets().values()
        )

    def _targets(self) -> dict[Path, Path]:
        """Each file in `files`, with where it goes."""
        return {
            source: self.targets(source.relative_to(self.files))
            for source in sorted(p for p in self.files.rglob("*") if p.is_file())
        }

    def upgrade_commands(self) -> list[str]:
        return [
            "uv tool install --force "
            f"<the plan_review-*.whl of the newest release: {releases.RELEASES_PAGE}>",
            f"plan-review install {self.key}",
        ]

    def _print_commands(self, heading: str) -> None:
        print(heading, file=sys.stderr)
        for command in self.upgrade_commands():
            print(f"  {command}", file=sys.stderr)

    def upgrade(self) -> int:
        uv = shutil.which("uv")
        if uv is None:
            self._print_commands("`uv` not found on PATH: install uv first, then run:")
            return 1
        try:
            wheel = releases.newest_wheel(releases.fetch_releases())
        except (OSError, ValueError) as error:
            self._print_commands(f"can't reach GitHub ({error}). To upgrade, run:")
            return 1
        if wheel is None:
            self._print_commands("no plan-review release with a wheel was found. To upgrade, run:")
            return 1
        code = subprocess.run([uv, "tool", "install", "--force", wheel], check=False).returncode
        if code != 0:
            return code
        # The new copy writes the files: this process still runs the old code.
        binary = self._installed_binary(uv)
        if binary is None:
            self._print_commands("uv installed it, but `plan-review` is not on PATH. Run:")
            return 1
        return subprocess.run([binary, "install", self.key], check=False).returncode

    def _installed_binary(self, uv: str) -> str | None:
        """The `plan-review` uv just installed, from uv's tool bin folder (maybe not on PATH)."""
        asked = subprocess.run(
            [uv, "tool", "dir", "--bin"], capture_output=True, text=True, check=False
        )
        folder = (asked.stdout or "").strip() if asked.returncode == 0 else ""
        if folder:
            for name in ("plan-review", "plan-review.exe"):
                if (Path(folder) / name).is_file():
                    return str(Path(folder) / name)
        return shutil.which("plan-review")

    def install(self) -> int:
        """Write the files into the owner's home folders."""
        targets = self._targets()
        if not targets:
            print(
                f"{self.files.as_posix()}: the {self.tool_name} files are missing from this copy",
                file=sys.stderr,
            )
            return 1
        foreign = [
            t
            for t in targets.values()
            if t.is_file() and self.mark not in t.read_text("utf-8", "replace")
        ]
        if foreign:  # all or nothing: the owner's own files are never replaced
            for target in foreign:
                print(
                    f"{target.as_posix()}: not written by plan-review; left alone", file=sys.stderr
                )
            print("move it away or rename it, then run the command again", file=sys.stderr)
            return 1
        for source, target in targets.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            print(f"wrote {target.as_posix()}")
        return 0
