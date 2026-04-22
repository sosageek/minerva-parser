import re

from .eval import Evaluator

class TokenLevelEvaluator(Evaluator):
    """Metriche precision/recall/f1 case-insensitive

    si aspetta due stringhe di plain text
    (quindi è responsabilità del caller rimuovere sintassi md prima di passare argomenti)
    """

    # \w+ con flag Unicode: cattura lettere accentate (è, à, ù, ...) e scarta la punteggiatura
    _WORD_RE = re.compile(r"\w+", re.UNICODE)

    def evaluate(self, parsed_text: str, gold_text: str) -> dict:
        tokens_parsed = self._tokenize(parsed_text)
        tokens_gold = self._tokenize(gold_text)
        intersection = self._intersection(tokens_parsed, tokens_gold)

        return {
            "precision": self._precision(tokens_parsed, intersection),
            "recall": self._recall(tokens_gold, intersection),
            "f1": self._f1(tokens_parsed, tokens_gold, intersection)
        }

    def _tokenize(self, text: str) -> set:
        return set(self._WORD_RE.findall(text.lower()))

    def _intersection(self, a: set, b: set) -> set:
        return a & b

    def _precision(self, tokens_parsed: set, intersection: set) -> float:
        return round(len(intersection) / len(tokens_parsed), 4) if tokens_parsed else 0.0

    def _recall(self, tokens_gold: set, intersection: set) -> float:
        return round(len(intersection) / len(tokens_gold), 4) if tokens_gold else 0.0

    def _f1(self, tokens_parsed: set, tokens_gold: set, intersection: set) -> float:
        p = self._precision(tokens_parsed, intersection)
        r = self._recall(tokens_gold, intersection)
        return round(2 * p * r / (p + r), 4) if (p + r) > 0 else 0.0