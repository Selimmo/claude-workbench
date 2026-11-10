"""How a tool gets plan-review installed and upgraded."""

from plan_review.harness.distribution.base import Distribution, SelfInstall, ToolInstall
from plan_review.harness.distribution.marketplace import MarketplacePlugin
from plan_review.harness.distribution.wheel import WheelInstall

__all__ = ["Distribution", "MarketplacePlugin", "SelfInstall", "ToolInstall", "WheelInstall"]
