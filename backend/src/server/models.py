from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, RootModel


ServiceStatus = Literal["ok", "unavailable"]


class StatusOutput(BaseModel):
    """Stato del backend e dei servizi esterni usati dall'applicazione."""

    model_config = ConfigDict(extra="forbid")

    backend: ServiceStatus
    database: ServiceStatus
    ollama: ServiceStatus


class DBSchema(RootModel[dict[str, dict[str, str]]]):
    """Output di GET /db_schema"""


class DBStats(BaseModel):
    """Output di GET /db_stats

    Attributes:
        web_resources(dict[str, int]): numero di risorse per dominio
        gold_standard(dict[str, int]): numero di GS per dominio
        avg_eval(dict[str, dict[str, Any]]): metriche medie salvate nel database
        avg_eval_judge(dict[str, dict[str, Any]]): giudizi medi salvati nel database
    """

    model_config = ConfigDict(extra="forbid")

    web_resources: dict[str, int]
    gold_standard: dict[str, int]
    avg_eval: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )
    avg_eval_judge: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )


class ParseInput(BaseModel):
    """Body di POST /parse

    Attributes:
        url(str): URL sorgente
        local(bool): se True usa l'HTML salvato nel database
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    local: bool = False


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


class GoldStandardURLs(BaseModel):
    """Output di GET /gold_standard_urls

    Attributes:
        gold_standard_urls(list[str]): lista degli URL presenti nel GS
    """

    model_config = ConfigDict(extra="forbid")

    gold_standard_urls: list[str]


class WebResourceInput(BaseModel):
    """Body di POST /add_web_resource

    Attributes:
        url(str): URL della risorsa
        html_text(str): HTML grezzo da salvare nel database
    """

    model_config = ConfigDict(extra="ignore")

    url: str
    html_text: str


class GoldStandardInput(BaseModel):
    """Body di POST /add_gold_standard

    Attributes:
        url(str): URL della web resource associata
        gold_text(str): testo gold da salvare nel database
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    gold_text: str


class URLInput(BaseModel):
    """Body degli endpoint DELETE

    Attributes:
        url(str): URL dell'elemento da cancellare
    """

    model_config = ConfigDict(extra="forbid")

    url: str


class CRUDStatus(BaseModel):
    """Output degli endpoint CRUD

    Attributes:
        status(str): esito dell'operazione
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "error"]


class EvaluationInput(BaseModel):
    """Body di POST /evaluate
    
    Attributes:
        parsed_text(str): testo estratto da valutare
        gold_text(str): gold text di riferimento
    """

    model_config = ConfigDict(extra="forbid")

    parsed_text: str
    gold_text: str


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
