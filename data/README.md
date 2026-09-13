# Data policy

`data/raw/` is reserved for immutable downloaded benchmark artifacts and is normally not committed. `data/processed/` is reserved for derived data and is also normally not committed. Provenance manifests, checksums, transformations, and licensing information should be committed separately when they do not contain restricted data.

Benchmark data will be added incrementally. Dataset licenses and redistribution terms remain authoritative and will be recorded in `THIRD_PARTY_LICENSES.md` when resources are incorporated.

The official NL4Opt generation source is acquired locally under `data/raw/nl4opt_generation/<git-sha>/` and described by the tracked manifest `data/manifests/nl4opt_generation.json`. The raw files are intentionally not vendored into this public repository.

The frozen official evaluator source is acquired locally under `data/raw/nl4opt_evaluator/<git-sha>/` and described by `data/manifests/nl4opt_evaluator.json`. Provenance manifests are committed; raw downloads remain ignored.
