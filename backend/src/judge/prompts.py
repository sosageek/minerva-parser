"""Costruisce il prompt inviato al Judge"""

# Limite di caratteri per ciascuno dei due testi inviati al modello.
# La specifica consente esplicitamente il troncamento per limitare i tempi di
# attesa, e qui serve davvero: a 1500 caratteri il judge costa circa 21s per
# entry, dieci entry per dominio fanno 210s contro i 360s di timeout del
# tester, margine troppo stretto su una macchina più lenta della nostra. A 500
# si scende a circa 7s per entry. Non è nemmeno un compromesso sulla qualità:
# a 4000 caratteri il modello arrivava a riportare porzioni dell'articolo come
# rumore e a votare 1 estrazioni con F1 pari a 1.000, e nei test fatti in fase
# di selezione del modello il giudizio su input brevi è risultato anche più
# affidabile che su input lunghi.
MAX_CHARS: int = 500


# Prompt in inglese anche per i domini italiani: i modelli di questa fascia
# seguono le istruzioni in modo più affidabile, e nei confronti fatti sui
# cinque modelli ammessi la validità del JSON prodotto è risultata migliore.
JUDGE_PROMPT: str = """You are the judge of the quality of text extracted from a web page by an automatic parser.

Two things matter: whether the extracted text kept the article content, and whether it is free of unwanted material.

Step 1 - extra_noise: text that appears in the EXTRACTED text and does NOT appear anywhere in the REFERENCE text.

Before listing anything, verify it is really absent from the REFERENCE. If a phrase appears in both texts, it is NOT extra_noise, even when it looks like a menu, a title, a header, a date or a footer: the REFERENCE defines what belongs to the article, not your expectations about web pages. Typical real cases are leftover navigation, cookie banners, ads, social media links, and sentences repeated more times than in the REFERENCE. Write "none" if there is none.

Step 2 - score, from 1 to 5. You decide, weighing both what was lost and what was added:
5 = the article was kept whole and the text is clean
4 = the article is essentially whole, with a small detail lost or a small unwanted fragment
3 = one clear problem: either a visible part of the article is gone, or there is leftover boilerplate
2 = serious problems, or two problems at once
1 = the extracted text is unusable: almost nothing of the article survived, or it comes from a different page

EXTRACTED TEXT:
{parsed_text}

REFERENCE TEXT:
{gold_text}

Reply with ONLY this JSON object, with the fields in exactly this order:
{{"extra_noise": "<what is extra, or none>", "score": <integer 1-5>, "feedback": "<one short sentence explaining the score>"}}"""


# Appeso al prompt originale quando la prima risposta non è JSON valido.
REPAIR_SUFFIX: str = (
    "\n\nYour previous reply was not valid JSON. Reply with ONLY the JSON object, "
    'nothing else, in this exact form: {"extra_noise": "...", "score": 3, "feedback": "..."}'
)


def truncate(text: str, limit: int = MAX_CHARS) -> str:
    """Tronca il testo senza spezzare l'ultima parola"""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit * 0.8 else cut).rstrip() + " [...]"


def build_prompt(parsed_text: str, gold_text: str) -> str:
    """Compone il prompt con i due testi già troncati"""
    return JUDGE_PROMPT.format(
        parsed_text=truncate(parsed_text),
        gold_text=truncate(gold_text),
    )
