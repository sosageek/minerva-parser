import re


def strip_markdown(text: str) -> str:
    """Rimuove formattazione markdown visuale

    Args:
        text: testo markdown

    Returns:
        plain text
    """
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{3}([^*\n]+)\*{3}', r'\1', text)
    text = re.sub(r'\*{2}([^*\n]+)\*{2}', r'\1', text)
    text = re.sub(r'\*([^*\n]+)\*', r'\1', text)
    text = re.sub(r'_{3}([^_\n]+)_{3}', r'\1', text)
    text = re.sub(r'_{2}([^_\n]+)_{2}', r'\1', text)
    text = re.sub(r'_([^_\n]+)_', r'\1', text)
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
