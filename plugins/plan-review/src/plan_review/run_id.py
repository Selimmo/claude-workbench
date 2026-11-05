"""A run id names a work folder: an issue key (`42`, `PROJ-123`) or a dated prompt name."""

import re

RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class InvalidRunId(ValueError):
    pass


def check_run_id(text: str) -> str:
    """`text` if it is a valid run id; otherwise raise InvalidRunId."""
    if not RUN_ID.fullmatch(text):
        raise InvalidRunId(
            f"invalid run id '{text}': use letters, digits, '.', '_' and '-' ({RUN_ID.pattern})"
        )
    return text


def label(run_id: str) -> str:
    """How a run reads in messages and the page: `#42` for an all-digit id, else the id."""
    return f"#{run_id}" if run_id.isdecimal() else run_id
