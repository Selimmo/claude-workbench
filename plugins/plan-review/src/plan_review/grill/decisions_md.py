"""W/decisions.md, written from a confirmed grill in the format /ship wrote by hand."""

from plan_review.grill.state import Decision, GrillState


def decisions_markdown(state: GrillState, label: str) -> str:
    topics: dict[str, list[Decision]] = {}
    for decision in _standing(state.decisions):
        topics.setdefault(decision.topic, []).append(decision)
    lines = [f"# Decisions for {label}: {state.title}"]
    for topic, decisions in topics.items():
        lines += ["", f"## {topic}"]
        for d in decisions:
            why = f". {d.why}" if d.why else ""
            lines.append(f"- **{d.decision}**: {d.choice.removesuffix('.')}{why}")
    if state.out_of_scope:
        lines += ["", "## Out of scope", *(f"- {item}" for item in state.out_of_scope)]
    return "\n".join(lines) + "\n"


def _standing(decisions: list[Decision]) -> list[Decision]:
    """The decisions still standing: a replacement takes the place of the one it replaces."""
    standing: list[Decision] = []
    for decision in decisions:
        slot = next((i for i, d in enumerate(standing) if d.id == decision.replaces), None)
        if slot is None:
            standing.append(decision)
        else:
            standing[slot] = decision
    return standing
