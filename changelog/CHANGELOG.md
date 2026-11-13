# 0.4.0-rc.1 — pending human approval

Added shared semantic service, CLI/MCP adapters, full-candidate validation, signed review, provenance, revision checks, recoverable JSON transactions and trusted publication verification. Direct integrate_slice is intentionally disabled. Existing exports, Cairn proposals and historical release kits remain supported.

# Changelog

## Unreleased

Check and propose validate a Cairn document with the vendored `cairn_core` package. A consumer can extend or override that validation model. The commands do not import Deborah. The 0.3.0 release kit is unchanged.

## 0.3.0

The model can be read as a Cairn process with stable step names. A Cairn document can be checked against requirement ids, and a named process can be proposed as a slice that stays out of the model until a person approves it.

## 0.2.0

A copied release validates a consumer manifest and a small model. Each release kit is checked against its own source snapshot. Validation reads real proposal files, rejects escaped evidence paths, and regenerates documents only through `imk regenerate`.

## 0.1.0

First consumable release. The authoritative model, the validator, role narratives, skill gating, and the release kit are in place. The interpreter contract is partial. Verification roles, canonical tests, and execution adapters are planned.
