from sacrebleu.metrics import CHRF
from .eval import Evaluator


class ChrFEvaluator(Evaluator):
    """Implementa metodo per l'evaluation con metrica ChrF

    * valuta la correttezza un'ipotesi di testo rispetto a un testo riferimento con f-score su n-grammi di caratteri
    * meno penalizzante su errori di battitura o parafrasi

    Formula:
        chrF = ((1 + beta^2) * P * R) / ((beta^2 * P) + R)

    Attributes:
        char_order(int): lunghezza massima degli n-grammi di caratteri (default: 6)
        word_order(int): lunghezza massima degli n-grammi di parole (default: 0)
        beta(float): parametro che determina il peso di precision e recall nell'f-score (default: 2.0)

    si sono usati i parametri default di sacrebleu: ``char_order=6``, ``word_order=0``, ``beta=2.0`` (dà più peso a recall che a precision nell'f-score)
    """

    def __init__(self, char_order: int = 6, word_order: int = 0, beta: float = 2.0):
        self._chrf = CHRF(char_order=char_order, word_order=word_order, beta=beta)

    def evaluate(self, parsed_text: str, gold_text: str) -> float:
        """Score ChrF tra parsed e gold normalizzato in [0,1]

        il punteggio viene ritornato normalizzato per essere conforme alle altre metriche
        (libreria sacrebleu ritorna il punteggio in scala 0-100)

        Args:
            parsed_text(str): testo estratto dal parser
            gold_text(str): testo di riferimento del gold standard

        Returns:
            float tra 0 e 1. 
            1 = match perfetto sugli n-grammi di caratteri, 0 = nessuna sovrapposizione
        """
        result = self._chrf.sentence_score(
            hypothesis=parsed_text,
            references=[gold_text],
        )
        normalized_score = round(result.score / 100, 4)

        return normalized_score
