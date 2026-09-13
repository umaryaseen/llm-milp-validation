# Experiment artifacts

This directory contains experiment-level configuration and documentation. Runtime artifacts under `experiments/*/runs/` may become large and are ignored by Git. A run is reserved before generation and includes the request, normalized response, raw response text, and final record when available.

Curated aggregate results, compact metrics, and provenance manifests may be committed separately. Experiment failures are retained as observations rather than silently removed.
