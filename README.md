# SCL

SCL is an [IOMR](docs/IOMR-developer-narrative.md) framework. One JSON model is the source of truth for why the work exists and which requirements constrain each interaction. Releases, traceability, and the role narratives are generated or checked from that model.

Version 0.2.0. Metamodel `iomr-evolved` 2.0.0.

## What is implemented

Releases, repository layout, governance gates, upgrade guides, release eligibility, the four-step lifecycle, machine-readable version discovery, context capture, human-authored and AI-inferred modes, role narratives, open questions, and skill gating.

The interpreter contract is **partial**: a solution fails only on a real requirement boundary. There is no full execution runtime.

Verification roles, canonical tests, and execution adapters are **planned**. Their requirements are in the model. They are not enforced yet.

## Check

```
python3 validate-framework.py
./imk validate --strict
python3 -m unittest discover -s tests -v
```

`./imk` is the same command as `python3 -m scl`. The contract's check is `./imk validate --strict`. These commands do not use `PYTHONPATH`.

`./imk export` renders to stdout or to `-o`. It does not rewrite the repository. Regenerate the derived documents with:

```
./imk regenerate
```

Do not hand-edit `TRACEABILITY.md` or `docs/REQUIREMENTS-*.md`. If they disagree with the model, change the model and regenerate.

## Layout

`src`, `releases`, `meta/iomr-model`, `changelog`, `docs`, and the root `iomr-manifest.json` are required. The consumable kits are `releases/v0.1.0/iomr-kit` and `releases/v0.2.0/iomr-kit`. A copied 0.2.0 release validates a manifest and a small model with `iomr-kit/src/framework/consume.py`. Each kit is checked against its own `source-snapshot.json`.

A release is cut only when a project-consumable path changes (`src/templates`, `src/prompts`, `src/schemas`, `src/framework`, `src/tooling`, `src/examples`, `docs`, or `validate-framework.py`). Changes under `meta`, `changelog`, `internal`, `research`, or `design-work` are not a release.
