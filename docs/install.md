# Install

SCL 0.3.0 uses the Python standard library. From the repository root:

```
python3 validate-framework.py
./imk validate --strict
python3 -m unittest discover -s tests -v
```

Regenerate derived documents with `./imk regenerate`.

A consuming project copies `src/examples/project-manifest.json` and points `modelLocation` at its own model. A copied 0.3.0 release can run `python3 iomr-kit/src/framework/consume.py` on that manifest and on `src/examples/consumer-model.json`.

`./imk export cairn` renders the model as a named process. `./imk cairn check` and `./imk cairn propose` parse with the vendored process-description core in `src/tooling/cairn_core` (core 1.0.0). They do not import the Deborah package. A copied 0.3.0 release kit still expects Deborah beside the framework for those two commands.

For API and optional MCP installation, see [API modelling](api-modelling.md). The development version is 0.4.0rc1; 0.3.0 remains the latest approved consumer release.
