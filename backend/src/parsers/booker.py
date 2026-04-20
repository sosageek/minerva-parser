import re
from urllib.parse import urlparse
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import normalize_whitespace


class BookerParser(Parser):

    _RE_TERMINAL = re.compile(
        r'^#{0,6}\s*(?:Features|Discover more about this year|Related content'
        r'|Read about the \d{4} prize)',
        re.IGNORECASE | re.MULTILINE,
    )

    def __init__(self):
        super().__init__(
            target_elements=["main", "article", ".node__content", ".field--name-body"],
            excluded_selector=(
                "nav, footer, header, aside, figcaption, "
                ".cookies-banner, .sprite-icon, .newsletter-signup-block, "
                ".share-icons, .skip-link, .author-socials, .social-share, "
                "section.youtube-carousel, .c-path"
            ),
        )

    async def parse(self, url: str) -> ParsedDocument:
        result = await self._fetch(url)
        title = result.metadata.get('title', '')
        if not title or "|" in title:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', result.html, re.DOTALL | re.IGNORECASE)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        final_text = self.normalize(result.markdown)
        return ParsedDocument(
            url=url, domain=urlparse(url).netloc, title=title,
            html_text=result.cleaned_html, parsed_text=final_text
        )

    def normalize(self, text: str) -> str:
        if not text:
            return ""

        #trasforma link e immagini markdown 
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)

        #tronca alle sezioni terminali 
        m = self._RE_TERMINAL.search(text)
        if m:
            text = text[:m.start()]

        lines = text.split('\n')
        cleaned_lines = []

        #frasi che indicano righe da eliminare
        garbage_phrases = [
            "sprite-icon", "skip to", "cookies","facebook page", "instagram page", "twitter profile",
            "tiktok page", "youtube page", "watch our films", "play video",
            "connect","publication date and time","more about","read more about","an interview with",
            "buy the book","shop now","buying books using","hardback","paperback","ebook","audiobook",
            "bookshop.org","waterstones", "blackwells","bookkind","watch quickfire","get to know the shortlist",
            "get involved","meet the longlisted","meet the judges:","reading challenge","join the international booker",
            "why you should read","discover our reading guides","book recommendations","book extract",
            "read more on","david szalay interview:", "reading guide:", "an extract from",
            "everything you need to know about", "quiz:", "competition",
            "explore more features", "the ceremony in pictures",
            "visit david szalay's facebook", "go to our",
        ]

        seen_books = False        #heading "other nominated books" già visto
        skip_after_books = False  
        in_books_section = False  
        books_seen_lines = set()  

        for line in lines:
            line_strip = line.strip()
            line_lower = line_strip.lower()

            if len(line_strip) < 3:
                continue

            #filtra alt text di immagini orfane (es. "!Titolo immagine")
            if line_strip.startswith('!'):
                continue

            #filtra crediti fotografici (© Fotografo per ...)
            if '©' in line_strip:
                continue

            #salta tutto dopo la seconda occorrenza di "other nominated books"
            if skip_after_books:
                continue

            #scarta se contiene frasi garbage_phrases
            if any(phrase in line_lower for phrase in garbage_phrases):
                continue

            #gestione della sezione "Other nominated books"
            if "other nominated books" in line_lower:
                if seen_books:
                    #seconda occorrenza: salta questo e tutto ciò che segue
                    skip_after_books = True
                    continue
                seen_books = True
                in_books_section = True
                books_seen_lines = set()
                cleaned_lines.append(line_strip)
                continue

            #deduplicazione righe all'interno della sezione libri nominati
            if in_books_section:
                if line_strip in books_seen_lines:
                    continue
                books_seen_lines.add(line_strip)

            cleaned_lines.append(line_strip)

        text = "\n".join(cleaned_lines)

        #normalizzazione dei caratteri
        text = text.replace("—", "-").replace("–", "-")
        text = text.replace("#", "").replace("*", "").replace("_", "").replace(">", "")
        text = text.replace('\u00A0', ' ')

        text = normalize_whitespace(text)
     
        return text.strip()