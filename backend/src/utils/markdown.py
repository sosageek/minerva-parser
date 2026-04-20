import re


_RE_HEADING        = re.compile(r'^#{1,6}\s+', re.MULTILINE)
_RE_HORIZ_RULE     = re.compile(r'^[-*_]{3,}\s*$', re.MULTILINE)

_RE_BOLD_ITALIC_AST = re.compile(r'\*{3}([^*\n]+)\*{3}')
_RE_BOLD_AST        = re.compile(r'\*{2}([^*\n]+)\*{2}')
_RE_ITALIC_AST      = re.compile(r'\*([^*\n]+)\*')

_RE_BOLD_ITALIC_UND = re.compile(r'_{3}([^_\n]+)_{3}')
_RE_BOLD_UND        = re.compile(r'_{2}([^_\n]+)_{2}')
_RE_ITALIC_UND      = re.compile(r'_([^_\n]+)_')

_RE_MULTI_SPACE    = re.compile(r'[ \t]+')
_RE_MULTI_NL       = re.compile(r'\n{3,}')


def strip_formatting(text: str) -> str:
    """Rimuove formattazione markdown

    Args:
        text: testo markdown

    Returns:
        plain text
    """
    text = _RE_HEADING.sub('', text)
    text = _RE_BOLD_ITALIC_AST.sub(r'\1', text)
    text = _RE_BOLD_AST.sub(r'\1', text)
    text = _RE_ITALIC_AST.sub(r'\1', text)
    text = _RE_BOLD_ITALIC_UND.sub(r'\1', text)
    text = _RE_BOLD_UND.sub(r'\1', text)
    text = _RE_ITALIC_UND.sub(r'\1', text)
    text = _RE_HORIZ_RULE.sub('', text)
    text = _RE_MULTI_SPACE.sub(' ', text)
    text = _RE_MULTI_NL.sub('\n\n', text)
    return text.strip()
