# SCL 0.4.0 release candidate

Status: **pending human release approval**. Development package: `0.4.0rc1`.
Target release: `0.4.0`. Latest approved consumer release: `0.3.0`.

Consumer impact: YES

Behavioural difference: consumers can discover and propose semantic IOMR changes through
one service, CLI or local MCP, validate full candidate graphs, obtain independently
verified review and integrate with concurrency, provenance and generated-document safety.
The old unrestricted integrate_slice writer is intentionally disabled.

1. Meta-model is a release candidate (metamodel version itself remains 2.0.0).
2. Downstream artifacts for the self-model proposal are generated as pending previews.
3. AI-test results are recorded in the implementation summary and validation checklist.
4. Release only on an explicit, documented human green light: **not yet received**.

No tag, published package or approved release directory is created. Historical releases
are unchanged. This folder is deliberately outside `releases` and cannot masquerade as
an approved release. Root version discovery explicitly reports candidate status.

The prepared `iomr-kit` contains the legacy consumer validator and the complete stdlib
CLI/service/Cairn tooling. MCP requires its separately installed optional dependency.
`source-snapshot.json` and `MANIFEST.sha256` record candidate bytes. Rebuild after any
source change. Before publication, review and integrate the self-model proposal, activate
hosting governance, choose final version metadata, rebuild and rerun all checks; obtain
human release approval for those final bytes.
