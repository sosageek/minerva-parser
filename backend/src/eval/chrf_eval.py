from sacrebleu.metrics import CHRF
from .eval import Evaluator


class ChrFEvaluator(Evaluator):
    """
    Usiamo i parametri default di sacrebleu: char_order=6, word_order=0, beta=2.
    """

    def __init__(self, char_order: int = 6, word_order: int = 0, beta: float = 2.0):
        self._chrf = CHRF(char_order=char_order, word_order=word_order, beta=beta)

    def evaluate(self, parsed_text: str, gold_text: str) -> dict:
        result = self._chrf.sentence_score(
            hypothesis=parsed_text,
            references=[gold_text],
        )
        score = round(result.score, 4)
        return {
            "chrf": score,
            "chrf_normalized": round(score / 100, 4),
        }
