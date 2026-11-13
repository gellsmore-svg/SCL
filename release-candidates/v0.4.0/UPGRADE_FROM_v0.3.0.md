# Upgrade from 0.3.0 to the 0.4.0 candidate

Canonical layouts and the metamodel do not need restructuring. Existing exports,
validation, Cairn checks, consumer manifests and historical release kits remain valid.

Install the candidate package from the source checkout. Add the optional MCP extra only
if needed. Discover with `imk api get_context`. Existing projects may continue to use
`imk` or `scl`; both now expose `api` operations. New files remain in their existing
canonical groups unless a storage destination is configured.

Replace direct edits and `integrate_slice` calls with proposals. Import legacy slices,
complete missing evidence/participants/traceability, validate, obtain signed review and
commit. The old integration function now fails safely; this is an intentional contract
change. Inference is retained in provenance, not left as authoritative inferred basis.

An administrator must set trusted allowed signers outside the checkout and activate a
required independently trusted hosting check. Until then local operation is proposal-only.
Protect reviewer private keys and the authoritative branch. A successful local check is
not proof that hosting enforcement has been enabled.

The service bundles generated documents with integration. Read-only exports and explicit
regeneration remain available. Never commit only half of a model transaction.

Do not mark a consumer manifest as the approved 0.4.0 release yet. This is an unpublished
candidate; 0.3.0 remains the latest approved release until the release gate is completed.
