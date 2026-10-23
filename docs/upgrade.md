# Upgrade

0.1.0 is the first release. 0.2.0 is the next.

A project on 0.1.0 moves forward by copying `releases/v0.2.0` and reading `UPGRADE_FROM_v0.1.0.md` inside that folder. Set `iomrVersion` to 0.2.0 when the project is ready to use the new kit.

0.2.0 can validate a consumer manifest and a small model from the copied release, without this checkout. Historical kit bytes stay pinned to their own source snapshot.
