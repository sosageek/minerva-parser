import re
from urllib.parse import urlparse
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import remove_markup, normalize_whitespace


class BookerParser(Parser):

    _TARGET_ELEMENTS = ["main", "article", ".node__content", ".field--name-body"]

    _EXCLUDED_SELECTORS = (
        "nav, footer, header, aside, figcaption, "
        ".cookies-banner, .newsletter-signup-block, "
        ".share-icons, .social-share, "
        "section.youtube-carousel, .c-path, .breadcrumb, "
        ".book_selling_form, .book-selling-retailers, .book-selling-formats, "
        ".c-modal, .flickity-button, .sr-only"
    )

    _RE_EDITORIAL_INLINE = re.compile(
        r'(interview|reading guide|extract|book recommendations|'
        r'watch|read more|discover|quiz|competition|information)',
        re.IGNORECASE
    )

    _RE_SOCIAL = re.compile(
        r'(facebook|instagram|twitter|youtube|tiktok)',
        re.IGNORECASE
    )

    _RE_BUY = re.compile(
        r'(buy the book|shop now|hardback|paperback|ebook|audiobook|'
        r'bookkind|amazon|blackwells|waterstones|bookshop\.org)',
        re.IGNORECASE
    )

    _RE_CEREMONY_NOISE = re.compile(
        r'(ceremony|in pictures|reacts to|hugs|holding|trophies|speech|performs)',
        re.IGNORECASE
    )

    _RE_NAVIGATION = re.compile(
        r'^(get to know|get involved|meet the|join the|read about|'
        r'why you should|why pen|generation tf|everything you need to know|'
        r"dua lipa|'spinning|spinning an illusion)",
        re.IGNORECASE
    )

    _RE_NAVIGATION_ANYWHERE = re.compile(
        r'(shortlistees said|reading challenge|longlisted authors and|'
        r'makes you sexy|why pen presents|spinning an illusion)',
        re.IGNORECASE
    )

    _RE_URL = re.compile(r'https?://\S+')
    _RE_EXCLAMATION_LINE = re.compile(r'^\s*!')

    def __init__(self):
        super().__init__(
            target_elements=self._TARGET_ELEMENTS,
            excluded_selector=self._EXCLUDED_SELECTORS,
        )

    async def parse(self, url: str) -> ParsedDocument:
        result = await self._fetch(url)

        title = result.metadata.get('title', '')
        if not title or "|" in title:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', result.html, re.DOTALL | re.IGNORECASE)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        self._current_url = url

        return ParsedDocument(
            url=url,
            domain=urlparse(url).netloc,
            title=title,
            html_text=result.cleaned_html,
            parsed_text=self.normalize(result.markdown),
        )

    def _is_editorial_noise(self, line: str, lower: str) -> bool:
        m = self._RE_EDITORIAL_INLINE.search(lower)
        if not m:
            return False
        if m.start() < 30:
            return True           
        return len(line) <= 150  

    def normalize(self, text: str) -> str:
        if not text:
            return ""

        text = remove_markup(text)
        text = re.sub(r',([^\s\d])', r', \1', text)
        text = re.sub(r"\s+'s", "'s", text)

        lines = text.split('\n')
        cleaned = []
        seen_long = set()
        recent_short = []
        SHORT_WINDOW = 3

        in_books_section = False

        for line in lines:
            line = line.strip()

            if len(line) < 4 or line.lower() == "play video":
                continue

            lower = line.lower()

            if lower.count('translated by') >= 3:
                continue

            if "other nominated books" in lower:
                in_books_section = True
                cleaned.append(line)
                continue

            if in_books_section and len(line) > 100:
                continue

            if self._RE_NAVIGATION.search(lower):
                continue

            if self._RE_NAVIGATION_ANYWHERE.search(lower):
                continue

            if len(line) <= 200:
                if self._RE_CEREMONY_NOISE.search(lower):
                    continue

            if len(line) <= 150:
                if self._RE_BUY.search(lower):
                    continue
                if self._RE_SOCIAL.search(lower) or self._RE_URL.search(line):
                    continue

            if self._is_editorial_noise(line, lower) or '©' in line:
                continue

            if len(line) > 150:
                if self._RE_URL.search(line) or self._RE_BUY.search(lower):
                    continue

            if len(line) > 60:
                if lower in seen_long:
                    continue
                seen_long.add(lower)
            else:
                if lower in recent_short:
                    continue
                recent_short.append(lower)
                if len(recent_short) > SHORT_WINDOW:
                    recent_short.pop(0)

            cleaned.append(line)

        text = "\n".join(cleaned)
        text = text.replace("\u2014", " ").replace("\u2013", " ")
        text = text.replace("#", "").replace("*", "").replace("_", "").replace(">", "")
        text = text.replace('\u00A0', ' ')
        text = text.replace('\u2019', "'").replace('\u2018', "'")

        return normalize_whitespace(text).strip()