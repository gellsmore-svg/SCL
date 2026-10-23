# Install

SCL 0.1.0 uses the Python standard library. From the repository root:

```
PYTHONPATH=src/tooling python3 -m scl validate --strict
python3 validate-framework.py
python3 -m unittest discover -s tests -v
```

A consuming project copies `src/examples/project-manifest.json` and points `modelLocation` at its own model.
