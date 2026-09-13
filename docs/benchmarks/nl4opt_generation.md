# NL4Opt generation benchmark audit

This document records the Phase 1 acquisition and audit of the official NL4Opt generation/formulation source. It describes the source as acquired; it does not reproduce a cleaned or solver-transformed dataset.

## Provenance

- **Benchmark ID:** `nl4opt_generation`
- **Source alias:** `neurips2022-official`
- **Upstream repository:** https://github.com/nl4opt/nl4opt-competition
- **Frozen Git commit:** `49f1e0d66b7fdcd33305a7f281c2a7c13f5620ea`
- **Acquisition date:** 2026-09-13 (UTC; exact timestamp is in the manifest)
- **License:** MIT, from upstream `LICENSE`
- **Generation baseline reference:** https://github.com/nl4opt/nl4opt-subtask2-baseline

The tracked machine-readable provenance record is [`data/manifests/nl4opt_generation.json`](../../data/manifests/nl4opt_generation.json). Raw files are stored locally under `data/raw/nl4opt_generation/<git-sha>/` and are ignored by Git.

## Dataset structure

The acquired files are the upstream root `LICENSE` and the three official generation files:

| Upstream path | Format | Split | Records |
| --- | --- | ---: | ---: |
| `generation_data/train.jsonl` | JSONL | train | 713 |
| `generation_data/dev.jsonl` | JSONL | dev | 99 |
| `generation_data/test.jsonl` | JSONL | test | 289 |

The total is **1,101 records**. Each JSONL line is an object with exactly one outer source-ID key whose value is the record. The source files are copied byte-for-byte; no line is reformatted.

## Record schema

Every audited record had the same set of fields:

`document`, `vars`, `var_mentions`, `var_mention_to_first_var`, `first_var_to_mentions`, `params`, `obj_declaration`, `const_declarations`, `spans`, `tokens`, `_input_hash`, and `order_mapping`.

`document` is the natural-language problem description. `obj_declaration` is the reference objective declaration. `const_declarations` is the list of reference constraint declarations. `spans` and `tokens` contain the entity and token annotations used by the source task. Variable mentions, parameters, and ordering metadata remain available through the preserved raw record.

The adapter does not turn declarations into a solver model or canonicalize mathematical expressions.

## Adapter mapping

| Normalized field | Upstream source |
| --- | --- |
| `benchmark_id` | fixed adapter identity `nl4opt_generation` |
| `benchmark_version` | frozen Git commit SHA in the manifest |
| `split` | source filename stem: `train`, `dev`, or `test` |
| `case_id` | outer JSON object key |
| `description` | record `document` |
| `reference_objective` | record `obj_declaration` |
| `reference_constraints` | record `const_declarations` |
| `named_entities` | record `spans` and `tokens`, grouped without alteration |
| `source_id` | outer JSON object key |
| `raw_record` | complete inner JSON object |

No expected solution or numeric objective value is inferred. Optional data is left optional in the normalized interface.

## Integrity

`datasets verify nl4opt` checks the tracked manifest, every required file, byte size, SHA-256 checksum, JSONL parseability, required fields, and split counts. The adapter also performs this verification before direct access. A checksum or size mismatch fails with the affected path and expected and actual values. Verification never redownloads, repairs, or regenerates the manifest.

The manifest records these SHA-256 checksums and byte sizes:

- `LICENSE`: `d8165362b50a26ccad4bc717c050c86db776b1c6d2ec40f288e416d0ecb62399`, 1,076 bytes
- `generation_data/train.jsonl`: `120ff6881c723296c458ef34f3840b5f14d174c6c30dd7002711f59e7e262380`, 9,150,479 bytes
- `generation_data/dev.jsonl`: `6538ce1fe76861f89879672a6c9a02c8f41156952256f3cfde82c2808ba320ee`, 1,437,713 bytes
- `generation_data/test.jsonl`: `2a4a20a11935aacc99068ee4207d5265f15c0b387d4720c548c196d8ff2fcf5b`, 3,897,679 bytes

## Stable IDs

The upstream outer keys are present, non-empty, and unique across all 1,101 records, so they are preserved as case IDs. No random or runtime-dependent fallback is used. Repeated adapter loads produce the same IDs and normalized values.

## Audit observations

- JSON parsing errors: none observed.
- Records missing required adapter fields: none observed.
- Null values in the audited fields: none observed.
- Duplicate upstream source IDs: none observed.
- Duplicate natural-language descriptions: none observed.
- Inner schema key variations: none observed.
- Empty `const_declarations`: 3 records.
- Empty `first_var_to_mentions` and `var_mention_to_first_var`: 28 records each.
- Objective direction strings include variants such as `maximize`, `minimize`, `minimum`, `maximum`, `reduce`, and related source spellings. These are preserved as source content and are not interpreted as semantic errors.

The empty fields and direction variants are potentially unusual parseable observations requiring later review; no record is labelled incorrect or removed in this phase.

## Historical consistency

Observed counts agree exactly with the commonly reported approximate counts of 713 train, 99 development, and 289 test examples. The observed source filenames are `train`, `dev`, and `test`; `dev` is retained as the upstream split name and is not renamed to `validation`.

## Deliberately unchanged content

This official benchmark variant does not correct labels, normalize formulas, clean descriptions, solve instances, replace reference formulations, apply survey corrections, deduplicate records, or change split membership. Future cleaned, solver-verified, or semantically annotated datasets must use distinct benchmark IDs and source paths rather than overwriting this frozen source.
