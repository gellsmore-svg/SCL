# SCL

SCL is an [IOMR](docs/IOMR-developer-narrative.md) framework. One JSON model is the source of truth for why the work exists and which requirements constrain each interaction. Releases, traceability, and the role narratives are generated or checked from that model.

Version 0.1.0. Metamodel `iomr-evolved` 2.0.0.

## What is implemented

Releases, repository layout, governance gates, upgrade guides, release eligibility, the four-step lifecycle, machine-readable version discovery, context capture, human-authored and AI-inferred modes, role narratives, open questions, and skill gating.

The interpreter contract is **partial**: a solution fails only on a real requirement boundary. There is no full execution runtime.

Verification roles, canonical tests, and execution adapters are **planned**. Their requirements are in the model. They are not enforced yet.

## Check

```
python3 validate-framework.py
PYTHONPATH=src/tooling python3 -m scl validate --strict
python3 -m unittest discover -s tests -v
```

`./imk` is the same command as `python3 -m scl`. The contract's check is `./imk validate --strict`.

Regenerate the derived documents with:

```
PYTHONPATH=src/tooling python3 -m scl export markdown -o TRACEABILITY.md
```

Do not hand-edit `TRACEABILITY.md` or `docs/REQUIREMENTS-*.md`. If they disagree with the model, change the model and export again.

## Layout

`src`, `releases/v0.1.0`, `meta/iomr-model`, `changelog`, `docs`, and the root `iomr-manifest.json` are required. The consumable kit is `releases/v0.1.0/iomr-kit`.

A release is cut only when a project-consumable path changes (`src/templates`, `src/prompts`, `src/schemas`, `src/framework`, `src/tooling`, `src/examples`, `docs`, or `validate-framework.py`). Changes under `meta`, `changelog`, `internal`, `research`, or `design-work` are not a release.
