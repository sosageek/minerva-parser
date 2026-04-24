from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class ParseInput(BaseModel):
    """Body di POST /parse

    Attributes:
        url(str): URL sorgente
        html_text(str): HTML già scaricato dal client, sul cui il parser lavora senza effettuare una nuova richiesta
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    html_text: str


class ParseOutput(BaseModel):
    """Output di GET /parse e POST /parse

    Attributes:
        url(str): URL sorgente documento parsato
        domain(str): netloc dominio
        title(str): titolo estratto
        html_text(str): HTML pulito restituito dal crawler (input del parser)
        parsed_text(str): testo pulito in formato markdown (output del parser)
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    domain: str
    title: str
    html_text: str
    parsed_text: str


class SupportedDomains(BaseModel):
    """Output di GET /domains: lista dei domini supportati dal sistema
    
    Attributes:
        domains(list[str]): lista dei domini
    """

    model_config = ConfigDict(extra="forbid")

    domains: list[str]


class GSEntry(BaseModel):
    """Entry singola del GS (output di GET /gold_standard)

    nota: il campo ``gold_text`` è plain text senza markdown, al posto di ``parsed_text`` di ``ParseOutput``.

    Attributes:
        url(str): URL della pagina
        domain(str): netloc dominio
        title(str): titolo gold
        html_text(str): HTML gold
        gold_text(str): testo gold di riferimento per evaluation
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    domain: str
    title: str
    html_text: str
    gold_text: str


class ListGSEntry(BaseModel):
    """Output di GET /full_gold_standard: tutte le entry del GS di un dominio
    
    Attributes:
        gold_standard(list[GSEntry]): lista delle entry del GS di un dominio
    """

    model_config = ConfigDict(extra="forbid")

    gold_standard: list[GSEntry]


class TokenLevelEval(BaseModel):
    """Metriche token-level (precision, recall, f1)

    Attributes:
        precision(float): |token_parsed ∩ token_gold| / |token_parsed|
        recall(float): |token_parsed ∩ token_gold| / |token_gold|
        f1(float): (2 * precision * recall) / (precision + recall)

    nota: attributi corrispondono 1:1 ai campi del dict restituito da `TokenLevelEvaluator`
    """

    model_config = ConfigDict(extra="forbid")

    precision: float
    recall: float
    f1: float


class EvaluationInput(BaseModel):
    """Body di POST /evaluate
    
    Attributes:
        parsed_text(str): testo estratto da valutare
        gold_text(str): gold text di riferimento
    """

    model_config = ConfigDict(extra="forbid")

    parsed_text: str
    gold_text: str


class ParseEvaluation(BaseModel):
    """Output di POST /evaluate e GET /full_gs_eval

    Attributes:
        token_level_eval(TokenLevelEval): struttura delle metriche token-level di default (precision, recall, f1)
        x_eval(dict[str, Any]): dizionario per metriche di evaluation alternative

    * campo ``token_level_eval`` è obbligatorio
    * ``x_eval`` è uno schema aperto
    """

    model_config = ConfigDict(extra="forbid")

    token_level_eval: TokenLevelEval
    x_eval: dict[str, Any] = Field(default_factory=dict)
