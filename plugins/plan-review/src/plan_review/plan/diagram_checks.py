"""What the viewer can draw: the extra checks `plan-review validate` runs."""

from plan_review.plan.model import Plan, PlanClass, Relation


def _is_changed(cls: PlanClass) -> bool:
    return cls.status != "unchanged" or any(m.status != "unchanged" for m in cls.members)


def _class_problems(cls: PlanClass) -> list[str]:
    found: list[str] = []
    if cls.side is None:
        found.append(f"{cls.id}: side is required (front or back)")
    if cls.kind == "function":
        found.append(
            f"{cls.id}: a plain function gets no box of its own; "
            "put it in its module's box (kind 'module') as a method"
        )
    for member in cls.members:
        if member.name is None:
            found.append(f"{member.id}: name is required")
        if member.kind is None:
            found.append(f"{member.id}: kind is required (property or method)")
    return found


def _relation_problem(rel: Relation, a: PlanClass, b: PlanClass) -> list[str]:
    found: list[str] = []
    if rel.kind in ("inherits", "implements"):
        found.append(
            f"{rel.id}: '{rel.kind}' is not drawn as an arrow; list the base in the class's 'bases'"
        )
    if a.side and b.side and a.side != b.side:
        found.append(
            f"{rel.id}: links a {a.side} class to a {b.side} class; front and back are drawn apart"
        )
    return found


def _linked_to_changed(plan: Plan) -> set[str]:
    """Ids of the classes linked, on their own side, to a changed class."""
    by_id = {c.id: c for c in plan.classes}
    linked: set[str] = set()
    for rel in plan.relations:
        a, b = by_id[rel.source], by_id[rel.target]
        if a.side != b.side:
            continue
        for one, other in ((a, b), (b, a)):
            if _is_changed(other):
                linked.add(one.id)
    return linked


def shape_problems(plan: Plan) -> list[str]:
    """What `plan-review validate` requires beyond what loading accepts: one line per
    problem, starting with the element id. Old plans load without these; the viewer
    draws them the old way."""
    by_id = {c.id: c for c in plan.classes}
    found = [line for cls in plan.classes for line in _class_problems(cls)]
    for rel in plan.relations:
        found += _relation_problem(rel, by_id[rel.source], by_id[rel.target])
    linked = _linked_to_changed(plan)
    found += [
        f"{cls.id}: unchanged and linked to no changed class on its side, "
        "so it is not drawn; leave it out of the plan"
        for cls in plan.classes
        if cls.side and not _is_changed(cls) and cls.id not in linked
    ]
    return found
