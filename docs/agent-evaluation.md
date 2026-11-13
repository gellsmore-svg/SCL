# Agent workflow evaluation

Executed against a disposable consumer project with a different model location, split node files and different relationship filename. All scenarios use the public JSON application contract. Fixture setup and test-key signing are excluded from operation counts; discovery, preview, approval verification and commit calls are included. Test signatures simulate review; they are not human approval of the repository model.

| Scenario | Operations | Response bytes (total / largest) | Result |
|---|---:|---:|---|
| A — Add a Requirement under a known Model | 5 | 11646 / 4672 | Passed |
| B — Add an interaction, participants and constraints together | 5 | 16662 / 6401 | Passed |
| C — Discover and reuse an existing Intent/Outcome chain | 7 | 12754 / 4684 | Passed |
| D — Correct an illegal relationship from structured findings | 7 | 12377 / 4097 | Passed |
| E — Rebase after a competing revision commits | 13 | 29495 / 4724 | Passed |
| F — Block unauthenticated inferred integration | 5 | 5940 / 4672 | Passed |

No scenario needs canonical filenames or direct JSON editing. A known-parent Requirement takes one authoring call after revision discovery; separate preview/signature verification/integration calls preserve human review. Discovery returns paginated summaries rather than the complete graph.

D obtains `rel.legality`, replaces the proposal using its content revision and commits the corrected candidate. E receives `revision.conflict`, refreshes, rebases and reviews again; both changes survive. F demonstrates rejection of fabricated approval and unapproved integration. A and B validate the complete graph and generated documents after integration.

These measurements establish operation count and transferred JSON size, not a controlled comparison of model token usage or human review time. Automated scenarios test outcomes and recovery. The modelling instructions are also exercised independently in a disposable project; see the implementation summary for that result.

Reproduce with `python3 tests/evaluate_agent_workflows.py`. Machine-readable results: `docs/agent-evaluation.json`.

Independent instruction trial: an isolated agent discovered the existing chain, submitted a valid Requirement proposal and correctly stopped before integration when approval was unavailable. It found a CLI schema-dispatch collision and read-lock contention; both were fixed. A follow-up observed successful schema discovery and simultaneous record/trace reads (three calls, 6,568 bytes of formatted CLI output) with no lock errors. That follow-up is a verification of the fixes, not an end-to-end comparative benchmark.
