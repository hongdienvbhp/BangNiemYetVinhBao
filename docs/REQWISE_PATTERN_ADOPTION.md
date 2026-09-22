# Reqwise-inspired governance for Vinh Bao canonical TTHC

## Architecture

Official sources → adapters → parser/normalizer → diff engine → deterministic validators → canonical TTHC → generated/read-only consumers.

Exceptions go to AI semantic review and human QC. AI is not used for schema, duplicate, enum, URL, count or drift checks.

## P0 — Canonical contract

- Owner: `data/thu-tuc.json`.
- Contract: `schemas/tthc-canonical.schema.json`.
- Policy registry: `config/tthc-policy-registry.json`.
- CI gate: `python scripts/tthc_governance.py --audit`.
- Dataset identity: deterministic `<version>@<sourceSnapshotDate>` plus runtime Git `sourceCommit`.
- Provenance is mandatory at record level through `sourceEvidence`.
- Single writer; consumers may only read/transform/display.

## P1 — Audit / change / drift / review / telemetry

`scripts/tthc_governance.py` provides:

- deterministic audit;
- duplicate and provenance validation;
- cross-field authority/reception check;
- canonical ↔ generated fallback drift detection;
- change-set generation using record fingerprints;
- review queue generation for warnings/errors;
- telemetry JSONL;
- dataset fingerprint and Git source commit.

Commands:

```bash
python scripts/tthc_governance.py --audit
python scripts/tthc_governance.py --all
python scripts/tthc_governance.py --changeset-from path/to/old-thu-tuc.json
```

CI uses non-mutating `--audit`. Operational workflows may use `--all` to materialize audit/review/telemetry artifacts.

## P2 — Policy / diagram / Agent contract

The policy registry is the canonical location for shared rules. Do not hard-code equivalent policy independently in consumers.

Agent contract:

1. Many readers are allowed.
2. Only the canonical writer may mutate canonical data.
3. Agents propose a minimal patch/change-set rather than regenerating the whole dataset.
4. Deterministic validators run before AI review.
5. AI handles semantic differences and exceptional cases only.
6. Human QC is required for unresolved legal/authority discrepancies.
7. A change is complete only after tests, governance audit, drift gate and Git evidence pass.

Diagram-as-code is generated from the governance script into `docs/TTHC_CANONICAL_PIPELINE.mmd`.

## Consumer rule

`CongkhaiTTHC`, `tthc-monitor`, `thutuchanhchinh`, dashboards and future agents must treat this repository as source-of-truth and must not create an independent TTHC master.

## Definition of Done

Code complete + tests PASS + governance audit PASS + drift = 0 + CI PASS + commit/PR evidence.
