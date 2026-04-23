from ..utils import strip_formatting
from .eval import Evaluator


class CoverageScoreEvaluator(Evaluator):
    """
    Misura quanta informazione del gold standard è stata recuperata dal parser.

    Formula:
        coverage = |token_gold ∩ token_parsed| / |token_gold|

    Un coverage vicino a 1 significa che quasi tutto il contenuto del gold standard
    è presente nel testo estratto. Un valore basso significa che il parser
    ha scartato troppo contenuto utile.
    """

    def evaluate(self, parsed_text: str, gold_text: str) -> dict:
        tokens_parsed = self._tokenize(strip_formatting(parsed_text))
        tokens_gold = self._tokenize(gold_text)

        intersection = tokens_parsed & tokens_gold
        coverage = self._coverage(tokens_gold, intersection)

        return {
            "coverage": coverage,
            "covered_token_count": len(intersection),
            "gold_token_count": len(tokens_gold),
            "parsed_token_count": len(tokens_parsed),
        }

    def _tokenize(self, text: str) -> set:
        return set(text.lower().split())

    def _coverage(self, tokens_gold: set, intersection: set) -> float:
        return round(len(intersection) / len(tokens_gold), 4) if tokens_gold else 0.0