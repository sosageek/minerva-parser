"""Rigenera metriche e giudizi reali a partire dagli HTML del Gold Standard"""

import asyncio
import json
from pathlib import Path

from ..config import GS_DATA_DIR, PRECOMPUTED_RESULTS_FILE
from ..eval import ChrFEvaluator, RougeOneEvaluator, TokenLevelEvaluator
from ..judge import judge
from ..parsers._crawler import close_crawler
from ..server.registry import get_parser
from ..utils import strip_formatting


def _load_gold_standard() -> list[dict[str, str]]:
    """Carica tutte le entry versionate del Gold Standard"""
    entries: list[dict[str, str]] = []
    for path in sorted(GS_DATA_DIR.glob("*_gs.json")):
        with path.open(encoding="utf-8") as source:
            content = json.load(source)
        if not isinstance(content, list):
            raise ValueError(f"{path} non contiene una lista JSON")
        entries.extend(content)
    return entries


def _write_json(path: Path, content: list[dict]) -> None:
    """Scrive il file json in modo leggibile e stabile"""
    temporary = path.with_suffix(".partial.json")
    with temporary.open("w", encoding="utf-8") as target:
        json.dump(content, target, ensure_ascii=False, indent=2)
        target.write("\n")
    temporary.replace(path)


async def generate() -> None:
    """Rigenera metriche e giudizi usando gli html salvati"""
    entries = _load_gold_standard()
    token_evaluator = TokenLevelEvaluator()
    chrf_evaluator = ChrFEvaluator()
    rouge_evaluator = RougeOneEvaluator()
    output: list[dict] = []

    try:
        for index, entry in enumerate(entries, start=1):
            parser = get_parser(entry["domain"])
            if parser is None:
                raise ValueError(f"Parser mancante per {entry['domain']}")

            document = await parser.parse(entry["url"], raw_html=entry["html_text"])
            parsed_clean = strip_formatting(document.parsed_text)
            gold_clean = strip_formatting(entry["gold_text"])
            token_eval = token_evaluator.evaluate(parsed_clean, gold_clean)
            rouge_eval = rouge_evaluator.evaluate(parsed_clean, gold_clean)
            judge_result = await asyncio.to_thread(
                judge,
                document.parsed_text,
                entry["gold_text"],
            )
            if judge_result.diagnostics not in ("ok", "repaired"):
                raise RuntimeError(
                    f"Judge non valido per {entry['url']}: "
                    f"{judge_result.diagnostics}"
                )

            output.append(
                {
                    "url": entry["url"],
                    "parsed_text": document.parsed_text,
                    "token_level_eval": token_eval,
                    "x_eval": {
                        "chrf": chrf_evaluator.evaluate(parsed_clean, gold_clean),
                        "noise_ratio": token_evaluator.noise_ratio(
                            parsed_clean,
                            gold_clean,
                        ),
                        "rouge_1": rouge_eval,
                    },
                    "judge": {
                        "model_name": judge_result.model_name,
                        "judge_score": judge_result.judge_score,
                        "judge_feedback": judge_result.judge_feedback,
                        "extra_noise": judge_result.extra_noise,
                        "prompt_version": judge_result.prompt_version,
                    },
                }
            )
            print(f"[{index}/{len(entries)}] {entry['url']}", flush=True)
    finally:
        await close_crawler()

    _write_json(PRECOMPUTED_RESULTS_FILE, output)
    print(f"Scritti {len(output)} risultati in {PRECOMPUTED_RESULTS_FILE}")


if __name__ == "__main__":
    asyncio.run(generate())
