import tomllib
from pathlib import Path

from thesis_bench.config.models import RunConfig


def load_config(path: Path) -> RunConfig:
    """Resolve relative artifact roots against the config file, independent of cwd."""
    path = path.resolve()
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    config = RunConfig.model_validate(document)
    output_dir = config.experiment.output_dir
    if not output_dir.is_absolute():
        output_dir = path.parent / output_dir
    experiment = config.experiment.model_copy(update={"output_dir": output_dir.resolve()})
    return config.model_copy(update={"experiment": experiment})
