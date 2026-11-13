# API tooling in the candidate kit

The kit contains the standalone consumer validator and the complete `scl` and
`cairn_core` Python packages. Python 3.11 or later is required.

Run `python3 imk --root PROJECT api get_context` from the kit. The project must have
an `imk.json`, a supported metamodel and an existing valid IOMR graph. Use
`api get_api_schema --json '{"operation":"add_requirement"}'` for exact input fields.

MCP is optional: install `mcp>=2.3,<3`, put `src/tooling` on the Python path, and run
`python3 -m scl.mcp_server --root PROJECT`. It uses local stdio.

Normal agents propose through the API. Integration requires a detached reviewer
signature verified against an externally administered `SCL_ALLOWED_SIGNERS` file.
No private key is shipped. Required trusted CI and protected branches must be configured
by the consumer's administrators. The API does not remove local filesystem privileges.
