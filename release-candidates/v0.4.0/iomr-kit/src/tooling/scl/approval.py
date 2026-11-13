"""Verify detached SSH signatures against an independently administered trust file.

No signing key is ever loaded here. Trust configuration belongs to the host, not
an MCP request or the project. Same-user hostile code can bypass a local service;
required trusted CI must reverify before accepting an authoritative Git change.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
from typing import Protocol

from scl.contracts import ServiceError
from scl.domain import canonical

NAMESPACE = "scl-iomr-v1"


class ApprovalVerifier(Protocol):
    def verify(self, payload: dict, approval: dict) -> None: ...


class UnavailableApproval:
    def verify(self, payload, approval):
        raise ServiceError("approval.unavailable", "Proposal-only mode: an administrator must configure SCL_ALLOWED_SIGNERS outside the checkout; a reviewer must sign the approval payload.")


class SSHApproval:
    def __init__(self, allowed_signers: Path):
        self.allowed_signers = allowed_signers.resolve()

    def verify(self, payload: dict, approval: dict):
        identity = approval.get("identity")
        signature = approval.get("signature")
        if not isinstance(identity, str) or not identity or not isinstance(signature, str) or len(signature) > 20000:
            raise ServiceError("approval.invalid", "Supply reviewer identity and a detached SSH signature of the exact approval_payload.")
        if identity != payload.get("reviewer"):
            raise ServiceError("approval.invalid", "Signature identity differs from the reviewed candidate.")
        if not self.allowed_signers.is_file():
            raise ServiceError("approval.unavailable", "Trusted allowed-signers file is missing.")
        with tempfile.TemporaryDirectory(prefix="scl-verify-") as temp:
            path = Path(temp) / "approval.sig"
            path.write_text(signature, encoding="utf-8")
            try:
                checked = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(self.allowed_signers),
                    "-I", identity, "-n", NAMESPACE, "-s", str(path)], input=canonical(payload), capture_output=True, timeout=15)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ServiceError("approval.unavailable", "OpenSSH signature verification is unavailable.") from exc
        if checked.returncode:
            raise ServiceError("approval.invalid", "Signature is invalid or reviewer is not trusted; review and sign the current payload again.")


def verifier_from_environment(root: Path) -> ApprovalVerifier:
    setting = os.environ.get("SCL_ALLOWED_SIGNERS")
    if not setting:
        return UnavailableApproval()
    path = Path(setting).resolve()
    if path.is_relative_to(root.resolve()):
        raise ServiceError("approval.trust", "Allowed signers must be administered outside the agent checkout.")
    return SSHApproval(path)
