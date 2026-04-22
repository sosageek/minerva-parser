from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class ParseInput(BaseModel):
    """Body di POST /parse

    Attributes:
        url: URL sorgente (serve a dedurre il dominio e quindi il parser da usare)
        html_text: HTML già scaricato dal client, sul quale il parser lavora
            senza effettuare una nuova richiesta di rete
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    html_text: str


class ParseOutput(BaseModel):
    """Output di GET /parse e POST /parse

    Attributes:
        url: URL sorgente documento parsato
        domain: netloc dominio
        title: titolo estratto
        html_text: HTML pulito restituito dal crawler (input del parser)
        parsed_text: testo pulito in formato markdown (output del parser)
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    domain: str
    title: str
    html_text: str
    parsed_text: str


class SupportedDomains(BaseModel):
    """Output di GET /domains: lista dei domini supportati dal sistema"""

    model_config = ConfigDict(extra="forbid")

    domains: list[str]


class GSEntry(BaseModel):
    """Entry singola del GS (output di GET /gold_standard)

    nota: il campo ``gold_text`` è plain text senza markdown, al posto di ``parsed_text`` di ``ParseOutput``.
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    domain: str
    title: str
    html_text: str
    gold_text: str


class ListGSEntry(BaseModel):
    """Output di GET /full_gold_standard: tutte le entry del GS di un dominio"""

    model_config = ConfigDict(extra="forbid")

    gold_standard: list[GSEntry]


class TokenLevelEval(BaseModel):
    """Metriche token-level (precision, recall, f1)

    corrisponde al dict restituito da `TokenLevelEvaluator`
    """

    model_config = ConfigDict(extra="forbid")

    precision: float
    recall: float
    f1: float


class EvaluationInput(BaseModel):
    """Body di POST /evaluate"""

    model_config = ConfigDict(extra="forbid")

    parsed_text: str
    gold_text: str


class ParseEvaluation(BaseModel):
    """Output di POST /evaluate e GET /full_gs_eval

    * campo ``token_level_eval`` è obbligatorio
    * ``x_eval`` è uno schema aperto
    """

    model_config = ConfigDict(extra="forbid")

    token_level_eval: TokenLevelEval
    x_eval: dict[str, Any] = Field(default_factory=dict)
