"""Generic helpers: files, JSON and text. Imports nothing else from plan_review."""

from plan_review.utils.json_files import BrokenFile, named_errors, read_file, readable_errors
from plan_review.utils.safe_files import HeldLock, file_lock, write_atomically
from plan_review.utils.text import BlankComment, require_text

__all__ = [
    "BlankComment",
    "BrokenFile",
    "HeldLock",
    "file_lock",
    "named_errors",
    "read_file",
    "readable_errors",
    "require_text",
    "write_atomically",
]
