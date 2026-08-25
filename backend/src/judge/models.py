"""Definisce i dati prodotti dal Judge"""

from pydantic import BaseModel, ConfigDict, Field


# versione del prompt: va persistita insieme al giudizio, così i risultati
# precalcolati nel database restano riconducibili al prompt che li ha prodotti
PROMPT_VERSION: str = "v8"


class JudgeResult(BaseModel):
    """Esito della valutazione qualitativa di un testo parsato"""

    # protected_namespaces disattivato: pydantic riserva il prefisso model_,
    # ma model_name è imposto dalla specifica degli endpoint
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str
    judge_score: int = Field(strict=True, ge=1, le=5)
    judge_feedback: str = Field(default="", max_length=500)
    extra_noise: str = Field(default="", max_length=300)
    diagnostics: str = "ok"
    prompt_version: str = PROMPT_VERSION
    latency_s: float | None = None
