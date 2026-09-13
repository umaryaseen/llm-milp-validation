"""Shared validation rules for portable, serializable experiment data."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

type NonEmptyStr = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
type FileID = Annotated[
    str, StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
]


class SchemaModel(BaseModel):
    """Reject misspelled fields and preserve strings exactly as supplied."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
