"""`install` and `upgrade`: set plan-review up in a tool. The real work is in harness/."""

from plan_review.harness.adapters import adapter_by_key
from plan_review.harness.upgrade import upgrade as upgrade_plugin


def install(key: str) -> int:
    harness = adapter_by_key(key)
    assert harness is not None  # argparse limited the choices to the adapters
    return harness.install()


def upgrade() -> int:
    return upgrade_plugin()
