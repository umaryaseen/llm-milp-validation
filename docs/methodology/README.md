# Methodology

This directory will document the experimental methodology, validation criteria, and provenance rules used by the thesis framework.

The foundation preserves benchmark case identity, benchmark version and split, prompt protocol version, exact provider/model identifiers, generation settings, raw responses, and run status. Semantic outputs are never repaired or silently discarded. Detailed methodology will be added alongside each benchmark integration.

## Future prompt naming convention

Prompts are not implemented as part of Phase 1. Future protocols will use the explicit name pattern `<benchmark>_<paper-or-protocol>_<condition>`, with the prompt version stored separately. For example, a later protocol may be named `nl4opt_lm4opt_zero_shot` at version `1`. Any wording change that can affect model output requires a new prompt version.
