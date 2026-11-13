# Candidate validation

From the source checkout:

```sh
python3 validate-framework.py
./imk validate --strict
python3 -m pip install -e '.[mcp]'
python3 -m unittest discover -s tests -v
python3 tests/evaluate_agent_workflows.py
./imk export markdown -o /tmp/scl-traceability.md
cmp TRACEABILITY.md /tmp/scl-traceability.md
```

Copy this entire candidate folder to a temporary location, then verify the existing
consumer validator independently of the checkout:

```sh
python3 iomr-kit/src/framework/consume.py manifest iomr-kit/src/examples/project-manifest.json
python3 iomr-kit/src/framework/consume.py model iomr-kit/src/examples/consumer-model.json
```

The copied service is usable as `python3 iomr-kit/imk --root CONSUMER api get_context`.
For MCP, install the optional SDK separately and run `python3 -m scl.mcp_server` with
`iomr-kit/src/tooling` on the Python path. No candidate source is executed in trusted CI.

Confirm the snapshot and path/byte digest match the copied kit; verify historical
releases independently. Do not substitute these technical checks for model review or
release approval. Hosting required checks and signer provisioning remain administrator steps.
