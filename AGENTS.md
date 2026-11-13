# SCL development

Use `.kiro/skills/intent-modelling/SKILL.md` for modelling work. Discover the service
with `./imk api get_context`; use the MCP `scl_*` tools when available. Canonical model
JSON and generated documents are not ordinary authoring surfaces.

Run `python3 validate-framework.py`, `./imk validate --strict` and
`python3 -m unittest discover -s tests -v`. Install `.[mcp]` and run the same tests to
include the real MCP contract and stdio tests. Existing release snapshots are immutable.

Human model approval and human release approval are separate. Keep unsigned proposals
and release candidates pending; do not manufacture approval evidence. Review security
changes to the service, trusted CI and allowed signers as changes to trusted code.
