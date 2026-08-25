"""Verifica i contratti pubblici delle API del Judge"""

import asyncio
from types import SimpleNamespace

from backend.src.server import server
from backend.src.server.models import EvaluationInput


def test_evaluate_judge_exposes_public_fields(monkeypatch):
    """Espone soltanto i campi pubblici del Judge"""
    monkeypatch.setattr(
        server,
        "judge",
        lambda parsed, gold: SimpleNamespace(
            model_name="qwen3:4b",
            judge_score=4,
            judge_feedback="Minor omission.",
            extra_noise="",
            prompt_version="v8",
        ),
    )

    result = asyncio.run(
        server.evaluate_judge(EvaluationInput(parsed_text="parsed", gold_text="gold"))
    )

    assert result.judge_score == 4
    assert result.model_name == "qwen3:4b"


def test_full_gs_eval_calculates_from_static_html(monkeypatch):
    """Calcola gli aggregati partendo dagli html statici"""
    domain = next(iter(server.PARSERS))

    async def parse_static(url, html_text):
        """Finge il parsing locale di un html salvato"""

        return SimpleNamespace(parsed_text=f"parsed {url}")

    monkeypatch.setattr(
        server.gold_standard_repository,
        "list_by_domain",
        lambda selected: [
            {"url": "one", "html_text": "<main>one</main>", "gold_text": "gold one"},
            {"url": "two", "html_text": "<main>two</main>", "gold_text": "gold two"},
        ],
    )
    monkeypatch.setattr(server, "_do_parse", parse_static)
    monkeypatch.setattr(
        server,
        "_do_evaluate",
        lambda parsed, gold: server.ParseEvaluation(
            token_level_eval=server.TokenLevelEval(precision=0.9, recall=0.8, f1=0.85),
            x_eval={
                "chrf": 0.8,
                "noise_ratio": 0.1,
                "rouge_1": {"precision": 0.9, "recall": 0.8, "f1": 0.85},
            }
        ),
    )
    monkeypatch.setattr(
        server,
        "_judge_cached",
        lambda parsed, gold: SimpleNamespace(judge_score=4),
    )

    result = asyncio.run(server.full_gs_eval(domain))

    assert result.judge_score == 4
    assert result.token_level_eval.f1 == 0.85
    assert result.x_eval["n_total"] == 2
