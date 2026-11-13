# Upgrade

0.1.0 is the first release. 0.2.0 adds a copied-release check. 0.3.0 is the next.

A project on 0.2.0 moves forward by copying `releases/v0.3.0` and reading `UPGRADE_FROM_v0.2.0.md` inside that folder. Set `iomrVersion` to 0.3.0 when the project uses named process export, bind checks, or proposals.

0.2.0 manifests remain valid. Historical kit bytes stay pinned to their own source snapshot.

The next candidate replaces direct slice integration with the governed model service. Read [API modelling](api-modelling.md) and the candidate upgrade guide before adopting it.
