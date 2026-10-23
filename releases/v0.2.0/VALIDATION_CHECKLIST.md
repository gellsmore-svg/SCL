# Validation checklist for 0.2.0

From this release folder, with python3 and no framework checkout:

1. Run python3 iomr-kit/src/framework/consume.py manifest iomr-kit/src/examples/project-manifest.json and expect VALID and errors: 0.
2. Run python3 iomr-kit/src/framework/consume.py model iomr-kit/src/examples/consumer-model.json and expect VALID and errors: 0.
3. Confirm iomr-manifest.json version is 0.2.0, matching the folder name.
4. Confirm each file listed in source-snapshot.json matches the same path under iomr-kit, and iomr-kit/MANIFEST.sha256 matches those bytes.
