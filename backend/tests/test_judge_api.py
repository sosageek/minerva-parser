import asyncio
from types import SimpleNamespace

from backend.src.server import server
from backend.src.server.models import EvaluationInput


def test_evaluate_judge_exposes_public_fields(monkeypatch):
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


def test_full_gs_eval_reads_precomputed_aggregates(monkeypatch):
    domain = next(iter(server.PARSERS))
    monkeypatch.setattr(
        server.gold_standard_repository,
        "list_by_domain",
        lambda selected: [{"url": "one"}, {"url": "two"}],
    )
    monkeypatch.setattr(
        server.evaluation_repository,
        "averages_by_domain",
        lambda: {
            domain: {
                "token_level_eval": {"precision": 0.9, "recall": 0.8, "f1": 0.85},
                "x_eval": {"chrf": 0.8, "noise_ratio": 0.1, "n_evaluated": 2},
            }
        },
    )
    monkeypatch.setattr(
        server.judge_repository,
        "averages_by_domain",
        lambda: {domain: {"judge_score": 4.5, "n_evaluated": 2}},
    )

    result = asyncio.run(server.full_gs_eval(domain))

    assert result.judge_score == 4.5
    assert result.token_level_eval.f1 == 0.85
    assert result.x_eval["n_total"] == 2
