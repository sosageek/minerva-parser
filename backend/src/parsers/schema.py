"""Definisce il documento restituito dai parser"""

from pydantic import BaseModel, ConfigDict

class ParsedDocument(BaseModel):
    """Documento parsato"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    domain: str
    title: str
    html_text: str
    parsed_text: str
