# Official NL4Opt evaluation

Phase 2 reproduces the public Subtask 2 evaluator from [`nl4opt-subtask2-baseline`](https://github.com/nl4opt/nl4opt-subtask2-baseline), frozen at commit `18a54bcb2c34be7d034d994c9e065e59cdf1ddfe`. Relevant upstream files and SHA-256 checksums are recorded in `data/manifests/nl4opt_evaluator.json`; the upstream code is MIT licensed.

Generated XML-like declarations are parsed by the upstream `ModelOutputXMLParser`, gold JSON declarations by `JSONFormulationParser`, and both are converted to canonical coefficient rows before `scoring.per_example_scores` and `scoring.overall_score`. A dependency-light compatibility implementation keeps verification offline while retaining raw predictions and parse diagnostics.

The historical corpus evaluator is `test_utils.collate_score_declarations`, which groups declaration chunks by document and delegates corpus aggregation to `scoring.overall_score`. The tracked implementation keeps these upstream modules attributed under `src/thesis_bench/_vendor/nl4opt/`; the source snapshot itself is also available through `evaluators fetch nl4opt`.

Canonicalization uses dataset variable order. Objective and constraint arrays use exact floating-point equality. Objective direction is parsed but does not change coefficients. Constraint order is ignored, duplicate predicted rows are removed, and a `GREATER_OR_EQUAL` row is multiplied by -1. Algebraic scaling is not equivalent. Variable names use upstream fuzzy matching; unknown numeric text is best-effort parsed and may become zero.

The score is declaration accuracy, not F1, precision, or recall. For each case, `d = 1 + number of gold constraints`; objective mismatch contributes one false positive, unmatched unique predicted rows contribute false positives, missing gold rows contribute false negatives, and false positives are capped at `d`. The score is `1 - (FP + FN) / d`; corpus scoring sums these quantities over cases.

The historical flow groups declaration text by document in `test_utils.collate_score_declarations`, then calls `scoring.overall_score` (micro-style weighting by total declarations). On the frozen 1,101-record source, the gold XML oracle parsed all 1,101 cases. One source case (`-1864917274`) contains duplicate gold constraints; because predicted duplicates are deduplicated but gold rows are not, its contribution is below one. The measured aggregate is `0.9997628083491461`. This is an upstream edge case retained in the audit report, not corrected locally.

Malformed XML is retained as a failed prediction. The official parser falls back to an empty formulation (and may skip an individual malformed constraint), so results record both the parse failure and official score contribution. No generated formulation is repaired or silently discarded.

`results/nl4opt/evaluator_characterization.json` records deterministic offline examples. Run the full gold-as-prediction check with:

```bash
uv run python -m thesis_bench evaluators gold-check nl4opt
```

This is a reproducibility reference for the historical benchmark baseline, not a semantic-equivalence validator.

Phase 1’s three empty-constraint records receive a denominator of one and can score perfectly when the objective parses. The 28 records with empty mention mappings remain governed by their explicit `order_mapping`; no mention text is normalized here. Objective direction strings such as `maximize`, `minimum`, `maximum`, and `reduce` are retained as text and do not alter canonical coefficients.
