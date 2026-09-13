# Historical LM4OPT prompt protocol

This document records a source-grounded reconstruction of the zero-shot and
one-shot protocol in Ahmed and Choudhury, *LM4OPT: Unveiling the Potential of
Large Language Models in Formulating Mathematical Optimization Problems*,
INFOR 62(4), 559–572 (2024), [arXiv:2403.01342](https://arxiv.org/abs/2403.01342).
The paper is the primary source; its Figure 2 is the source of the prompt
templates tracked under `prompts/nl4opt/lm4opt/`.

## Evidence and provenance

| Protocol element | Status | Evidence or limitation |
|---|---|---|
| Zero-shot and one-shot wording | Paper-reproduced | Figure 2 in the arXiv source |
| Hotel demonstration | Paper-reproduced | Figure 1 and Figure 2 |
| Input is the description only | Directly reported | The paper contrasts LLM inputs with the NER-augmented BART baseline |
| Historical model identifiers | Directly reported | `gpt-3.5-turbo-0613`, `gpt-4-0613`; access date 2023-11-01 |
| Original response parser/converter | Unknown | No author-released LM4OPT inference/conversion implementation was located as of 2026-09-13 |
| Parser used here | Necessary reconstruction | Narrow explicit-linear compatibility parser, not claimed to be the original |
| GPT inference parameters | Not reported | See the audit below |
| Historical aggregate scores | Paper-reported metadata | Stored in `results/lm4opt/paper_reported_results.json`; not reproduced here |

The paper describes a generated intermediate equation representation being
converted to a canonical minimization form. This repository therefore labels
its bridge to the frozen Phase 2 evaluator as a **reconstructed compatibility
conversion**. It preserves raw output and parser diagnostics; it never repairs
or discards a malformed response.

## Input and conditions

Both protocols expose exactly one target-case field: the NL4Opt natural
language problem description. They do not expose `obj_declaration`,
`const_declarations`, canonical coefficients, reference labels, evaluator
output, named-entity labels, or mention mappings. This policy is implemented by
`LM4OptProtocol.input_view_for`, rather than by selecting fields in a runner.

“Zero-shot” in the paper includes an example response format. It does not
include a solved example problem. The one-shot condition includes both the
hotel problem and its example response. This distinction is retained in the
metadata and tests.

The paper does not specify whether the text was sent as a system message, a
user message, or a legacy completion prompt. The implementation represents the
paper text as one provider-neutral user message; this is an implementation
representation, not a historical claim.

## Protocols

`nl4opt_lm4opt_zero_shot@1` asks for variables, constraints, and objective
functions, shows the hotel-shaped response format, requires constraints in
less-than-or-equal form, requires exactly three named sections, and appends the
target description. `nl4opt_lm4opt_one_shot@1` has the same instructions and
target suffix, but precedes it with the hotel problem and demonstrated answer.
The exact tracked templates are authoritative and their SHA-256 hashes are
recorded by the protocol object.

The hotel demonstration uses cleaners, receptionists, weekly wages 500 and
350, at least 100 workers, at least 20 receptionists, a one-third ratio, and a
30000 wage cap. The source objective spelling `receptionist` is preserved.

## Expected output and conversion

A response has `Variables:`, `Constraints:`, and `Objective Function:`. The
reconstructed parser accepts only explicit linear terms such as
`(500.0) * cleaners + (350.0) * receptionists <= 30000.0`; it accepts `<=`,
`≤`, and the source `\leq` spelling. It retains raw text, missing sections,
extra text, and malformed terms as diagnostics. It is not a symbolic algebra
engine and does not use case references or gold mappings.

For the Figure 1 hotel regression, the parser can be run with the explicit
`paper_hotel_alias=True` compatibility assumption. That records the source typo
mapping `receptionist` to declared `receptionists`; the raw text is unchanged.
Ordinary target parsing is strict and never applies that alias.

The reconstructed hotel canonical form is:

```text
constraints = [[-1.0, -1.0, -100.0], [0.0, -1.0, -20.0],
               [0.33, -1.0, 0.0], [500.0, 350.0, 30000.0]]
objective = [500.0, 350.0]
```

For a source maximization, this parser negates objective coefficients to follow
the paper's minimization convention. The Phase 2 official evaluator is a
separate pipeline and does not normalize objective direction in the same way.
The discrepancy is visible in parser notes and evaluation diagnostics.

## API parameter audit

| Parameter | Value | Status |
|---|---|---|
| GPT-3.5 model | `gpt-3.5-turbo-0613` | Reported |
| GPT-4 model | `gpt-4-0613` | Reported |
| API access date | 2023-11-01 | Reported |
| temperature, top_p, max tokens | — | Not reported |
| frequency/presence penalties, stop, n, seed | — | Not reported |
| timeout and retries | — | Not reported |
| system/user role | — | Not reported |
| Llama maximum response sequence length | 200 | Reported for fine-tuning; not transferred to GPT API |

No executable provider configuration or current model recommendation is
created in Phase 3.

## Historical results

The paper calls its reported metric “F1-score”. The Phase 2 reproduction found
that the pinned evaluator computes declaration-accuracy-style scores with
specific duplicate, direction, and scaling behavior; it is not conventional
precision/recall F1. The JSON metadata is therefore labelled
`paper_reported_score` and `reproduced_here: false`.

## Reproduction artifacts and limits

Tracked fixtures cover two train, two dev, and five test IDs and deterministic
paper-format responses. Prompt snapshots live under
`tests/fixtures/prompts/lm4opt/`. Offline dry runs use `MockLLMProvider` and
write ignored artifacts under
`experiments/lm4opt-protocol-mock/runs/<run-id>/`, including the rendered
prompt, hashes, raw response, parser output, canonical form, evaluator output,
and provenance record.

No author-released LM4OPT inference/conversion implementation was located as
of 2026-09-13. Exact API role construction, generation parameters,
retry/stopping policy, repeated-generation policy, and private conversion
details remain unresolved gaps for later methodology review. The paper and its
figures are not copied into this repository.
