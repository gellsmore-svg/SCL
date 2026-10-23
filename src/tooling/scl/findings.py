"""Validation findings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    rule: str
    message: str
    record_id: str = ""

    def format(self) -> str:
        where = f" [{self.record_id}]" if self.record_id else ""
        return f"{self.rule}{where}: {self.message}"
