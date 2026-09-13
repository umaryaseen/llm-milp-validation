# Methodology

This directory will document the experimental methodology, validation criteria, and provenance rules used by the thesis framework.

The foundation preserves benchmark case identity, benchmark version and split, prompt protocol version, exact provider/model identifiers, generation settings, raw responses, and run status. Semantic outputs are never repaired or silently discarded. The Phase 3 LM4OPT protocol reconstruction is documented in [`docs/benchmarks/lm4opt_protocol.md`](../benchmarks/lm4opt_protocol.md).

## Future prompt naming convention

Protocols use the explicit name pattern `<benchmark>_<paper-or-protocol>_<condition>`, with the prompt version stored separately. The reconstructed LM4OPT protocols are `nl4opt_lm4opt_zero_shot` and `nl4opt_lm4opt_one_shot`, both at version `1`. Any wording change that can affect model output requires a new prompt version.
