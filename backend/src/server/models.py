"""Definisce i contratti pubblici delle API"""

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, RootModel


ServiceStatus = Literal["ok", "error"]


class StatusOutput(BaseModel):
    """Stato del backend e dei servizi esterni usati dall'applicazione"""

    model_config = ConfigDict(extra="forbid")

    backend: ServiceStatus
    database: ServiceStatus
    ollama: ServiceStatus


class DBSchema(RootModel[dict[str, dict[str, str]]]):
    """Output di GET /db_schema"""


class DBStats(BaseModel):
    """Output di GET /db_stats"""

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
    """Body di POST /parse"""

    model_config = ConfigDict(extra="forbid")

    url: str
    local: bool = False


class ParseOutput(BaseModel):
    """Output di GET /parse e POST /parse"""

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
    """Descrive una singola entry restituita dal Gold Standard"""

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


class GoldStandardURLs(BaseModel):
    """Output di GET /gold_standard_urls"""

    model_config = ConfigDict(extra="forbid")

    gold_standard_urls: list[str]


class WebResourceInput(BaseModel):
    """Body di POST /add_web_resource"""

    model_config = ConfigDict(extra="ignore")

    url: str
    html_text: str


class GoldStandardInput(BaseModel):
    """Body di POST /add_gold_standard"""

    model_config = ConfigDict(extra="forbid")

    url: str
    gold_text: str


class URLInput(BaseModel):
    """Body degli endpoint DELETE"""

    model_config = ConfigDict(extra="forbid")

    url: str


class CRUDStatus(BaseModel):
    """Output degli endpoint CRUD"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "error"]


class EvaluationInput(BaseModel):
    """Body di POST /evaluate"""

    model_config = ConfigDict(extra="forbid")

    parsed_text: str
    gold_text: str


class JudgeEvaluation(BaseModel):
    """Risposta pubblica di POST /evaluate_judge"""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str
    judge_score: int = Field(strict=True, ge=1, le=5)
    judge_feedback: str
    extra_noise: str = ""
    prompt_version: str


class TokenLevelEval(BaseModel):
    """Raccoglie precision recall e f1 a livello di token"""

    model_config = ConfigDict(extra="forbid")

    precision: float
    recall: float
    f1: float


class ParseEvaluation(BaseModel):
    """Output di POST /evaluate e GET /full_gs_eval"""

    model_config = ConfigDict(extra="forbid")

    token_level_eval: TokenLevelEval
    x_eval: dict[str, Any] = Field(default_factory=dict)


class FullParseEvaluation(ParseEvaluation):
    """Evaluation aggregata, comprensiva del Judge precalcolato"""

    judge_score: float = Field(ge=1, le=5)
