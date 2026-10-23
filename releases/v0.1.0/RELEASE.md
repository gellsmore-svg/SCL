# SCL 0.1.0

1. Meta-model is a release candidate.
2. Downstream artifacts were generated from the model.
3. AI-test passed (`imk validate --strict`, `validate-framework.py`, and the engine tests).
4. Release only on an explicit, documented human green light.

Green light: gellsmore-svg

Consumer impact: YES

Behavioural difference: A project can validate an IOMR model, discover its framework version, and consume a self-contained kit. No previous release exists.

The kit bytes are under iomr-kit. Rebuild them from the file list at the tag and the digest matches.
