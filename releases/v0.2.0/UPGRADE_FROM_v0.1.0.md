# Upgrade from 0.1.0 to 0.2.0

Copy this release folder. A project manifest may set iomrVersion to 0.2.0.

Validate the copied kit without the framework checkout:

    python3 iomr-kit/src/framework/consume.py manifest iomr-kit/src/examples/project-manifest.json
    python3 iomr-kit/src/framework/consume.py model iomr-kit/src/examples/consumer-model.json

0.1.0 kit bytes stay pinned to that release's source snapshot. Do not rebuild 0.1.0 from later sources.
