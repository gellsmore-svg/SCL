"""A suspected missing interaction is a challenge, not a new fact."""

from __future__ import annotations


def potential_model_gap(observation: str, concern: str, possibilities: str, question: str) -> str:
    return (
        "POTENTIAL MODEL GAP\n"
        f"Observation: {observation}\n"
        f"Concern: {concern}\n"
        f"Possibilities: {possibilities}\n"
        f"Question: {question}\n"
    )
