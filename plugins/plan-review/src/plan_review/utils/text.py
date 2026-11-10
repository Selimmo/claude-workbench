"""Checks on text a person typed."""


class BlankComment(ValueError):
    def __init__(self) -> None:
        super().__init__("comment text is empty")


def require_text(text: str) -> None:
    # Checked up front so callers get BlankComment, not a wrapped pydantic error.
    if not text.strip():
        raise BlankComment
