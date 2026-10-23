"""Repository structure, release folders, and the consumer-impact rule."""

from __future__ import annotations

import hashlib
import json
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


def digest_bytes(files: list[tuple[str, bytes]]) -> str:
    """Hash kit paths and bytes the same way a release manifest does."""
    digest = hashlib.sha256()
    for relative, data in sorted(files):
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def kit_digest(root: Path, files: list[str]) -> str:
    pairs = []
    for relative in files:
        pairs.append((relative, (root / relative).read_bytes()))
    return digest_bytes(pairs)


def snapshot_from_kit(kit: Path) -> dict[str, dict[str, str]]:
    """Record the kit files that a rebuild must reproduce. The digest file is excluded."""
    files: dict[str, str] = {}
    for path in sorted(kit.rglob("*")):
        if path.is_file() and path.name != "MANIFEST.sha256":
            files[path.relative_to(kit).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"files": files}


def write_source_snapshot(kit: Path, dest: Path) -> None:
    dest.write_text(json.dumps(snapshot_from_kit(kit), indent=2) + "\n", encoding="utf-8")


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
            if answer.startswith("NO"):
                findings.append(
                    Finding(
                        "framework.consumer-impact",
                        "NO prohibits this release. There is no first-release exception",
                        name,
                    )
                )
            elif answer.startswith("YES"):
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
            else:
                findings.append(Finding("framework.consumer-impact", "consumer impact must be YES", name))
        changes = folder / "changes.txt"
        if not changes.is_file():
            findings.append(Finding("framework.release-eligibility", "release is missing changes.txt", name))
        else:
            changed = [
                line.strip()
                for line in changes.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            ]
            absent = [item for item in changed if not (root / item).exists()]
            if absent:
                findings.append(
                    Finding(
                        "framework.release-eligibility",
                        "recorded change is not in the repository: " + ", ".join(absent),
                        name,
                    )
                )
            elif not release_eligible(changed):
                findings.append(
                    Finding(
                        "framework.release-eligibility",
                        "recorded changes do not include a consumer asset, so this folder must not be a release",
                        name,
                    )
                )
        if version_tuple(version) >= (0, 2, 0):
            checklist = folder / "VALIDATION_CHECKLIST.md"
            consumer = folder / "iomr-kit" / "src" / "framework" / "consume.py"
            checklist_text = checklist.read_text(encoding="utf-8") if checklist.is_file() else ""
            if not consumer.is_file() or "consume.py" not in checklist_text:
                findings.append(
                    Finding(
                        "framework.validation-instructions",
                        "release 0.2.0 and later must ship consume.py and document how to run it",
                        name,
                    )
                )
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
        snapshot_path = folder / "source-snapshot.json"
        if not kit.is_dir() or not manifest_sha.is_file() or not snapshot_path.is_file():
            findings.append(
                Finding(
                    "framework.reproducible",
                    "release kit, MANIFEST.sha256, or source-snapshot.json is missing",
                    name,
                )
            )
        else:
            try:
                snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
                expected = snapshot.get("files") if isinstance(snapshot, dict) else None
                if not isinstance(expected, dict) or not expected:
                    raise ValueError("files")
            except (json.JSONDecodeError, ValueError):
                findings.append(Finding("framework.reproducible", "source snapshot is not a file map", name))
                expected = None
            if expected is not None:
                actual_files = {
                    path.relative_to(kit).as_posix()
                    for path in kit.rglob("*")
                    if path.is_file() and path.name != "MANIFEST.sha256"
                }
                extra = sorted(actual_files - set(expected))
                missing = sorted(set(expected) - actual_files)
                for relative in extra:
                    findings.append(Finding("framework.reproducible", f"kit has an unexpected file: {relative}", name))
                for relative in missing:
                    findings.append(Finding("framework.reproducible", f"kit is missing snapshotted file: {relative}", name))
                pairs: list[tuple[str, bytes]] = []
                for relative, recorded in sorted(expected.items()):
                    copied = kit / relative
                    if not copied.is_file():
                        continue
                    data = copied.read_bytes()
                    pairs.append((relative, data))
                    if hashlib.sha256(data).hexdigest() != recorded:
                        findings.append(
                            Finding(
                                "framework.reproducible",
                                f"kit file differs from the release snapshot: {relative}",
                                name,
                            )
                        )
                actual_digest = manifest_sha.read_text(encoding="utf-8").strip()
                if pairs and actual_digest != digest_bytes(pairs):
                    findings.append(
                        Finding(
                            "framework.reproducible",
                            "kit digest does not match the snapshotted files",
                            name,
                        )
                    )
        previous = folder
    return findings
