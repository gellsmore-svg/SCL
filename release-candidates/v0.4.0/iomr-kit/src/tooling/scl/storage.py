"""JSON workspace adapter with locking, write-ahead undo and deterministic layout.

Multiple replacements are NOT filesystem-atomic. Service readers share the lock;
interrupted writes roll back before another service operation. Git publication is
an independent commit/ref boundary. Uncooperative filesystem writers are outside
this lock's guarantee and are checked at the signed publication boundary.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Protocol

from scl.contracts import ServiceError
from scl.export import ROLES, generated_texts
from scl.model import Loaded, contained_path, load_model, metamodel_findings


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


class Storage(Protocol):
    root: Path
    model_location: str
    def locked(self, readonly=False): ...
    def load(self) -> Loaded: ...
    def snapshot(self) -> dict: ...
    def candidate_files(self, candidate: Loaded) -> dict[str, bytes | None]: ...
    def transaction(self, writes: dict[str, bytes | None]) -> None: ...
    def read_proposal(self, proposal_id: str) -> dict: ...
    def proposal_exists(self, proposal_id: str) -> bool: ...
    def save_proposal(self, proposal: dict) -> None: ...
    def commit(self, writes, proposal, receipt) -> None: ...
    def after_snapshot(self, writes) -> dict: ...
    def legacy_changes(self, slug: str) -> list[dict]: ...
    def read_receipt(self, proposal_id: str) -> dict: ...


class JsonStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.config = json.loads(self.path("imk.json").read_text(encoding="utf-8"))
        self.model = self.path(self.config["model"])
        self.state = self.path(".scl")
        if self.model == self.root or self.state == self.model:
            raise ServiceError("storage.path", "Model must be in its own repository-relative directory.")

    @property
    def model_location(self):
        return self.config["model"]

    def proposal_exists(self, proposal_id):
        return self.path(self.proposal_path(proposal_id)).is_file()

    def save_proposal(self, proposal):
        self.transaction({self.proposal_path(proposal["id"]): json_bytes(proposal)})

    def commit(self, writes, proposal, receipt):
        writes = dict(writes)
        writes[self.proposal_path(proposal["id"])] = json_bytes(proposal)
        writes[f".scl/receipts/{proposal['id']}.json"] = json_bytes(receipt)
        self.transaction(writes)

    def read_receipt(self, proposal_id):
        self.proposal_path(proposal_id)
        path = self.path(f".scl/receipts/{proposal_id}.json")
        if not path.is_file():
            raise ServiceError("approval.required", "Committed proposal has no signed receipt.")
        return json.loads(path.read_text(encoding="utf-8"))

    def legacy_changes(self, slug):
        import re
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ServiceError("slice.identity", "Use a lowercase hyphenated slice slug.")
        changes = []
        for group, op, key in (("nodes", "add_record", "record"), ("relationships", "add_relationship", "relationship")):
            path = (self.model / group / f"slice-{slug}.json").relative_to(self.root).as_posix()
            changes += [{"op": op, key: item} for item in json.loads(self.path(path).read_text(encoding="utf-8"))]
        return changes

    def path(self, relative: str) -> Path:
        path = contained_path(self.root, relative)
        if path is None or Path(relative).is_absolute():
            raise ServiceError("storage.path", "Paths must stay inside the project.", str(relative))
        current = self.root
        for part in Path(relative).parts:
            current = current / part
            if current.is_symlink():
                raise ServiceError("storage.path", "Symlink paths are not supported for managed files.", relative)
        return path

    def load(self) -> Loaded:
        findings = metamodel_findings(self.root)
        if findings:
            raise ServiceError(findings[0].rule, findings[0].message)
        loaded = load_model(self.root)
        loaded.metamodel = json.loads((self.model / "metamodel.json").read_text(encoding="utf-8"))
        return loaded

    def model_paths(self, group: str) -> list[str]:
        return [p.relative_to(self.root).as_posix() for p in sorted((self.model / group).glob("*.json"))
                if not p.name.startswith("slice-")]

    def protected_paths(self) -> set[str]:
        paths = {"imk.json", self.model.relative_to(self.root).as_posix() + "/metamodel.json", "TRACEABILITY.md"}
        paths.update(self.model_paths("nodes"))
        paths.update(self.model_paths("relationships"))
        paths.update(source["path"] for source in self.config.get("sources", []))
        for role in ROLES:
            paths.update((f"docs/REQUIREMENTS-{role}.md", f"docs/REQUIREMENTS-{role}-appendix.md"))
        return paths

    def snapshot(self) -> dict[str, str | None]:
        return {name: hashlib.sha256(self.path(name).read_bytes()).hexdigest() if self.path(name).is_file() else None
                for name in sorted(self.protected_paths())}

    def candidate_files(self, candidate: Loaded) -> dict[str, bytes | None]:
        writes = {}
        for group, records in (("nodes", candidate.nodes), ("relationships", candidate.relationships)):
            paths = self.model_paths(group)
            default = paths[0] if paths else (self.model / group / ("records.json" if group == "nodes" else "links.json")).relative_to(self.root).as_posix()
            target = self.config.get("storage", {}).get(group, default)
            target_path = self.path(target)
            if target_path.parent != self.model / group or target_path.suffix != ".json" or target_path.name.startswith("slice-"):
                raise ServiceError("storage.path", f"storage.{group} must name a canonical JSON file in the model's {group} directory.")
            owners, buckets = {}, {path: [] for path in paths}
            buckets.setdefault(target, [])
            for path in paths:
                old = json.loads(self.path(path).read_text(encoding="utf-8"))
                for record in old if isinstance(old, list) else [old]:
                    owners[record["id"]] = path
            for record in records:
                buckets[owners.get(record["id"], target)].append(record)
            writes.update({name: json_bytes(items) for name, items in buckets.items()})
        if candidate.sources != self.config.get("sources", []):
            config = deepcopy(self.config)
            config["sources"] = candidate.sources
            writes["imk.json"] = json_bytes(config)
        for source in candidate.sources:
            self.source_path(source)
        # Avoid churn for semantically identical existing arrays.
        for name in list(writes):
            path = self.path(name)
            if path.is_file() and name.endswith(".json") and json.loads(path.read_bytes()) == json.loads(writes[name]):
                writes[name] = path.read_bytes()
        texts = generated_texts(candidate)
        writes.update({name: text.encode() for name, text in texts.items()})
        for role in ROLES:
            name = f"docs/REQUIREMENTS-{role}-appendix.md"
            if name not in texts:
                writes[name] = None
        return writes

    def source_path(self, source):
        path = self.path(source["path"])
        relative = path.relative_to(self.root)
        generated_paths = {"TRACEABILITY.md"}
        for role in ROLES:
            generated_paths.update((f"docs/REQUIREMENTS-{role}.md", f"docs/REQUIREMENTS-{role}-appendix.md"))
        if (relative.parts[0] in {".git", ".scl"} or relative.as_posix() == "imk.json"
                or relative.as_posix() in generated_paths
                or path.is_relative_to(self.model / "nodes")
                or path.is_relative_to(self.model / "relationships")):
            raise ServiceError("ref.evidence", "Evidence sources cannot alias mutable canonical outputs or service state.", source["alias"])
        return path

    def after_snapshot(self, writes) -> dict:
        after = self.snapshot()
        config = json.loads(writes["imk.json"]) if "imk.json" in writes else self.config
        for source in config.get("sources", []):
            path = self.path(source["path"])
            after[source["path"]] = hashlib.sha256(path.read_bytes()).hexdigest()
        for name, data in writes.items():
            after[name] = hashlib.sha256(data).hexdigest() if data is not None else None
        return dict(sorted(after.items()))

    def proposal_path(self, proposal_id: str) -> str:
        import re
        if not isinstance(proposal_id, str) or not re.fullmatch(r"proposal-[a-f0-9]{24}", proposal_id):
            raise ServiceError("proposal.identity", "Use the proposal_id returned by propose_change.")
        return f".scl/proposals/{proposal_id}.json"

    def read_proposal(self, proposal_id: str) -> dict:
        path = self.path(self.proposal_path(proposal_id))
        if not path.is_file():
            raise ServiceError("proposal.missing", "Proposal was not found.", proposal_id)
        return json.loads(path.read_text(encoding="utf-8"))

    @contextmanager
    def locked(self, readonly=False):
        self.state.mkdir(exist_ok=True)
        lock = self.path(".scl/lock")
        with lock.open("a+b") as handle:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    if not handle.read(1):
                        handle.write(b"0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, (fcntl.LOCK_SH if readonly else fcntl.LOCK_EX) | fcntl.LOCK_NB)
            except (OSError, BlockingIOError) as exc:
                raise ServiceError("storage.busy", "Another service transaction holds the lock; retry.", retryable=True) from exc
            try:
                if readonly and os.name != "nt" and self.path(".scl/transaction.json").exists():
                    try:
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError as exc:
                        raise ServiceError("storage.busy", "Recovery needs exclusive access; retry.", retryable=True) from exc
                    self.recover()
                    fcntl.flock(handle, fcntl.LOCK_SH)
                elif not readonly or os.name == "nt":
                    self.recover()
                self.config = json.loads(self.path("imk.json").read_text(encoding="utf-8"))
                self.model = self.path(self.config["model"])
                yield
            finally:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)

    def _sync_dir(self, directory: Path):
        if os.name != "nt":
            fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def _replace(self, relative: str, data: bytes | None):
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if data is None:
            path.unlink(missing_ok=True)
        else:
            fd, temp = tempfile.mkstemp(prefix=".scl-write-", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, path)
            finally:
                Path(temp).unlink(missing_ok=True)
        self._sync_dir(path.parent)

    def recover(self):
        journal = self.path(".scl/transaction.json")
        if not journal.is_file():
            return
        undo = json.loads(journal.read_text(encoding="utf-8"))
        for name, encoded in undo.items():
            self._replace(name, base64.b64decode(encoded, validate=True) if encoded is not None else None)
        journal.unlink()
        self._sync_dir(journal.parent)

    def transaction(self, writes: dict[str, bytes | None]):
        # Caller must hold locked(). Prepare all content before entering here.
        undo = {name: base64.b64encode(self.path(name).read_bytes()).decode() if self.path(name).is_file() else None for name in writes}
        self._replace(".scl/transaction.json", json_bytes(undo))
        try:
            for name, data in writes.items():
                self._replace(name, data)
            journal = self.path(".scl/transaction.json")
            journal.unlink()
            self._sync_dir(journal.parent)
        except BaseException:
            self.recover()
            raise
