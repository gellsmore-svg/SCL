#!/usr/bin/env python3
"""Framework self-check. Prints VALID and errors: 0 when the layout holds."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "tooling"))

from scl.framework import framework_findings  # noqa: E402


def main() -> int:
    findings = framework_findings(ROOT)
    if findings:
        for finding in findings:
            print(finding.format())
        print(f"errors: {len(findings)}")
        return 1
    print("VALID")
    print("errors: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
