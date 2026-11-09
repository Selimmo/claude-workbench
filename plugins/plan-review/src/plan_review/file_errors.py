"""Naming a run's file in its error lines, and reading one that may be broken."""

from pathlib import Path

from pydantic import TypeAdapter, ValidationError


def readable_errors(error: ValidationError) -> list[str]:
    """One `location: message` line per error; whole-model checks have no location."""
    lines: list[str] = []
    for e in error.errors():
        where = ".".join(str(part) for part in e["loc"])
        message = e["msg"].removeprefix("Value error, ")  # pydantic's wrapper adds nothing
        lines.append(f"{where}: {message}" if where else message)
    return lines


def named_errors(path: Path, error: ValidationError) -> list[str]:
    """`<path>: <line>` for each readable error line."""
    return [f"{path.as_posix()}: {line}" for line in readable_errors(error)]


class BrokenFile(Exception):
    """A run file that can't be read or written, one named line per problem."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


def read_file[T](path: Path, adapter: TypeAdapter[T]) -> T | None:
    """The parsed file; None if there is no file; BrokenFile if it doesn't parse."""
    if not path.is_file():
        return None
    try:
        return adapter.validate_json(path.read_bytes())
    except ValidationError as error:
        raise BrokenFile(named_errors(path, error)) from error
