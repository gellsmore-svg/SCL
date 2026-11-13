"""The partial interpreter contract.

Intent dominates, Outcomes are optimisation targets, Models are the logical
shape, and Requirements are hard boundaries. Unknown solution fields are not
failures. Only a boundary a requirement actually states can fail a solution.
"""

from __future__ import annotations

from dataclasses import dataclass


LAYER_ROLES = {
    "Intent": "dominant constraint",
    "Outcome": "optimisation target",
    "Model": "logical shape",
    "Requirement": "hard boundary",
}


@dataclass(frozen=True)
class Boundary:
    requirement_id: str
    field: str
    forbidden_value: object


def failures(solution: dict, boundaries: list[Boundary]) -> list[str]:
    """Return the ids of boundaries this solution actually violates.

    Keys the boundaries do not mention are ignored, including ones the engine
    has never seen.
    """
    violated = []
    for boundary in boundaries:
        if solution.get(boundary.field) == boundary.forbidden_value:
            violated.append(boundary.requirement_id)
    return violated
