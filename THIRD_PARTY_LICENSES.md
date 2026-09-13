# Third-party licenses

The official NL4Opt generation benchmark source has been acquired locally for Phase 1 from:

- Repository: https://github.com/nl4opt/nl4opt-competition
- Frozen source commit: `49f1e0d66b7fdcd33305a7f281c2a7c13f5620ea`
- License: MIT
- License file: `LICENSE` in the upstream repository
- Local acquisition: `data/raw/nl4opt_generation/<git-sha>/` (ignored and not committed)

The upstream license governs the benchmark assets. This entry does not make a claim about redistribution beyond the terms of that license. The official repository README also links the Subtask 2 generation baseline, which was inspected for schema context but not incorporated into this repository.

As benchmark adapters and supporting resources are added, this file will record their source, version or revision, applicable license, attribution requirements, and whether redistribution is permitted. Upstream license terms remain authoritative; the repository MIT License applies only to code authored here.

## Official NL4Opt evaluator

Phase 2 uses the Subtask 2 baseline at https://github.com/nl4opt/nl4opt-subtask2-baseline, frozen at commit `18a54bcb2c34be7d034d994c9e065e59cdf1ddfe` under its MIT license. The small attributed parser/scorer copy in `src/thesis_bench/_vendor/nl4opt/` is retained for offline, exact-parity execution; its provenance and original file checksums are in `data/manifests/nl4opt_evaluator.json`. One import is adapted for package isolation. No benchmark data are redistributed.
