# SCL 0.2.0

1. Meta-model is a release candidate.
2. Downstream artifacts were generated from the model.
3. AI-test passed (`imk validate --strict`, `validate-framework.py`, and the engine tests).
4. Release only on an explicit, documented human green light.

Green light: gellsmore-svg

Consumer impact: YES

Behavioural difference: A copied release can validate a consumer manifest and a small model without the framework checkout, and historical kits are checked against their own source snapshot.

The kit bytes are under iomr-kit. They match the source snapshot recorded for this release.
