# Contributing

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). Run the test suite and Ruff before opening a change:

```bash
uv sync
uv run pytest
uv run ruff check .
```

Work on short-lived feature branches such as `phase/01-nl4opt` and open a pull request into `main`. Do not commit secrets, `.env` files, raw datasets, runtime run directories, or provider credentials. Every experiment change should preserve benchmark provenance, prompt/model configuration, raw outputs, failures, and enough metadata for another researcher to reproduce the run.
