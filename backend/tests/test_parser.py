"""Test unitari per le utility di pulizia markdown.

Eseguire dalla root del progetto:
    pytest backend/tests/test_parser.py -v
"""

from backend.src.utils.cleaning import (
    normalize_whitespace,
    remove_markup,
)


def _clean(text: str) -> str:
    """Helper di test: compone i due step come li userebbe un parser."""
    return normalize_whitespace(remove_markup(text))


# ---------------------------------------------------------------------------
# remove_markup
# ---------------------------------------------------------------------------

def test_rimuove_immagini_markdown():
    src = "![logo](https://example.com/logo.png) Testo iniziale"
    out = remove_markup(src)
    assert "logo" not in out
    assert "Testo iniziale" in out


def test_link_mantiene_solo_il_testo():
    src = "Vedi la voce [Roma](https://en.wikipedia.org/wiki/Rome) per dettagli."
    out = remove_markup(src)
    assert "Roma" in out
    assert "wikipedia" not in out
    assert "http" not in out


def test_link_con_parentesi_annidate():
    """Caso Wikipedia: `[testo](https://x.org/foo_(bar))`."""
    src = "Vedi [Parigi](https://en.wikipedia.org/wiki/Paris_(city)) qui."
    out = remove_markup(src)
    assert "Parigi" in out
    assert "wikipedia" not in out


def test_link_reference_style():
    src = "Questo link [Wikipedia][wiki] punta altrove."
    out = remove_markup(src)
    assert "Wikipedia" in out
    assert "[wiki]" not in out


def test_ref_definition_rimossa():
    src = "Testo utile.\n[1]: https://example.com/riferimento\nAltro testo."
    out = remove_markup(src)
    assert "https://example.com" not in out
    assert "Testo utile" in out
    assert "Altro testo" in out


def test_note_orfane_rimosse():
    src = "Dante nacque nel 1265 [1] a Firenze [citation needed]."
    out = remove_markup(src)
    assert "[1]" not in out
    assert "citation needed" not in out
    assert "Dante nacque nel 1265" in out


def test_parentesi_quadre_lunghe_preservate():
    """Un blocco `[...]` molto lungo non è una nota: non va toccato."""
    contenuto_lungo = "x" * 80
    src = f"Prima [{contenuto_lungo}] dopo"
    out = remove_markup(src)
    assert contenuto_lungo in out


def test_tabelle_markdown_rimosse():
    src = (
        "Introduzione.\n"
        "| Col A | Col B |\n"
        "|-------|-------|\n"
        "| val1  | val2  |\n"
        "Conclusione."
    )
    out = remove_markup(src)
    assert "Col A" not in out
    assert "val1" not in out
    assert "Introduzione" in out
    assert "Conclusione" in out


def test_tag_html_rimossi():
    src = "<p>Paragrafo <b>importante</b></p> fine."
    out = remove_markup(src)
    assert "<p>" not in out and "<b>" not in out
    assert "Paragrafo importante" in out


def test_html_commenti_rimossi():
    src = "prima <!-- commento nascosto --> dopo"
    out = remove_markup(src)
    assert "commento" not in out
    assert "prima" in out and "dopo" in out


def test_disuguaglianze_preservate():
    """Regressione: `a < b` NON è un tag HTML, non va strippato."""
    src = "Dato che a < b e b > 0, allora a > 0."
    out = remove_markup(src)
    assert "a < b" in out
    assert "a > 0" in out


def test_entita_html_decodificate():
    src = "5 &lt; 10 &amp; &quot;ciao&quot;"
    out = remove_markup(src)
    assert "<" in out and "&" in out and '"ciao"' in out
    assert "&lt;" not in out and "&amp;" not in out


# ---------------------------------------------------------------------------
# normalize_whitespace
# ---------------------------------------------------------------------------

def test_collassa_spazi_multipli():
    src = "parola    con      molti   spazi"
    assert normalize_whitespace(src) == "parola con molti spazi"


def test_spazio_prima_punteggiatura():
    src = "ciao , mondo !  come va ?"
    assert normalize_whitespace(src) == "ciao, mondo! come va?"


def test_newline_prima_punteggiatura_non_mangiata():
    """Regressione: `\\s+` avrebbe mangiato il `\\n`, unendo due righe."""
    src = "prima riga\n. seconda riga"
    out = normalize_whitespace(src)
    assert "\n" in out


def test_trailing_whitespace_rimosso():
    src = "riga con coda   \naltra riga"
    assert normalize_whitespace(src) == "riga con coda\naltra riga"


def test_collassa_newline_multipli():
    src = "paragrafo uno\n\n\n\n\nparagrafo due"
    assert normalize_whitespace(src) == "paragrafo uno\n\nparagrafo due"


# ---------------------------------------------------------------------------
# integrazione: strip + normalize insieme
# ---------------------------------------------------------------------------

def test_pipeline_completa_wikipedia_like():
    """Input realistico stile markdown estratto da Wikipedia."""
    src = (
        "# Dante Alighieri\n\n"
        "Dante nacque a [Firenze](https://en.wikipedia.org/wiki/Florence) "
        "nel 1265 [1]. Autore della <i>Divina Commedia</i> [citation needed].\n\n"
        "| Opera | Anno |\n"
        "|-------|------|\n"
        "| Vita Nuova | 1294 |\n\n"
        "[1]: https://example.com/dante-nascita\n"
    )
    out = _clean(src)

    assert "Firenze" in out
    assert "Divina Commedia" in out
    assert "Dante nacque a Firenze nel 1265" in out

    for noise in ["http", "<i>", "[1]", "citation needed", "Vita Nuova", "|"]:
        assert noise not in out


def test_idempotente():
    """Applicare la pulizia due volte deve dare lo stesso risultato."""
    src = "Vedi [Roma](https://example.com) [1] ![img](x.png) <b>!</b>"
    once = _clean(src)
    twice = _clean(once)
    assert once == twice


def test_stringa_vuota():
    assert _clean("") == ""
    assert _clean("   \n\n   ") == ""
