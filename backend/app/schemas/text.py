"""Text accepted by PostgreSQL, including multiline annotations."""
from typing import Annotated

from pydantic import AfterValidator


def validate_text(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Text cannot contain a null character")
    return value


DatabaseText = Annotated[str, AfterValidator(validate_text)]
