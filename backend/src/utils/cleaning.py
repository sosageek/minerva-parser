"""Pulisce il markup lasciato dal crawler"""

import html
import re

_RE_IMAGE       = re.compile(r'!\[[^\]]*\]\((?:[^()]*|\([^()]*\))*\)')
_RE_LINK        = re.compile(r'\[([^\]]*)\]\((?:[^()]*|\([^()]*\))*\)')
_RE_REF_LINK    = re.compile(r'\[([^\]]+)\]\[[^\]]*\]')
_RE_REF_DEF     = re.compile(r'^\[[^\]]+\]:\s+\S+.*$', re.MULTILINE)

_RE_FENCED_CODE = re.compile(r'^```[^\n]*\n(.*?)\n```[ \t]*$', re.MULTILINE | re.DOTALL)
_RE_INLINE_CODE = re.compile(r'`([^`\n]+)`')

_RE_TABLE_ROW   = re.compile(r'^\|.*\|\s*$', re.MULTILINE)
_RE_TABLE_SEP   = re.compile(r'^[|:\-\s]+$', re.MULTILINE)

_RE_HTML_TAG    = re.compile(r'<(?:!--.*?--|/?[a-zA-Z][^<>]*)>', re.DOTALL)
_RE_CITATION    = re.compile(
    r'\[(?:\d+(?:\s*[,\-–]\s*\d+)*|citation needed)\]',
    re.IGNORECASE,
)
_RE_STRAY_BR    = re.compile(r'(?<!\[)\]|\[(?!\])')

_RE_SPACE_PUNCT = re.compile(r'[ \t]+([.,;:!?)\]])')
_RE_MULTI_SPACE = re.compile(r'[ \t]+')
_RE_TRAIL_WS    = re.compile(r'[ \t]+\n')
_RE_MULTI_NL    = re.compile(r'\n{3,}')


def remove_markup(text: str) -> str:
    """Pulisce la sintassi markdown/html irrilevante"""
    text = _RE_FENCED_CODE.sub(r'\1', text)
    text = _RE_INLINE_CODE.sub(r'\1', text)
    text = _RE_IMAGE.sub('', text)
    text = _RE_LINK.sub(r'\1', text)
    text = _RE_REF_LINK.sub(r'\1', text)
    text = _RE_REF_DEF.sub('', text)
    text = _RE_TABLE_ROW.sub('', text)
    text = _RE_TABLE_SEP.sub('', text)
    text = _RE_HTML_TAG.sub('', text)
    text = _RE_CITATION.sub('', text)
    text = html.unescape(text)
    text = _RE_STRAY_BR.sub('', text)
    return text


def normalize_whitespace(text: str) -> str:
    """Normalizza spazi e righe vuote"""
    text = _RE_SPACE_PUNCT.sub(r'\1', text)
    text = _RE_MULTI_SPACE.sub(' ', text)
    text = _RE_TRAIL_WS.sub('\n', text)
    text = _RE_MULTI_NL.sub('\n\n', text)
    return text.strip()
