"""Utility di pulizia del markdown

funzioni pure stringa -> stringa
indipendenti dalla gerarchia ``Parser``

interfacce:
    ``strip_markdown_syntax``: rimuove sintassi markdown e html residuo
    ``normalize_whitespace``:  normalizza spazi/tab e newline
"""

import html
import re

_FOOTNOTE_CONTENT = (
    r'\d{1,3}'
    r'|[a-z]{1,3}'
    r'|[*\u2020\u2021\u00a7\u00b6]+'
    r'|(?:note|nb|n)\s+\d+'
    r'|citation\s+needed'
    r'|clarification\s+needed'
    r'|better\s+source\s+needed'
    r'|failed\s+verification'
    r'|original\s+research\??'
    r'|according\s+to\s+whom\??'
    r'|dubious(?:\s*[\u2013\u2014\-][^\]]*)?'
    r'|sic\??'
    r'|(?:who|when|where|why|which|what|how)\?'
)

_RE_IMAGE       = re.compile(r'!\[[^\]]*\]\((?:[^()]*|\([^()]*\))*\)')
_RE_LINK        = re.compile(r'\[([^\]]*)\]\((?:[^()]*|\([^()]*\))*\)')
_RE_REF_LINK    = re.compile(r'\[([^\]]+)\]\[[^\]]*\]')
_RE_REF_DEF     = re.compile(r'^\[[^\]]+\]:\s+\S+.*$', re.MULTILINE)
_RE_ORPHAN_BR   = re.compile(rf'\[(?:{_FOOTNOTE_CONTENT})\]', re.IGNORECASE)

_RE_TABLE_ROW   = re.compile(r'^\|.*\|$', re.MULTILINE)
_RE_TABLE_SEP   = re.compile(r'^[|:\-\s]+$', re.MULTILINE)

_RE_HTML_TAG    = re.compile(r'<(?:!--.*?--|/?[a-zA-Z][^<>]*)>', re.DOTALL)
_RE_STRAY_BR    = re.compile(r'(?<!\[)\]|\[(?!\])')

_RE_SPACE_PUNCT = re.compile(r'[ \t]+([.,;:!?)\]])')
_RE_MULTI_SPACE = re.compile(r'[ \t]+')
_RE_TRAIL_WS    = re.compile(r'[ \t]+\n')
_RE_MULTI_NL    = re.compile(r'\n{3,}')


def strip_markdown_syntax(text: str) -> str:
    """Pulisce la sintassi markdown/html irrilevante

    * cancella ``![alt](url)``, ``[id]:``, ``[...]``, righe di tabella md, tag HTML e commenti, quadre spaiate
    * sostituisce ``[testo](url)``, ``[testo][id]`` con solo testo

    Args:
        text: markdown grezzo

    Returns:
        il testo privato senza markdown e html (spazi e newline non normalizzati)
    """
    text = _RE_IMAGE.sub('', text)
    text = _RE_LINK.sub(r'\1', text)
    text = _RE_REF_LINK.sub(r'\1', text)
    text = _RE_REF_DEF.sub('', text)
    text = _RE_ORPHAN_BR.sub('', text)
    text = _RE_TABLE_ROW.sub('', text)
    text = _RE_TABLE_SEP.sub('', text)
    text = _RE_HTML_TAG.sub('', text)
    text = html.unescape(text)
    text = _RE_STRAY_BR.sub('', text)
    return text


def normalize_whitespace(text: str) -> str:
    """Normalizza spazi e righe vuote

    * cancella spazi/tab prima della punteggiatura, spazi a fine riga
    * collassa piu spazi e tab in singolo spazio e newline multipli a soli due

    Args:
        text: testo con eventuale spazio non normalizzato

    Returns:
        testo con whitespace uniforme
    """
    text = _RE_SPACE_PUNCT.sub(r'\1', text)
    text = _RE_MULTI_SPACE.sub(' ', text)
    text = _RE_TRAIL_WS.sub('\n', text)
    text = _RE_MULTI_NL.sub('\n\n', text)
    return text.strip()
