"""Repository structure, release folders, and the consumer-impact rule."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from scl.findings import Finding

REQUIRED_DIRS = ("src", "releases", "meta/iomr-model", "changelog", "docs")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
CONSUMER_PREFIXES = (
    "src/templates/",
    "src/prompts/",
    "src/schemas/",
    "src/framework/",
    "src/tooling/",
    "src/examples/",
    "docs/",
)
CONSUMER_FILES = {"validate-framework.py"}
INTERNAL_PREFIXES = ("meta/", "internal/", "research/", "design-work/", "changelog/")
LIFECYCLE_MARKERS = (
    "1. Meta-model is a release candidate.",
    "2. Downstream artifacts were generated from the model.",
    "3. AI-test passed",
)


def version_tuple(text: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(text)
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in text.split("."))  # type: ignore[return-value]


def release_dirs(root: Path) -> list[Path]:
    base = root / "releases"
    if not base.is_dir():
        return []
    found = [path for path in base.iterdir() if path.is_dir() and path.name.startswith("v")]
    return sorted(found, key=lambda path: version_tuple(path.name[1:]))


def classify_path(path: str) -> str:
    """Return consumer, internal, or other for one repo-relative path."""
    relative = path.lstrip("./")
    if relative in CONSUMER_FILES or any(relative.startswith(prefix) for prefix in CONSUMER_PREFIXES):
        return "consumer"
    if any(relative.startswith(prefix) for prefix in INTERNAL_PREFIXES):
        return "internal"
    return "other"


def release_eligible(paths: list[str]) -> bool:
    """A release may be cut only when a project-consumable asset changed."""
    return any(classify_path(path) == "consumer" for path in paths)


def kit_sources(root: Path) -> list[str]:
    listing = root / "src" / "framework" / "kit-files.txt"
    lines = listing.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def kit_digest(root: Path, files: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(files):
        data = (root / relative).read_bytes()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def build_kit(root: Path, dest: Path) -> str:
    files = kit_sources(root)
    if dest.exists():
        for child in dest.rglob("*"):
            if child.is_file():
                child.unlink()
    for relative in files:
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / relative).read_bytes())
    digest = kit_digest(root, files)
    (dest / "MANIFEST.sha256").write_text(digest + "\n", encoding="utf-8")
    return digest


def _external_reference(text: str) -> str | None:
    if "http://" in text or "https://" in text:
        return "network URL"
    if "/home/" in text:
        return "absolute filesystem path"
    for line in text.splitlines():
        if "](../" in line or "](/" in line or "](http" in line:
            return "link that leaves the release folder"
    return None


def framework_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative in REQUIRED_DIRS:
        if not (root / relative).is_dir():
            findings.append(Finding("framework.structure", f"missing directory {relative}"))
    manifest = root / "iomr-manifest.json"
    if not manifest.is_file():
        findings.append(Finding("framework.structure", "missing root iomr-manifest.json"))
    if not (root / "validate-framework.py").is_file():
        findings.append(Finding("framework.structure", "missing validate-framework.py"))
    if not (root / "src" / "framework" / "kit-files.txt").is_file():
        findings.append(Finding("framework.structure", "missing src/framework/kit-files.txt"))

    releases = release_dirs(root)
    if not releases:
        findings.append(Finding("framework.release-version", "no release folder"))
        return findings

    previous = None
    for folder in releases:
        name = folder.name
        version = name[1:]
        if not SEMVER.fullmatch(version):
            findings.append(Finding("framework.release-version", f"{name} is not vX.Y.Z", name))
            continue
        manifest_path = folder / "iomr-manifest.json"
        if not manifest_path.is_file():
            findings.append(Finding("framework.release-version", "release is missing iomr-manifest.json", name))
        else:
            import json

            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if data.get("version") != version:
                findings.append(
                    Finding(
                        "framework.release-version",
                        f"manifest version {data.get('version')} does not match folder {name}",
                        name,
                    )
                )
        for required in ("RELEASE.md", "CHANGELOG.md"):
            if not (folder / required).is_file():
                findings.append(Finding("framework.change-docs", f"missing {required}", name))
        if not (folder / "VALIDATION_CHECKLIST.md").is_file():
            findings.append(Finding("framework.validation-instructions", "missing VALIDATION_CHECKLIST.md", name))
        if previous is not None:
            upgrade = folder / f"UPGRADE_FROM_{previous.name}.md"
            if not upgrade.is_file():
                findings.append(Finding("framework.upgrade-guide", f"missing {upgrade.name}", name))
        release_text = (folder / "RELEASE.md").read_text(encoding="utf-8") if (folder / "RELEASE.md").is_file() else ""
        if "Green light:" not in release_text:
            findings.append(Finding("framework.green-light", "release has no documented human green light", name))
        for marker in LIFECYCLE_MARKERS:
            if marker not in release_text:
                findings.append(Finding("framework.lifecycle", f"missing lifecycle marker: {marker}", name))
        if "imk validate --strict" not in release_text or "validate-framework.py" not in release_text:
            findings.append(Finding("framework.ai-test", "release does not record the AI-test commands", name))
        if "Consumer impact:" not in release_text:
            findings.append(Finding("framework.consumer-impact", "release does not answer the consumer impact test", name))
        else:
            impact_line = next((line for line in release_text.splitlines() if "Consumer impact:" in line), "")
            answer = impact_line.split("Consumer impact:", 1)[1].strip().upper()
            if answer.startswith("YES"):
                difference = ""
                for line in release_text.splitlines():
                    if line.startswith("Behavioural difference:"):
                        difference = line.split(":", 1)[1].strip()
                if len(difference) < 20:
                    findings.append(
                        Finding(
                            "framework.consumer-impact",
                            "YES impact requires a behavioural difference of at least 20 characters",
                            name,
                        )
                    )
            elif not answer.startswith("NO"):
                findings.append(Finding("framework.consumer-impact", "consumer impact must be YES or NO", name))
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".md", ".json", ".txt", ""} and path.name != "MANIFEST.sha256":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            reason = _external_reference(text)
            if reason:
                findings.append(Finding("framework.self-contained", f"{path.relative_to(folder)} contains a {reason}", name))
        kit = folder / "iomr-kit"
        manifest_sha = kit / "MANIFEST.sha256"
        if not kit.is_dir() or not manifest_sha.is_file():
            findings.append(Finding("framework.reproducible", "release kit or MANIFEST.sha256 is missing", name))
        else:
            files = kit_sources(root)
            expected = kit_digest(root, files)
            actual = manifest_sha.read_text(encoding="utf-8").strip()
            if actual != expected:
                findings.append(Finding("framework.reproducible", "kit digest does not match a rebuild from source", name))
            for relative in files:
                source = root / relative
                copied = kit / relative
                if not copied.is_file() or copied.read_bytes() != source.read_bytes():
                    findings.append(Finding("framework.reproducible", f"kit file differs from source: {relative}", name))
        previous = folder
    return findings
