# Install

SCL 0.2.0 uses the Python standard library. From the repository root:

```
python3 validate-framework.py
./imk validate --strict
python3 -m unittest discover -s tests -v
```

Regenerate derived documents with `./imk regenerate`.

A consuming project copies `src/examples/project-manifest.json` and points `modelLocation` at its own model. A copied 0.2.0 release can run `python3 iomr-kit/src/framework/consume.py` on that manifest and on `src/examples/consumer-model.json`.
