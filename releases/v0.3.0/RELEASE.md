# SCL 0.3.0

1. Meta-model is a release candidate.
2. Downstream artifacts were generated from the model.
3. AI-test passed (`imk validate --strict`, `validate-framework.py`, and the engine tests).
4. Release only on an explicit, documented human green light.

Green light: gellsmore-svg

Consumer impact: YES

Behavioural difference: A project can export the model as a named Cairn process, reject a step bind that is not a requirement, and propose a process as a slice that stays out of the model until a person approves it.

The kit bytes are under iomr-kit. They match the source snapshot recorded for this release.
