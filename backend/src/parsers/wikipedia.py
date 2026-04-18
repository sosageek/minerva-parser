import re
from urllib.parse import urlparse, unquote
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import strip_markdown_syntax, normalize_whitespace


class WikipediaParser(Parser):

    _RE_TERMINAL_SECTIONS = re.compile(
        r'^#{1,6}\s+(?:Notes|References|Bibliography|See also|Further reading'
        r'|External links|Categories|Career statistics|Honours|Honors|Awards'
        r'|Discography|Filmography|Selected works|Publications)\s*$',
        re.MULTILINE,
    )

    _RE_IPA_LINK         = re.compile(r'\[\[([^\]]*)\]\]\([^)]*Help:IPA[^)]*\)')
    _RE_BRACKET_LINK     = re.compile(r'\[\[[^\]]*\]\]\([^)]*\)')

    _RE_URL_WITH_CAPTION = re.compile(r'\(https?://(?:[^\s)\\]|\\.)+\)(?=\S)\S*')
    _RE_URL_PAREN        = re.compile(r'\(https?://(?:[^\s)\\]|\\.)+\)')
    _RE_URL_BARE         = re.compile(r'https?://(?:[^\s)\\]|\\.)*[^\s)\\.,;:!?]')

    _RE_DISAMBIG         = re.compile(r'^Disambiguation\s*[–—-][^\n]*\n?', re.MULTILINE)
    _RE_COORDINATES      = re.compile(
        r'^.*(?:WikiMiniAtlas|\d+°\d+[′\']\d+[″"][NSEW]).*\n?',
        re.MULTILINE,
    )
    _RE_SYMBOL_ONLY_LINE = re.compile(r'^[\s\ufeff/;.\d°′″,NSEW-]+$', re.MULTILINE)
    _RE_TITLE_ATTR       = re.compile(r'\( "[^"]*"\)')

    def __init__(self):
        super().__init__(
            excluded_selector=(
                ".mw-navigation, #mw-head, #mw-panel, .navbox, .sidebar, .toc, "
                ".hatnote, .ambox, .infobox, .shortdescription, .geo-dec, "
                ".geo-dms, .coordinates, #coordinates, "
                ".mw-editsection"
            ),
            target_elements=["#mw-content-text"],
        )

    async def parse(self, url: str) -> ParsedDocument:
        result = await self._fetch(url)
        final_url = getattr(result, "url", None) or url

        return ParsedDocument(
            url=final_url,
            domain=urlparse(final_url).netloc,
            title=self._extract_title(final_url),
            html_text=result.cleaned_html,
            parsed_text=self.clean_markdown(result.markdown),
        )

    def clean_markdown(self, text: str) -> str:
        text = self._truncate_terminal_sections(text)
        text = self._normalize_wiki_links(text)
        text = strip_markdown_syntax(text)
        text = self._remove_urls(text)
        text = self._remove_wiki_metadata(text)
        text = normalize_whitespace(text)
        return text.strip()

    def _normalize_wiki_links(self, text: str) -> str:
        """Converte link IPA con alfabeto fonetico e cancella citazioni con doppie quadre"""
        text = self._RE_IPA_LINK.sub(r'/\1/', text)
        text = self._RE_BRACKET_LINK.sub('', text)
        return text

    def _remove_urls(self, text: str) -> str:
        """Cancella URL (anche tra parentesi con eventuali caption)"""
        text = self._RE_URL_WITH_CAPTION.sub('', text)
        text = self._RE_URL_PAREN.sub('', text)
        text = self._RE_URL_BARE.sub('', text)
        return text

    def _remove_wiki_metadata(self, text: str) -> str:
        """Cancella disambiguazione, coordinate, attributi title residui"""
        text = self._RE_DISAMBIG.sub('', text)
        text = self._RE_COORDINATES.sub('', text)
        text = self._RE_SYMBOL_ONLY_LINE.sub('', text)
        text = self._RE_TITLE_ATTR.sub('', text)
        return text

    def _truncate_terminal_sections(self, text: str) -> str:
        """Taglia il testo alla prima sezione terminale (note, references, ...)"""
        return self._RE_TERMINAL_SECTIONS.split(text, maxsplit=1)[0]

    def _extract_title(self, url: str) -> str:
        path = urlparse(url).path
        if "/wiki/" in path:
            title = path.split("/wiki/", 1)[1]
        else:
            title = path.rstrip("/").rsplit("/", 1)[-1]
        return unquote(title).replace("_", " ")
