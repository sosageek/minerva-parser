from ..utils import strip_formatting
from .eval import Evaluator


class NoiseRatioEvaluator(Evaluator):
    """
    Misura la quantità di "rumore" nel testo estratto dal parser rispetto al gold standard.

    Formula principale (versione sofisticata):
        noise_ratio = |token_parsed - token_gold| / |token_parsed|

    Un noise_ratio vicino a 0 significa che quasi tutti i token estratti
    appartengono al gold standard. Un valore vicino a 1 significa che
    la maggior parte dei token estratti è garbage non presente nel gold.
    """

    def evaluate(self, parsed_text: str, gold_text: str) -> dict:
        tokens_parsed = self._tokenize(strip_formatting(parsed_text))
        tokens_gold = self._tokenize(gold_text)

        noise_tokens = tokens_parsed - tokens_gold
        noise_ratio = self._noise_ratio(tokens_parsed, noise_tokens)

        # Precision e Recall incluse per contesto diagnostico
        intersection = tokens_parsed & tokens_gold
        precision = self._precision(tokens_parsed, intersection)
        recall = self._recall(tokens_gold, intersection)

        return {
            "noise_ratio": noise_ratio,
            "noise_token_count": len(noise_tokens),
            "parsed_token_count": len(tokens_parsed),
            "gold_token_count": len(tokens_gold),
            "precision": precision,
            "recall": recall,
        }

    def _tokenize(self, text: str) -> set:
        return set(text.lower().split())

    def _noise_ratio(self, tokens_parsed: set, noise_tokens: set) -> float:
        if not tokens_parsed:
            return 0.0
        return round(len(noise_tokens) / len(tokens_parsed), 4)

    def _precision(self, tokens_parsed: set, intersection: set) -> float:
        return round(len(intersection) / len(tokens_parsed), 4) if tokens_parsed else 0.0

    def _recall(self, tokens_gold: set, intersection: set) -> float:
        return round(len(intersection) / len(tokens_gold), 4) if tokens_gold else 0.0
