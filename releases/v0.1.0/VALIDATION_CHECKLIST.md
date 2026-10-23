# Validation checklist for 0.1.0

From the repository that contains this release:

1. Run python3 validate-framework.py and expect VALID and errors: 0.
2. Run PYTHONPATH=src/tooling python3 -m scl validate --strict and expect VALID and errors: 0.
3. Run python3 -m unittest discover -s tests -v and expect every test to pass.
4. Confirm iomr-manifest.json version is 0.1.0, matching the folder name.
5. Confirm iomr-kit/MANIFEST.sha256 matches a rebuild from the kit file list.
